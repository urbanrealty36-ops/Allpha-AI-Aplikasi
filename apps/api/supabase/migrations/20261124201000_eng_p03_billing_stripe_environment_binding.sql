-- ENG-P03: bind Stripe provider cancellation to the actual test/live environment.
-- Existing rows remain NULL until their provider environment is known; the worker fails closed.

alter table public.billing_orders
  add column if not exists stripe_environment text;
alter table public.billing_orders
  drop constraint if exists billing_orders_stripe_environment_check;
alter table public.billing_orders
  add constraint billing_orders_stripe_environment_check
  check (stripe_environment is null or stripe_environment in ('test','live'));

alter table public.billing_subscriptions
  add column if not exists stripe_environment text;
alter table public.billing_subscriptions
  drop constraint if exists billing_subscriptions_stripe_environment_check;
alter table public.billing_subscriptions
  add constraint billing_subscriptions_stripe_environment_check
  check (stripe_environment is null or stripe_environment in ('test','live'));

-- New orders must persist the actual Stripe key environment separately from Checkout mode
-- (payment/subscription), which is the meaning of billing_orders.stripe_mode.
create or replace function public.billing_create_order(
  p_owner_user_id uuid,
  p_product_key text,
  p_idempotency_key text,
  p_stripe_environment text
) returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_product public.billing_products;
  v_order public.billing_orders;
begin
  if p_owner_user_id is null or coalesce(p_product_key,'') = ''
    or char_length(coalesce(p_idempotency_key,'')) not between 8 and 160
    or p_stripe_environment not in ('test','live') then
    raise exception 'BILLING_ORDER_COMMAND_INVALID' using errcode='22023';
  end if;
  select * into v_order from public.billing_orders
    where owner_user_id=p_owner_user_id and idempotency_key=p_idempotency_key for update;
  if found then
    if v_order.product_key <> p_product_key
       or v_order.stripe_environment is distinct from p_stripe_environment then
      raise exception 'BILLING_IDEMPOTENCY_CONFLICT' using errcode='23505';
    end if;
    return jsonb_build_object('order_id',v_order.id,'status',v_order.status,
      'stripe_checkout_session_id',v_order.stripe_checkout_session_id,
      'checkout_url',v_order.stripe_checkout_url);
  end if;
  select * into v_product from public.billing_products
    where product_key=p_product_key and status='active' for share;
  if not found then raise exception 'BILLING_PRODUCT_UNAVAILABLE' using errcode='P0002'; end if;
  if v_product.amount_minor <= 0 or v_product.stripe_price_id = '' then
    raise exception 'BILLING_PRODUCT_NOT_CONFIGURED' using errcode='23514';
  end if;
  insert into public.billing_orders(
    owner_user_id,product_id,product_key,product_name,purpose,stripe_price_id,stripe_mode,
    stripe_environment,amount_minor,currency,product_snapshot,idempotency_key
  ) values (
    p_owner_user_id,v_product.id,v_product.product_key,v_product.name,v_product.purpose,
    v_product.stripe_price_id,v_product.stripe_mode,p_stripe_environment,
    v_product.amount_minor,v_product.currency,
    jsonb_build_object(
      'product_key',v_product.product_key,'purpose',v_product.purpose,
      'product_approval_reference',v_product.product_approval_reference,
      'amount_minor',v_product.amount_minor,'currency',v_product.currency,
      'credits_grant',v_product.credits_grant,'monthly_credits_grant',v_product.monthly_credits_grant,
      'credit_policy_version',v_product.credit_policy_version,
      'credit_policy_approval_reference',v_product.credit_policy_approval_reference,
      'plan_key',v_product.plan_key,'entitlement_version',v_product.entitlement_version
    ),p_idempotency_key
  ) returning * into v_order;
  return jsonb_build_object('order_id',v_order.id,'status',v_order.status,
    'stripe_checkout_session_id',null,'checkout_url',null);
end;
$$;
revoke all on function public.billing_create_order(uuid,text,text,text) from public,anon,authenticated;
grant execute on function public.billing_create_order(uuid,text,text,text) to service_role;

-- Prevent legacy callers from silently creating orders without a known Stripe environment.
create or replace function public.billing_create_order(
  p_owner_user_id uuid,
  p_product_key text,
  p_idempotency_key text
) returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
begin
  raise exception 'BILLING_STRIPE_ENVIRONMENT_REQUIRED' using errcode='22023';
end;
$$;
revoke all on function public.billing_create_order(uuid,text,text) from public,anon,authenticated,service_role;

-- Carry the recorded environment from the checkout order to the durable subscription.
do $$
declare
  v_definition text;
  v_old text := $old$
    insert into public.billing_subscriptions(
      owner_user_id,product_id,stripe_subscription_id,stripe_customer_id,plan_key,
      entitlement_version,status,current_period_start,current_period_end
    ) values (
      v_order.owner_user_id,v_order.product_id,p_subscription_id,p_customer_id,
      v_order.product_snapshot->>'plan_key',v_order.product_snapshot->>'entitlement_version','active',
      p_current_period_start,p_current_period_end
    ) on conflict(stripe_subscription_id) do update set
      stripe_customer_id=coalesce(excluded.stripe_customer_id,billing_subscriptions.stripe_customer_id),
$old$;
  v_new text := $new$
    insert into public.billing_subscriptions(
      owner_user_id,product_id,stripe_subscription_id,stripe_environment,stripe_customer_id,plan_key,
      entitlement_version,status,current_period_start,current_period_end
    ) values (
      v_order.owner_user_id,v_order.product_id,p_subscription_id,v_order.stripe_environment,p_customer_id,
      v_order.product_snapshot->>'plan_key',v_order.product_snapshot->>'entitlement_version','active',
      p_current_period_start,p_current_period_end
    ) on conflict(stripe_subscription_id) do update set
      stripe_environment=coalesce(excluded.stripe_environment,billing_subscriptions.stripe_environment),
      stripe_customer_id=coalesce(excluded.stripe_customer_id,billing_subscriptions.stripe_customer_id),
$new$;
begin
  v_definition:=pg_get_functiondef('public.billing_finalize_stripe_checkout(text,uuid,text,uuid,text,bigint,text,text,text,text,timestamptz,timestamptz)'::regprocedure);
  if position(v_new in v_definition)>0 then return; end if;
  if position(v_old in v_definition)=0 then
    raise exception 'billing_subscription_environment_finalize_patch_anchor_missing';
  end if;
  execute replace(v_definition,v_old,v_new);
end;
$$;

-- Rename the cancellation queue field so it cannot be confused with Checkout's payment/subscription mode.
alter table private.account_deletion_subscription_cancellation_jobs
  rename column stripe_mode to stripe_environment;
alter table private.account_deletion_subscription_cancellation_jobs
  rename constraint account_deletion_subscription_cancellation_jobs_stripe_mode_check
  to account_deletion_subscription_cancellation_jobs_stripe_environment_check;

create or replace function public.prepare_account_deletion_subscription_cancellations()
returns integer
language plpgsql
security definer
set search_path = ''
as $$
declare v_count integer;
begin
  if coalesce(auth.jwt()->>'role','') <> 'service_role' then
    raise exception 'service_role_required' using errcode='42501';
  end if;
  insert into private.account_deletion_subscription_cancellation_jobs(
    request_id,billing_subscription_id,stripe_subscription_id,stripe_environment,idempotency_key
  )
  select r.id,bs.id,bs.stripe_subscription_id,bs.stripe_environment,
         'account-deletion:'||r.id::text||':'||bs.id::text
  from public.account_deletion_requests r
  join public.billing_subscriptions bs on bs.owner_user_id=r.user_id
  where r.user_id is not null
    and r.status in ('scheduled','blocked_dependency','processing')
    and bs.status in ('active','trialing','past_due','unpaid','incomplete','paused')
  on conflict(request_id,billing_subscription_id) do nothing;
  get diagnostics v_count=row_count;
  return v_count;
end;
$$;

drop function public.claim_account_deletion_subscription_cancellation_jobs(text,integer,integer);
create function public.claim_account_deletion_subscription_cancellation_jobs(
  p_worker_id text,
  p_limit integer default 10,
  p_lease_seconds integer default 300
) returns table(
  id uuid,
  billing_subscription_id uuid,
  stripe_subscription_id text,
  stripe_environment text,
  idempotency_key text,
  attempts integer,
  lease_token uuid
)
language plpgsql
security definer
set search_path = ''
as $$
begin
  if coalesce(auth.jwt()->>'role','') <> 'service_role' then
    raise exception 'service_role_required' using errcode='42501';
  end if;
  if p_worker_id is null or length(p_worker_id)<3 or p_limit not between 1 and 50
     or p_lease_seconds not between 30 and 1800 then
    raise exception 'account_deletion_subscription_claim_arguments_invalid' using errcode='22023';
  end if;
  return query
  with candidates as (
    select j.id from private.account_deletion_subscription_cancellation_jobs j
    where j.attempts<j.max_attempts
      and ((j.status in ('queued','retryable') and j.available_at<=clock_timestamp())
        or (j.status='processing' and j.lease_expires_at<=clock_timestamp()))
    order by j.available_at,j.created_at,j.id
    limit p_limit for update skip locked
  )
  update private.account_deletion_subscription_cancellation_jobs j
  set status='processing',attempts=j.attempts+1,lease_token=gen_random_uuid(),
      lease_expires_at=clock_timestamp()+make_interval(secs=>p_lease_seconds),
      error_code=null,updated_at=clock_timestamp()
  from candidates c where j.id=c.id
  returning j.id,j.billing_subscription_id,j.stripe_subscription_id,j.stripe_environment,
            j.idempotency_key,j.attempts,j.lease_token;
end;
$$;
revoke all on function public.claim_account_deletion_subscription_cancellation_jobs(text,integer,integer)
  from public, anon, authenticated;
grant execute on function public.claim_account_deletion_subscription_cancellation_jobs(text,integer,integer)
  to service_role;

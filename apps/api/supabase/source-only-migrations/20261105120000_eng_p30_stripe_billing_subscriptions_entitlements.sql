-- ENG-P30 Stripe billing, receipts, subscription and playback entitlement.
-- SOURCE ONLY: do not apply to production. Apply through the approved isolated
-- non-production migration/recovery gate. No products/prices are seeded.
-- Stripe is the sole provider. Client redirects never fulfill orders.
begin;

create table if not exists public.billing_products (
  id uuid primary key default gen_random_uuid(),
  product_key text not null unique check (product_key ~ '^[a-z0-9][a-z0-9._-]{1,79}$'),
  name text not null check (char_length(name) between 1 and 160),
  description text check (description is null or char_length(description) <= 1000),
  purpose text not null check (purpose in ('ai_credit_topup','premium_subscription')),
  stripe_price_id text not null unique check (stripe_price_id ~ '^price_[A-Za-z0-9]+$'),
  stripe_mode text not null check (stripe_mode in ('payment','subscription')),
  amount_minor bigint not null check (amount_minor > 0),
  currency text not null check (currency ~ '^[a-z]{3}$'),
  billing_interval text check (billing_interval is null or billing_interval in ('day','week','month','year')),
  credits_grant bigint not null default 0 check (credits_grant >= 0),
  credit_policy_version text references public.credit_policy_versions(policy_version) on delete restrict,
  credit_policy_approval_reference text,
  plan_key text,
  entitlement_version text,
  status text not null default 'draft' check (status in ('draft','active','retired')),
  sort_order integer not null default 100,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (
    (purpose = 'ai_credit_topup' and stripe_mode = 'payment' and credits_grant > 0
      and credit_policy_version is not null and credit_policy_approval_reference is not null
      and plan_key is null)
    or
    (purpose = 'premium_subscription' and stripe_mode = 'subscription'
      and credits_grant = 0 and plan_key is not null and entitlement_version is not null)
  )
);

create table if not exists public.billing_orders (
  id uuid primary key default gen_random_uuid(),
  owner_user_id uuid not null references auth.users(id) on delete restrict,
  product_id uuid not null references public.billing_products(id) on delete restrict,
  product_key text not null,
  product_name text not null,
  purpose text not null check (purpose in ('ai_credit_topup','premium_subscription')),
  stripe_price_id text not null,
  stripe_mode text not null check (stripe_mode in ('payment','subscription')),
  amount_minor bigint not null check (amount_minor > 0),
  currency text not null check (currency ~ '^[a-z]{3}$'),
  product_snapshot jsonb not null check (jsonb_typeof(product_snapshot) = 'object'),
  idempotency_key text not null check (char_length(idempotency_key) between 8 and 160),
  stripe_checkout_session_id text unique,
  stripe_checkout_url text,
  stripe_customer_id text,
  stripe_payment_intent_id text,
  stripe_subscription_id text,
  status text not null default 'checkout_pending'
    check (status in ('checkout_pending','paid','failed','expired','review_required','refunded','disputed')),
  paid_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(owner_user_id,idempotency_key)
);
create index if not exists billing_orders_owner_created_idx
  on public.billing_orders(owner_user_id,created_at desc);
create index if not exists billing_orders_status_created_idx
  on public.billing_orders(status,created_at);

create table if not exists public.billing_receipts (
  id uuid primary key default gen_random_uuid(),
  order_id uuid not null references public.billing_orders(id) on delete restrict,
  owner_user_id uuid not null references auth.users(id) on delete restrict,
  provider text not null default 'stripe' check (provider = 'stripe'),
  provider_receipt_id text not null unique,
  receipt_number text not null unique,
  stripe_payment_intent_id text,
  stripe_invoice_id text,
  amount_minor bigint not null check (amount_minor > 0),
  currency text not null check (currency ~ '^[a-z]{3}$'),
  hosted_invoice_url text,
  paid_at timestamptz not null,
  created_at timestamptz not null default now()
);
create index if not exists billing_receipts_owner_created_idx
  on public.billing_receipts(owner_user_id,created_at desc);

create table if not exists public.billing_subscriptions (
  id uuid primary key default gen_random_uuid(),
  owner_user_id uuid not null references auth.users(id) on delete restrict,
  product_id uuid not null references public.billing_products(id) on delete restrict,
  stripe_subscription_id text not null unique,
  stripe_customer_id text,
  plan_key text not null,
  entitlement_version text not null,
  status text not null check (status in ('active','past_due','canceled','unpaid','incomplete','incomplete_expired','paused','trialing')),
  current_period_start timestamptz,
  current_period_end timestamptz,
  cancel_at_period_end boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists billing_subscriptions_owner_updated_idx
  on public.billing_subscriptions(owner_user_id,updated_at desc);

create table if not exists public.playback_entitlements (
  id uuid primary key default gen_random_uuid(),
  owner_user_id uuid not null references auth.users(id) on delete restrict,
  entitlement_key text not null,
  entitlement_version text not null,
  source_subscription_id uuid not null references public.billing_subscriptions(id) on delete restrict,
  status text not null check (status in ('active','suspended','revoked')),
  valid_from timestamptz not null default now(),
  valid_until timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(owner_user_id,entitlement_key,source_subscription_id),
  check (valid_until is null or valid_until > valid_from)
);
create index if not exists playback_entitlements_owner_status_idx
  on public.playback_entitlements(owner_user_id,status,valid_until);

create table if not exists public.stripe_webhook_events (
  event_id text primary key check (event_id ~ '^evt_[A-Za-z0-9]+$'),
  event_type text not null check (char_length(event_type) between 1 and 120),
  event_created_at timestamptz not null,
  payload jsonb not null check (jsonb_typeof(payload) = 'object'),
  status text not null default 'received'
    check (status in ('received','awaiting_payment','processed','ignored','failed')),
  attempt_count integer not null default 0 check (attempt_count >= 0),
  last_error_code text,
  received_at timestamptz not null default now(),
  processed_at timestamptz
);
create index if not exists stripe_webhook_events_status_received_idx
  on public.stripe_webhook_events(status,received_at);

alter table public.billing_products enable row level security;
alter table public.billing_orders enable row level security;
alter table public.billing_receipts enable row level security;
alter table public.billing_subscriptions enable row level security;
alter table public.playback_entitlements enable row level security;
alter table public.stripe_webhook_events enable row level security;
revoke all on public.billing_products,public.billing_orders,public.billing_receipts,
  public.billing_subscriptions,public.playback_entitlements,public.stripe_webhook_events
  from public,anon,authenticated,service_role;
grant select,insert,update,delete on public.billing_products,public.billing_orders,
  public.billing_receipts,public.billing_subscriptions,public.playback_entitlements,
  public.stripe_webhook_events to service_role;

create or replace function public.billing_create_order(
  p_owner_user_id uuid,p_product_key text,p_idempotency_key text
) returns jsonb language plpgsql security definer set search_path = ''
as $$
declare
  v_product public.billing_products;
  v_order public.billing_orders;
begin
  if p_owner_user_id is null or coalesce(p_product_key,'') = ''
    or char_length(coalesce(p_idempotency_key,'')) not between 8 and 160 then
    raise exception 'BILLING_ORDER_COMMAND_INVALID' using errcode='22023';
  end if;
  select * into v_order from public.billing_orders
    where owner_user_id=p_owner_user_id and idempotency_key=p_idempotency_key for update;
  if found then
    if v_order.product_key <> p_product_key then
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
    amount_minor,currency,product_snapshot,idempotency_key
  ) values (
    p_owner_user_id,v_product.id,v_product.product_key,v_product.name,v_product.purpose,
    v_product.stripe_price_id,v_product.stripe_mode,v_product.amount_minor,v_product.currency,
    jsonb_build_object(
      'product_key',v_product.product_key,'purpose',v_product.purpose,
      'amount_minor',v_product.amount_minor,'currency',v_product.currency,
      'credits_grant',v_product.credits_grant,'credit_policy_version',v_product.credit_policy_version,
      'credit_policy_approval_reference',v_product.credit_policy_approval_reference,
      'plan_key',v_product.plan_key,'entitlement_version',v_product.entitlement_version
    ),p_idempotency_key
  ) returning * into v_order;
  return jsonb_build_object('order_id',v_order.id,'status',v_order.status,
    'stripe_checkout_session_id',null,'checkout_url',null);
end;
$$;

create or replace function public.billing_attach_checkout_session(
  p_order_id uuid,p_owner_user_id uuid,p_session_id text,p_checkout_url text,p_stripe_customer_id text default null
) returns jsonb language plpgsql security definer set search_path = ''
as $$
declare v_order public.billing_orders;
begin
  if p_order_id is null or p_owner_user_id is null
    or coalesce(p_session_id,'') !~ '^cs_[A-Za-z0-9_]+$'
    or coalesce(p_checkout_url,'') not like 'https://checkout.stripe.com/%' then
    raise exception 'BILLING_CHECKOUT_SESSION_INVALID' using errcode='22023';
  end if;
  select * into v_order from public.billing_orders
    where id=p_order_id and owner_user_id=p_owner_user_id for update;
  if not found then raise exception 'BILLING_ORDER_NOT_FOUND' using errcode='P0002'; end if;
  if v_order.status <> 'checkout_pending' then
    raise exception 'BILLING_ORDER_NOT_PENDING' using errcode='23514';
  end if;
  if v_order.stripe_checkout_session_id is not null and v_order.stripe_checkout_session_id <> p_session_id then
    raise exception 'BILLING_CHECKOUT_SESSION_CONFLICT' using errcode='23505';
  end if;
  update public.billing_orders set stripe_checkout_session_id=p_session_id,
    stripe_checkout_url=p_checkout_url,stripe_customer_id=coalesce(p_stripe_customer_id,stripe_customer_id),
    updated_at=now() where id=p_order_id;
  return jsonb_build_object('attached',true,'order_id',p_order_id);
end;
$$;

create or replace function public.billing_receive_stripe_event(
  p_event_id text,p_event_type text,p_event_created_at timestamptz,p_payload jsonb
) returns jsonb language plpgsql security definer set search_path = ''
as $$
declare v_event public.stripe_webhook_events;
begin
  if coalesce(p_event_id,'') !~ '^evt_[A-Za-z0-9]+$'
    or coalesce(p_event_type,'') = '' or p_event_created_at is null
    or jsonb_typeof(p_payload) <> 'object' then
    raise exception 'STRIPE_EVENT_INVALID' using errcode='22023';
  end if;
  insert into public.stripe_webhook_events(event_id,event_type,event_created_at,payload)
  values(p_event_id,p_event_type,p_event_created_at,p_payload)
  on conflict(event_id) do nothing;
  select * into v_event from public.stripe_webhook_events where event_id=p_event_id for update;
  if v_event.event_type <> p_event_type then
    raise exception 'STRIPE_EVENT_IDENTITY_CONFLICT' using errcode='23505';
  end if;
  if v_event.status in ('failed','awaiting_payment') then
    update public.stripe_webhook_events set attempt_count=attempt_count+1,status='received',
      last_error_code=null where event_id=p_event_id returning * into v_event;
  end if;
  return jsonb_build_object('duplicate',v_event.received_at < now() - interval '1 second',
    'status',v_event.status,'event_id',v_event.event_id);
end;
$$;

create or replace function public.billing_mark_stripe_event(
  p_event_id text,p_status text,p_error_code text default null
) returns jsonb language plpgsql security definer set search_path = ''
as $$
declare v_event public.stripe_webhook_events;
begin
  if p_status not in ('awaiting_payment','processed','ignored','failed') then
    raise exception 'STRIPE_EVENT_STATUS_INVALID' using errcode='22023';
  end if;
  update public.stripe_webhook_events set status=p_status,last_error_code=left(p_error_code,80),
    processed_at=case when p_status in ('processed','ignored') then now() else processed_at end
    where event_id=p_event_id returning * into v_event;
  if not found then raise exception 'STRIPE_EVENT_NOT_FOUND' using errcode='P0002'; end if;
  return jsonb_build_object('event_id',v_event.event_id,'status',v_event.status);
end;
$$;

create or replace function public.billing_finalize_stripe_checkout(
  p_event_id text,p_order_id uuid,p_session_id text,p_owner_user_id uuid,
  p_payment_status text,p_amount_total bigint,p_currency text,
  p_payment_intent_id text default null,p_subscription_id text default null,p_customer_id text default null,
  p_current_period_start timestamptz default null,p_current_period_end timestamptz default null
) returns jsonb language plpgsql security definer set search_path = ''
as $$
declare
  v_event public.stripe_webhook_events;
  v_order public.billing_orders;
  v_grant jsonb;
  v_sub public.billing_subscriptions;
begin
  select * into v_event from public.stripe_webhook_events where event_id=p_event_id for update;
  if not found then raise exception 'STRIPE_EVENT_NOT_RECEIVED' using errcode='P0002'; end if;
  select * into v_order from public.billing_orders where id=p_order_id for update;
  if not found or v_order.owner_user_id <> p_owner_user_id then
    raise exception 'BILLING_ORDER_NOT_FOUND' using errcode='P0002';
  end if;
  if v_order.status='paid' then
    update public.stripe_webhook_events set status='processed',processed_at=coalesce(processed_at,now()) where event_id=p_event_id;
    return jsonb_build_object('fulfilled',true,'idempotent_replay',true,'order_id',p_order_id);
  end if;
  if v_order.status <> 'checkout_pending'
    or v_order.stripe_checkout_session_id <> p_session_id
    or p_payment_status <> 'paid'
    or p_amount_total <> v_order.amount_minor
    or lower(p_currency) <> v_order.currency then
    update public.billing_orders set status='review_required',updated_at=now() where id=p_order_id;
    update public.stripe_webhook_events set status='failed',last_error_code='checkout_snapshot_mismatch' where event_id=p_event_id;
    raise exception 'BILLING_CHECKOUT_SNAPSHOT_MISMATCH' using errcode='23514';
  end if;
  if v_order.purpose='ai_credit_topup' then
    if coalesce((v_order.product_snapshot->>'credits_grant')::bigint,0) <= 0 then
      raise exception 'BILLING_CREDIT_GRANT_MISSING' using errcode='23514';
    end if;
    v_grant := public.credit_ledger_grant(jsonb_build_object(
      'owner_user_id',v_order.owner_user_id,
      'idempotency_key','stripe-topup:'||v_order.id::text,
      'entry_type','grant',
      'credits',(v_order.product_snapshot->>'credits_grant')::bigint,
      'policy_version',v_order.product_snapshot->>'credit_policy_version',
      'policy_approval_reference',v_order.product_snapshot->>'credit_policy_approval_reference',
      'source_event_id',p_session_id,
      'capability_id','stripe_ai_credit_topup',
      'metadata',jsonb_build_object('billing_order_id',v_order.id,'stripe_event_id',p_event_id)
    ));
  elsif v_order.purpose='premium_subscription' then
    if coalesce(p_subscription_id,'') = '' then
      raise exception 'BILLING_SUBSCRIPTION_ID_MISSING' using errcode='23514';
    end if;
    insert into public.billing_subscriptions(
      owner_user_id,product_id,stripe_subscription_id,stripe_customer_id,plan_key,
      entitlement_version,status,current_period_start,current_period_end
    ) values (
      v_order.owner_user_id,v_order.product_id,p_subscription_id,p_customer_id,
      v_order.product_snapshot->>'plan_key',v_order.product_snapshot->>'entitlement_version','active',
      p_current_period_start,p_current_period_end
    ) on conflict(stripe_subscription_id) do update set
      stripe_customer_id=coalesce(excluded.stripe_customer_id,billing_subscriptions.stripe_customer_id),
      current_period_start=coalesce(excluded.current_period_start,billing_subscriptions.current_period_start),
      current_period_end=coalesce(excluded.current_period_end,billing_subscriptions.current_period_end),
      status='active',updated_at=now()
    returning * into v_sub;
    insert into public.playback_entitlements(
      owner_user_id,entitlement_key,entitlement_version,source_subscription_id,status,valid_from,valid_until
    ) values (
      v_order.owner_user_id,v_sub.plan_key,v_sub.entitlement_version,v_sub.id,'active',now(),p_current_period_end
    ) on conflict(owner_user_id,entitlement_key,source_subscription_id) do update set
      status='active',valid_from=now(),valid_until=excluded.valid_until,updated_at=now();
  else
    raise exception 'BILLING_PURPOSE_UNSUPPORTED' using errcode='22023';
  end if;
  update public.billing_orders set status='paid',paid_at=now(),
    stripe_payment_intent_id=p_payment_intent_id,stripe_subscription_id=p_subscription_id,
    stripe_customer_id=coalesce(p_customer_id,stripe_customer_id),updated_at=now()
    where id=p_order_id;
  insert into public.billing_receipts(
    order_id,owner_user_id,provider_receipt_id,receipt_number,stripe_payment_intent_id,
    amount_minor,currency,paid_at
  ) values (
    p_order_id,v_order.owner_user_id,coalesce(p_payment_intent_id,p_session_id),
    'ALP-'||upper(right(replace(p_order_id::text,'-',''),12)),
    p_payment_intent_id,v_order.amount_minor,v_order.currency,now()
  ) on conflict(provider_receipt_id) do nothing;
  update public.stripe_webhook_events set status='processed',processed_at=now(),last_error_code=null
    where event_id=p_event_id;
  return jsonb_build_object('fulfilled',true,'idempotent_replay',false,'order_id',p_order_id,
    'credit_entry_id',v_grant->>'entry_id');
end;
$$;

create or replace function public.billing_apply_subscription_state(
  p_event_id text,p_subscription_id text,p_customer_id text,p_status text,
  p_current_period_start timestamptz default null,p_current_period_end timestamptz default null,
  p_cancel_at_period_end boolean default null
) returns jsonb language plpgsql security definer set search_path = ''
as $$
declare v_sub public.billing_subscriptions; v_entitlement_status text;
begin
  if p_status not in ('active','past_due','canceled','unpaid','incomplete','incomplete_expired','paused','trialing') then
    raise exception 'STRIPE_SUBSCRIPTION_STATUS_INVALID' using errcode='22023';
  end if;
  update public.billing_subscriptions set status=p_status,
    stripe_customer_id=coalesce(p_customer_id,stripe_customer_id),
    current_period_start=coalesce(p_current_period_start,current_period_start),
    current_period_end=coalesce(p_current_period_end,current_period_end),
    cancel_at_period_end=coalesce(p_cancel_at_period_end,cancel_at_period_end),updated_at=now()
    where stripe_subscription_id=p_subscription_id returning * into v_sub;
  if not found then
    raise exception 'BILLING_SUBSCRIPTION_NOT_REGISTERED' using errcode='P0002';
  end if;
  v_entitlement_status := case when p_status='active' then 'active'
    when p_status='canceled' and coalesce(p_cancel_at_period_end,v_sub.cancel_at_period_end) and coalesce(p_current_period_end,v_sub.current_period_end) > now() then 'active'
    when p_status in ('past_due','unpaid','incomplete','incomplete_expired','paused','trialing') then 'suspended'
    else 'revoked' end;
  update public.playback_entitlements set status=v_entitlement_status,
    valid_until=case when v_entitlement_status='active' then coalesce(p_current_period_end,v_sub.current_period_end) else coalesce(p_current_period_end,now()) end,
    updated_at=now()
    where source_subscription_id=v_sub.id;
  update public.stripe_webhook_events set status='processed',processed_at=now(),last_error_code=null
    where event_id=p_event_id;
  return jsonb_build_object('updated',true,'subscription_id',v_sub.id,'entitlement_status',v_entitlement_status);
end;
$$;

create or replace function public.billing_mark_checkout_failed(
  p_event_id text,p_order_id uuid,p_session_id text
) returns jsonb language plpgsql security definer set search_path = ''
as $$
declare v_order public.billing_orders;
begin
  select * into v_order from public.billing_orders where id=p_order_id for update;
  if found and v_order.stripe_checkout_session_id=p_session_id and v_order.status='checkout_pending' then
    update public.billing_orders set status='failed',updated_at=now() where id=p_order_id;
  end if;
  update public.stripe_webhook_events set status='processed',processed_at=now() where event_id=p_event_id;
  return jsonb_build_object('processed',true);
end;
$$;

revoke all on function public.billing_create_order(uuid,text,text),
  public.billing_attach_checkout_session(uuid,uuid,text,text,text),
  public.billing_receive_stripe_event(text,text,timestamptz,jsonb),
  public.billing_mark_stripe_event(text,text,text),
  public.billing_finalize_stripe_checkout(text,uuid,text,uuid,text,bigint,text,text,text,text,timestamptz,timestamptz),
  public.billing_apply_subscription_state(text,text,text,text,timestamptz,timestamptz,boolean),
  public.billing_mark_checkout_failed(text,uuid,text)
  from public,anon,authenticated;
grant execute on function public.billing_create_order(uuid,text,text),
  public.billing_attach_checkout_session(uuid,uuid,text,text,text),
  public.billing_receive_stripe_event(text,text,timestamptz,jsonb),
  public.billing_mark_stripe_event(text,text,text),
  public.billing_finalize_stripe_checkout(text,uuid,text,uuid,text,bigint,text,text,text,text,timestamptz,timestamptz),
  public.billing_apply_subscription_state(text,text,text,text,timestamptz,timestamptz,boolean),
  public.billing_mark_checkout_failed(text,uuid,text)
  to service_role;

comment on table public.billing_products is 'Operator-managed Stripe Price ID and approved Allpha commercial policy registry; no prices or products are seeded.';
comment on table public.billing_orders is 'Canonical Allpha billing order snapshot. Client redirects never fulfill an order.';
comment on table public.billing_receipts is 'Server-verified Stripe settlement receipts; no payment card data is stored.';
comment on table public.billing_subscriptions is 'Stripe subscription lifecycle mirrored from signed webhooks.';
comment on table public.playback_entitlements is 'Server-derived subscription entitlement; never client supplied.';
comment on table public.stripe_webhook_events is 'Signed Stripe event idempotency and recovery inbox with sanitized payload snapshots.';


create or replace function public.billing_record_subscription_invoice(
  p_event_id text,p_subscription_id text,p_invoice_id text,p_payment_intent_id text,
  p_amount_paid bigint,p_currency text,p_paid_at timestamptz,p_hosted_invoice_url text default null
) returns jsonb language plpgsql security definer set search_path = ''
as $$
declare v_sub public.billing_subscriptions; v_order public.billing_orders;
begin
  if coalesce(p_event_id,'') = '' or coalesce(p_subscription_id,'') = ''
    or coalesce(p_invoice_id,'') !~ '^in_[A-Za-z0-9]+$'
    or p_amount_paid is null or p_amount_paid < 0
    or coalesce(p_currency,'') !~ '^[a-z]{3}$' or p_paid_at is null then
    raise exception 'STRIPE_INVOICE_RECEIPT_INVALID' using errcode='22023';
  end if;
  select * into v_sub from public.billing_subscriptions
    where stripe_subscription_id=p_subscription_id for update;
  if not found then
    update public.stripe_webhook_events set status='ignored',processed_at=now(),
      last_error_code='invoice_subscription_not_registered' where event_id=p_event_id;
    return jsonb_build_object('recorded',false,'reason','subscription_not_registered');
  end if;
  select * into v_order from public.billing_orders
    where stripe_subscription_id=p_subscription_id and owner_user_id=v_sub.owner_user_id
    order by paid_at asc limit 1;
  if not found then
    raise exception 'BILLING_SUBSCRIPTION_ORDER_NOT_FOUND' using errcode='P0002';
  end if;
  if p_amount_paid > 0 then
    insert into public.billing_receipts(
      order_id,owner_user_id,provider_receipt_id,receipt_number,stripe_payment_intent_id,
      stripe_invoice_id,amount_minor,currency,hosted_invoice_url,paid_at
    ) values (
      v_order.id,v_sub.owner_user_id,p_invoice_id,
      'ALP-INV-'||upper(right(replace(p_invoice_id,'_',''),12)),
      p_payment_intent_id,p_invoice_id,p_amount_paid,p_currency,p_hosted_invoice_url,p_paid_at
    ) on conflict(provider_receipt_id) do nothing;
  end if;
  update public.stripe_webhook_events set status='processed',processed_at=now(),last_error_code=null
    where event_id=p_event_id;
  return jsonb_build_object('recorded',p_amount_paid > 0,'invoice_id',p_invoice_id);
end;
$$;

revoke all on function public.billing_record_subscription_invoice(text,text,text,text,bigint,text,timestamptz,text) from public,anon,authenticated;
grant execute on function public.billing_record_subscription_invoice(text,text,text,text,bigint,text,timestamptz,text) to service_role;

commit;

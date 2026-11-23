-- ENG-P03: durable pseudonymous identity subjects, source dispositions and Stripe cancellation.
-- No account data is deleted by this migration. The executor applies the dispositions
-- only after retention, legal-hold and Storage cleanup gates have passed.

create table if not exists private.account_identity_subjects (
  subject_id uuid primary key,
  subject_ref text not null unique check (subject_ref ~ '^[a-f0-9]{64}$'),
  status text not null default 'active' check (status in ('active','deleted')),
  created_at timestamptz not null default clock_timestamp(),
  deleted_at timestamptz,
  check ((status='active' and deleted_at is null) or (status='deleted' and deleted_at is not null))
);
alter table private.account_identity_subjects enable row level security;
revoke all on private.account_identity_subjects from public, anon, authenticated, service_role;

insert into private.account_identity_subjects(subject_id,subject_ref,status)
select u.id,encode(digest(u.id::text,'sha256'),'hex'),'active'
from auth.users u
on conflict(subject_id) do nothing;

create or replace function private.ensure_account_identity_subject()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_user_id uuid;
  v_subject_ref text;
  v_status text;
begin
  if coalesce(auth.jwt()->>'role','') <> 'service_role' then
    raise exception 'service_role_required' using errcode='42501';
  end if;
  v_user_id := nullif(to_jsonb(new)->>tg_argv[0],'')::uuid;
  if v_user_id is null then
    return new;
  end if;
  if not exists(select 1 from auth.users u where u.id=v_user_id) then
    raise exception 'account_identity_subject_auth_user_missing' using errcode='23503';
  end if;
  v_subject_ref := encode(digest(v_user_id::text,'sha256'),'hex');
  insert into private.account_identity_subjects(subject_id,subject_ref,status)
  values(v_user_id,v_subject_ref,'active')
  on conflict(subject_id) do nothing;
  select s.status into v_status
    from private.account_identity_subjects s where s.subject_id=v_user_id;
  if v_status is distinct from 'active' then
    raise exception 'account_identity_subject_deleted' using errcode='23514';
  end if;
  return new;
end;
$$;
revoke all on function private.ensure_account_identity_subject() from public, anon, authenticated;
grant execute on function private.ensure_account_identity_subject() to service_role;

drop trigger if exists agent_consumer_grant_events_identity_subject on public.agent_consumer_grant_events;
create trigger agent_consumer_grant_events_identity_subject
before insert or update of owner_user_id on public.agent_consumer_grant_events
for each row execute function private.ensure_account_identity_subject('owner_user_id');

drop trigger if exists billing_orders_identity_subject on public.billing_orders;
create trigger billing_orders_identity_subject
before insert or update of owner_user_id on public.billing_orders
for each row execute function private.ensure_account_identity_subject('owner_user_id');

drop trigger if exists billing_receipts_identity_subject on public.billing_receipts;
create trigger billing_receipts_identity_subject
before insert or update of owner_user_id on public.billing_receipts
for each row execute function private.ensure_account_identity_subject('owner_user_id');

drop trigger if exists billing_subscriptions_identity_subject on public.billing_subscriptions;
create trigger billing_subscriptions_identity_subject
before insert or update of owner_user_id on public.billing_subscriptions
for each row execute function private.ensure_account_identity_subject('owner_user_id');

drop trigger if exists content_retention_holds_identity_subject on public.content_retention_holds;
create trigger content_retention_holds_identity_subject
before insert or update of created_by on public.content_retention_holds
for each row execute function private.ensure_account_identity_subject('created_by');

drop trigger if exists credit_ledger_accounts_identity_subject on public.credit_ledger_accounts;
create trigger credit_ledger_accounts_identity_subject
before insert or update of owner_user_id on public.credit_ledger_accounts
for each row execute function private.ensure_account_identity_subject('owner_user_id');

drop trigger if exists playback_entitlements_identity_subject on public.playback_entitlements;
create trigger playback_entitlements_identity_subject
before insert or update of owner_user_id on public.playback_entitlements
for each row execute function private.ensure_account_identity_subject('owner_user_id');

-- Reparent only immutable/financial/retention references to the private pseudonymous subject.
-- The subject UUID is random and the subject registry contains no email, phone, name or metadata.
alter table public.agent_consumer_grant_events drop constraint agent_consumer_grant_events_owner_user_id_fkey;
alter table public.agent_consumer_grant_events add constraint agent_consumer_grant_events_owner_user_id_fkey
  foreign key (owner_user_id) references private.account_identity_subjects(subject_id) on delete restrict not valid;
alter table public.agent_consumer_grant_events validate constraint agent_consumer_grant_events_owner_user_id_fkey;

alter table public.billing_orders drop constraint billing_orders_owner_user_id_fkey;
alter table public.billing_orders add constraint billing_orders_owner_user_id_fkey
  foreign key (owner_user_id) references private.account_identity_subjects(subject_id) on delete restrict not valid;
alter table public.billing_orders validate constraint billing_orders_owner_user_id_fkey;

alter table public.billing_receipts drop constraint billing_receipts_owner_user_id_fkey;
alter table public.billing_receipts add constraint billing_receipts_owner_user_id_fkey
  foreign key (owner_user_id) references private.account_identity_subjects(subject_id) on delete restrict not valid;
alter table public.billing_receipts validate constraint billing_receipts_owner_user_id_fkey;

alter table public.billing_subscriptions drop constraint billing_subscriptions_owner_user_id_fkey;
alter table public.billing_subscriptions add constraint billing_subscriptions_owner_user_id_fkey
  foreign key (owner_user_id) references private.account_identity_subjects(subject_id) on delete restrict not valid;
alter table public.billing_subscriptions validate constraint billing_subscriptions_owner_user_id_fkey;

alter table public.content_retention_holds drop constraint content_retention_holds_created_by_fkey;
alter table public.content_retention_holds add constraint content_retention_holds_created_by_fkey
  foreign key (created_by) references private.account_identity_subjects(subject_id) on delete restrict not valid;
alter table public.content_retention_holds validate constraint content_retention_holds_created_by_fkey;

alter table public.credit_ledger_accounts drop constraint credit_ledger_accounts_owner_user_id_fkey;
alter table public.credit_ledger_accounts add constraint credit_ledger_accounts_owner_user_id_fkey
  foreign key (owner_user_id) references private.account_identity_subjects(subject_id) on delete restrict not valid;
alter table public.credit_ledger_accounts validate constraint credit_ledger_accounts_owner_user_id_fkey;

alter table public.playback_entitlements drop constraint playback_entitlements_owner_user_id_fkey;
alter table public.playback_entitlements add constraint playback_entitlements_owner_user_id_fkey
  foreign key (owner_user_id) references private.account_identity_subjects(subject_id) on delete restrict not valid;
alter table public.playback_entitlements validate constraint playback_entitlements_owner_user_id_fkey;

-- The remaining source-owned records are deleted only after their own Storage and dependency steps.
alter table public.account_deletion_dependency_rules
  drop constraint if exists account_deletion_dependency_rules_resolution_action_check;
alter table public.account_deletion_dependency_rules
  add constraint account_deletion_dependency_rules_resolution_action_check
  check (resolution_action = any (array[
    'database_cascade','database_set_null','delete_rows','set_null','block','transfer_owner','preserve_tombstone'
  ]::text[]));

update public.account_deletion_dependency_rules
set resolution_action='preserve_tombstone',
    reason='Preserve financial, credit, grant, entitlement or retention evidence under a private pseudonymous identity subject. No PII is stored in the subject registry; source-specific revocation/redaction is applied transactionally before Auth deletion.',
    updated_at=clock_timestamp()
where active=true and constraint_name in (
  'agent_consumer_grant_events_owner_user_id_fkey',
  'billing_orders_owner_user_id_fkey',
  'billing_receipts_owner_user_id_fkey',
  'billing_subscriptions_owner_user_id_fkey',
  'content_retention_holds_created_by_fkey',
  'credit_ledger_accounts_owner_user_id_fkey',
  'playback_entitlements_owner_user_id_fkey'
);

update public.account_deletion_dependency_rules
set resolution_action='delete_rows',
    reason='The canonical source handler deletes this owner-scoped operational record only after its dependent Storage objects are removed and its parent/child ordering has completed.',
    updated_at=clock_timestamp()
where active=true and constraint_name in (
  'cinema_generation_job_links_owner_id_fkey',
  'cinema_generation_job_links_owner_user_id_fkey',
  'cinema_generation_job_links_requester_user_id_fkey',
  'generation_artifact_deletion_jobs_owner_user_id_fkey',
  'generation_artifacts_owner_user_id_fkey',
  'generation_jobs_agent_owner_user_id_fkey',
  'generation_jobs_owner_user_id_fkey',
  'generation_jobs_payer_user_id_fkey'
);

update public.account_deletion_source_policies
set deletion_action='delete_rows',
    reason='Storage cleanup is queued for every artifact deletion job path before the operational queue rows are removed; active worker leases are fenced before DB cleanup.',
    updated_at=clock_timestamp()
where active=true and source_key='generation_artifact_deletions';

-- Durable provider-cancellation queue. Stripe outcome is confirmed before local subscription
-- state changes and before the account deletion executor may proceed.
create table if not exists private.account_deletion_subscription_cancellation_jobs (
  id uuid primary key default gen_random_uuid(),
  request_id uuid not null references public.account_deletion_requests(id) on delete cascade,
  billing_subscription_id uuid not null references public.billing_subscriptions(id) on delete restrict,
  stripe_subscription_id text,
  stripe_mode text check (stripe_mode is null or stripe_mode in ('test','live')),
  idempotency_key text not null unique,
  status text not null default 'queued'
    check (status in ('queued','processing','retryable','completed','dead')),
  attempts integer not null default 0 check (attempts >= 0 and attempts <= 12),
  max_attempts integer not null default 8 check (max_attempts between 1 and 12),
  available_at timestamptz not null default clock_timestamp(),
  lease_token uuid,
  lease_expires_at timestamptz,
  error_code text,
  provider_status text,
  created_at timestamptz not null default clock_timestamp(),
  updated_at timestamptz not null default clock_timestamp(),
  completed_at timestamptz,
  unique(request_id,billing_subscription_id),
  check ((lease_token is null and lease_expires_at is null) or
         (lease_token is not null and lease_expires_at is not null)),
  check ((status='completed' and completed_at is not null) or status<>'completed')
);
create index if not exists account_deletion_subscription_cancellation_claim_idx
  on private.account_deletion_subscription_cancellation_jobs(status,available_at,created_at);
alter table private.account_deletion_subscription_cancellation_jobs enable row level security;
revoke all on private.account_deletion_subscription_cancellation_jobs from public, anon, authenticated, service_role;

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
    request_id,billing_subscription_id,stripe_subscription_id,stripe_mode,idempotency_key
  )
  select r.id,bs.id,bs.stripe_subscription_id,bo.stripe_mode,
         'account-deletion:'||r.id::text||':'||bs.id::text
  from public.account_deletion_requests r
  join public.billing_subscriptions bs on bs.owner_user_id=r.user_id
  left join lateral (
    select o.stripe_mode from public.billing_orders o
    where o.owner_user_id=bs.owner_user_id
      and o.stripe_subscription_id=bs.stripe_subscription_id
    order by o.created_at desc limit 1
  ) bo on true
  where r.user_id is not null
    and r.status in ('scheduled','blocked_dependency','processing')
    and bs.status in ('active','trialing','past_due','unpaid','incomplete','paused')
  on conflict(request_id,billing_subscription_id) do nothing;
  get diagnostics v_count=row_count;
  return v_count;
end;
$$;
revoke all on function public.prepare_account_deletion_subscription_cancellations() from public, anon, authenticated;
grant execute on function public.prepare_account_deletion_subscription_cancellations() to service_role;

create or replace function public.claim_account_deletion_subscription_cancellation_jobs(
  p_worker_id text,
  p_limit integer default 10,
  p_lease_seconds integer default 300
) returns table(
  id uuid,
  billing_subscription_id uuid,
  stripe_subscription_id text,
  stripe_mode text,
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
  returning j.id,j.billing_subscription_id,j.stripe_subscription_id,j.stripe_mode,
            j.idempotency_key,j.attempts,j.lease_token;
end;
$$;
revoke all on function public.claim_account_deletion_subscription_cancellation_jobs(text,integer,integer)
  from public, anon, authenticated;
grant execute on function public.claim_account_deletion_subscription_cancellation_jobs(text,integer,integer)
  to service_role;

create or replace function public.complete_account_deletion_subscription_cancellation_job(
  p_job_id uuid,
  p_lease_token uuid
) returns boolean
language plpgsql
security definer
set search_path = ''
as $$
declare v_job private.account_deletion_subscription_cancellation_jobs%rowtype;
        v_rows integer;
begin
  if coalesce(auth.jwt()->>'role','') <> 'service_role' then
    raise exception 'service_role_required' using errcode='42501';
  end if;
  select * into v_job from private.account_deletion_subscription_cancellation_jobs
   where id=p_job_id and status='processing' and lease_token=p_lease_token
     and lease_expires_at>clock_timestamp() for update;
  if not found then raise exception 'account_deletion_subscription_lease_lost' using errcode='40001'; end if;
  update public.billing_subscriptions
     set status='canceled',cancel_at_period_end=false,updated_at=clock_timestamp()
   where id=v_job.billing_subscription_id
     and (v_job.stripe_subscription_id is null or stripe_subscription_id=v_job.stripe_subscription_id);
  get diagnostics v_rows=row_count;
  if v_rows<>1 then
    raise exception 'account_deletion_subscription_local_record_missing' using errcode='23503';
  end if;
  update private.account_deletion_subscription_cancellation_jobs
     set status='completed',provider_status='canceled',completed_at=clock_timestamp(),
         lease_token=null,lease_expires_at=null,error_code=null,updated_at=clock_timestamp()
   where id=p_job_id and lease_token=p_lease_token;
  return true;
end;
$$;
revoke all on function public.complete_account_deletion_subscription_cancellation_job(uuid,uuid)
  from public, anon, authenticated;
grant execute on function public.complete_account_deletion_subscription_cancellation_job(uuid,uuid)
  to service_role;

create or replace function public.fail_account_deletion_subscription_cancellation_job(
  p_job_id uuid,
  p_lease_token uuid,
  p_error_code text,
  p_retry_seconds integer
) returns boolean
language plpgsql
security definer
set search_path = ''
as $$
declare v_job private.account_deletion_subscription_cancellation_jobs%rowtype;
begin
  if coalesce(auth.jwt()->>'role','') <> 'service_role' then
    raise exception 'service_role_required' using errcode='42501';
  end if;
  if p_error_code is null or length(p_error_code)>80 or p_retry_seconds not between 1 and 86400 then
    raise exception 'account_deletion_subscription_failure_arguments_invalid' using errcode='22023';
  end if;
  select * into v_job from private.account_deletion_subscription_cancellation_jobs
   where id=p_job_id and status='processing' and lease_token=p_lease_token
     and lease_expires_at>clock_timestamp() for update;
  if not found then return false; end if;
  update private.account_deletion_subscription_cancellation_jobs
     set status=case when attempts>=max_attempts then 'dead' else 'retryable' end,
         available_at=clock_timestamp()+make_interval(secs=>p_retry_seconds),
         lease_token=null,lease_expires_at=null,error_code=p_error_code,
         updated_at=clock_timestamp()
   where id=p_job_id and lease_token=p_lease_token;
  return true;
end;
$$;
revoke all on function public.fail_account_deletion_subscription_cancellation_job(uuid,uuid,text,integer)
  from public, anon, authenticated;
grant execute on function public.fail_account_deletion_subscription_cancellation_job(uuid,uuid,text,integer)
  to service_role;

-- Extend the executor with source queue fencing and pseudonymous identity preservation.
do $$
declare
  v_definition text;
  v_source_old text := $old$
        if v_source.filter_kind='owner_columns' then
          if cardinality(v_source.owner_columns)=0 then
$old$;
  v_source_new text := $new$
        if v_source.filter_kind='owner_columns' then
          if v_step.step_key='generation_artifact_deletions'
             and exists(select 1 from public.generation_artifact_deletion_jobs d
               where d.owner_user_id=v_job.user_id and d.status='processing'
                 and d.lease_expires_at>clock_timestamp()) then
            raise exception 'account_deletion_artifact_queue_lease_active' using errcode='55000';
          end if;
          if cardinality(v_source.owner_columns)=0 then
$new$;
  v_fk_old text := $old$
      elsif v_step.action='block' then
        if private.account_deletion_fk_has_unresolved_user_rows(v_rule.id,v_job.user_id) then
$old$;
  v_fk_new text := $new$
      elsif v_step.action='preserve_tombstone' then
        if v_rule.child_schema<>'public' or v_rule.fk_column is null
           or v_rule.constraint_name not in (
             'agent_consumer_grant_events_owner_user_id_fkey',
             'billing_orders_owner_user_id_fkey',
             'billing_receipts_owner_user_id_fkey',
             'billing_subscriptions_owner_user_id_fkey',
             'content_retention_holds_created_by_fkey',
             'credit_ledger_accounts_owner_user_id_fkey',
             'playback_entitlements_owner_user_id_fkey'
           ) then
          raise exception 'account_deletion_tombstone_handler_missing:%',v_rule.constraint_name using errcode='0A000';
        end if;
        if not exists(select 1 from pg_constraint c
          where c.conname=v_rule.constraint_name
            and c.conrelid=to_regclass(format('%I.%I',v_rule.child_schema,v_rule.child_table))
            and c.contype='f' and c.confrelid='private.account_identity_subjects'::regclass
            and cardinality(c.conkey)=1 and cardinality(c.confkey)=1
            and (select a.attname from pg_attribute a where a.attrelid=c.conrelid and a.attnum=c.conkey[1])=v_rule.fk_column
            and (select a.attname from pg_attribute a where a.attrelid=c.confrelid and a.attnum=c.confkey[1])='subject_id'
        ) then
          raise exception 'account_deletion_tombstone_fk_mismatch:%',v_rule.constraint_name using errcode='55000';
        end if;
        insert into private.account_identity_subjects(subject_id,subject_ref,status,deleted_at)
        values(v_job.user_id,v_job.subject_ref,'deleted',clock_timestamp())
        on conflict(subject_id) do update
          set status='deleted',deleted_at=coalesce(private.account_identity_subjects.deleted_at,clock_timestamp())
          where private.account_identity_subjects.subject_ref=excluded.subject_ref;
        if not exists(select 1 from private.account_identity_subjects s
          where s.subject_id=v_job.user_id and s.subject_ref=v_job.subject_ref and s.status='deleted') then
          raise exception 'account_deletion_identity_tombstone_conflict' using errcode='23514';
        end if;
        if v_rule.child_table='agent_consumer_grant_events' then
          update public.agent_consumer_grant_events
             set details=jsonb_build_object('redacted',true,'reason','account_deletion')
           where owner_user_id=v_job.user_id;
        elsif v_rule.child_table='billing_orders' then
          update public.billing_orders set stripe_checkout_url=null
           where owner_user_id=v_job.user_id and stripe_checkout_url is not null;
        elsif v_rule.child_table='billing_receipts' then
          update public.billing_receipts set hosted_invoice_url=null
           where owner_user_id=v_job.user_id and hosted_invoice_url is not null;
        elsif v_rule.child_table='billing_subscriptions' then
          if exists(select 1 from private.account_deletion_subscription_cancellation_jobs j
            where j.request_id=v_job.request_id and j.status<>'completed') then
            raise exception 'account_deletion_subscription_cancellation_pending' using errcode='55000';
          end if;
          if exists(select 1 from public.billing_subscriptions bs
            where bs.owner_user_id=v_job.user_id
              and bs.status in ('active','trialing','past_due','unpaid','incomplete','paused')) then
            raise exception 'account_deletion_active_subscription_unresolved' using errcode='55000';
          end if;
        elsif v_rule.child_table='playback_entitlements' then
          update public.playback_entitlements
             set status='revoked',updated_at=clock_timestamp()
           where owner_user_id=v_job.user_id and status<>'revoked';
        elsif v_rule.child_table not in ('content_retention_holds','credit_ledger_accounts') then
          raise exception 'account_deletion_tombstone_source_handler_missing:%',v_rule.child_table using errcode='0A000';
        end if;
        get diagnostics v_rows=row_count;
      elsif v_step.action='block' then
        if private.account_deletion_fk_has_unresolved_user_rows(v_rule.id,v_job.user_id) then
$new$;
  v_auth_old text := $old$
  delete from auth.users where id=v_job.user_id;
$old$;
  v_auth_new text := $new$
  insert into private.account_identity_subjects(subject_id,subject_ref,status,deleted_at)
  values(v_job.user_id,v_job.subject_ref,'deleted',clock_timestamp())
  on conflict(subject_id) do update
    set status='deleted',deleted_at=coalesce(private.account_identity_subjects.deleted_at,clock_timestamp())
    where private.account_identity_subjects.subject_ref=excluded.subject_ref;
  if not exists(select 1 from private.account_identity_subjects s
    where s.subject_id=v_job.user_id and s.subject_ref=v_job.subject_ref and s.status='deleted') then
    raise exception 'account_deletion_identity_tombstone_missing' using errcode='23514';
  end if;
  delete from auth.users where id=v_job.user_id;
$old$;
begin
  v_definition:=pg_get_functiondef('public.execute_account_deletion_execution_job(uuid,uuid)'::regprocedure);
  if position(v_fk_new in v_definition)=0 then
    if position(v_fk_old in v_definition)=0 then
      raise exception 'account_deletion_tombstone_executor_patch_anchor_missing';
    end if;
    v_definition:=replace(v_definition,v_fk_old,v_fk_new);
  end if;
  if position(v_source_new in v_definition)=0 then
    if position(v_source_old in v_definition)=0 then
      raise exception 'account_deletion_artifact_queue_patch_anchor_missing';
    end if;
    v_definition:=replace(v_definition,v_source_old,v_source_new);
  end if;
  if position(v_auth_new in v_definition)=0 then
    if position(v_auth_old in v_definition)=0 then
      raise exception 'account_deletion_tombstone_auth_patch_anchor_missing';
    end if;
    v_definition:=replace(v_definition,v_auth_old,v_auth_new);
  end if;
  execute v_definition;
end;
$$;

-- Add all Storage objects referenced by the user-scoped artifact deletion queue to the same
-- lease-fenced account deletion storage pipeline before its queue rows are removed.
do $$
declare
  v_definition text;
  v_old text := $old$
  insert into public.account_deletion_storage_jobs(execution_job_id,source_key,storage_bucket,storage_path)
  select v_job.id,'account_export_jobs',j.storage_bucket,j.storage_path from public.account_export_jobs j
$old$;
  v_new text := $new$
  insert into public.account_deletion_storage_jobs(execution_job_id,source_key,storage_bucket,storage_path)
  select v_job.id,'generation_artifact_deletions',d.bucket_id,d.object_path
    from public.generation_artifact_deletion_jobs d
   where d.owner_user_id=v_request.user_id and d.status<>'succeeded'
     and d.object_path<>'' and left(d.object_path,1)<>'/'
     and position('..' in d.object_path)=0 on conflict do nothing;

  insert into public.account_deletion_storage_jobs(execution_job_id,source_key,storage_bucket,storage_path)
  select v_job.id,'account_export_jobs',j.storage_bucket,j.storage_path from public.account_export_jobs j
$new$;
begin
  v_definition:=pg_get_functiondef('public.prepare_account_deletion_execution(uuid)'::regprocedure);
  if position(v_new in v_definition)>0 then return; end if;
  if position(v_old in v_definition)=0 then
    raise exception 'account_deletion_artifact_storage_prepare_patch_anchor_missing';
  end if;
  execute replace(v_definition,v_old,v_new);
end;
$$;

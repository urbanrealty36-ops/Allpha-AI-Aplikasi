-- Restored 2026-11-24 from the original Supabase Postgres migration statement log.
-- The log truncated at the final CREATE TRIGGER; its remaining function call was verified
-- against pg_get_triggerdef('public.account_legal_holds'::regclass trigger metadata).
-- ENG-P03: executable, lease-fenced account deletion with explicit data-class
-- and FK dependency policy. No retention values or destructive mappings are seeded.
begin;

alter table public.account_deletion_requests
  drop constraint if exists account_deletion_requests_status_check;
alter table public.account_deletion_requests
  add constraint account_deletion_requests_status_check
  check (status = any (array[
    'awaiting_policy','scheduled','processing','blocked_legal_hold',
    'blocked_dependency','completed','cancelled','failed'
  ]::text[]));
drop index if exists public.account_deletion_one_open_request_per_user;
create unique index account_deletion_one_open_request_per_user
  on public.account_deletion_requests(user_id)
  where user_id is not null and status in
    ('awaiting_policy','scheduled','processing','blocked_legal_hold','blocked_dependency');

alter table public.account_lifecycle_events
  drop constraint if exists account_lifecycle_events_event_type_check;
alter table public.account_lifecycle_events
  add constraint account_lifecycle_events_event_type_check
  check (event_type = any (array[
    'export_requested','export_started','export_completed','export_failed',
    'deletion_requested','deletion_cancelled','deletion_scheduled','deletion_started',
    'deletion_blocked','deletion_unblocked','deletion_policy_pending',
    'deletion_completed','deletion_failed'
  ]::text[]));

create table if not exists public.account_deletion_source_policies (
  source_key text primary key references private.account_export_sources(source_key) on delete cascade,
  data_class text check (data_class in (
    'owner_private','agent_operational','tenant_shared',
    'published_knowledge','session_scoped','public_catalog'
  )),
  deletion_action text check (deletion_action in ('delete_rows','preserve','block')),
  dependency_order integer not null default 100,
  policy_version text,
  reason text,
  approved_by uuid,
  approved_at timestamptz,
  active boolean not null default false,
  updated_at timestamptz not null default now(),
  check (
    (active = false) or
    (data_class is not null and deletion_action is not null
     and policy_version is not null and approved_by is not null
     and approved_at is not null and reason is not null)
  )
);
insert into public.account_deletion_source_policies(source_key,dependency_order)
select source_key,sort_order from private.account_export_sources where enabled
on conflict (source_key) do nothing;

create table if not exists public.account_deletion_dependency_rules (
  id uuid primary key default gen_random_uuid(),
  child_schema text not null,
  child_table text not null,
  constraint_name text not null,
  fk_column text,
  delete_rule text not null check (delete_rule in ('CASCADE','SET NULL','RESTRICT','NO ACTION','SET DEFAULT')),
  resolution_action text not null check (resolution_action in (
    'database_cascade','database_set_null','delete_rows','set_null','block'
  )),
  reason text,
  approved_by uuid,
  approved_at timestamptz,
  active boolean not null default true,
  updated_at timestamptz not null default now(),
  unique(child_schema,child_table,constraint_name)
);
insert into public.account_deletion_dependency_rules(
  child_schema,child_table,constraint_name,fk_column,delete_rule,resolution_action
)
select child_ns.nspname,child.relname,con.conname,
  case when cardinality(con.conkey)=1 then child_att.attname else null end,
  case con.confdeltype when 'c' then 'CASCADE' when 'n' then 'SET NULL'
    when 'r' then 'RESTRICT' when 'a' then 'NO ACTION' when 'd' then 'SET DEFAULT' end,
  case con.confdeltype when 'c' then 'database_cascade' when 'n' then 'database_set_null' else 'block' end
from pg_constraint con
join pg_class child on child.oid=con.conrelid
join pg_namespace child_ns on child_ns.oid=child.relnamespace
join pg_class parent on parent.oid=con.confrelid
join pg_namespace parent_ns on parent_ns.oid=parent.relnamespace
left join lateral (
  select a.attname from unnest(con.conkey) with ordinality k(attnum,ord)
  join pg_attribute a on a.attrelid=child.oid and a.attnum=k.attnum
  order by k.ord limit 1
) child_att on true
where con.contype='f' and parent_ns.nspname='auth' and parent.relname='users'
  and child_ns.nspname in ('public','private')
on conflict (child_schema,child_table,constraint_name) do nothing;

create table if not exists public.account_deletion_execution_jobs (
  id uuid primary key default gen_random_uuid(),
  request_id uuid not null unique references public.account_deletion_requests(id) on delete restrict,
  user_id uuid not null,
  subject_ref text not null,
  status text not null default 'queued'
    check (status in ('queued','running','blocked','failed','completed')),
  attempts integer not null default 0 check (attempts >= 0),
  max_attempts integer not null default 8 check (max_attempts between 1 and 20),
  next_attempt_at timestamptz not null default now(),
  lease_token uuid, lease_owner text, lease_expires_at timestamptz,
  policy_snapshot jsonb not null default '{}'::jsonb,
  error_code text, started_at timestamptz, completed_at timestamptz,
  created_at timestamptz not null default now(), updated_at timestamptz not null default now()
);
create index if not exists account_deletion_execution_claim_idx
  on public.account_deletion_execution_jobs(status,next_attempt_at,created_at)
  where status in ('queued','running');

create table if not exists public.account_deletion_execution_steps (
  id uuid primary key default gen_random_uuid(),
  job_id uuid not null references public.account_deletion_execution_jobs(id) on delete cascade,
  step_kind text not null check (step_kind in ('source','foreign_key')),
  step_key text not null, action text not null, data_class text,
  dependency_order integer not null default 100,
  status text not null default 'pending' check (status in ('pending','completed','blocked','failed')),
  affected_rows bigint not null default 0 check (affected_rows >= 0),
  error_code text, started_at timestamptz, completed_at timestamptz,
  unique(job_id,step_kind,step_key)
);
create index if not exists account_deletion_steps_pending_idx
  on public.account_deletion_execution_steps(job_id,status,dependency_order desc);

create table if not exists public.account_deletion_storage_jobs (
  id uuid primary key default gen_random_uuid(),
  execution_job_id uuid not null references public.account_deletion_execution_jobs(id) on delete cascade,
  storage_bucket text not null, storage_path text not null,
  status text not null default 'pending' check (status in ('pending','running','completed','failed')),
  attempts integer not null default 0 check (attempts >= 0),
  lease_token uuid, lease_expires_at timestamptz, error_code text,
  completed_at timestamptz, created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(execution_job_id,storage_bucket,storage_path),
  check (storage_bucket ~ '^[a-z0-9][a-z0-9._-]{1,62}$'),
  check (storage_path <> '' and left(storage_path,1) <> '/' and position('..' in storage_path)=0)
);
create index if not exists account_deletion_storage_claim_idx
  on public.account_deletion_storage_jobs(execution_job_id,status,created_at)
  where status in ('pending','running');

alter table public.account_deletion_source_policies enable row level security;
alter table public.account_deletion_dependency_rules enable row level security;
alter table public.account_deletion_execution_jobs enable row level security;
alter table public.account_deletion_execution_steps enable row level security;
alter table public.account_deletion_storage_jobs enable row level security;
revoke all on public.account_deletion_source_policies,public.account_deletion_dependency_rules,
  public.account_deletion_execution_jobs,public.account_deletion_execution_steps,
  public.account_deletion_storage_jobs from public,anon,authenticated;
grant select,insert,update,delete on public.account_deletion_source_policies,
  public.account_deletion_dependency_rules,public.account_deletion_execution_jobs,
  public.account_deletion_execution_steps,public.account_deletion_storage_jobs to service_role;

create or replace function public.set_account_deletion_source_policy(
  p_source_key text,p_data_class text,p_deletion_action text,
  p_policy_version text,p_reason text,p_actor_user_id uuid
) returns public.account_deletion_source_policies
language plpgsql security definer set search_path=''
as $fn$
declare v_source private.account_export_sources%rowtype; v_policy public.account_deletion_source_policies%rowtype;
begin
  if coalesce(auth.role(),'')<>'service_role' then raise exception 'service_role_required' using errcode='42501'; end if;
  if p_actor_user_id is null or not exists (
    select 1 from public.platform_operator_grants g where g.user_id=p_actor_user_id
      and g.status='active' and 'platform:account_lifecycle.manage'=any(g.scopes)
      and (g.expires_at is null or g.expires_at>clock_timestamp())
  ) then raise exception 'account_lifecycle_operator_scope_required' using errcode='42501'; end if;
  if p_data_class not in ('owner_private','agent_operational','tenant_shared','published_knowledge','session_scoped','public_catalog')
     or p_deletion_action not in ('delete_rows','preserve','block')
     or p_policy_version is null or char_length(p_policy_version) not between 1 and 40
     or p_reason is null or char_length(p_reason) not between 8 and 500 then
    raise exception 'account_deletion_source_policy_invalid' using errcode='22023';
  end if;
  select * into v_source from private.account_export_sources where source_key=p_source_key and enabled=true;
  if not found then raise exception 'account_deletion_source_not_found' using errcode='P0002'; end if;
  if p_deletion_action='delete_rows' and
     (v_source.filter_kind<>'owner_columns' or cardinality(v_source.owner_columns)=0) then
    raise exception 'account_deletion_source_requires_explicit_handler' using errcode='22023';
  end if;
  insert into public.account_deletion_source_policies(
    source_key,data_class,deletion_action,dependency_order,policy_version,reason,approved_by,approved_at,active,updated_at
  ) values(p_source_key,p_data_class,p_deletion_action,v_source.sort_order,p_policy_version,
    p_reason,p_actor_user_id,clock_timestamp(),true,clock_timestamp())
  on conflict(source_key) do update set data_class=excluded.data_class,
    deletion_action=excluded.deletion_action,dependency_order=excluded.dependency_order,
    policy_version=excluded.policy_version,reason=excluded.reason,approved_by=excluded.approved_by,
    approved_at=excluded.approved_at,active=true,updated_at=clock_timestamp()
  returning * into v_policy;
  return v_policy;
end;
$fn$;

create or replace function public.set_account_deletion_dependency_rule(
  p_rule_id uuid,p_resolution_action text,p_reason text,p_actor_user_id uuid
) returns public.account_deletion_dependency_rules
language plpgsql security definer set search_path=''
as $fn$
declare v_rule public.account_deletion_dependency_rules%rowtype; v_nullable boolean;
begin
  if coalesce(auth.role(),'')<>'service_role' then raise exception 'service_role_required' using errcode='42501'; end if;
  if p_actor_user_id is null or not exists (
    select 1 from public.platform_operator_grants g where g.user_id=p_actor_user_id
      and g.status='active' and 'platform:account_lifecycle.manage'=any(g.scopes)
      and (g.expires_at is null or g.expires_at>clock_timestamp())
  ) then raise exception 'account_lifecycle_operator_scope_required' using errcode='42501'; end if;
  if p_resolution_action not in ('delete_rows','set_null','block')
     or p_reason is null or char_length(p_reason) not between 8 and 500 then
    raise exception 'account_deletion_dependency_rule_invalid' using errcode='22023';
  end if;
  select * into v_rule from public.account_deletion_dependency_rules where id=p_rule_id for update;
  if not found then raise exception 'account_deletion_dependency_rule_not_found' using errcode='P0002'; end if;
  if v_rule.fk_column is null then raise exception 'composite_foreign_key_requires_manual_handler' using errcode='22023'; end if;
  if p_resolution_action='set_null' then
    select c.is_nullable='YES' into v_nullable from information_schema.columns c
    where c.table_schema=v_rule.child_schema and c.table_name=v_rule.child_table and c.column_name=v_rule.fk_column;
    if coalesce(v_nullable,false)=false then raise exception 'foreign_key_column_not_nullable' using errcode='22023'; end if;
  end if;
  update public.account_deletion_dependency_rules set resolution_action=p_resolution_action,
    reason=p_reason,approved_by=p_actor_user_id,approved_at=clock_timestamp(),updated_at=clock_timestamp(),active=true
  where id=p_rule_id returning * into v_rule;
  return v_rule;
end;
$fn$;

create or replace function public.prepare_account_deletion_execution(p_request_id uuid)
returns jsonb language plpgsql security definer set search_path=''
as $fn$
declare v_request public.account_deletion_requests%rowtype; v_job public.account_deletion_execution_jobs%rowtype;
        v_missing_classes text[]; v_missing_sources integer; v_blocked_fks integer; v_policy_snapshot jsonb;
begin
  if coalesce(auth.role(),'')<>'service_role' then raise exception 'service_role_required' using errcode='42501'; end if;
  select * into v_request from public.account_deletion_requests where id=p_request_id for update;
  if not found then return jsonb_build_object('outcome','not_found'); end if;
  if v_request.status not in ('awaiting_policy','blocked_dependency') then
    select * into v_job from public.account_deletion_execution_jobs where request_id=p_request_id;
    return jsonb_build_object('outcome','already_processed','job_id',v_job.id);
  end if;
  perform pg_advisory_xact_lock(hashtextextended(v_request.subject_ref,0));
  if exists(select 1 from public.account_legal_holds h where h.subject_ref=v_request.subject_ref and h.active) then
    update public.account_deletion_requests set status='blocked_legal_hold',scheduled_for=null,
      error_code='LEGAL_HOLD_ACTIVE',updated_at=clock_timestamp() where id=p_request_id;
    insert into public.account_lifecycle_events(request_id,subject_ref,event_type,metadata)
    values(p_request_id,v_request.subject_ref,'deletion_blocked',jsonb_build_object('reason_code','LEGAL_HOLD_ACTIVE'));
    return jsonb_build_object('outcome','blocked_legal_hold');
  end if;
  select array_agg(required.data_class order by required.data_class) into v_missing_classes
  from (values ('owner_private'),('agent_operational'),('tenant_shared'),
    ('published_knowledge'),('session_scoped'),('public_catalog')) required(data_class)
  where not exists(select 1 from public.account_data_retention_policies p
    where p.data_class=required.data_class and p.active=true);
  select count(*) into v_missing_sources from private.account_export_sources s
  left join public.account_deletion_source_policies p on p.source_key=s.source_key and p.active=true
  where s.enabled=true and (p.source_key is null or p.data_class is null
    or p.deletion_action is null or p.deletion_action='block');
  select count(*) into v_blocked_fks from public.account_deletion_dependency_rules r
    where r.active=true and r.resolution_action='block';
  if coalesce(cardinality(v_missing_classes),0)>0 or v_missing_sources>0 or v_blocked_fks>0 then
    update public.account_deletion_requests set status='blocked_dependency',scheduled_for=null,
      error_code='DELETION_POLICY_OR_DEPENDENCY_MAP_INCOMPLETE',
      request_metadata=coalesce(request_metadata,'{}'::jsonb)||jsonb_build_object(
        'missing_data_classes',coalesce(to_jsonb(v_missing_classes),'[]'::jsonb),
        'unmapped_sources',v_missing_sources,'blocked_foreign_keys',v_blocked_fks,
        'checked_at',clock_timestamp()),updated_at=clock_timestamp() where id=p_request_id;
    return jsonb_build_object('outcome','blocked_dependency',
      'missing_data_classes',coalesce(to_jsonb(v_missing_classes),'[]'::jsonb),
      'unmapped_sources',v_missing_sources,'blocked_foreign_keys',v_blocked_fks);
  end if;
  select coalesce(jsonb_object_agg(p.data_class,p.policy_version),'{}'::jsonb)
    into v_policy_snapshot from public.account_data_retention_policies p where p.active=true;
  insert into public.account_deletion_execution_jobs(request_id,user_id,subject_ref,status,policy_snapshot)
  values(p_request_id,v_request.user_id,v_request.subject_ref,'queued',v_policy_snapshot)
  on conflict(request_id) do update set status='queued',error_code=null,lease_token=null,
    lease_owner=null,lease_expires_at=null,policy_snapshot=excluded.policy_snapshot,updated_at=clock_timestamp()
  returning * into v_job;
  delete from public.account_deletion_execution_steps where job_id=v_job.id;
  insert into public.account_deletion_execution_steps(job_id,step_kind,step_key,action,data_class,dependency_order)
  select v_job.id,'source',p.source_key,p.deletion_action,p.data_class,p.dependency_order
  from public.account_deletion_source_policies p join private.account_export_sources s
    on s.source_key=p.source_key and s.enabled=true where p.active=true;
  insert into public.account_deletion_execution_steps(job_id,step_kind,step_key,action,dependency_order)
  select v_job.id,'foreign_key',r.id::text,r.resolution_action,
    10000-row_number() over(order by r.child_schema,r.child_table,r.constraint_name)
  from public.account_deletion_dependency_rules r where r.active=true;

  insert into public.account_deletion_storage_jobs(execution_job_id,storage_bucket,storage_path)
  select v_job.id,'agent-knowledge',s.storage_path from public.agent_knowledge_sources s
  where s.owner_id=v_request.user_id and s.storage_path<>'' and left(s.storage_path,1)<>'/'
    and position('..' in s.storage_path)=0 on conflict do nothing;
  insert into public.account_deletion_storage_jobs(execution_job_id,storage_bucket,storage_path)
  select v_job.id,m.bucket_id,m.storage_path from public.content_media m
  where m.owner_id=v_request.user_id and m.storage_path<>'' and left(m.storage_path,1)<>'/'
    and position('..' in m.storage_path)=0 on conflict do nothing;
  insert into public.account_deletion_storage_jobs(execution_job_id,storage_bucket,storage_path)
  select v_job.id,m.bucket_id,d.value->>'storage_path' from public.content_media m
  cross join lateral jsonb_array_elements(case when jsonb_typeof(m.derivatives)='array' then m.derivatives else '[]'::jsonb end) d(value)
  where m.owner_id=v_request.user_id and jsonb_typeof(d.value)='object'
    and coalesce(d.value->>'storage_path','')<>'' and left(d.value->>'storage_path',1)<>'/'
    and position('..' in d.value->>'storage_path')=0 on conflict do nothing;
  insert into public.account_deletion_storage_jobs(execution_job_id,storage_bucket,storage_path)
  select v_job.id,a.storage_bucket,a.storage_path from public.generation_artifacts a
  where a.owner_user_id=v_request.user_id and a.storage_path<>'' and left(a.storage_path,1)<>'/'
    and position('..' in a.storage_path)=0 on conflict do nothing;
  insert into public.account_deletion_storage_jobs(execution_job_id,storage_bucket,storage_path)
  select v_job.id,j.storage_bucket,j.storage_path from public.account_export_jobs j
  where j.user_id=v_request.user_id and j.status='succeeded' and j.storage_path is not null
    and j.storage_bucket='account-exports' and j.storage_path<>'' and left(j.storage_path,1)<>'/'
    and position('..' in j.storage_path)=0 on conflict do nothing;
  update public.account_deletion_storage_jobs set status='pending',lease_token=null,lease_expires_at=null,error_code=null
    where execution_job_id=v_job.id and status='failed';

  update public.account_deletion_requests set status='processing',error_code=null,
    policy_version='account-deletion-v1',
    request_metadata=coalesce(request_metadata,'{}'::jsonb)||jsonb_build_object(
      'execution_job_id',v_job.id,'policy_snapshot',v_policy_snapshot,
      'storage_cleanup_queued',true,'prepared_at',clock_timestamp()),updated_at=clock_timestamp()
  where id=p_request_id;
  insert into public.account_lifecycle_events(request_id,user_id,subject_ref,event_type,metadata)
  values(p_request_id,v_request.user_id,v_request.subject_ref,'deletion_started',
    jsonb_build_object('execution_job_id',v_job.id,'policy_snapshot',v_policy_snapshot));
  return jsonb_build_object('outcome','queued','job_id',v_job.id);
end;
$fn$;

create or replace function public.prepare_account_deletion_execution_batch(p_limit integer default 20)
returns table(processed_count integer,queued_count integer,blocked_count integer)
language plpgsql security definer set search_path=''
as $fn$
declare v_id uuid; v_result jsonb; v_processed integer:=0; v_queued integer:=0; v_blocked integer:=0;
begin
  if coalesce(auth.role(),'')<>'service_role' then raise exception 'service_role_required' using errcode='42501'; end if;
  if p_limit is null or p_limit not between 1 and 100 then raise exception 'invalid_deletion_prepare_limit' using errcode='22023'; end if;
  for v_id in select id from public.account_deletion_requests
    where status in ('awaiting_policy','blocked_dependency')
    order by requested_at,id limit p_limit for update skip locked
  loop
    v_result:=public.prepare_account_deletion_execution(v_id); v_processed:=v_processed+1;
    if v_result->>'outcome'='queued' then v_queued:=v_queued+1;
    elsif v_result->>'outcome' in ('blocked_dependency','blocked_legal_hold') then v_blocked:=v_blocked+1; end if;
  end loop;
  return query select v_processed,v_queued,v_blocked;
end;
$fn$;

create or replace function public.claim_account_deletion_execution_jobs(
  p_worker_id text,p_limit integer default 2,p_lease_seconds integer default 300
) returns setof public.account_deletion_execution_jobs
language plpgsql security definer set search_path=''
as $fn$
begin
  if coalesce(auth.role(),'')<>'service_role' then raise exception 'service_role_required' using errcode='42501'; end if;
  if p_worker_id is null or char_length(p_worker_id) not between 1 and 120
     or p_limit is null or p_limit not between 1 and 20
     or p_lease_seconds is null or p_lease_seconds not between 30 and 3600 then
    raise exception 'invalid_account_deletion_claim_bounds' using errcode='22023';
  end if;
  return query with picked as (
    select j.id from public.account_deletion_execution_jobs j
    where (j.status='queued' and j.next_attempt_at<=clock_timestamp())
       or (j.status='running' and j.lease_expires_at<=clock_timestamp())
    order by j.created_at,j.id limit p_limit for update skip locked
  )
  update public.account_deletion_execution_jobs j set status='running',attempts=j.attempts+1,
    lease_token=gen_random_uuid(),lease_owner=p_worker_id,
    lease_expires_at=clock_timestamp()+make_interval(secs=>p_lease_seconds),
    started_at=coalesce(j.started_at,clock_timestamp()),updated_at=clock_timestamp()
  from picked where j.id=picked.id returning j.*;
end;
$fn$;

create or replace function public.claim_account_deletion_storage_jobs(
  p_execution_job_id uuid,p_job_lease_token uuid,p_limit integer default 50,p_lease_seconds integer default 300
) returns table(id uuid,storage_bucket text,storage_path text,lease_token uuid,attempts integer)
language plpgsql security definer set search_path=''
as $fn$
declare v_job public.account_deletion_execution_jobs%rowtype;
begin
  if coalesce(auth.role(),'')<>'service_role' then raise exception 'service_role_required' using errcode='42501'; end if;
  select * into v_job from public.account_deletion_execution_jobs
   where id=p_execution_job_id and status='running' and lease_token=p_job_lease_token
     and lease_expires_at>clock_timestamp() for update;
  if not found then raise exception 'account_deletion_execution_lease_lost' using errcode='40001'; end if;
  if exists(select 1 from public.account_legal_holds h where h.subject_ref=v_job.subject_ref and h.active) then
    update public.account_deletion_execution_jobs set status='blocked',error_code='LEGAL_HOLD_ACTIVE',
      lease_token=null,lease_owner=null,lease_expires_at=null,updated_at=clock_timestamp() where id=v_job.id;
    update public.account_deletion_requests set status='blocked_legal_hold',error_code='LEGAL_HOLD_ACTIVE',
      updated_at=clock_timestamp() where id=v_job.request_id;
    return;
  end if;
  return query with picked as (
    select s.id from public.account_deletion_storage_jobs s
    where s.execution_job_id=p_execution_job_id
      and (s.status='pending' or (s.status='running' and s.lease_expires_at<=clock_timestamp()) or (s.status='failed' and s.attempts<12))
    order by s.created_at,s.id limit p_limit for update skip locked
  )
  update public.account_deletion_storage_jobs s set status='running',attempts=s.attempts+1,
    lease_token=gen_random_uuid(),lease_expires_at=clock_timestamp()+make_interval(secs=>p_lease_seconds),
    updated_at=clock_timestamp()
  from picked where s.id=picked.id returning s.id,s.storage_bucket,s.storage_path,s.lease_token,s.attempts;
end;
$fn$;

create or replace function public.complete_account_deletion_storage_job(p_job_id uuid,p_lease_token uuid)
returns boolean language plpgsql security definer set search_path=''
as $fn$
begin
  if coalesce(auth.role(),'')<>'service_role' then raise exception 'service_role_required' using errcode='42501'; end if;
  update public.account_deletion_storage_jobs set status='completed',completed_at=clock_timestamp(),
    lease_token=null,lease_expires_at=null,error_code=null,updated_at=clock_timestamp()
  where id=p_job_id and status='running' and lease_token=p_lease_token and lease_expires_at>clock_timestamp();
  return found;
end;
$fn$;

create or replace function public.fail_account_deletion_storage_job(
  p_job_id uuid,p_lease_token uuid,p_error_code text,p_retry_seconds integer default 300
) returns boolean language plpgsql security definer set search_path=''
as $fn$
begin
  if coalesce(auth.role(),'')<>'service_role' then raise exception 'service_role_required' using errcode='42501'; end if;
  update public.account_deletion_storage_jobs set status=case when attempts>=8 then 'failed' else 'pending' end,
    error_code=left(coalesce(p_error_code,'STORAGE_DELETE_FAILED'),80),
    lease_token=null,lease_expires_at=null,updated_at=clock_timestamp()
  where id=p_job_id and status='running' and lease_token=p_lease_token;
  return found;
end;
$fn$;

create or replace function public.execute_account_deletion_execution_job(p_job_id uuid,p_lease_token uuid)
returns boolean language plpgsql security definer set search_path=''
as $fn$
declare v_job public.account_deletion_execution_jobs%rowtype;
        v_request public.account_deletion_requests%rowtype;
        v_step public.account_deletion_execution_steps%rowtype;
        v_source private.account_export_sources%rowtype;
        v_policy public.account_deletion_source_policies%rowtype;
        v_rule public.account_deletion_dependency_rules%rowtype;
        v_column text; v_predicate text; v_sql text; v_rows bigint;
        v_missing_classes integer; v_blocked_fks integer; v_missing_sources integer; v_missing_fk_steps integer;
begin
  if coalesce(auth.role(),'')<>'service_role' then raise exception 'service_role_required' using errcode='42501'; end if;
  select * into v_job from public.account_deletion_execution_jobs
   where id=p_job_id and status='running' and lease_token=p_lease_token
     and lease_expires_at>clock_timestamp() for update;
  if not found then raise exception 'account_deletion_execution_lease_lost' using errcode='40001'; end if;
  select * into v_request from public.account_deletion_requests where id=v_job.request_id for update;
  if not found or v_request.user_id is distinct from v_job.user_id then
    raise exception 'account_deletion_request_subject_mismatch' using errcode='23514';
  end if;
  perform pg_advisory_xact_lock(hashtextextended(v_job.subject_ref,0));
  if exists(select 1 from public.account_legal_holds h where h.subject_ref=v_job.subject_ref and h.active) then
    update public.account_deletion_execution_jobs set status='blocked',error_code='LEGAL_HOLD_ACTIVE',
      lease_token=null,lease_owner=null,lease_expires_at=null,updated_at=clock_timestamp() where id=v_job.id;
    update public.account_deletion_requests set status='blocked_legal_hold',error_code='LEGAL_HOLD_ACTIVE',
      updated_at=clock_timestamp() where id=v_request.id;
    return false;
  end if;
  if exists(select 1 from public.account_deletion_storage_jobs s
            where s.execution_job_id=v_job.id and s.status<>'completed') then
    raise exception 'account_deletion_storage_cleanup_incomplete' using errcode='55000';
  end if;
  select count(*) into v_missing_classes from (values
    ('owner_private'),('agent_operational'),('tenant_shared'),
    ('published_knowledge'),('session_scoped'),('public_catalog')
  ) required(data_class)
  where not exists(select 1 from public.account_data_retention_policies p
    where p.data_class=required.data_class and p.active=true
      and p.policy_version=v_job.policy_snapshot->>required.data_class);
  select count(*) into v_blocked_fks from public.account_deletion_dependency_rules r
    where r.active=true and r.resolution_action='block';
  select count(*) into v_missing_sources from private.account_export_sources s
    left join public.account_deletion_source_policies p on p.source_key=s.source_key and p.active=true
    where s.enabled=true and (p.source_key is null or p.data_class is null
      or p.deletion_action is null or p.deletion_action='block');
  select count(*) into v_missing_fk_steps from public.account_deletion_dependency_rules r
    where r.active=true and r.resolution_action not in ('database_cascade','database_set_null')
      and not exists(select 1 from public.account_deletion_execution_steps st
        where st.job_id=v_job.id and st.step_kind='foreign_key' and st.step_key=r.id::text);
  if v_missing_classes>0 or v_blocked_fks>0 or v_missing_sources>0 or v_missing_fk_steps>0 then
    update public.account_deletion_execution_jobs set status='blocked',error_code='DELETION_POLICY_CHANGED',
      lease_token=null,lease_owner=null,lease_expires_at=null,updated_at=clock_timestamp() where id=v_job.id;
    update public.account_deletion_requests set status='blocked_dependency',error_code='DELETION_POLICY_CHANGED',
      updated_at=clock_timestamp() where id=v_request.id;
    return false;
  end if;
  for v_step in select * from public.account_deletion_execution_steps
    where job_id=v_job.id and status='pending'
    order by dependency_order desc,step_kind desc,step_key for update
  loop
    v_rows:=0;
    if v_step.step_kind='source' then
      select * into v_policy from public.account_deletion_source_policies
       where source_key=v_step.step_key and active=true;
      if not found or v_policy.deletion_action is distinct from v_step.action
         or v_policy.data_class is distinct from v_step.data_class then
        raise exception 'account_deletion_source_policy_changed:%',v_step.step_key using errcode='40001';
      end if;
      if v_step.action='preserve' then
        v_rows:=0;
      elsif v_step.action='delete_rows' then
        select * into v_source from private.account_export_sources
         where source_key=v_step.step_key and enabled=true;
        if not found or v_source.filter_kind<>'owner_columns' or cardinality(v_source.owner_columns)=0 then
          raise exception 'account_deletion_source_handler_missing:%',v_step.step_key using errcode='0A000';
        end if;
        v_predicate:='';
        foreach v_column in array v_source.owner_columns loop
          if not exists(select 1 from information_schema.columns c
            where c.table_schema='public' and c.table_name=v_source.table_name and c.column_name=v_column) then
            raise exception 'account_deletion_source_column_missing:%.%',v_source.table_name,v_column;
          end if;
          if v_predicate<>'' then v_predicate:=v_predicate||' OR '; end if;
          v_predicate:=v_predicate||format('%I::text = $1',v_column);
        end loop;
        v_sql:=format('DELETE FROM public.%I WHERE %s',v_source.table_name,v_predicate);
        execute v_sql using v_job.user_id::text;
        get diagnostics v_rows=row_count;
      else
        raise exception 'account_deletion_source_action_unsupported:%',v_step.action using errcode='0A000';
      end if;
    elsif v_step.step_kind='foreign_key' then
      select * into v_rule from public.account_deletion_dependency_rules
       where id::text=v_step.step_key and active=true;
      if not found or v_rule.resolution_action is distinct from v_step.action then
        raise exception 'account_deletion_dependency_rule_changed:%',v_step.step_key using errcode='40001';
      end if;
      if v_step.action in ('database_cascade','database_set_null') then
        v_rows:=0;
      elsif v_step.action in ('delete_rows','set_null') then
        if v_rule.fk_column is null then raise exception 'composite_foreign_key_requires_manual_handler'; end if;
        if v_step.action='delete_rows' then
          v_sql:=format('DELETE FROM %I.%I WHERE %I::text = $1',v_rule.child_schema,v_rule.child_table,v_rule.fk_column);
        else
          v_sql:=format('UPDATE %I.%I SET %I=NULL WHERE %I::text = $1',
            v_rule.child_schema,v_rule.child_table,v_rule.fk_column,v_rule.fk_column);
        end if;
        execute v_sql using v_job.user_id::text;
        get diagnostics v_rows=row_count;
      else
        raise exception 'account_deletion_dependency_unresolved:%',v_rule.constraint_name using errcode='55000';
      end if;
    else
      raise exception 'account_deletion_step_kind_invalid';
    end if;
    update public.account_deletion_execution_steps set status='completed',
      affected_rows=v_rows,completed_at=clock_timestamp() where id=v_step.id;
  end loop;
  if exists(select 1 from public.account_deletion_execution_steps where job_id=v_job.id and status<>'completed') then
    raise exception 'account_deletion_steps_incomplete' using errcode='55000';
  end if;
  if exists(select 1 from public.account_legal_holds h where h.subject_ref=v_job.subject_ref and h.active) then
    update public.account_deletion_execution_jobs set status='blocked',error_code='LEGAL_HOLD_ACTIVE',
      lease_token=null,lease_owner=null,lease_expires_at=null,updated_at=clock_timestamp() where id=v_job.id;
    update public.account_deletion_requests set status='blocked_legal_hold',error_code='LEGAL_HOLD_ACTIVE',
      updated_at=clock_timestamp() where id=v_request.id;
    return false;
  end if;
  delete from auth.users where id=v_job.user_id;
  if not found then raise exception 'account_deletion_auth_subject_missing' using errcode='P0002'; end if;
  update public.account_deletion_requests set status='completed',user_id=null,completed_at=clock_timestamp(),
    error_code=null,request_metadata=coalesce(request_metadata,'{}'::jsonb)||
      jsonb_build_object('execution_job_id',v_job.id,'completed_at',clock_timestamp()),
    updated_at=clock_timestamp() where id=v_request.id;
  insert into public.account_lifecycle_events(request_id,subject_ref,event_type,metadata)
  values(v_request.id,v_job.subject_ref,'deletion_completed',
    jsonb_build_object('execution_job_id',v_job.id,'steps_completed',
      (select count(*) from public.account_deletion_execution_steps where job_id=v_job.id)));
  update public.account_deletion_execution_jobs set status='completed',completed_at=clock_timestamp(),
    lease_token=null,lease_owner=null,lease_expires_at=null,error_code=null,updated_at=clock_timestamp()
  where id=v_job.id;
  return true;
end;
$fn$;

create or replace function public.fail_account_deletion_execution_job(
  p_job_id uuid,p_lease_token uuid,p_error_code text,p_retry_seconds integer default 300
) returns boolean language plpgsql security definer set search_path=''
as $fn$
declare v_job public.account_deletion_execution_jobs%rowtype;
begin
  if coalesce(auth.role(),'')<>'service_role' then raise exception 'service_role_required' using errcode='42501'; end if;
  update public.account_deletion_execution_jobs set
    status=case when attempts>=max_attempts then 'failed' else 'queued' end,
    next_attempt_at=clock_timestamp()+make_interval(secs=>greatest(1,least(coalesce(p_retry_seconds,300),86400))),
    error_code=left(coalesce(p_error_code,'ACCOUNT_DELETION_FAILED'),80),
    lease_token=null,lease_owner=null,lease_expires_at=null,updated_at=clock_timestamp()
  where id=p_job_id and status='running' and lease_token=p_lease_token returning * into v_job;
  if not found then return false; end if;
  if v_job.status='failed' then
    update public.account_deletion_requests set status='failed',error_code=v_job.error_code,updated_at=clock_timestamp()
      where id=v_job.request_id;
    insert into public.account_lifecycle_events(request_id,subject_ref,event_type,metadata)
    values(v_job.request_id,v_job.subject_ref,'deletion_failed',jsonb_build_object('error_code',v_job.error_code));
  end if;
  return true;
end;
$fn$;

create or replace function public.cancel_my_account_deletion(p_request_id uuid)
returns boolean language plpgsql security definer set search_path=''
as $fn$
declare v_request public.account_deletion_requests%rowtype;
begin
  if auth.uid() is null then raise exception 'authenticated_user_required' using errcode='42501'; end if;
  update public.account_deletion_requests set status='cancelled',cancelled_at=clock_timestamp(),
    updated_at=clock_timestamp(),error_code=null
  where id=p_request_id and user_id=auth.uid()
    and status in ('awaiting_policy','blocked_dependency','blocked_legal_hold')
  returning * into v_request;
  if not found then return false; end if;
  update public.profiles set account_status='active',updated_at=clock_timestamp()
   where id=auth.uid() and account_status='deactivation_requested';
  insert into public.account_lifecycle_events(request_id,user_id,subject_ref,event_type,metadata)
  values(v_request.id,auth.uid(),v_request.subject_ref,'deletion_cancelled','{}'::jsonb);
  return true;
end;
$fn$;

create or replace function private.lock_account_legal_hold_subject()
returns trigger language plpgsql security definer set search_path=''
as $fn$
begin
  perform pg_advisory_xact_lock(hashtextextended(new.subject_ref,0));
  return new;
end;
$fn$;
drop trigger if exists account_legal_hold_subject_lock on public.account_legal_holds;
create trigger account_legal_hold_subject_lock before insert or update on public.account_legal_holds
for each row execute function private.lock_account_legal_hold_subject();

revoke all on function public.set_account_deletion_source_policy(text,text,text,text,text,uuid) from public,anon,authenticated;
revoke all on function public.set_account_deletion_dependency_rule(uuid,text,text,uuid) from public,anon,authenticated;
revoke all on function public.prepare_account_deletion_execution(uuid) from public,anon,authenticated;
revoke all on function public.prepare_account_deletion_execution_batch(integer) from public,anon,authenticated;
revoke all on function public.claim_account_deletion_execution_jobs(text,integer,integer) from public,anon,authenticated;
revoke all on function public.claim_account_deletion_storage_jobs(uuid,uuid,integer,integer) from public,anon,authenticated;
revoke all on function public.complete_account_deletion_storage_job(uuid,uuid) from public,anon,authenticated;
revoke all on function public.fail_account_deletion_storage_job(uuid,uuid,text,integer) from public,anon,authenticated;
revoke all on function public.execute_account_deletion_execution_job(uuid,uuid) from public,anon,authenticated;
revoke all on function public.fail_account_deletion_execution_job(uuid,uuid,text,integer) from public,anon,authenticated;
revoke all on function public.cancel_my_account_deletion(uuid) from public,anon;
grant execute on function public.set_account_deletion_source_policy(text,text,text,text,text,uuid) to service_role;
grant execute on function public.set_account_deletion_dependency_rule(uuid,text,text,uuid) to service_role;
grant execute on function public.prepare_account_deletion_execution(uuid) to service_role;
grant execute on function public.prepare_account_deletion_execution_batch(integer) to service_role;
grant execute on function public.claim_account_deletion_execution_jobs(text,integer,integer) to service_role;
grant execute on function public.claim_account_deletion_storage_jobs(uuid,uuid,integer,integer) to service_role;
grant execute on function public.complete_account_deletion_storage_job(uuid,uuid) to service_role;
grant execute on function public.fail_account_deletion_storage_job(uuid,uuid,text,integer) to service_role;
grant execute on function public.execute_account_deletion_execution_job(uuid,uuid) to service_role;
grant execute on function public.fail_account_deletion_execution_job(uuid,uuid,text,integer) to service_role;
grant execute on function public.cancel_my_account_deletion(uuid) to authenticated;
commit;
;

-- track statements in history table
insert into supabase_migrations.schema_migrations as old
  (version, name, statements, created_by, idempotency_key, rollback)
values (
  to_char(current_timestamp, 'YYYYMMDDHH24MISS'),
  $YtSNdGXGUCkhfeJqYXQw$eng_p03_account_deletion_executor$YtSNdGXGUCkhfeJqYXQw$,
  array[$YtSNdGXGUCkhfeJqYXQw$-- ENG-P03: executable, lease-fenced account deletion with explicit data-class
-- and FK dependency policy. No retention values or destructive mappings are seeded.
begin;

alter table public.account_deletion_requests
  drop constraint if exists account_deletion_requests_status_check;
alter table public.account_deletion_requests
  add constraint account_deletion_requests_status_check
  check (status = any (array[
    'awaiting_policy','scheduled','processing','blocked_legal_hold',
    'blocked_dependency','completed','cancelled','failed'
  ]::text[]));
drop index if exists public.account_deletion_one_open_request_per_user;
create unique index account_deletion_one_open_request_per_user
  on public.account_deletion_requests(user_id)
  where user_id is not null and status in
    ('awaiting_policy','scheduled','processing','blocked_legal_hold','blocked_dependency');

alter table public.account_lifecycle_events
  drop constraint if exists account_lifecycle_events_event_type_check;
alter table public.account_lifecycle_events
  add constraint account_lifecycle_events_event_type_check
  check (event_type = any (array[
    'export_requested','export_started','export_completed','export_failed',
    'deletion_requested','deletion_cancelled','deletion_scheduled','deletion_started',
    'deletion_blocked','deletion_unblocked','deletion_policy_pending',
    'deletion_completed','deletion_failed'
  ]::text[]));

create table if not exists public.account_deletion_source_policies (
  source_key text primary key references private.account_export_sources(source_key) on delete cascade,
  data_class text check (data_class in (
    'owner_private','agent_operational','tenant_shared',
    'published_knowledge','session_scoped','public_catalog'
  )),
  deletion_action text check (deletion_action in ('delete_rows','preserve','block')),
  dependency_order integer not null default 100,
  policy_version text,
  reason text,
  approved_by uuid,
  approved_at timestamptz,
  active boolean not null default false,
  updated_at timestamptz not null default now(),
  check (
    (active = false) or
    (data_class is not null and deletion_action is not null
     and policy_version is not null and approved_by is not null
     and approved_at is not null and reason is not null)
  )
);
insert into public.account_deletion_source_policies(source_key,dependency_order)
select source_key,sort_order from private.account_export_sources where enabled
on conflict (source_key) do nothing;

create table if not exists public.account_deletion_dependency_rules (
  id uuid primary key default gen_random_uuid(),
  child_schema text not null,
  child_table text not null,
  constraint_name text not null,
  fk_column text,
  delete_rule text not null check (delete_rule in ('CASCADE','SET NULL','RESTRICT','NO ACTION','SET DEFAULT')),
  resolution_action text not null check (resolution_action in (
    'database_cascade','database_set_null','delete_rows','set_null','block'
  )),
  reason text,
  approved_by uuid,
  approved_at timestamptz,
  active boolean not null default true,
  updated_at timestamptz not null default now(),
  unique(child_schema,child_table,constraint_name)
);
insert into public.account_deletion_dependency_rules(
  child_schema,child_table,constraint_name,fk_column,delete_rule,resolution_action
)
select child_ns.nspname,child.relname,con.conname,
  case when cardinality(con.conkey)=1 then child_att.attname else null end,
  case con.confdeltype when 'c' then 'CASCADE' when 'n' then 'SET NULL'
    when 'r' then 'RESTRICT' when 'a' then 'NO ACTION' when 'd' then 'SET DEFAULT' end,
  case con.confdeltype when 'c' then 'database_cascade' when 'n' then 'database_set_null' else 'block' end
from pg_constraint con
join pg_class child on child.oid=con.conrelid
join pg_namespace child_ns on child_ns.oid=child.relnamespace
join pg_class parent on parent.oid=con.confrelid
join pg_namespace parent_ns on parent_ns.oid=parent.relnamespace
left join lateral (
  select a.attname from unnest(con.conkey) with ordinality k(attnum,ord)
  join pg_attribute a on a.attrelid=child.oid and a.attnum=k.attnum
  order by k.ord limit 1
) child_att on true
where con.contype='f' and parent_ns.nspname='auth' and parent.relname='users'
  and child_ns.nspname in ('public','private')
on conflict (child_schema,child_table,constraint_name) do nothing;

create table if not exists public.account_deletion_execution_jobs (
  id uuid primary key default gen_random_uuid(),
  request_id uuid not null unique references public.account_deletion_requests(id) on delete restrict,
  user_id uuid not null,
  subject_ref text not null,
  status text not null default 'queued'
    check (status in ('queued','running','blocked','failed','completed')),
  attempts integer not null default 0 check (attempts >= 0),
  max_attempts integer not null default 8 check (max_attempts between 1 and 20),
  next_attempt_at timestamptz not null default now(),
  lease_token uuid, lease_owner text, lease_expires_at timestamptz,
  policy_snapshot jsonb not null default '{}'::jsonb,
  error_code text, started_at timestamptz, completed_at timestamptz,
  created_at timestamptz not null default now(), updated_at timestamptz not null default now()
);
create index if not exists account_deletion_execution_claim_idx
  on public.account_deletion_execution_jobs(status,next_attempt_at,created_at)
  where status in ('queued','running');

create table if not exists public.account_deletion_execution_steps (
  id uuid primary key default gen_random_uuid(),
  job_id uuid not null references public.account_deletion_execution_jobs(id) on delete cascade,
  step_kind text not null check (step_kind in ('source','foreign_key')),
  step_key text not null, action text not null, data_class text,
  dependency_order integer not null default 100,
  status text not null default 'pending' check (status in ('pending','completed','blocked','failed')),
  affected_rows bigint not null default 0 check (affected_rows >= 0),
  error_code text, started_at timestamptz, completed_at timestamptz,
  unique(job_id,step_kind,step_key)
);
create index if not exists account_deletion_steps_pending_idx
  on public.account_deletion_execution_steps(job_id,status,dependency_order desc);

create table if not exists public.account_deletion_storage_jobs (
  id uuid primary key default gen_random_uuid(),
  execution_job_id uuid not null references public.account_deletion_execution_jobs(id) on delete cascade,
  storage_bucket text not null, storage_path text not null,
  status text not null default 'pending' check (status in ('pending','running','completed','failed')),
  attempts integer not null default 0 check (attempts >= 0),
  lease_token uuid, lease_expires_at timestamptz, error_code text,
  completed_at timestamptz, created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(execution_job_id,storage_bucket,storage_path),
  check (storage_bucket ~ '^[a-z0-9][a-z0-9._-]{1,62}$'),
  check (storage_path <> '' and left(storage_path,1) <> '/' and position('..' in storage_path)=0)
);
create index if not exists account_deletion_storage_claim_idx
  on public.account_deletion_storage_jobs(execution_job_id,status,created_at)
  where status in ('pending','running');

alter table public.account_deletion_source_policies enable row level security;
alter table public.account_deletion_dependency_rules enable row level security;
alter table public.account_deletion_execution_jobs enable row level security;
alter table public.account_deletion_execution_steps enable row level security;
alter table public.account_deletion_storage_jobs enable row level security;
revoke all on public.account_deletion_source_policies,public.account_deletion_dependency_rules,
  public.account_deletion_execution_jobs,public.account_deletion_execution_steps,
  public.account_deletion_storage_jobs from public,anon,authenticated;
grant select,insert,update,delete on public.account_deletion_source_policies,
  public.account_deletion_dependency_rules,public.account_deletion_execution_jobs,
  public.account_deletion_execution_steps,public.account_deletion_storage_jobs to service_role;

create or replace function public.set_account_deletion_source_policy(
  p_source_key text,p_data_class text,p_deletion_action text,
  p_policy_version text,p_reason text,p_actor_user_id uuid
) returns public.account_deletion_source_policies
language plpgsql security definer set search_path=''
as $fn$
declare v_source private.account_export_sources%rowtype; v_policy public.account_deletion_source_policies%rowtype;
begin
  if coalesce(auth.role(),'')<>'service_role' then raise exception 'service_role_required' using errcode='42501'; end if;
  if p_actor_user_id is null or not exists (
    select 1 from public.platform_operator_grants g where g.user_id=p_actor_user_id
      and g.status='active' and 'platform:account_lifecycle.manage'=any(g.scopes)
      and (g.expires_at is null or g.expires_at>clock_timestamp())
  ) then raise exception 'account_lifecycle_operator_scope_required' using errcode='42501'; end if;
  if p_data_class not in ('owner_private','agent_operational','tenant_shared','published_knowledge','session_scoped','public_catalog')
     or p_deletion_action not in ('delete_rows','preserve','block')
     or p_policy_version is null or char_length(p_policy_version) not between 1 and 40
     or p_reason is null or char_length(p_reason) not between 8 and 500 then
    raise exception 'account_deletion_source_policy_invalid' using errcode='22023';
  end if;
  select * into v_source from private.account_export_sources where source_key=p_source_key and enabled=true;
  if not found then raise exception 'account_deletion_source_not_found' using errcode='P0002'; end if;
  if p_deletion_action='delete_rows' and
     (v_source.filter_kind<>'owner_columns' or cardinality(v_source.owner_columns)=0) then
    raise exception 'account_deletion_source_requires_explicit_handler' using errcode='22023';
  end if;
  insert into public.account_deletion_source_policies(
    source_key,data_class,deletion_action,dependency_order,policy_version,reason,approved_by,approved_at,active,updated_at
  ) values(p_source_key,p_data_class,p_deletion_action,v_source.sort_order,p_policy_version,
    p_reason,p_actor_user_id,clock_timestamp(),true,clock_timestamp())
  on conflict(source_key) do update set data_class=excluded.data_class,
    deletion_action=excluded.deletion_action,dependency_order=excluded.dependency_order,
    policy_version=excluded.policy_version,reason=excluded.reason,approved_by=excluded.approved_by,
    approved_at=excluded.approved_at,active=true,updated_at=clock_timestamp()
  returning * into v_policy;
  return v_policy;
end;
$fn$;

create or replace function public.set_account_deletion_dependency_rule(
  p_rule_id uuid,p_resolution_action text,p_reason text,p_actor_user_id uuid
) returns public.account_deletion_dependency_rules
language plpgsql security definer set search_path=''
as $fn$
declare v_rule public.account_deletion_dependency_rules%rowtype; v_nullable boolean;
begin
  if coalesce(auth.role(),'')<>'service_role' then raise exception 'service_role_required' using errcode='42501'; end if;
  if p_actor_user_id is null or not exists (
    select 1 from public.platform_operator_grants g where g.user_id=p_actor_user_id
      and g.status='active' and 'platform:account_lifecycle.manage'=any(g.scopes)
      and (g.expires_at is null or g.expires_at>clock_timestamp())
  ) then raise exception 'account_lifecycle_operator_scope_required' using errcode='42501'; end if;
  if p_resolution_action not in ('delete_rows','set_null','block')
     or p_reason is null or char_length(p_reason) not between 8 and 500 then
    raise exception 'account_deletion_dependency_rule_invalid' using errcode='22023';
  end if;
  select * into v_rule from public.account_deletion_dependency_rules where id=p_rule_id for update;
  if not found then raise exception 'account_deletion_dependency_rule_not_found' using errcode='P0002'; end if;
  if v_rule.fk_column is null then raise exception 'composite_foreign_key_requires_manual_handler' using errcode='22023'; end if;
  if p_resolution_action='set_null' then
    select c.is_nullable='YES' into v_nullable from information_schema.columns c
    where c.table_schema=v_rule.child_schema and c.table_name=v_rule.child_table and c.column_name=v_rule.fk_column;
    if coalesce(v_nullable,false)=false then raise exception 'foreign_key_column_not_nullable' using errcode='22023'; end if;
  end if;
  update public.account_deletion_dependency_rules set resolution_action=p_resolution_action,
    reason=p_reason,approved_by=p_actor_user_id,approved_at=clock_timestamp(),updated_at=clock_timestamp(),active=true
  where id=p_rule_id returning * into v_rule;
  return v_rule;
end;
$fn$;

create or replace function public.prepare_account_deletion_execution(p_request_id uuid)
returns jsonb language plpgsql security definer set search_path=''
as $fn$
declare v_request public.account_deletion_requests%rowtype; v_job public.account_deletion_execution_jobs%rowtype;
        v_missing_classes text[]; v_missing_sources integer; v_blocked_fks integer; v_policy_snapshot jsonb;
begin
  if coalesce(auth.role(),'')<>'service_role' then raise exception 'service_role_required' using errcode='42501'; end if;
  select * into v_request from public.account_deletion_requests where id=p_request_id for update;
  if not found then return jsonb_build_object('outcome','not_found'); end if;
  if v_request.status not in ('awaiting_policy','blocked_dependency') then
    select * into v_job from public.account_deletion_execution_jobs where request_id=p_request_id;
    return jsonb_build_object('outcome','already_processed','job_id',v_job.id);
  end if;
  perform pg_advisory_xact_lock(hashtextextended(v_request.subject_ref,0));
  if exists(select 1 from public.account_legal_holds h where h.subject_ref=v_request.subject_ref and h.active) then
    update public.account_deletion_requests set status='blocked_legal_hold',scheduled_for=null,
      error_code='LEGAL_HOLD_ACTIVE',updated_at=clock_timestamp() where id=p_request_id;
    insert into public.account_lifecycle_events(request_id,subject_ref,event_type,metadata)
    values(p_request_id,v_request.subject_ref,'deletion_blocked',jsonb_build_object('reason_code','LEGAL_HOLD_ACTIVE'));
    return jsonb_build_object('outcome','blocked_legal_hold');
  end if;
  select array_agg(required.data_class order by required.data_class) into v_missing_classes
  from (values ('owner_private'),('agent_operational'),('tenant_shared'),
    ('published_knowledge'),('session_scoped'),('public_catalog')) required(data_class)
  where not exists(select 1 from public.account_data_retention_policies p
    where p.data_class=required.data_class and p.active=true);
  select count(*) into v_missing_sources from private.account_export_sources s
  left join public.account_deletion_source_policies p on p.source_key=s.source_key and p.active=true
  where s.enabled=true and (p.source_key is null or p.data_class is null
    or p.deletion_action is null or p.deletion_action='block');
  select count(*) into v_blocked_fks from public.account_deletion_dependency_rules r
    where r.active=true and r.resolution_action='block';
  if coalesce(cardinality(v_missing_classes),0)>0 or v_missing_sources>0 or v_blocked_fks>0 then
    update public.account_deletion_requests set status='blocked_dependency',scheduled_for=null,
      error_code='DELETION_POLICY_OR_DEPENDENCY_MAP_INCOMPLETE',
      request_metadata=coalesce(request_metadata,'{}'::jsonb)||jsonb_build_object(
        'missing_data_classes',coalesce(to_jsonb(v_missing_classes),'[]'::jsonb),
        'unmapped_sources',v_missing_sources,'blocked_foreign_keys',v_blocked_fks,
        'checked_at',clock_timestamp()),updated_at=clock_timestamp() where id=p_request_id;
    return jsonb_build_object('outcome','blocked_dependency',
      'missing_data_classes',coalesce(to_jsonb(v_missing_classes),'[]'::jsonb),
      'unmapped_sources',v_missing_sources,'blocked_foreign_keys',v_blocked_fks);
  end if;
  select coalesce(jsonb_object_agg(p.data_class,p.policy_version),'{}'::jsonb)
    into v_policy_snapshot from public.account_data_retention_policies p where p.active=true;
  insert into public.account_deletion_execution_jobs(request_id,user_id,subject_ref,status,policy_snapshot)
  values(p_request_id,v_request.user_id,v_request.subject_ref,'queued',v_policy_snapshot)
  on conflict(request_id) do update set status='queued',error_code=null,lease_token=null,
    lease_owner=null,lease_expires_at=null,policy_snapshot=excluded.policy_snapshot,updated_at=clock_timestamp()
  returning * into v_job;
  delete from public.account_deletion_execution_steps where job_id=v_job.id;
  insert into public.account_deletion_execution_steps(job_id,step_kind,step_key,action,data_class,dependency_order)
  select v_job.id,'source',p.source_key,p.deletion_action,p.data_class,p.dependency_order
  from public.account_deletion_source_policies p join private.account_export_sources s
    on s.source_key=p.source_key and s.enabled=true where p.active=true;
  insert into public.account_deletion_execution_steps(job_id,step_kind,step_key,action,dependency_order)
  select v_job.id,'foreign_key',r.id::text,r.resolution_action,
    10000-row_number() over(order by r.child_schema,r.child_table,r.constraint_name)
  from public.account_deletion_dependency_rules r where r.active=true;

  insert into public.account_deletion_storage_jobs(execution_job_id,storage_bucket,storage_path)
  select v_job.id,'agent-knowledge',s.storage_path from public.agent_knowledge_sources s
  where s.owner_id=v_request.user_id and s.storage_path<>'' and left(s.storage_path,1)<>'/'
    and position('..' in s.storage_path)=0 on conflict do nothing;
  insert into public.account_deletion_storage_jobs(execution_job_id,storage_bucket,storage_path)
  select v_job.id,m.bucket_id,m.storage_path from public.content_media m
  where m.owner_id=v_request.user_id and m.storage_path<>'' and left(m.storage_path,1)<>'/'
    and position('..' in m.storage_path)=0 on conflict do nothing;
  insert into public.account_deletion_storage_jobs(execution_job_id,storage_bucket,storage_path)
  select v_job.id,m.bucket_id,d.value->>'storage_path' from public.content_media m
  cross join lateral jsonb_array_elements(case when jsonb_typeof(m.derivatives)='array' then m.derivatives else '[]'::jsonb end) d(value)
  where m.owner_id=v_request.user_id and jsonb_typeof(d.value)='object'
    and coalesce(d.value->>'storage_path','')<>'' and left(d.value->>'storage_path',1)<>'/'
    and position('..' in d.value->>'storage_path')=0 on conflict do nothing;
  insert into public.account_deletion_storage_jobs(execution_job_id,storage_bucket,storage_path)
  select v_job.id,a.storage_bucket,a.storage_path from public.generation_artifacts a
  where a.owner_user_id=v_request.user_id and a.storage_path<>'' and left(a.storage_path,1)<>'/'
    and position('..' in a.storage_path)=0 on conflict do nothing;
  insert into public.account_deletion_storage_jobs(execution_job_id,storage_bucket,storage_path)
  select v_job.id,j.storage_bucket,j.storage_path from public.account_export_jobs j
  where j.user_id=v_request.user_id and j.status='succeeded' and j.storage_path is not null
    and j.storage_bucket='account-exports' and j.storage_path<>'' and left(j.storage_path,1)<>'/'
    and position('..' in j.storage_path)=0 on conflict do nothing;
  update public.account_deletion_storage_jobs set status='pending',lease_token=null,lease_expires_at=null,error_code=null
    where execution_job_id=v_job.id and status='failed';

  update public.account_deletion_requests set status='processing',error_code=null,
    policy_version='account-deletion-v1',
    request_metadata=coalesce(request_metadata,'{}'::jsonb)||jsonb_build_object(
      'execution_job_id',v_job.id,'policy_snapshot',v_policy_snapshot,
      'storage_cleanup_queued',true,'prepared_at',clock_timestamp()),updated_at=clock_timestamp()
  where id=p_request_id;
  insert into public.account_lifecycle_events(request_id,user_id,subject_ref,event_type,metadata)
  values(p_request_id,v_request.user_id,v_request.subject_ref,'deletion_started',
    jsonb_build_object('execution_job_id',v_job.id,'policy_snapshot',v_policy_snapshot));
  return jsonb_build_object('outcome','queued','job_id',v_job.id);
end;
$fn$;

create or replace function public.prepare_account_deletion_execution_batch(p_limit integer default 20)
returns table(processed_count integer,queued_count integer,blocked_count integer)
language plpgsql security definer set search_path=''
as $fn$
declare v_id uuid; v_result jsonb; v_processed integer:=0; v_queued integer:=0; v_blocked integer:=0;
begin
  if coalesce(auth.role(),'')<>'service_role' then raise exception 'service_role_required' using errcode='42501'; end if;
  if p_limit is null or p_limit not between 1 and 100 then raise exception 'invalid_deletion_prepare_limit' using errcode='22023'; end if;
  for v_id in select id from public.account_deletion_requests
    where status in ('awaiting_policy','blocked_dependency')
    order by requested_at,id limit p_limit for update skip locked
  loop
    v_result:=public.prepare_account_deletion_execution(v_id); v_processed:=v_processed+1;
    if v_result->>'outcome'='queued' then v_queued:=v_queued+1;
    elsif v_result->>'outcome' in ('blocked_dependency','blocked_legal_hold') then v_blocked:=v_blocked+1; end if;
  end loop;
  return query select v_processed,v_queued,v_blocked;
end;
$fn$;

create or replace function public.claim_account_deletion_execution_jobs(
  p_worker_id text,p_limit integer default 2,p_lease_seconds integer default 300
) returns setof public.account_deletion_execution_jobs
language plpgsql security definer set search_path=''
as $fn$
begin
  if coalesce(auth.role(),'')<>'service_role' then raise exception 'service_role_required' using errcode='42501'; end if;
  if p_worker_id is null or char_length(p_worker_id) not between 1 and 120
     or p_limit is null or p_limit not between 1 and 20
     or p_lease_seconds is null or p_lease_seconds not between 30 and 3600 then
    raise exception 'invalid_account_deletion_claim_bounds' using errcode='22023';
  end if;
  return query with picked as (
    select j.id from public.account_deletion_execution_jobs j
    where (j.status='queued' and j.next_attempt_at<=clock_timestamp())
       or (j.status='running' and j.lease_expires_at<=clock_timestamp())
    order by j.created_at,j.id limit p_limit for update skip locked
  )
  update public.account_deletion_execution_jobs j set status='running',attempts=j.attempts+1,
    lease_token=gen_random_uuid(),lease_owner=p_worker_id,
    lease_expires_at=clock_timestamp()+make_interval(secs=>p_lease_seconds),
    started_at=coalesce(j.started_at,clock_timestamp()),updated_at=clock_timestamp()
  from picked where j.id=picked.id returning j.*;
end;
$fn$;

create or replace function public.claim_account_deletion_storage_jobs(
  p_execution_job_id uuid,p_job_lease_token uuid,p_limit integer default 50,p_lease_seconds integer default 300
) returns table(id uuid,storage_bucket text,storage_path text,lease_token uuid,attempts integer)
language plpgsql security definer set search_path=''
as $fn$
declare v_job public.account_deletion_execution_jobs%rowtype;
begin
  if coalesce(auth.role(),'')<>'service_role' then raise exception 'service_role_required' using errcode='42501'; end if;
  select * into v_job from public.account_deletion_execution_jobs
   where id=p_execution_job_id and status='running' and lease_token=p_job_lease_token
     and lease_expires_at>clock_timestamp() for update;
  if not found then raise exception 'account_deletion_execution_lease_lost' using errcode='40001'; end if;
  if exists(select 1 from public.account_legal_holds h where h.subject_ref=v_job.subject_ref and h.active) then
    update public.account_deletion_execution_jobs set status='blocked',error_code='LEGAL_HOLD_ACTIVE',
      lease_token=null,lease_owner=null,lease_expires_at=null,updated_at=clock_timestamp() where id=v_job.id;
    update public.account_deletion_requests set status='blocked_legal_hold',error_code='LEGAL_HOLD_ACTIVE',
      updated_at=clock_timestamp() where id=v_job.request_id;
    return;
  end if;
  return query with picked as (
    select s.id from public.account_deletion_storage_jobs s
    where s.execution_job_id=p_execution_job_id
      and (s.status='pending' or (s.status='running' and s.lease_expires_at<=clock_timestamp()) or (s.status='failed' and s.attempts<12))
    order by s.created_at,s.id limit p_limit for update skip locked
  )
  update public.account_deletion_storage_jobs s set status='running',attempts=s.attempts+1,
    lease_token=gen_random_uuid(),lease_expires_at=clock_timestamp()+make_interval(secs=>p_lease_seconds),
    updated_at=clock_timestamp()
  from picked where s.id=picked.id returning s.id,s.storage_bucket,s.storage_path,s.lease_token,s.attempts;
end;
$fn$;

create or replace function public.complete_account_deletion_storage_job(p_job_id uuid,p_lease_token uuid)
returns boolean language plpgsql security definer set search_path=''
as $fn$
begin
  if coalesce(auth.role(),'')<>'service_role' then raise exception 'service_role_required' using errcode='42501'; end if;
  update public.account_deletion_storage_jobs set status='completed',completed_at=clock_timestamp(),
    lease_token=null,lease_expires_at=null,error_code=null,updated_at=clock_timestamp()
  where id=p_job_id and status='running' and lease_token=p_lease_token and lease_expires_at>clock_timestamp();
  return found;
end;
$fn$;

create or replace function public.fail_account_deletion_storage_job(
  p_job_id uuid,p_lease_token uuid,p_error_code text,p_retry_seconds integer default 300
) returns boolean language plpgsql security definer set search_path=''
as $fn$
begin
  if coalesce(auth.role(),'')<>'service_role' then raise exception 'service_role_required' using errcode='42501'; end if;
  update public.account_deletion_storage_jobs set status=case when attempts>=8 then 'failed' else 'pending' end,
    error_code=left(coalesce(p_error_code,'STORAGE_DELETE_FAILED'),80),
    lease_token=null,lease_expires_at=null,updated_at=clock_timestamp()
  where id=p_job_id and status='running' and lease_token=p_lease_token;
  return found;
end;
$fn$;

create or replace function public.execute_account_deletion_execution_job(p_job_id uuid,p_lease_token uuid)
returns boolean language plpgsql security definer set search_path=''
as $fn$
declare v_job public.account_deletion_execution_jobs%rowtype;
        v_request public.account_deletion_requests%rowtype;
        v_step public.account_deletion_execution_steps%rowtype;
        v_source private.account_export_sources%rowtype;
        v_policy public.account_deletion_source_policies%rowtype;
        v_rule public.account_deletion_dependency_rules%rowtype;
        v_column text; v_predicate text; v_sql text; v_rows bigint;
        v_missing_classes integer; v_blocked_fks integer; v_missing_sources integer; v_missing_fk_steps integer;
begin
  if coalesce(auth.role(),'')<>'service_role' then raise exception 'service_role_required' using errcode='42501'; end if;
  select * into v_job from public.account_deletion_execution_jobs
   where id=p_job_id and status='running' and lease_token=p_lease_token
     and lease_expires_at>clock_timestamp() for update;
  if not found then raise exception 'account_deletion_execution_lease_lost' using errcode='40001'; end if;
  select * into v_request from public.account_deletion_requests where id=v_job.request_id for update;
  if not found or v_request.user_id is distinct from v_job.user_id then
    raise exception 'account_deletion_request_subject_mismatch' using errcode='23514';
  end if;
  perform pg_advisory_xact_lock(hashtextextended(v_job.subject_ref,0));
  if exists(select 1 from public.account_legal_holds h where h.subject_ref=v_job.subject_ref and h.active) then
    update public.account_deletion_execution_jobs set status='blocked',error_code='LEGAL_HOLD_ACTIVE',
      lease_token=null,lease_owner=null,lease_expires_at=null,updated_at=clock_timestamp() where id=v_job.id;
    update public.account_deletion_requests set status='blocked_legal_hold',error_code='LEGAL_HOLD_ACTIVE',
      updated_at=clock_timestamp() where id=v_request.id;
    return false;
  end if;
  if exists(select 1 from public.account_deletion_storage_jobs s
            where s.execution_job_id=v_job.id and s.status<>'completed') then
    raise exception 'account_deletion_storage_cleanup_incomplete' using errcode='55000';
  end if;
  select count(*) into v_missing_classes from (values
    ('owner_private'),('agent_operational'),('tenant_shared'),
    ('published_knowledge'),('session_scoped'),('public_catalog')
  ) required(data_class)
  where not exists(select 1 from public.account_data_retention_policies p
    where p.data_class=required.data_class and p.active=true
      and p.policy_version=v_job.policy_snapshot->>required.data_class);
  select count(*) into v_blocked_fks from public.account_deletion_dependency_rules r
    where r.active=true and r.resolution_action='block';
  select count(*) into v_missing_sources from private.account_export_sources s
    left join public.account_deletion_source_policies p on p.source_key=s.source_key and p.active=true
    where s.enabled=true and (p.source_key is null or p.data_class is null
      or p.deletion_action is null or p.deletion_action='block');
  select count(*) into v_missing_fk_steps from public.account_deletion_dependency_rules r
    where r.active=true and r.resolution_action not in ('database_cascade','database_set_null')
      and not exists(select 1 from public.account_deletion_execution_steps st
        where st.job_id=v_job.id and st.step_kind='foreign_key' and st.step_key=r.id::text);
  if v_missing_classes>0 or v_blocked_fks>0 or v_missing_sources>0 or v_missing_fk_steps>0 then
    update public.account_deletion_execution_jobs set status='blocked',error_code='DELETION_POLICY_CHANGED',
      lease_token=null,lease_owner=null,lease_expires_at=null,updated_at=clock_timestamp() where id=v_job.id;
    update public.account_deletion_requests set status='blocked_dependency',error_code='DELETION_POLICY_CHANGED',
      updated_at=clock_timestamp() where id=v_request.id;
    return false;
  end if;
  for v_step in select * from public.account_deletion_execution_steps
    where job_id=v_job.id and status='pending'
    order by dependency_order desc,step_kind desc,step_key for update
  loop
    v_rows:=0;
    if v_step.step_kind='source' then
      select * into v_policy from public.account_deletion_source_policies
       where source_key=v_step.step_key and active=true;
      if not found or v_policy.deletion_action is distinct from v_step.action
         or v_policy.data_class is distinct from v_step.data_class then
        raise exception 'account_deletion_source_policy_changed:%',v_step.step_key using errcode='40001';
      end if;
      if v_step.action='preserve' then
        v_rows:=0;
      elsif v_step.action='delete_rows' then
        select * into v_source from private.account_export_sources
         where source_key=v_step.step_key and enabled=true;
        if not found or v_source.filter_kind<>'owner_columns' or cardinality(v_source.owner_columns)=0 then
          raise exception 'account_deletion_source_handler_missing:%',v_step.step_key using errcode='0A000';
        end if;
        v_predicate:='';
        foreach v_column in array v_source.owner_columns loop
          if not exists(select 1 from information_schema.columns c
            where c.table_schema='public' and c.table_name=v_source.table_name and c.column_name=v_column) then
            raise exception 'account_deletion_source_column_missing:%.%',v_source.table_name,v_column;
          end if;
          if v_predicate<>'' then v_predicate:=v_predicate||' OR '; end if;
          v_predicate:=v_predicate||format('%I::text = $1',v_column);
        end loop;
        v_sql:=format('DELETE FROM public.%I WHERE %s',v_source.table_name,v_predicate);
        execute v_sql using v_job.user_id::text;
        get diagnostics v_rows=row_count;
      else
        raise exception 'account_deletion_source_action_unsupported:%',v_step.action using errcode='0A000';
      end if;
    elsif v_step.step_kind='foreign_key' then
      select * into v_rule from public.account_deletion_dependency_rules
       where id::text=v_step.step_key and active=true;
      if not found or v_rule.resolution_action is distinct from v_step.action then
        raise exception 'account_deletion_dependency_rule_changed:%',v_step.step_key using errcode='40001';
      end if;
      if v_step.action in ('database_cascade','database_set_null') then
        v_rows:=0;
      elsif v_step.action in ('delete_rows','set_null') then
        if v_rule.fk_column is null then raise exception 'composite_foreign_key_requires_manual_handler'; end if;
        if v_step.action='delete_rows' then
          v_sql:=format('DELETE FROM %I.%I WHERE %I::text = $1',v_rule.child_schema,v_rule.child_table,v_rule.fk_column);
        else
          v_sql:=format('UPDATE %I.%I SET %I=NULL WHERE %I::text = $1',
            v_rule.child_schema,v_rule.child_table,v_rule.fk_column,v_rule.fk_column);
        end if;
        execute v_sql using v_job.user_id::text;
        get diagnostics v_rows=row_count;
      else
        raise exception 'account_deletion_dependency_unresolved:%',v_rule.constraint_name using errcode='55000';
      end if;
    else
      raise exception 'account_deletion_step_kind_invalid';
    end if;
    update public.account_deletion_execution_steps set status='completed',
      affected_rows=v_rows,completed_at=clock_timestamp() where id=v_step.id;
  end loop;
  if exists(select 1 from public.account_deletion_execution_steps where job_id=v_job.id and status<>'completed') then
    raise exception 'account_deletion_steps_incomplete' using errcode='55000';
  end if;
  if exists(select 1 from public.account_legal_holds h where h.subject_ref=v_job.subject_ref and h.active) then
    update public.account_deletion_execution_jobs set status='blocked',error_code='LEGAL_HOLD_ACTIVE',
      lease_token=null,lease_owner=null,lease_expires_at=null,updated_at=clock_timestamp() where id=v_job.id;
    update public.account_deletion_requests set status='blocked_legal_hold',error_code='LEGAL_HOLD_ACTIVE',
      updated_at=clock_timestamp() where id=v_request.id;
    return false;
  end if;
  delete from auth.users where id=v_job.user_id;
  if not found then raise exception 'account_deletion_auth_subject_missing' using errcode='P0002'; end if;
  update public.account_deletion_requests set status='completed',user_id=null,completed_at=clock_timestamp(),
    error_code=null,request_metadata=coalesce(request_metadata,'{}'::jsonb)||
      jsonb_build_object('execution_job_id',v_job.id,'completed_at',clock_timestamp()),
    updated_at=clock_timestamp() where id=v_request.id;
  insert into public.account_lifecycle_events(request_id,subject_ref,event_type,metadata)
  values(v_request.id,v_job.subject_ref,'deletion_completed',
    jsonb_build_object('execution_job_id',v_job.id,'steps_completed',
      (select count(*) from public.account_deletion_execution_steps where job_id=v_job.id)));
  update public.account_deletion_execution_jobs set status='completed',completed_at=clock_timestamp(),
    lease_token=null,lease_owner=null,lease_expires_at=null,error_code=null,updated_at=clock_timestamp()
  where id=v_job.id;
  return true;
end;
$fn$;

create or replace function public.fail_account_deletion_execution_job(
  p_job_id uuid,p_lease_token uuid,p_error_code text,p_retry_seconds integer default 300
) returns boolean language plpgsql security definer set search_path=''
as $fn$
declare v_job public.account_deletion_execution_jobs%rowtype;
begin
  if coalesce(auth.role(),'')<>'service_role' then raise exception 'service_role_required' using errcode='42501'; end if;
  update public.account_deletion_execution_jobs set
    status=case when attempts>=max_attempts then 'failed' else 'queued' end,
    next_attempt_at=clock_timestamp()+make_interval(secs=>greatest(1,least(coalesce(p_retry_seconds,300),86400))),
    error_code=left(coalesce(p_error_code,'ACCOUNT_DELETION_FAILED'),80),
    lease_token=null,lease_owner=null,lease_expires_at=null,updated_at=clock_timestamp()
  where id=p_job_id and status='running' and lease_token=p_lease_token returning * into v_job;
  if not found then return false; end if;
  if v_job.status='failed' then
    update public.account_deletion_requests set status='failed',error_code=v_job.error_code,updated_at=clock_timestamp()
      where id=v_job.request_id;
    insert into public.account_lifecycle_events(request_id,subject_ref,event_type,metadata)
    values(v_job.request_id,v_job.subject_ref,'deletion_failed',jsonb_build_object('error_code',v_job.error_code));
  end if;
  return true;
end;
$fn$;

create or replace function public.cancel_my_account_deletion(p_request_id uuid)
returns boolean language plpgsql security definer set search_path=''
as $fn$
declare v_request public.account_deletion_requests%rowtype;
begin
  if auth.uid() is null then raise exception 'authenticated_user_required' using errcode='42501'; end if;
  update public.account_deletion_requests set status='cancelled',cancelled_at=clock_timestamp(),
    updated_at=clock_timestamp(),error_code=null
  where id=p_request_id and user_id=auth.uid()
    and status in ('awaiting_policy','blocked_dependency','blocked_legal_hold')
  returning * into v_request;
  if not found then return false; end if;
  update public.profiles set account_status='active',updated_at=clock_timestamp()
   where id=auth.uid() and account_status='deactivation_requested';
  insert into public.account_lifecycle_events(request_id,user_id,subject_ref,event_type,metadata)
  values(v_request.id,auth.uid(),v_request.subject_ref,'deletion_cancelled','{}'::jsonb);
  return true;
end;
$fn$;

create or replace function private.lock_account_legal_hold_subject()
returns trigger language plpgsql security definer set search_path=''
as $fn$
begin
  perform pg_advisory_xact_lock(hashtextextended(new.subject_ref,0));
  return new;
end;
$fn$;
drop trigger if exists account_legal_hold_subject_lock on public.account_legal_holds;
create trigger account_legal_hold_subject_lock before insert or update on public.account_legal_holds
for each row execute function private.lock_account_legal_hold_subject();

commit;

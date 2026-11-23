-- ENG-P03: export archive expiry is driven only by an explicitly approved
-- account_data_retention_policies row for data_class=account_export_artifact.
-- With no active policy, the archive remains private and download links stay
-- short-lived; engineering does not invent an archive retention duration.

alter table public.account_export_jobs
  add column if not exists expires_at timestamptz;

create or replace function private.assign_account_export_artifact_expiry()
returns trigger
language plpgsql
security definer
set search_path = ''
as $assign_export_expiry$
declare
  v_retention_days integer;
begin
  if new.status = 'succeeded' and old.status is distinct from 'succeeded' then
    select p.retention_days into v_retention_days
      from public.account_data_retention_policies p
     where p.data_class = 'account_export_artifact' and p.active
     limit 1;
    if found then
      new.expires_at := pg_catalog.clock_timestamp()
        + pg_catalog.make_interval(days => v_retention_days);
    else
      new.expires_at := null;
    end if;
  end if;
  return new;
end;
$assign_export_expiry$;

drop trigger if exists account_export_artifact_expiry on public.account_export_jobs;
create trigger account_export_artifact_expiry
before update of status on public.account_export_jobs
for each row execute function private.assign_account_export_artifact_expiry();

create table if not exists public.account_export_artifact_cleanup_jobs (
  id uuid primary key default gen_random_uuid(),
  export_job_id uuid not null unique references public.account_export_jobs(id) on delete cascade,
  storage_bucket text not null,
  storage_path text not null,
  status text not null default 'queued'
    check (status in ('queued','running','completed','failed')),
  attempts integer not null default 0 check (attempts >= 0),
  max_attempts integer not null default 5 check (max_attempts between 1 and 10),
  next_attempt_at timestamptz not null default now(),
  lease_token uuid,
  lease_owner text,
  lease_expires_at timestamptz,
  error_code text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  completed_at timestamptz
);
create index if not exists account_export_artifact_cleanup_claim_idx
  on public.account_export_artifact_cleanup_jobs(status,next_attempt_at,created_at)
  where status in ('queued','running');

create or replace function public.enqueue_expired_account_export_artifacts()
returns integer
language plpgsql
security definer
set search_path = ''
as $enqueue_expired_exports$
declare v_count integer;
begin
  if coalesce(auth.role(),'') <> 'service_role' then
    raise exception 'service_role_required' using errcode='42501';
  end if;
  insert into public.account_export_artifact_cleanup_jobs(
    export_job_id,storage_bucket,storage_path
  )
  select j.id,j.storage_bucket,j.storage_path
    from public.account_export_jobs j
   where j.status='succeeded'
     and j.expires_at is not null
     and j.expires_at <= pg_catalog.clock_timestamp()
     and j.storage_path is not null
  on conflict(export_job_id) do nothing;
  get diagnostics v_count = row_count;
  return v_count;
end;
$enqueue_expired_exports$;

create or replace function public.claim_account_export_artifact_cleanup_jobs(
  p_worker_id text,p_limit integer default 10,p_lease_seconds integer default 300
)
returns table(
  id uuid,export_job_id uuid,storage_bucket text,storage_path text,
  lease_token uuid,attempts integer
)
language plpgsql
security definer
set search_path = ''
as $claim_expired_exports$
begin
  if coalesce(auth.role(),'') <> 'service_role' then
    raise exception 'service_role_required' using errcode='42501';
  end if;
  if p_worker_id is null or pg_catalog.char_length(p_worker_id) not between 1 and 160
     or p_limit is null or p_limit not between 1 and 100
     or p_lease_seconds is null or p_lease_seconds not between 30 and 3600 then
    raise exception 'invalid_export_cleanup_claim_bounds' using errcode='22023';
  end if;

  update public.account_export_artifact_cleanup_jobs q
     set status=case when q.attempts >= q.max_attempts then 'failed' else 'queued' end,
         lease_token=null,lease_owner=null,lease_expires_at=null,
         next_attempt_at=pg_catalog.clock_timestamp(),updated_at=pg_catalog.clock_timestamp(),
         error_code=case when q.attempts >= q.max_attempts then 'EXPORT_CLEANUP_LEASE_EXHAUSTED' else q.error_code end
   where q.status='running' and q.lease_expires_at <= pg_catalog.clock_timestamp();

  return query
  with candidates as (
    select q.id from public.account_export_artifact_cleanup_jobs q
     where q.status='queued' and q.next_attempt_at <= pg_catalog.clock_timestamp()
     order by q.next_attempt_at,q.created_at
     for update skip locked limit p_limit
  )
  update public.account_export_artifact_cleanup_jobs q
     set status='running',attempts=q.attempts+1,lease_token=gen_random_uuid(),
         lease_owner=p_worker_id,
         lease_expires_at=pg_catalog.clock_timestamp()+pg_catalog.make_interval(secs=>p_lease_seconds),
         updated_at=pg_catalog.clock_timestamp()
    from candidates c where q.id=c.id
  returning q.id,q.export_job_id,q.storage_bucket,q.storage_path,q.lease_token,q.attempts;
end;
$claim_expired_exports$;

create or replace function public.complete_account_export_artifact_cleanup_job(
  p_job_id uuid,p_lease_token uuid
)
returns boolean
language plpgsql
security definer
set search_path = ''
as $complete_export_cleanup$
declare
  v_export_job_id uuid;
  v_export_status text;
begin
  if coalesce(auth.role(),'') <> 'service_role' then
    raise exception 'service_role_required' using errcode='42501';
  end if;
  select q.export_job_id into v_export_job_id
    from public.account_export_artifact_cleanup_jobs q
   where q.id=p_job_id and q.lease_token=p_lease_token and q.status='running'
   for update;
  if not found then return false; end if;

  update public.account_export_jobs j
     set status='expired',storage_path=null,lease_token=null,lease_owner=null,
         lease_expires_at=null,updated_at=pg_catalog.clock_timestamp()
   where j.id=v_export_job_id and j.status='succeeded'
     and j.expires_at is not null and j.expires_at <= pg_catalog.clock_timestamp();
  if not found then
    select j.status into v_export_status
      from public.account_export_jobs j where j.id=v_export_job_id;
    if v_export_status is distinct from 'expired' then return false; end if;
  end if;

  update public.account_export_artifact_cleanup_jobs q
     set status='completed',completed_at=pg_catalog.clock_timestamp(),
         lease_token=null,lease_owner=null,lease_expires_at=null,
         error_code=null,updated_at=pg_catalog.clock_timestamp()
   where q.id=p_job_id and q.lease_token=p_lease_token and q.status='running';
  return found;
end;
$complete_export_cleanup$;

create or replace function public.fail_account_export_artifact_cleanup_job(
  p_job_id uuid,p_lease_token uuid,p_error_code text,p_retry_seconds integer default 60
)
returns boolean
language plpgsql
security definer
set search_path = ''
as $fail_export_cleanup$
begin
  if coalesce(auth.role(),'') <> 'service_role' then
    raise exception 'service_role_required' using errcode='42501';
  end if;
  if p_retry_seconds not between 1 and 86400 then
    raise exception 'invalid_export_cleanup_retry_delay' using errcode='22023';
  end if;
  update public.account_export_artifact_cleanup_jobs q
     set status=case when q.attempts >= q.max_attempts then 'failed' else 'queued' end,
         next_attempt_at=pg_catalog.clock_timestamp()+pg_catalog.make_interval(secs=>p_retry_seconds),
         error_code=pg_catalog.left(pg_catalog.coalesce(p_error_code,'EXPORT_CLEANUP_FAILED'),80),
         lease_token=null,lease_owner=null,lease_expires_at=null,
         updated_at=pg_catalog.clock_timestamp()
   where q.id=p_job_id and q.lease_token=p_lease_token and q.status='running';
  return found;
end;
$fail_export_cleanup$;

alter table public.account_export_artifact_cleanup_jobs enable row level security;
revoke all privileges on public.account_export_artifact_cleanup_jobs from public,anon,authenticated;
grant select,insert,update,delete on public.account_export_artifact_cleanup_jobs to service_role;

revoke all on function private.assign_account_export_artifact_expiry() from public,anon,authenticated;
revoke all on function public.enqueue_expired_account_export_artifacts() from public,anon,authenticated;
revoke all on function public.claim_account_export_artifact_cleanup_jobs(text,integer,integer) from public,anon,authenticated;
revoke all on function public.complete_account_export_artifact_cleanup_job(uuid,uuid) from public,anon,authenticated;
revoke all on function public.fail_account_export_artifact_cleanup_job(uuid,uuid,text,integer) from public,anon,authenticated;
grant execute on function public.enqueue_expired_account_export_artifacts() to service_role;
grant execute on function public.claim_account_export_artifact_cleanup_jobs(text,integer,integer) to service_role;
grant execute on function public.complete_account_export_artifact_cleanup_job(uuid,uuid) to service_role;
grant execute on function public.fail_account_export_artifact_cleanup_job(uuid,uuid,text,integer) to service_role;

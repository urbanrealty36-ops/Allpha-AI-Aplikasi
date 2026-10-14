-- ENG-P09: database-backed queue lease primitives.
-- SOURCE ONLY. Validate concurrency, privileges, and migration order in approved
-- isolated non-production before applying anywhere.
alter table public.agent_knowledge_sources
  add column if not exists sensitivity text
    check (sensitivity in ('public','internal','confidential','restricted'));

alter table public.agent_knowledge_jobs
  add column if not exists source_version integer,
  add column if not exists lease_token uuid,
  add column if not exists lease_expires_at timestamptz,
  add column if not exists available_at timestamptz not null default now(),
  add column if not exists max_attempts integer not null default 5
    check (max_attempts between 1 and 8),
  add column if not exists idempotency_key text;

update public.agent_knowledge_jobs j
set source_version = s.source_version
from public.agent_knowledge_sources s
where s.id = j.source_id and j.source_version is null;

alter table public.agent_knowledge_jobs
  alter column source_version set not null;

create unique index if not exists agent_knowledge_jobs_idempotency_uidx
  on public.agent_knowledge_jobs(owner_id, idempotency_key)
  where idempotency_key is not null;

create index if not exists agent_knowledge_jobs_claim_idx
  on public.agent_knowledge_jobs(available_at, created_at)
  where status in ('queued','processing');

create or replace function public.claim_agent_knowledge_job(
  p_lease_seconds integer default 90,
  p_stage text default null
)
returns setof public.agent_knowledge_jobs
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  v_job_id uuid;
  v_token uuid := gen_random_uuid();
begin
  if p_lease_seconds < 10 or p_lease_seconds > 900 then
    raise exception 'LEASE_SECONDS_OUT_OF_RANGE' using errcode = '22023';
  end if;

  select j.id into v_job_id
  from public.agent_knowledge_jobs j
  where j.available_at <= now()
    and (p_stage is null or j.stage = p_stage)
    and j.attempt < j.max_attempts
    and (
      j.status = 'queued'
      or (j.status = 'processing' and j.lease_expires_at < now())
    )
  order by j.available_at, j.created_at
  for update skip locked
  limit 1;

  if v_job_id is null then
    return;
  end if;

  return query
  update public.agent_knowledge_jobs j
  set status = 'processing',
      attempt = j.attempt + 1,
      lease_token = v_token,
      lease_expires_at = now() + make_interval(secs => p_lease_seconds),
      progress = greatest(j.progress, 1),
      error_code = null,
      updated_at = now()
  where j.id = v_job_id
  returning j.*;
end;
$$;

create or replace function public.finalize_agent_knowledge_job(
  p_job_id uuid,
  p_lease_token uuid,
  p_outcome text,
  p_stage text,
  p_progress integer default 100,
  p_error_code text default null,
  p_retry_delay_seconds integer default 30
)
returns boolean
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  v_job public.agent_knowledge_jobs%rowtype;
  v_current_version integer;
begin
  if p_outcome not in ('succeeded','failed','retry') then
    raise exception 'INVALID_JOB_OUTCOME' using errcode = '22023';
  end if;
  if p_progress < 0 or p_progress > 100 then
    raise exception 'INVALID_JOB_PROGRESS' using errcode = '22023';
  end if;
  if p_retry_delay_seconds < 0 or p_retry_delay_seconds > 3600 then
    raise exception 'INVALID_RETRY_DELAY' using errcode = '22023';
  end if;

  select * into v_job
  from public.agent_knowledge_jobs
  where id = p_job_id
  for update;

  if not found
     or v_job.status <> 'processing'
     or v_job.lease_token is distinct from p_lease_token
     or v_job.lease_expires_at is null
     or v_job.lease_expires_at <= now() then
    return false;
  end if;

  select source_version into v_current_version
  from public.agent_knowledge_sources
  where id = v_job.source_id
    and owner_id = v_job.owner_id
    and agent_id = v_job.agent_id
    and status <> 'deleting'
  for share;

  if v_current_version is null or v_current_version <> v_job.source_version then
    update public.agent_knowledge_jobs
    set status = 'cancelled',
        stage = 'stale_source_version',
        error_code = 'STALE_SOURCE_VERSION',
        lease_token = null,
        lease_expires_at = null,
        updated_at = now()
    where id = p_job_id;
    return false;
  end if;

  if p_outcome = 'retry' and v_job.attempt < v_job.max_attempts then
    update public.agent_knowledge_jobs
    set status = 'queued',
        stage = p_stage,
        progress = least(p_progress, 99),
        error_code = p_error_code,
        available_at = now() + make_interval(secs => p_retry_delay_seconds),
        lease_token = null,
        lease_expires_at = null,
        updated_at = now()
    where id = p_job_id;
  else
    update public.agent_knowledge_jobs
    set status = case
          when p_outcome = 'succeeded' then 'succeeded'
          else 'failed'
        end,
        stage = p_stage,
        progress = case when p_outcome = 'succeeded' then 100 else least(p_progress, 99) end,
        error_code = case when p_outcome = 'succeeded' then null else coalesce(p_error_code, 'JOB_FAILED') end,
        lease_token = null,
        lease_expires_at = null,
        updated_at = now()
    where id = p_job_id;
  end if;

  return true;
end;
$$;

revoke all on function public.claim_agent_knowledge_job(integer, text) from public, anon, authenticated;
revoke all on function public.finalize_agent_knowledge_job(uuid, uuid, text, text, integer, text, integer) from public, anon, authenticated;
grant execute on function public.claim_agent_knowledge_job(integer, text) to service_role;
grant execute on function public.finalize_agent_knowledge_job(uuid, uuid, text, text, integer, text, integer) to service_role;

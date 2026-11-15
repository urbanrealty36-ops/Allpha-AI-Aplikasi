-- SOURCE ONLY — WP-07 requester-controlled deletion of private Generation artifacts.
-- Depends on 20261105130000_eng_p09_durable_generation_jobs.sql.
-- This adds explicit owner deletion only. Automatic retention periods remain unconfigured
-- because the Master PRD lists retention periods and deletion SLAs as open policy decisions.
-- Do not apply to canonical production or staging during the source-only implementation window.
begin;

alter table public.generation_jobs
  add column if not exists artifact_deletion_requested_at timestamptz,
  add column if not exists artifact_deleted_at timestamptz,
  add constraint generation_jobs_artifact_deletion_order
    check (artifact_deleted_at is null or artifact_deletion_requested_at is not null);

create table if not exists public.generation_artifact_deletion_jobs (
  id uuid primary key default gen_random_uuid(),
  generation_job_id uuid not null unique references public.generation_jobs(id) on delete restrict,
  owner_user_id uuid not null references auth.users(id) on delete restrict,
  requested_by uuid not null references auth.users(id) on delete restrict,
  bucket_id text not null check (bucket_id = 'generation-artifacts'),
  object_path text not null check (char_length(object_path) between 1 and 1024),
  idempotency_key text not null unique check (char_length(idempotency_key) between 8 and 160),
  status text not null default 'queued'
    check (status in ('queued','processing','succeeded','dead')),
  attempts integer not null default 0 check (attempts between 0 and 20),
  max_attempts integer not null default 8 check (max_attempts between 1 and 20),
  available_at timestamptz not null default now(),
  lease_token uuid,
  lease_expires_at timestamptz,
  error_code text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  completed_at timestamptz,
  check ((lease_token is null and lease_expires_at is null) or
         (lease_token is not null and lease_expires_at is not null)),
  check (status <> 'succeeded' or completed_at is not null)
);

create index if not exists generation_artifact_deletion_claim_idx
  on public.generation_artifact_deletion_jobs(available_at, created_at, id)
  where status in ('queued','processing');
create index if not exists generation_artifact_deletion_owner_idx
  on public.generation_artifact_deletion_jobs(owner_user_id, created_at desc);

alter table public.generation_artifact_deletion_jobs enable row level security;
revoke all on public.generation_artifact_deletion_jobs from public, anon, authenticated, service_role;
grant select, insert, update on public.generation_artifact_deletion_jobs to service_role;

create or replace function public.generation_request_artifact_deletion(p_command jsonb)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_job public.generation_jobs;
  v_delete public.generation_artifact_deletion_jobs;
  v_job_id uuid;
  v_owner_id uuid;
  v_actor_id uuid;
  v_key text;
begin
  if jsonb_typeof(p_command) <> 'object' then
    raise exception 'GENERATION_ARTIFACT_DELETE_COMMAND_INVALID' using errcode='22023';
  end if;
  v_job_id := nullif(p_command->>'job_id','')::uuid;
  v_owner_id := nullif(p_command->>'owner_user_id','')::uuid;
  v_actor_id := nullif(p_command->>'requested_by','')::uuid;
  v_key := p_command->>'idempotency_key';
  if v_job_id is null or v_owner_id is null or v_actor_id is null
     or v_actor_id <> v_owner_id or v_key is null
     or char_length(v_key) < 8 or char_length(v_key) > 160 then
    raise exception 'GENERATION_ARTIFACT_DELETE_COMMAND_INVALID' using errcode='22023';
  end if;

  select * into v_job
  from public.generation_jobs
  where id=v_job_id and owner_user_id=v_owner_id
  for update;
  if not found then
    raise exception 'GENERATION_ARTIFACT_NOT_FOUND' using errcode='P0002';
  end if;
  if v_job.status <> 'succeeded' or v_job.moderation_status <> 'approved'
     or v_job.artifact_bucket <> 'generation-artifacts' or v_job.artifact_path is null then
    raise exception 'GENERATION_ARTIFACT_NOT_DELETABLE' using errcode='55000';
  end if;
  if v_job.artifact_deleted_at is not null then
    return jsonb_build_object('job_id',v_job.id,'status','succeeded',
      'artifact_available',false,'idempotent_replay',true);
  end if;

  select * into v_delete
  from public.generation_artifact_deletion_jobs
  where generation_job_id=v_job.id
  for update;
  if found then
    update public.generation_jobs
    set artifact_deletion_requested_at=coalesce(artifact_deletion_requested_at,now()),
        updated_at=now()
    where id=v_job.id;
    return jsonb_build_object('job_id',v_job.id,'deletion_job_id',v_delete.id,
      'status',v_delete.status,'artifact_available',false,'idempotent_replay',true);
  end if;

  insert into public.generation_artifact_deletion_jobs(
    generation_job_id,owner_user_id,requested_by,bucket_id,object_path,idempotency_key
  ) values (
    v_job.id,v_owner_id,v_actor_id,v_job.artifact_bucket,v_job.artifact_path,v_key
  ) returning * into v_delete;

  update public.generation_jobs
  set artifact_deletion_requested_at=now(),updated_at=now()
  where id=v_job.id;

  return jsonb_build_object('job_id',v_job.id,'deletion_job_id',v_delete.id,
    'status',v_delete.status,'artifact_available',false,'idempotent_replay',false);
end;
$$;

create or replace function public.claim_generation_artifact_deletions(p_command jsonb)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_worker uuid;
  v_limit integer;
  v_lease_seconds integer;
  v_jobs jsonb;
begin
  if jsonb_typeof(p_command) <> 'object' then
    raise exception 'GENERATION_ARTIFACT_DELETE_CLAIM_INVALID' using errcode='22023';
  end if;
  v_worker := nullif(p_command->>'worker_id','')::uuid;
  v_limit := least(20,greatest(1,coalesce((p_command->>'limit')::integer,5)));
  v_lease_seconds := least(900,greatest(30,coalesce((p_command->>'lease_seconds')::integer,300)));
  if v_worker is null then
    raise exception 'GENERATION_ARTIFACT_DELETE_CLAIM_INVALID' using errcode='22023';
  end if;

  with candidates as (
    select id
    from public.generation_artifact_deletion_jobs
    where attempts < max_attempts
      and ((status='queued' and available_at<=now())
        or (status='processing' and lease_expires_at<=now()))
    order by available_at,created_at,id
    for update skip locked
    limit v_limit
  ), claimed as (
    update public.generation_artifact_deletion_jobs d
    set status='processing',attempts=d.attempts+1,lease_token=v_worker,
        lease_expires_at=now()+make_interval(secs=>v_lease_seconds),updated_at=now()
    from candidates c
    where d.id=c.id
    returning d.id,d.generation_job_id,d.bucket_id,d.object_path,d.attempts,d.max_attempts,d.lease_token
  )
  select coalesce(jsonb_agg(to_jsonb(claimed)),'[]'::jsonb) into v_jobs from claimed;
  return v_jobs;
end;
$$;

create or replace function public.complete_generation_artifact_deletion(p_command jsonb)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_id uuid := nullif(p_command->>'deletion_job_id','')::uuid;
  v_lease uuid := nullif(p_command->>'lease_token','')::uuid;
  v_job public.generation_artifact_deletion_jobs;
begin
  if v_id is null or v_lease is null then
    raise exception 'GENERATION_ARTIFACT_DELETE_COMPLETION_INVALID' using errcode='22023';
  end if;
  select * into v_job from public.generation_artifact_deletion_jobs where id=v_id for update;
  if not found then raise exception 'GENERATION_ARTIFACT_DELETE_JOB_NOT_FOUND' using errcode='P0002'; end if;
  if v_job.status='succeeded' then
    return jsonb_build_object('status','succeeded','idempotent_replay',true);
  end if;
  if v_job.status<>'processing' or v_job.lease_token is distinct from v_lease then
    raise exception 'GENERATION_ARTIFACT_DELETE_LEASE_LOST' using errcode='40001';
  end if;

  update public.generation_jobs
  set artifact_deleted_at=coalesce(artifact_deleted_at,now()),updated_at=now()
  where id=v_job.generation_job_id and owner_user_id=v_job.owner_user_id
    and artifact_deletion_requested_at is not null;
  if not found then raise exception 'GENERATION_ARTIFACT_DELETE_SOURCE_CHANGED' using errcode='40001'; end if;

  update public.generation_artifact_deletion_jobs
  set status='succeeded',completed_at=now(),lease_token=null,lease_expires_at=null,
      error_code=null,updated_at=now()
  where id=v_id;
  return jsonb_build_object('status','succeeded','idempotent_replay',false);
end;
$$;

create or replace function public.fail_generation_artifact_deletion(p_command jsonb)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_id uuid := nullif(p_command->>'deletion_job_id','')::uuid;
  v_lease uuid := nullif(p_command->>'lease_token','')::uuid;
  v_error text := left(coalesce(p_command->>'error_code','artifact_delete_failed'),80);
  v_retry integer := least(3600,greatest(5,coalesce((p_command->>'retry_seconds')::integer,60)));
  v_job public.generation_artifact_deletion_jobs;
  v_status text;
begin
  if v_id is null or v_lease is null then
    raise exception 'GENERATION_ARTIFACT_DELETE_FAILURE_INVALID' using errcode='22023';
  end if;
  select * into v_job from public.generation_artifact_deletion_jobs where id=v_id for update;
  if not found then raise exception 'GENERATION_ARTIFACT_DELETE_JOB_NOT_FOUND' using errcode='P0002'; end if;
  if v_job.status<>'processing' or v_job.lease_token is distinct from v_lease then
    raise exception 'GENERATION_ARTIFACT_DELETE_LEASE_LOST' using errcode='40001';
  end if;
  v_status := case when v_job.attempts >= v_job.max_attempts then 'dead' else 'queued' end;
  update public.generation_artifact_deletion_jobs
  set status=v_status,error_code=v_error,
      available_at=case when v_status='queued' then now()+make_interval(secs=>v_retry) else available_at end,
      lease_token=null,lease_expires_at=null,updated_at=now()
  where id=v_id;
  return jsonb_build_object('status',v_status,'attempts',v_job.attempts);
end;
$$;

revoke all on function public.generation_request_artifact_deletion(jsonb),
  public.claim_generation_artifact_deletions(jsonb),
  public.complete_generation_artifact_deletion(jsonb),
  public.fail_generation_artifact_deletion(jsonb)
from public,anon,authenticated,service_role;
grant execute on function public.generation_request_artifact_deletion(jsonb),
  public.claim_generation_artifact_deletions(jsonb),
  public.complete_generation_artifact_deletion(jsonb),
  public.fail_generation_artifact_deletion(jsonb)
to service_role;

comment on table public.generation_artifact_deletion_jobs is
  'Durable requester-authorized deletion queue for private Generation artifacts. Does not define an automatic retention TTL.';
comment on column public.generation_jobs.artifact_deletion_requested_at is
  'Timestamp when the authenticated artifact owner requested deletion; artifact access is denied immediately.';
comment on column public.generation_jobs.artifact_deleted_at is
  'Timestamp when private Storage object deletion was confirmed by the durable deletion worker.';

commit;

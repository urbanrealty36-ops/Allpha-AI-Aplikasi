-- ENG-P09 durable AI generation jobs.
-- SOURCE ONLY: apply only in an approved isolated non-production environment.
-- A job is created only after an atomic AI Credit reservation. Provider calls
-- are never replayed after an expired worker lease or unknown provider outcome.
begin;

create table if not exists public.generation_jobs (
  id uuid primary key default gen_random_uuid(),
  owner_user_id uuid not null references auth.users(id) on delete restrict,
  agent_id uuid not null references public.ai_agents(id) on delete restrict,
  skill_id uuid not null references public.agent_skills(id) on delete restrict,
  capability_id text not null check (char_length(capability_id) between 3 and 128),
  sensitivity text not null check (sensitivity in ('private','internal','public')),
  task_id text not null unique check (char_length(task_id) between 8 and 160),
  trace_id text not null check (char_length(trace_id) between 8 and 160),
  idempotency_key text not null check (char_length(idempotency_key) between 8 and 160),
  prompt text not null check (char_length(prompt) between 1 and 32768),
  prompt_sha256 text not null check (prompt_sha256 ~ '^[0-9a-f]{64}$'),
  max_output_tokens integer not null check (max_output_tokens between 1 and 16384),
  timeout_ms integer not null check (timeout_ms between 100 and 120000),
  estimated_usage_units bigint not null check (estimated_usage_units > 0),
  usage_unit text not null,
  estimated_cost_microunits bigint not null check (estimated_cost_microunits >= 0),
  cost_unit text not null,
  credits_to_reserve bigint not null check (credits_to_reserve > 0),
  credits_per_usage_unit bigint not null check (credits_per_usage_unit > 0),
  credit_scheme_version text not null,
  tariff_version text not null,
  entitlement_version text not null,
  policy_version text not null references public.credit_policy_versions(policy_version) on delete restrict,
  policy_approval_reference text not null,
  allow_success_settlement boolean not null,
  allow_definitive_failure_release boolean not null,
  allow_partial_settlement boolean not null,
  reservation_id uuid not null references public.credit_reservations(id) on delete restrict,
  provider_id text not null,
  model_id text not null,
  model_version text not null,
  pricing_version text not null,
  max_cost_microunits bigint not null check (max_cost_microunits >= 0),
  status text not null default 'queued'
    check (status in ('queued','running','succeeded','failed','pending_reconciliation','cancelled')),
  attempt_count integer not null default 0 check (attempt_count between 0 and 1),
  lease_token uuid,
  lease_expires_at timestamptz,
  input_tokens bigint,
  output_tokens bigint,
  actual_cost_microunits bigint,
  output_text text,
  error_code text,
  started_at timestamptz,
  completed_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(owner_user_id,idempotency_key),
  check ((lease_token is null and lease_expires_at is null) or (lease_token is not null and lease_expires_at is not null)),
  check (status <> 'succeeded' or (output_text is not null and input_tokens is not null and output_tokens is not null))
);
create index if not exists generation_jobs_owner_created_idx
  on public.generation_jobs(owner_user_id,created_at desc);
create index if not exists generation_jobs_claim_idx
  on public.generation_jobs(created_at,id)
  where status='queued';
create index if not exists generation_jobs_reconcile_idx
  on public.generation_jobs(updated_at,id)
  where status='pending_reconciliation';

alter table public.generation_jobs enable row level security;
revoke all on public.generation_jobs from public,anon,authenticated,service_role;
grant select,insert,update,delete on public.generation_jobs to service_role;

create or replace function public.generation_create_job(p_command jsonb)
returns jsonb language plpgsql security definer set search_path = ''
as $$
declare
  v_owner uuid := (p_command->>'owner_user_id')::uuid;
  v_agent uuid := (p_command->>'agent_id')::uuid;
  v_skill uuid := (p_command->>'skill_id')::uuid;
  v_task text := p_command->>'task_id';
  v_key text := p_command->>'idempotency_key';
  v_existing public.generation_jobs;
  v_job public.generation_jobs;
  v_reservation jsonb;
  v_reservation_id uuid;
begin
  if v_owner is null or v_agent is null or v_skill is null
    or coalesce(v_task,'')='' or coalesce(v_key,'')=''
    or coalesce(p_command->>'prompt','')=''
    or coalesce(p_command->>'prompt_sha256','') !~ '^[0-9a-f]{64}$' then
    raise exception 'GENERATION_JOB_COMMAND_INVALID' using errcode='22023';
  end if;
  select * into v_existing from public.generation_jobs
    where owner_user_id=v_owner and idempotency_key=v_key for update;
  if found then
    if v_existing.prompt_sha256 <> p_command->>'prompt_sha256'
      or v_existing.capability_id <> p_command->>'capability_id'
      or v_existing.agent_id <> v_agent or v_existing.skill_id <> v_skill then
      raise exception 'GENERATION_JOB_IDEMPOTENCY_CONFLICT' using errcode='23505';
    end if;
    return jsonb_build_object('job_id',v_existing.id,'task_id',v_existing.task_id,
      'reservation_id',v_existing.reservation_id,'status',v_existing.status,'idempotent_replay',true);
  end if;
  if not exists (
    select 1 from public.agent_ownerships o
    where o.agent_id=v_agent and o.owner_user_id=v_owner
      and o.ownership_role='owner' and o.status='active'
  ) then raise exception 'GENERATION_AGENT_OWNER_REQUIRED' using errcode='42501'; end if;
  if not exists (
    select 1 from public.agent_skills s
    where s.id=v_skill and s.agent_id=v_agent and s.status='published'
  ) then raise exception 'GENERATION_SKILL_NOT_PUBLISHED' using errcode='42501'; end if;

  -- Reservation and queue insertion share one PostgreSQL transaction. An
  -- idempotent retry cannot create an orphan reservation.
  v_reservation := public.credit_ledger_reserve(jsonb_build_object(
    'owner_user_id',v_owner,
    'idempotency_key','generation-reserve:'||v_task,
    'task_id',v_task,
    'capability_id',p_command->>'capability_id',
    'credits_to_reserve',(p_command->>'credits_to_reserve')::bigint,
    'estimated_usage_units',(p_command->>'estimated_usage_units')::bigint,
    'usage_unit',p_command->>'usage_unit',
    'estimated_cost_microunits',(p_command->>'estimated_cost_microunits')::bigint,
    'cost_unit',p_command->>'cost_unit',
    'credit_scheme_version',p_command->>'credit_scheme_version',
    'tariff_version',p_command->>'tariff_version',
    'entitlement_version',p_command->>'entitlement_version',
    'policy_version',p_command->>'policy_version',
    'policy_approval_reference',p_command->>'policy_approval_reference'
  ));
  v_reservation_id := (v_reservation->>'reservation_id')::uuid;

  insert into public.generation_jobs(
    owner_user_id,agent_id,skill_id,capability_id,sensitivity,task_id,trace_id,idempotency_key,
    prompt,prompt_sha256,max_output_tokens,timeout_ms,estimated_usage_units,usage_unit,
    estimated_cost_microunits,cost_unit,credits_to_reserve,credits_per_usage_unit,
    credit_scheme_version,tariff_version,entitlement_version,policy_version,
    policy_approval_reference,allow_success_settlement,allow_definitive_failure_release,
    allow_partial_settlement,reservation_id,provider_id,model_id,model_version,pricing_version,
    max_cost_microunits
  ) values (
    v_owner,v_agent,v_skill,p_command->>'capability_id',p_command->>'sensitivity',v_task,
    p_command->>'trace_id',v_key,p_command->>'prompt',p_command->>'prompt_sha256',
    (p_command->>'max_output_tokens')::integer,(p_command->>'timeout_ms')::integer,
    (p_command->>'estimated_usage_units')::bigint,p_command->>'usage_unit',
    (p_command->>'estimated_cost_microunits')::bigint,p_command->>'cost_unit',
    (p_command->>'credits_to_reserve')::bigint,(p_command->>'credits_per_usage_unit')::bigint,
    p_command->>'credit_scheme_version',p_command->>'tariff_version',
    p_command->>'entitlement_version',p_command->>'policy_version',
    p_command->>'policy_approval_reference',(p_command->>'allow_success_settlement')::boolean,
    (p_command->>'allow_definitive_failure_release')::boolean,
    (p_command->>'allow_partial_settlement')::boolean,v_reservation_id,
    p_command->>'provider_id',p_command->>'model_id',p_command->>'model_version',
    p_command->>'pricing_version',(p_command->>'max_cost_microunits')::bigint
  ) returning * into v_job;
  return jsonb_build_object('job_id',v_job.id,'task_id',v_job.task_id,
    'reservation_id',v_job.reservation_id,'status',v_job.status,'idempotent_replay',false);
end;
$$;

create or replace function public.claim_generation_jobs(
  p_worker_id uuid,p_limit integer default 5,p_lease_seconds integer default 300
) returns setof public.generation_jobs
language plpgsql security definer set search_path = ''
as $$
declare v_expired record;
begin
  if p_worker_id is null or p_limit < 1 or p_limit > 20
    or p_lease_seconds < 60 or p_lease_seconds > 600 then
    raise exception 'GENERATION_JOB_CLAIM_BOUNDS_INVALID' using errcode='22023';
  end if;
  -- An expired running lease is an unknown provider outcome. Never requeue it.
  -- Preserve already-settled/released ledger state if a crash occurred between
  -- ledger finalization and writing the terminal job state.
  for v_expired in
    select j.id,j.reservation_id,r.state as reservation_state
    from public.generation_jobs j
    join public.credit_reservations r on r.id=j.reservation_id
    where j.status='running' and j.lease_expires_at < now()
    for update of j skip locked
  loop
    if v_expired.reservation_state in ('reserved','pending_reconciliation') then
      perform public.credit_ledger_mark_pending(jsonb_build_object(
        'reservation_id',v_expired.reservation_id,
        'reason_code','generation_worker_lease_expired_outcome_unknown'
      ));
    end if;
    update public.generation_jobs set status='pending_reconciliation',
      lease_token=null,lease_expires_at=null,error_code='worker_lease_expired_outcome_unknown',
      updated_at=now() where id=v_expired.id;
  end loop;
  return query
    with due as (
      select id from public.generation_jobs
      where status='queued' and attempt_count=0
      order by created_at,id for update skip locked limit p_limit
    )
    update public.generation_jobs j set status='running',attempt_count=1,
      lease_token=p_worker_id,lease_expires_at=now()+make_interval(secs=>p_lease_seconds),
      started_at=coalesce(started_at,now()),updated_at=now()
    from due where j.id=due.id
    returning j.*;
end;
$$;

create or replace function public.generation_complete_job(
  p_job_id uuid,p_lease_token uuid,p_result jsonb
) returns jsonb language plpgsql security definer set search_path = ''
as $$
declare v_job public.generation_jobs;
begin
  select * into v_job from public.generation_jobs
    where id=p_job_id and status='running' and lease_token=p_lease_token
      and lease_expires_at > now() for update;
  if not found then raise exception 'GENERATION_JOB_LEASE_LOST' using errcode='40001'; end if;
  if coalesce(p_result->>'output_text','')='' or
    (p_result->>'input_tokens')::bigint < 0 or (p_result->>'output_tokens')::bigint < 0 then
    raise exception 'GENERATION_JOB_RESULT_INVALID' using errcode='22023';
  end if;
  update public.generation_jobs set status='succeeded',
    input_tokens=(p_result->>'input_tokens')::bigint,
    output_tokens=(p_result->>'output_tokens')::bigint,
    actual_cost_microunits=(p_result->>'cost_microunits')::bigint,
    output_text=p_result->>'output_text',completed_at=now(),
    lease_token=null,lease_expires_at=null,updated_at=now()
    where id=p_job_id returning * into v_job;
  return jsonb_build_object('job_id',v_job.id,'status',v_job.status);
end;
$$;

create or replace function public.generation_mark_pending_reconciliation(
  p_job_id uuid,p_lease_token uuid,p_reason_code text
) returns jsonb language plpgsql security definer set search_path = ''
as $$
declare v_job public.generation_jobs;
begin
  select * into v_job from public.generation_jobs
    where id=p_job_id and status='running' and lease_token=p_lease_token for update;
  if not found then raise exception 'GENERATION_JOB_LEASE_LOST' using errcode='40001'; end if;
  perform public.credit_ledger_mark_pending(jsonb_build_object(
    'reservation_id',v_job.reservation_id,'reason_code',left(coalesce(p_reason_code,'provider_outcome_unknown'),100)
  ));
  update public.generation_jobs set status='pending_reconciliation',
    error_code=left(coalesce(p_reason_code,'provider_outcome_unknown'),100),
    lease_token=null,lease_expires_at=null,updated_at=now()
    where id=p_job_id returning * into v_job;
  return jsonb_build_object('job_id',v_job.id,'status',v_job.status);
end;
$$;

create or replace function public.generation_mark_failed(
  p_job_id uuid,p_lease_token uuid,p_reason_code text
) returns jsonb language plpgsql security definer set search_path = ''
as $$
declare v_job public.generation_jobs;
begin
  select * into v_job from public.generation_jobs
    where id=p_job_id and status='running' and lease_token=p_lease_token for update;
  if not found then raise exception 'GENERATION_JOB_LEASE_LOST' using errcode='40001'; end if;
  if v_job.allow_definitive_failure_release then
    perform public.credit_ledger_release(jsonb_build_object(
      'reservation_id',v_job.reservation_id,
      'idempotency_key','generation-failure:'||v_job.task_id,
      'policy_version',v_job.policy_version,
      'reason_code',left(coalesce(p_reason_code,'definitive_failure'),100)
    ));
  else
    perform public.credit_ledger_mark_pending(jsonb_build_object(
      'reservation_id',v_job.reservation_id,'reason_code','failure_release_policy_not_approved'
    ));
  end if;
  update public.generation_jobs set status=case when v_job.allow_definitive_failure_release then 'failed' else 'pending_reconciliation' end,
    error_code=left(coalesce(p_reason_code,'definitive_failure'),100),
    completed_at=now(),lease_token=null,lease_expires_at=null,updated_at=now()
    where id=p_job_id returning * into v_job;
  return jsonb_build_object('job_id',v_job.id,'status',v_job.status);
end;
$$;

revoke all on function public.generation_create_job(jsonb),
  public.claim_generation_jobs(uuid,integer,integer),
  public.generation_complete_job(uuid,uuid,jsonb),
  public.generation_mark_pending_reconciliation(uuid,uuid,text),
  public.generation_mark_failed(uuid,uuid,text)
  from public,anon,authenticated;
grant execute on function public.generation_create_job(jsonb),
  public.claim_generation_jobs(uuid,integer,integer),
  public.generation_complete_job(uuid,uuid,jsonb),
  public.generation_mark_pending_reconciliation(uuid,uuid,text),
  public.generation_mark_failed(uuid,uuid,text)
  to service_role;

comment on table public.generation_jobs is 'Durable private AI generation queue; atomic credit reservation precedes enqueue. Expired worker leases become pending_reconciliation and are never automatically replayed.';

commit;

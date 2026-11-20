-- WP-07: persist typed pure-tool inputs atomically with durable Generation Jobs.
-- This migration does not grant private Memory access to External Consumers.
begin;

alter table public.generation_jobs
  add column if not exists tool_inputs jsonb not null default '{}'::jsonb;

do $$
begin
  alter table public.generation_jobs
    add constraint generation_jobs_tool_inputs_object_check
    check (jsonb_typeof(tool_inputs) = 'object');
exception when duplicate_object then
  null;
end;
$$;

create or replace function public.generation_create_job_with_tool_inputs(p_command jsonb)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_result jsonb;
  v_job_id uuid;
  v_inputs jsonb := coalesce(p_command->'tool_inputs', '{}'::jsonb);
  v_job public.generation_jobs;
  v_dependencies text[];
  v_input_keys text[];
  v_skill_snapshot jsonb;
begin
  if jsonb_typeof(v_inputs) <> 'object' then
    raise exception 'GENERATION_TOOL_INPUTS_MUST_BE_OBJECT' using errcode = '22023';
  end if;

  -- The existing function creates the job and reserves credits in one transaction.
  -- This wrapper stores the typed inputs before that transaction becomes visible
  -- to claim_generation_jobs, so a worker cannot claim an input-less job.
  v_result := public.generation_create_job(p_command);
  v_job_id := (v_result->>'job_id')::uuid;
  if v_job_id is null then
    raise exception 'GENERATION_JOB_ID_MISSING' using errcode = '22023';
  end if;

  select * into v_job
  from public.generation_jobs
  where id = v_job_id
  for update;
  if not found then
    raise exception 'GENERATION_JOB_NOT_FOUND' using errcode = 'P0002';
  end if;

  v_skill_snapshot := coalesce(v_job.skill_snapshot, '{}'::jsonb);
  if jsonb_typeof(coalesce(v_skill_snapshot->'tool_dependencies', '[]'::jsonb)) <> 'array' then
    raise exception 'GENERATION_SKILL_TOOL_DEPENDENCIES_INVALID' using errcode = '22023';
  end if;
  select coalesce(array_agg(d.tool_key order by d.tool_key), array[]::text[])
  into v_dependencies
  from jsonb_array_elements_text(coalesce(v_skill_snapshot->'tool_dependencies', '[]'::jsonb)) as d(tool_key);

  select coalesce(array_agg(k.tool_key order by k.tool_key), array[]::text[])
  into v_input_keys
  from jsonb_object_keys(v_inputs) as k(tool_key);

  if v_input_keys is distinct from v_dependencies then
    raise exception 'GENERATION_TOOL_INPUT_KEYS_DO_NOT_MATCH_SKILL' using errcode = '22023';
  end if;

  if coalesce((v_result->>'idempotent_replay')::boolean, false)
     and v_job.tool_inputs is distinct from v_inputs then
    raise exception 'GENERATION_JOB_TOOL_INPUT_IDEMPOTENCY_CONFLICT' using errcode = '23505';
  end if;

  update public.generation_jobs
  set tool_inputs = v_inputs
  where id = v_job_id;

  return v_result;
end;
$$;

revoke all on function public.generation_create_job_with_tool_inputs(jsonb) from public, anon, authenticated;
grant execute on function public.generation_create_job_with_tool_inputs(jsonb) to service_role;

commit;

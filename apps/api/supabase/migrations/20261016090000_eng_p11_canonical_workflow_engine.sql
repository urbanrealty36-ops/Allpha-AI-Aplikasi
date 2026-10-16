-- ENG-P11: canonical PostgreSQL-backed Workflow Engine.
-- Source-only migration. Apply only on the approved isolated non-production target in ENG-P37.
-- This file is not authorization to mutate canonical production or create a paid DB branch.

create table if not exists public.workflow_definitions (
  id uuid primary key default gen_random_uuid(),
  owner_user_id uuid not null references auth.users(id) on delete cascade,
  workflow_key text not null check (workflow_key ~ '^[a-z0-9][a-z0-9._-]{2,79}$'),
  version integer not null check (version > 0),
  definition jsonb not null check (jsonb_typeof(definition) = 'object'),
  digest text not null check (digest ~ '^[a-f0-9]{64}$'),
  status text not null default 'active' check (status in ('active','archived')),
  created_at timestamptz not null default now(),
  unique (owner_user_id, workflow_key, version),
  unique (id, owner_user_id, version)
);
create index if not exists workflow_definitions_owner_updated_idx
  on public.workflow_definitions(owner_user_id, created_at desc);

create table if not exists public.workflow_runs (
  id uuid primary key default gen_random_uuid(),
  owner_user_id uuid not null references auth.users(id) on delete cascade,
  definition_id uuid not null,
  definition_version integer not null check (definition_version > 0),
  status text not null default 'queued' check (status in ('created','queued','running','succeeded','failed','cancelled','timed_out')),
  input_payload jsonb not null default '{}'::jsonb check (jsonb_typeof(input_payload) = 'object'),
  output_payload jsonb check (output_payload is null or jsonb_typeof(output_payload) = 'object'),
  trace_id text not null check (char_length(trace_id) between 1 and 160),
  run_version bigint not null default 1 check (run_version > 0),
  max_runtime_seconds integer not null default 60 check (max_runtime_seconds between 1 and 900),
  cancel_requested boolean not null default false,
  started_at timestamptz,
  completed_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  foreign key (definition_id, owner_user_id, definition_version)
    references public.workflow_definitions(id, owner_user_id, version) on delete restrict,
  unique (id, owner_user_id)
);
create index if not exists workflow_runs_owner_created_idx
  on public.workflow_runs(owner_user_id, created_at desc);
create index if not exists workflow_runs_claim_idx on public.workflow_runs(status, created_at)
  where status in ('queued','running');

create table if not exists public.workflow_steps (
  id uuid primary key default gen_random_uuid(),
  run_id uuid not null references public.workflow_runs(id) on delete cascade,
  owner_user_id uuid not null references auth.users(id) on delete cascade,
  node_key text not null check (char_length(node_key) between 1 and 80),
  node_kind text not null check (node_kind in ('input','constant','pass_through','concat','merge')),
  node_config jsonb not null default '{}'::jsonb check (jsonb_typeof(node_config) = 'object'),
  depends_on text[] not null default '{}',
  status text not null default 'pending' check (status in ('pending','running','retrying','succeeded','failed','cancelled','skipped')),
  attempts integer not null default 0 check (attempts >= 0),
  max_attempts integer not null default 1 check (max_attempts between 1 and 4),
  timeout_seconds integer not null default 5 check (timeout_seconds between 1 and 30),
  lease_token uuid,
  lease_expires_at timestamptz,
  input_payload jsonb check (input_payload is null or jsonb_typeof(input_payload) = 'object'),
  output_payload jsonb check (output_payload is null or jsonb_typeof(output_payload) = 'object'),
  checkpoint jsonb check (checkpoint is null or jsonb_typeof(checkpoint) = 'object'),
  error_code text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  completed_at timestamptz,
  unique (run_id, node_key),
  foreign key (run_id, owner_user_id) references public.workflow_runs(id, owner_user_id) on delete cascade
);
create index if not exists workflow_steps_claim_idx on public.workflow_steps(run_id, status, created_at);
create index if not exists workflow_steps_lease_idx on public.workflow_steps(status, lease_expires_at)
  where status = 'running';

create table if not exists public.workflow_run_events (
  id bigint generated always as identity primary key,
  run_id uuid not null references public.workflow_runs(id) on delete cascade,
  owner_user_id uuid not null references auth.users(id) on delete cascade,
  sequence bigint not null check (sequence > 0),
  event_type text not null check (char_length(event_type) between 1 and 80),
  step_key text,
  details jsonb not null default '{}'::jsonb check (jsonb_typeof(details) = 'object'),
  created_at timestamptz not null default now(),
  unique (run_id, sequence),
  foreign key (run_id, owner_user_id) references public.workflow_runs(id, owner_user_id) on delete cascade
);
create index if not exists workflow_run_events_timeline_idx on public.workflow_run_events(run_id, sequence);

alter table public.workflow_definitions enable row level security;
alter table public.workflow_runs enable row level security;
alter table public.workflow_steps enable row level security;
alter table public.workflow_run_events enable row level security;
revoke all on public.workflow_definitions, public.workflow_runs, public.workflow_steps, public.workflow_run_events from public, anon, authenticated;
grant select, insert on public.workflow_definitions to service_role;
grant select, insert, update on public.workflow_runs to service_role;
grant select, insert, update on public.workflow_steps to service_role;
grant select, insert on public.workflow_run_events to service_role;

create or replace function public.create_workflow_run(
  p_owner_user_id uuid, p_definition_id uuid, p_input_payload jsonb,
  p_trace_id text, p_step_specs jsonb
) returns setof public.workflow_runs
language plpgsql security definer set search_path = ''
as $$
declare
  definition_row public.workflow_definitions%rowtype;
  run_row public.workflow_runs%rowtype;
  spec jsonb;
  seq bigint := 0;
begin
  if jsonb_typeof(p_input_payload) <> 'object' or jsonb_typeof(p_step_specs) <> 'array'
     or jsonb_array_length(p_step_specs) < 1 or jsonb_array_length(p_step_specs) > 50 then
    raise exception 'invalid workflow run payload' using errcode = '22023';
  end if;
  select * into definition_row from public.workflow_definitions d
   where d.id = p_definition_id and d.owner_user_id = p_owner_user_id and d.status = 'active'
   for share;
  if not found then
    return;
  end if;
  insert into public.workflow_runs(owner_user_id, definition_id, definition_version, input_payload,
                                   trace_id, max_runtime_seconds)
  values (p_owner_user_id, definition_row.id, definition_row.version, p_input_payload,
          p_trace_id, least(900, greatest(1, (definition_row.definition->>'max_runtime_seconds')::integer)))
  returning * into run_row;
  for spec in select value from jsonb_array_elements(p_step_specs)
  loop
    seq := seq + 1;
    insert into public.workflow_steps(run_id, owner_user_id, node_key, node_kind, node_config,
      depends_on, max_attempts, timeout_seconds)
    values (run_row.id, p_owner_user_id, spec->>'node_key', spec->>'node_kind',
      coalesce(spec->'node_config','{}'::jsonb),
      array(select jsonb_array_elements_text(coalesce(spec->'depends_on','[]'::jsonb))),
      least(4, greatest(1, (spec->>'max_attempts')::integer)),
      least(30, greatest(1, (spec->>'timeout_seconds')::integer)));
    insert into public.workflow_run_events(run_id, owner_user_id, sequence, event_type, step_key, details)
    values (run_row.id, p_owner_user_id, seq, 'step_created', spec->>'node_key',
            jsonb_build_object('node_kind', spec->>'node_kind'));
  end loop;
  insert into public.workflow_run_events(run_id, owner_user_id, sequence, event_type, details)
  values (run_row.id, p_owner_user_id, seq + 1, 'run_queued', jsonb_build_object('definition_version', definition_row.version));
  return next run_row;
end;
$$;
revoke all on function public.create_workflow_run(uuid, uuid, jsonb, text, jsonb) from public, anon, authenticated;
grant execute on function public.create_workflow_run(uuid, uuid, jsonb, text, jsonb) to service_role;

create or replace function public.cancel_workflow_run(p_run_id uuid, p_owner_user_id uuid)
returns setof public.workflow_runs
language plpgsql security definer set search_path = ''
as $$
declare
  run_row public.workflow_runs%rowtype;
begin
  select * into run_row from public.workflow_runs
   where id = p_run_id and owner_user_id = p_owner_user_id for update;
  if not found or run_row.status in ('succeeded','failed','cancelled','timed_out') then
    return;
  end if;
  update public.workflow_runs set status = 'cancelled', cancel_requested = true,
    completed_at = now(), updated_at = now(), run_version = run_version + 1
   where id = p_run_id and owner_user_id = p_owner_user_id returning * into run_row;
  update public.workflow_steps set status = 'cancelled', lease_token = null, lease_expires_at = null,
    updated_at = now(), completed_at = now()
   where run_id = p_run_id and owner_user_id = p_owner_user_id and status in ('pending','retrying','running');
  insert into public.workflow_run_events(run_id, owner_user_id, sequence, event_type, details)
  select r.id, r.owner_user_id,
    coalesce((select max(e.sequence) from public.workflow_run_events e where e.run_id = r.id),0)+1,
    'run_cancelled', jsonb_build_object('requested_by_owner', true)
  from public.workflow_runs r where r.id = p_run_id and r.owner_user_id = p_owner_user_id;
  return next run_row;
end;
$$;
revoke all on function public.cancel_workflow_run(uuid, uuid) from public, anon, authenticated;
grant execute on function public.cancel_workflow_run(uuid, uuid) to service_role;

create or replace function public.claim_workflow_step(
  p_run_id uuid, p_owner_user_id uuid, p_lease_token uuid, p_lease_seconds integer default 30
) returns setof public.workflow_steps
language plpgsql security definer set search_path = ''
as $$
declare
  step_row public.workflow_steps%rowtype;
begin
  if p_lease_seconds < 5 or p_lease_seconds > 120 then
    raise exception 'workflow lease outside allowed bounds' using errcode = '22023';
  end if;
  select s.* into step_row from public.workflow_steps s
  join public.workflow_runs r on r.id = s.run_id and r.owner_user_id = s.owner_user_id
  where s.run_id = p_run_id and s.owner_user_id = p_owner_user_id
    and r.status in ('queued','running') and not r.cancel_requested
    and (s.status in ('pending','retrying') or (s.status = 'running' and s.lease_expires_at < now()))
    and s.attempts < s.max_attempts
    and not exists (
      select 1 from unnest(s.depends_on) dep
      join public.workflow_steps parent on parent.run_id = s.run_id and parent.node_key = dep
      where parent.status <> 'succeeded'
    )
  order by s.created_at, s.node_key
  for update of s skip locked limit 1;
  if not found then return; end if;
  update public.workflow_steps set status = 'running', attempts = attempts + 1,
    lease_token = p_lease_token, lease_expires_at = now() + make_interval(secs => p_lease_seconds),
    updated_at = now(), completed_at = null
  where id = step_row.id returning * into step_row;
  update public.workflow_runs set status = 'running', started_at = coalesce(started_at, now()),
    updated_at = now(), run_version = run_version + 1 where id = p_run_id;
  return next step_row;
end;
$$;
revoke all on function public.claim_workflow_step(uuid, uuid, uuid, integer) from public, anon, authenticated;
grant execute on function public.claim_workflow_step(uuid, uuid, uuid, integer) to service_role;

create or replace function public.finalize_workflow_step(
  p_run_id uuid, p_owner_user_id uuid, p_step_id uuid, p_lease_token uuid,
  p_terminal_state text, p_output_payload jsonb, p_error_code text, p_checkpoint jsonb
) returns setof public.workflow_steps
language plpgsql security definer set search_path = ''
as $$
declare
  step_row public.workflow_steps%rowtype;
  remaining_count integer;
  failed_count integer;
  next_seq bigint;
begin
  if p_terminal_state not in ('succeeded','failed','retrying') then
    raise exception 'invalid workflow step final state' using errcode = '22023';
  end if;
  select * into step_row from public.workflow_steps s
   where s.id = p_step_id and s.run_id = p_run_id and s.owner_user_id = p_owner_user_id
   for update;
  if not found or step_row.status <> 'running' or step_row.lease_token is distinct from p_lease_token
     or step_row.lease_expires_at is null or step_row.lease_expires_at <= now() then
    raise exception 'stale workflow lease' using errcode = '40001';
  end if;
  if p_terminal_state = 'retrying' and step_row.attempts >= step_row.max_attempts then
    p_terminal_state := 'failed';
  end if;
  update public.workflow_steps set status = p_terminal_state,
    output_payload = case when p_terminal_state = 'succeeded' then p_output_payload else output_payload end,
    checkpoint = case when p_checkpoint is not null then p_checkpoint else checkpoint end,
    error_code = p_error_code, lease_token = null, lease_expires_at = null,
    completed_at = case when p_terminal_state in ('succeeded','failed') then now() else null end,
    updated_at = now() where id = p_step_id returning * into step_row;
  select coalesce(max(sequence),0)+1 into next_seq from public.workflow_run_events where run_id = p_run_id;
  insert into public.workflow_run_events(run_id, owner_user_id, sequence, event_type, step_key, details)
  values (p_run_id, p_owner_user_id, next_seq, 'step_' || p_terminal_state, step_row.node_key,
          jsonb_build_object('attempt', step_row.attempts, 'error_code', p_error_code));
  select count(*) into remaining_count from public.workflow_steps
   where run_id = p_run_id and owner_user_id = p_owner_user_id and status not in ('succeeded','skipped','cancelled');
  select count(*) into failed_count from public.workflow_steps
   where run_id = p_run_id and owner_user_id = p_owner_user_id and status = 'failed';
  if failed_count > 0 then
    update public.workflow_runs set status = 'failed', completed_at = now(), updated_at = now(),
      run_version = run_version + 1 where id = p_run_id and status not in ('cancelled','succeeded');
  elsif remaining_count = 0 then
    update public.workflow_runs set status = 'succeeded', completed_at = now(), updated_at = now(),
      run_version = run_version + 1 where id = p_run_id and status not in ('cancelled','succeeded');
  end if;
  return next step_row;
end;
$$;
revoke all on function public.finalize_workflow_step(uuid, uuid, uuid, uuid, text, jsonb, text, jsonb) from public, anon, authenticated;
grant execute on function public.finalize_workflow_step(uuid, uuid, uuid, uuid, text, jsonb, text, jsonb) to service_role;

comment on table public.workflow_definitions is 'Owner-scoped immutable declarative workflow versions; digest pins content.';
comment on table public.workflow_runs is 'Durable workflow execution lifecycle; definition version and owner are pinned at creation.';
comment on table public.workflow_steps is 'Durable step state, dependency graph, lease fencing, attempts and checkpoints.';
comment on table public.workflow_run_events is 'Append-only per-run ordered lifecycle events for traceability.';

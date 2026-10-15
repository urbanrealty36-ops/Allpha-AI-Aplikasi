-- ENG-P10: durable conversation sessions and bounded Agent task lifecycle.
-- Source-only migration. Execute against the approved isolated target at ENG-P37,
-- never as a production test. Runtime tables are backend-only; clients use FastAPI.
alter table public.ai_agents
  add column if not exists version integer not null default 1 check (version > 0);

alter table public.agent_capabilities
  add column if not exists policy_version text;

create or replace function public.bump_ai_agent_version()
returns trigger
language plpgsql
security invoker
set search_path = ''
as $$
begin
  new.version := old.version + 1;
  new.updated_at := now();
  return new;
end;
$$;
revoke all on function public.bump_ai_agent_version() from public, anon, authenticated;
drop trigger if exists ai_agents_bump_version on public.ai_agents;
create trigger ai_agents_bump_version
  before update on public.ai_agents
  for each row execute function public.bump_ai_agent_version();

create table if not exists public.agent_runtime_sessions (
  id uuid primary key default gen_random_uuid(),
  owner_user_id uuid not null references auth.users(id) on delete cascade,
  agent_id uuid not null references public.ai_agents(id) on delete cascade,
  title text not null default 'Percakapan baru' check (char_length(title) between 1 and 120),
  status text not null default 'active' check (status in ('active','archived','cancelled')),
  metadata jsonb not null default '{}'::jsonb check (jsonb_typeof(metadata) = 'object'),
  last_activity_at timestamptz not null default now(),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (id, owner_user_id)
);
create index if not exists agent_runtime_sessions_owner_activity_idx
  on public.agent_runtime_sessions(owner_user_id, last_activity_at desc);
create index if not exists agent_runtime_sessions_agent_idx
  on public.agent_runtime_sessions(agent_id, created_at desc);

create unique index if not exists agent_skills_id_agent_unique_idx
  on public.agent_skills(id, agent_id);

create table if not exists public.agent_runtime_tasks (
  id uuid primary key default gen_random_uuid(),
  owner_user_id uuid not null references auth.users(id) on delete cascade,
  session_id uuid not null,
  agent_id uuid not null references public.ai_agents(id) on delete cascade,
  skill_id uuid not null references public.agent_skills(id) on delete restrict,
  task_version integer not null default 1 check (task_version > 0),
  agent_version integer not null check (agent_version > 0),
  skill_version integer not null check (skill_version > 0),
  state text not null default 'created' check (state in (
    'created','queued','policy_check','budget_reserved','context_building','planning',
    'executing','validating','succeeded','waiting_for_approval','waiting_for_input',
    'retrying','partially_succeeded','failed','cancelled','timed_out','budget_exhausted'
  )),
  idempotency_key text not null check (char_length(idempotency_key) between 8 and 160),
  request_fingerprint text not null check (request_fingerprint ~ '^[a-f0-9]{64}$'),
  tool_key text not null check (tool_key ~ '^[a-z][a-z0-9_.:-]{2,99}$'),
  input_payload jsonb not null check (jsonb_typeof(input_payload) = 'object'),
  output_payload jsonb check (output_payload is null or jsonb_typeof(output_payload) = 'object'),
  event_log jsonb not null default '[]'::jsonb check (jsonb_typeof(event_log) = 'array'),
  trace_id text not null check (char_length(trace_id) between 8 and 160),
  policy_version text,
  error_code text,
  cancel_requested boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  completed_at timestamptz,
  foreign key (session_id, owner_user_id)
    references public.agent_runtime_sessions(id, owner_user_id) on delete cascade,
  foreign key (skill_id, agent_id)
    references public.agent_skills(id, agent_id) on delete restrict,
  unique (owner_user_id, idempotency_key)
);
create index if not exists agent_runtime_tasks_owner_created_idx
  on public.agent_runtime_tasks(owner_user_id, created_at desc);
create index if not exists agent_runtime_tasks_session_created_idx
  on public.agent_runtime_tasks(session_id, created_at desc);
create index if not exists agent_runtime_tasks_recovery_idx
  on public.agent_runtime_tasks(state, updated_at)
  where state in ('created','queued','executing','retrying','waiting_for_approval','waiting_for_input');

alter table public.agent_runtime_sessions enable row level security;
alter table public.agent_runtime_tasks enable row level security;
revoke all on public.agent_runtime_sessions, public.agent_runtime_tasks from public, anon, authenticated;
grant select, insert, update, delete on public.agent_runtime_sessions, public.agent_runtime_tasks to service_role;

comment on table public.agent_runtime_sessions is
  'Durable owner-scoped Agent conversation sessions. Access only through canonical FastAPI runtime.';
comment on table public.agent_runtime_tasks is
  'Version-pinned durable Agent task lifecycle, idempotency, bounded input/output, trace and recovery metadata; backend-only.';
comment on column public.agent_capabilities.policy_version is
  'Explicit approved runtime policy version; NULL means this capability cannot authorize runtime execution.';

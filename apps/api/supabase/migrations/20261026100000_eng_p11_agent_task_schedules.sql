-- ENG-P11 extension: durable Human Owner task schedules.
alter table public.agent_runtime_tasks
  add column if not exists task_budget_limits jsonb not null default '{}'::jsonb
  check (jsonb_typeof(task_budget_limits) = 'object');
-- Source-only migration. Apply only through the approved ENG-P37 database acceptance gate.
-- This extends the canonical Workflow Engine + Agent Runtime; it is not a parallel queue.

alter table public.workflow_steps drop constraint if exists workflow_steps_node_kind_check;
alter table public.workflow_steps add constraint workflow_steps_node_kind_check
  check (node_kind in ('input','constant','pass_through','concat','merge','agent_task'));

create table if not exists public.agent_task_schedules (
  id uuid primary key default gen_random_uuid(),
  owner_user_id uuid not null references auth.users(id) on delete cascade,
  agent_id uuid not null references public.ai_agents(id) on delete cascade,
  session_id uuid not null,
  workflow_definition_id uuid not null references public.workflow_definitions(id) on delete restrict,
  skill_id uuid not null,
  tool_key text not null check (tool_key ~ '^[a-z][a-z0-9_.:-]{2,99}$'),
  title text not null check (char_length(title) between 1 and 160),
  instructions text not null check (char_length(instructions) between 1 and 8000),
  task_type text not null check (task_type in ('SCHEDULING_POST','BROADCAST_INFO','KNOWLEDGE_DISPATCH','ANALYTICS_REPORT','SKILL_EXECUTION')),
  schedule_kind text not null check (schedule_kind in ('once','daily','weekly')),
  timezone_name text not null check (char_length(timezone_name) between 1 and 80),
  local_time time not null,
  weekdays smallint[] not null default '{}'::smallint[],
  run_at timestamptz,
  next_run_at timestamptz,
  last_run_at timestamptz,
  status text not null default 'active' check (status in ('active','paused','completed','needs_approval','failed','cancelled')),
  require_approval boolean not null default true,
  granted_permission_scopes text[] not null default '{}'::text[],
  budget_limit jsonb not null default '{}'::jsonb check (jsonb_typeof(budget_limit) = 'object'),
  input_payload jsonb not null default '{}'::jsonb check (jsonb_typeof(input_payload) = 'object'),
  last_runtime_task_id uuid references public.agent_runtime_tasks(id) on delete set null,
  last_workflow_run_id uuid references public.workflow_runs(id) on delete set null,
  run_count integer not null default 0 check (run_count >= 0),
  lease_token uuid,
  lease_expires_at timestamptz,
  version bigint not null default 1 check (version > 0),
  created_by_agent_version integer not null check (created_by_agent_version > 0),
  created_by_skill_version integer not null check (created_by_skill_version > 0),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  foreign key (session_id, owner_user_id)
    references public.agent_runtime_sessions(id, owner_user_id) on delete cascade,
  foreign key (skill_id, agent_id)
    references public.agent_skills(id, agent_id) on delete restrict,
  check (
    (schedule_kind = 'once' and run_at is not null and cardinality(weekdays) = 0)
    or (schedule_kind = 'daily' and run_at is null and cardinality(weekdays) = 0)
    or (schedule_kind = 'weekly' and run_at is null and cardinality(weekdays) between 1 and 7)
  ),
  check (weekdays <@ array[0,1,2,3,4,5,6]::smallint[])
);
create unique index if not exists workflow_runs_agent_schedule_trace_uidx
  on public.workflow_runs(owner_user_id, trace_id)
  where trace_id like 'agent-task-schedule:%';

create index if not exists agent_task_schedules_due_idx
  on public.agent_task_schedules(next_run_at, id)
  where status = 'active' and next_run_at is not null;
create index if not exists agent_task_schedules_owner_idx
  on public.agent_task_schedules(owner_user_id, created_at desc);
create index if not exists agent_task_schedules_lease_idx
  on public.agent_task_schedules(lease_expires_at)
  where lease_token is not null;

create table if not exists public.agent_task_schedule_runs (
  id uuid primary key default gen_random_uuid(),
  schedule_id uuid not null references public.agent_task_schedules(id) on delete cascade,
  owner_user_id uuid not null references auth.users(id) on delete cascade,
  scheduled_for timestamptz not null,
  runtime_task_id uuid references public.agent_runtime_tasks(id) on delete set null,
  workflow_run_id uuid references public.workflow_runs(id) on delete set null,
  status text not null default 'claimed' check (status in ('claimed','waiting_for_approval','queued','running','succeeded','partially_succeeded','failed','timed_out','cancelled','outcome_unknown')),
  idempotency_key text not null check (char_length(idempotency_key) between 8 and 160),
  trace_id text not null check (char_length(trace_id) between 8 and 160),
  approved_at timestamptz,
  approved_by uuid references auth.users(id) on delete set null,
  result_summary text check (result_summary is null or char_length(result_summary) <= 2000),
  error_code text,
  started_at timestamptz,
  completed_at timestamptz,
  created_at timestamptz not null default now(),
  unique (schedule_id, scheduled_for),
  unique (owner_user_id, idempotency_key),
  check ((approved_at is null and approved_by is null) or (approved_at is not null and approved_by is not null))
);
create index if not exists agent_task_schedule_runs_owner_idx
  on public.agent_task_schedule_runs(owner_user_id, created_at desc);
create index if not exists agent_task_schedule_runs_schedule_idx
  on public.agent_task_schedule_runs(schedule_id, scheduled_for desc);

alter table public.agent_task_schedules enable row level security;
alter table public.agent_task_schedule_runs enable row level security;
revoke all on public.agent_task_schedules, public.agent_task_schedule_runs from public, anon, authenticated;
grant select, insert, update, delete on public.agent_task_schedules, public.agent_task_schedule_runs to service_role;

create or replace function public.claim_due_agent_task_schedules(
  p_lease_token uuid,
  p_limit integer default 25,
  p_lease_seconds integer default 60
) returns setof public.agent_task_schedules
language plpgsql security definer set search_path = ''
as $$
begin
  if p_limit < 1 or p_limit > 100 or p_lease_seconds < 5 or p_lease_seconds > 300 then
    raise exception 'schedule claim bounds invalid' using errcode = '22023';
  end if;
  return query
    with due as (
      select s.id
      from public.agent_task_schedules s
      where s.status = 'active'
        and s.next_run_at is not null
        and s.next_run_at <= now()
        and (s.lease_token is null or s.lease_expires_at < now())
      order by s.next_run_at, s.id
      for update skip locked
      limit p_limit
    )
    update public.agent_task_schedules s
       set lease_token = p_lease_token,
           lease_expires_at = now() + make_interval(secs => p_lease_seconds),
           updated_at = now(),
           version = s.version + 1
      from due
     where s.id = due.id
    returning s.*;
end;
$$;
revoke all on function public.claim_due_agent_task_schedules(uuid, integer, integer) from public, anon, authenticated;
grant execute on function public.claim_due_agent_task_schedules(uuid, integer, integer) to service_role;

comment on table public.agent_task_schedules is
  'Durable owner-defined AI Agent task schedules. Actual execution must be dispatched through the canonical Agent Runtime and Workflow Engine after live policy checks.';
comment on table public.agent_task_schedule_runs is
  'Idempotent per-occurrence execution records with trace, real runtime/workflow IDs, outcome and summary; never synthesize success.';

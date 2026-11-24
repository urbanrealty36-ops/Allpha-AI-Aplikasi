-- WP-07 / ENG-P10: durable idempotent reservations for Model Router generated tool plans.
-- Source-only migration. Do not apply to production until the WP-07 database review gate.
-- Depends on the canonical ENG-P10 sessions/tasks/skills schema and keeps all access behind FastAPI.
begin;

create table if not exists public.agent_runtime_tool_plans (
  id uuid primary key default gen_random_uuid(),
  owner_user_id uuid not null references auth.users(id) on delete cascade,
  agent_id uuid not null references public.ai_agents(id) on delete cascade,
  session_id uuid not null,
  skill_id uuid not null,
  agent_version integer not null check (agent_version > 0),
  skill_version integer not null check (skill_version > 0),
  idempotency_key text not null check (char_length(idempotency_key) between 8 and 160),
  request_fingerprint text not null check (request_fingerprint ~ '^[0-9a-f]{64}$'),
  intent_sha256 text not null check (intent_sha256 ~ '^[0-9a-f]{64}$'),
  trace_id text not null check (char_length(trace_id) between 8 and 160),
  status text not null default 'planning'
    check (status in ('planning','completed','failed','outcome_unknown','used','expired')),
  tool_plan jsonb,
  planner_evidence jsonb,
  memory_context_refs jsonb not null default '[]'::jsonb
    check (jsonb_typeof(memory_context_refs) = 'array'
      and jsonb_array_length(memory_context_refs) <= 8
      and octet_length(memory_context_refs::text) <= 16384),
  memory_context_sha256 text not null
    default '4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945'
    check (memory_context_sha256 ~ '^[0-9a-f]{64}$'),
  knowledge_context_refs jsonb not null default '[]'::jsonb
    check (jsonb_typeof(knowledge_context_refs) = 'array'
      and jsonb_array_length(knowledge_context_refs) <= 8
      and octet_length(knowledge_context_refs::text) <= 16384),
  knowledge_context_sha256 text not null
    default '4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945'
    check (knowledge_context_sha256 ~ '^[0-9a-f]{64}$'),
  knowledge_context_state text not null default 'not_configured'
    check (knowledge_context_state in ('not_configured','empty','available')),
  error_code text check (error_code is null or char_length(error_code) between 1 and 120),
  task_id uuid references public.agent_runtime_tasks(id) on delete cascade,
  expires_at timestamptz not null default (now() + interval '10 minutes'),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (owner_user_id, idempotency_key),
  foreign key (session_id, owner_user_id)
    references public.agent_runtime_sessions(id, owner_user_id) on delete cascade,
  foreign key (skill_id, agent_id)
    references public.agent_skills(id, agent_id) on delete restrict,
  check (tool_plan is null or (jsonb_typeof(tool_plan) = 'array' and octet_length(tool_plan::text) <= 65536)),
  check (planner_evidence is null or (jsonb_typeof(planner_evidence) = 'object' and octet_length(planner_evidence::text) <= 32768)),
  check (status <> 'completed' or (tool_plan is not null and planner_evidence is not null)),
);

create index if not exists agent_runtime_tool_plans_owner_status_idx
  on public.agent_runtime_tool_plans(owner_user_id, status, expires_at desc);
create index if not exists agent_runtime_tool_plans_session_idx
  on public.agent_runtime_tool_plans(session_id, created_at desc);

create or replace function public.guard_agent_runtime_tool_plan_update()
returns trigger
language plpgsql
security invoker
set search_path = ''
as $$
begin
  if new.id is distinct from old.id
    or new.owner_user_id is distinct from old.owner_user_id
    or new.agent_id is distinct from old.agent_id
    or new.session_id is distinct from old.session_id
    or new.skill_id is distinct from old.skill_id
    or new.agent_version is distinct from old.agent_version
    or new.skill_version is distinct from old.skill_version
    or new.idempotency_key is distinct from old.idempotency_key
    or new.request_fingerprint is distinct from old.request_fingerprint
    or new.intent_sha256 is distinct from old.intent_sha256
    or new.trace_id is distinct from old.trace_id
    or new.memory_context_refs is distinct from old.memory_context_refs
    or new.memory_context_sha256 is distinct from old.memory_context_sha256
    or new.knowledge_context_refs is distinct from old.knowledge_context_refs
    or new.knowledge_context_sha256 is distinct from old.knowledge_context_sha256
    or new.knowledge_context_state is distinct from old.knowledge_context_state
    or new.expires_at is distinct from old.expires_at
    or new.created_at is distinct from old.created_at then
    raise exception 'agent_runtime_tool_plan_reservation_is_immutable' using errcode = '42501';
  end if;

  if old.status = 'planning' and new.status not in ('planning','completed','failed','outcome_unknown','expired') then
    raise exception 'agent_runtime_tool_plan_transition_denied' using errcode = '42501';
  elsif old.status = 'completed' and new.status not in ('completed','used','expired') then
    raise exception 'agent_runtime_tool_plan_transition_denied' using errcode = '42501';
  elsif old.status not in ('planning','completed') and new.status is distinct from old.status then
    raise exception 'agent_runtime_tool_plan_terminal_state' using errcode = '42501';
  end if;

  if old.status <> 'planning'
    and (new.tool_plan is distinct from old.tool_plan
      or new.planner_evidence is distinct from old.planner_evidence) then
    raise exception 'agent_runtime_tool_plan_result_is_immutable' using errcode = '42501';
  end if;

  if old.task_id is not null and new.task_id is distinct from old.task_id then
    raise exception 'agent_runtime_tool_plan_task_binding_is_immutable' using errcode = '42501';
  end if;
  if new.status = 'used' and new.task_id is null then
    raise exception 'agent_runtime_tool_plan_task_binding_required' using errcode = '23514';
  end if;
  return new;
end;
$$;

drop trigger if exists agent_runtime_tool_plan_update_guard on public.agent_runtime_tool_plans;
create trigger agent_runtime_tool_plan_update_guard
before update on public.agent_runtime_tool_plans
for each row execute function public.guard_agent_runtime_tool_plan_update();

alter table public.agent_runtime_tool_plans enable row level security;
revoke all on public.agent_runtime_tool_plans from public, anon, authenticated;
grant select, insert, update on public.agent_runtime_tool_plans to service_role;
revoke all on function public.guard_agent_runtime_tool_plan_update() from public, anon, authenticated;

comment on table public.agent_runtime_tool_plans is
  'Owner-scoped durable Model Router tool-plan reservations. Raw user intent, private memory and knowledge text are not stored; only digests, validated tool plans, sanitized planner evidence and content-free citations are retained.';
comment on column public.agent_runtime_tool_plans.memory_context_refs is
  'Bounded non-content provenance references for owner-consented Memory items used by the planner.';
comment on column public.agent_runtime_tool_plans.memory_context_sha256 is
  'Digest of the bounded Memory context supplied to the planner; raw Memory text is never persisted here.';
comment on column public.agent_runtime_tool_plans.knowledge_context_refs is
  'Bounded content-free source/chunk/version/digest citations for owner-authorized Knowledge context; raw document text is never persisted here.';
comment on column public.agent_runtime_tool_plans.knowledge_context_sha256 is
  'Digest of the bounded Knowledge context supplied to the planner; raw document text is never persisted here.';

commit;

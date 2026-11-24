-- WP-07: durable idempotent reservations for Model Router generated tool plans.
-- Source-only migration. Do not apply to production until the WP-07 database review gate.
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
    check (jsonb_typeof(memory_context_refs)='array'),
  memory_context_sha256 text not null
    default '4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945'
    check (memory_context_sha256 ~ '^[0-9a-f]{64}  error_code text,
  task_id uuid references public.agent_runtime_tasks(id) on delete set null,
  expires_at timestamptz not null default (now() + interval '10 minutes'),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (owner_user_id, idempotency_key),
  foreign key (session_id, owner_user_id)
    references public.agent_runtime_sessions(id, owner_user_id) on delete cascade,
  foreign key (skill_id, agent_id)
    references public.agent_skills(id, agent_id) on delete restrict,
  check (tool_plan is null or jsonb_typeof(tool_plan)='array'),
  check (planner_evidence is null or jsonb_typeof(planner_evidence)='object')
);

create index if not exists agent_runtime_tool_plans_owner_status_idx
  on public.agent_runtime_tool_plans(owner_user_id, status, expires_at desc);
create index if not exists agent_runtime_tool_plans_session_idx
  on public.agent_runtime_tool_plans(session_id, created_at desc);

alter table public.agent_runtime_tool_plans enable row level security;
revoke all on public.agent_runtime_tool_plans from public, anon, authenticated;
grant all on public.agent_runtime_tool_plans to service_role;

comment on table public.agent_runtime_tool_plans is
  'Owner-scoped durable Model Router tool plans. Raw user intent and private Memory are not stored; only its digest, validated plan, and sanitized metering evidence are retained.';
comment on column public.agent_runtime_tool_plans.memory_context_refs is
  'Non-content provenance references for owner-consented Memory items used by the planner.';
comment on column public.agent_runtime_tool_plans.memory_context_sha256 is
  'Digest of the bounded Memory context supplied to the planner; raw Memory text is never persisted here.';
comment on column public.agent_runtime_tool_plans.knowledge_context_refs is
  'Content-free source/chunk/version/digest citations for owner-authorized Knowledge context; raw document text is never persisted here.';
comment on column public.agent_runtime_tool_plans.knowledge_context_sha256 is
  'Digest of the bounded Knowledge context supplied to the planner; raw document text is never persisted here.';

commit;
),
  knowledge_context_refs jsonb not null default '[]'::jsonb
    check (jsonb_typeof(knowledge_context_refs)='array'),
  knowledge_context_sha256 text not null
    default '4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945'
    check (knowledge_context_sha256 ~ '^[0-9a-f]{64}  error_code text,
  task_id uuid references public.agent_runtime_tasks(id) on delete set null,
  expires_at timestamptz not null default (now() + interval '10 minutes'),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (owner_user_id, idempotency_key),
  foreign key (session_id, owner_user_id)
    references public.agent_runtime_sessions(id, owner_user_id) on delete cascade,
  foreign key (skill_id, agent_id)
    references public.agent_skills(id, agent_id) on delete restrict,
  check (tool_plan is null or jsonb_typeof(tool_plan)='array'),
  check (planner_evidence is null or jsonb_typeof(planner_evidence)='object')
);

create index if not exists agent_runtime_tool_plans_owner_status_idx
  on public.agent_runtime_tool_plans(owner_user_id, status, expires_at desc);
create index if not exists agent_runtime_tool_plans_session_idx
  on public.agent_runtime_tool_plans(session_id, created_at desc);

alter table public.agent_runtime_tool_plans enable row level security;
revoke all on public.agent_runtime_tool_plans from public, anon, authenticated;
grant all on public.agent_runtime_tool_plans to service_role;

comment on table public.agent_runtime_tool_plans is
  'Owner-scoped durable Model Router tool plans. Raw user intent and private Memory are not stored; only its digest, validated plan, and sanitized metering evidence are retained.';
comment on column public.agent_runtime_tool_plans.memory_context_refs is
  'Non-content provenance references for owner-consented Memory items used by the planner.';
comment on column public.agent_runtime_tool_plans.memory_context_sha256 is
  'Digest of the bounded Memory context supplied to the planner; raw Memory text is never persisted here.';

commit;
),
  knowledge_context_state text not null default 'not_configured'
    check (knowledge_context_state in ('not_configured','empty','available')),
  error_code text,
  task_id uuid references public.agent_runtime_tasks(id) on delete set null,
  expires_at timestamptz not null default (now() + interval '10 minutes'),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (owner_user_id, idempotency_key),
  foreign key (session_id, owner_user_id)
    references public.agent_runtime_sessions(id, owner_user_id) on delete cascade,
  foreign key (skill_id, agent_id)
    references public.agent_skills(id, agent_id) on delete restrict,
  check (tool_plan is null or jsonb_typeof(tool_plan)='array'),
  check (planner_evidence is null or jsonb_typeof(planner_evidence)='object')
);

create index if not exists agent_runtime_tool_plans_owner_status_idx
  on public.agent_runtime_tool_plans(owner_user_id, status, expires_at desc);
create index if not exists agent_runtime_tool_plans_session_idx
  on public.agent_runtime_tool_plans(session_id, created_at desc);

alter table public.agent_runtime_tool_plans enable row level security;
revoke all on public.agent_runtime_tool_plans from public, anon, authenticated;
grant all on public.agent_runtime_tool_plans to service_role;

comment on table public.agent_runtime_tool_plans is
  'Owner-scoped durable Model Router tool plans. Raw user intent and private Memory are not stored; only its digest, validated plan, and sanitized metering evidence are retained.';
comment on column public.agent_runtime_tool_plans.memory_context_refs is
  'Non-content provenance references for owner-consented Memory items used by the planner.';
comment on column public.agent_runtime_tool_plans.memory_context_sha256 is
  'Digest of the bounded Memory context supplied to the planner; raw Memory text is never persisted here.';

commit;

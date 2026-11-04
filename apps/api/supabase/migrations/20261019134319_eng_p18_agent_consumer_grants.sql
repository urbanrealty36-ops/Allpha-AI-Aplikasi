-- ENG-P18 durable owner-approved Consumer grants for public Agent messaging.
-- Additive, forward-only schema change. Consumer grants never grant owner-memory access.
create table if not exists public.agent_consumer_grants (
  id uuid primary key default gen_random_uuid(),
  requester_user_id uuid not null references auth.users(id) on delete cascade,
  owner_user_id uuid not null references auth.users(id) on delete cascade,
  agent_id uuid not null references public.ai_agents(id) on delete cascade,
  agent_version integer not null check (agent_version > 0),
  skill_id uuid not null references public.agent_skills(id) on delete cascade,
  skill_version integer not null check (skill_version > 0),
  runtime_policy_version text not null check (length(runtime_policy_version) between 1 and 120),
  granted_scopes text[] not null default array['public_invoke']::text[],
  status text not null default 'active' check (status in ('active','revoked')),
  idempotency_key text not null check (length(idempotency_key) between 1 and 256),
  expires_at timestamptz,
  granted_by uuid not null references auth.users(id) on delete restrict,
  granted_at timestamptz not null default now(),
  revoked_by uuid references auth.users(id) on delete restrict,
  revoked_at timestamptz,
  revoke_reason text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint agent_consumer_grant_not_owner check (requester_user_id <> owner_user_id),
  constraint agent_consumer_grant_scopes check (
    cardinality(granted_scopes) > 0
    and granted_scopes <@ array['public_invoke']::text[]
  ),
  constraint agent_consumer_grant_revocation check (
    (status = 'active' and revoked_by is null and revoked_at is null and revoke_reason is null)
    or (status = 'revoked' and revoked_by is not null and revoked_at is not null)
  ),
  constraint agent_consumer_grant_idempotency unique (owner_user_id, idempotency_key)
);
create index if not exists agent_consumer_grants_lookup_idx
  on public.agent_consumer_grants(requester_user_id, agent_id, skill_id, status, expires_at);
create index if not exists agent_consumer_grants_owner_idx
  on public.agent_consumer_grants(owner_user_id, agent_id, status, granted_at desc);
create unique index if not exists agent_consumer_grants_one_active_version
  on public.agent_consumer_grants(requester_user_id, agent_id, agent_version, skill_id, skill_version)
  where status = 'active';

alter table public.agent_consumer_grants enable row level security;
revoke all on table public.agent_consumer_grants from public, anon, authenticated;
grant select, insert, update on table public.agent_consumer_grants to service_role;

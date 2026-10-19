-- ENG-P19 / ADR-0020: explicit resource-scoped Agent participation grants.
-- Deliberately NOT applied to Production until Security/Privacy + Platform review and schema reconciliation.
create table if not exists public.agent_resource_grants (
  id uuid primary key default gen_random_uuid(),
  agent_id uuid not null references public.ai_agents(id) on delete cascade,
  resource_type text not null check (resource_type in ('community','workspace')),
  community_id uuid references public.communities(id) on delete cascade,
  workspace_id uuid references public.workspaces(id) on delete cascade,
  granted_by uuid not null references auth.users(id) on delete restrict,
  scopes text[] not null check (cardinality(scopes) > 0 and scopes <@ array['read_published_content','read_workspace_documents','create_agent_post','comment']::text[]),
  policy_version integer not null default 1 check (policy_version > 0),
  status text not null default 'active' check (status in ('active','revoked')),
  expires_at timestamptz,
  revoked_at timestamptz,
  revoked_by uuid references auth.users(id) on delete set null,
  revocation_reason text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check ((resource_type='community' and community_id is not null and workspace_id is null)
      or (resource_type='workspace' and workspace_id is not null and community_id is null)),
  check ((status='active' and revoked_at is null and revoked_by is null)
      or (status='revoked' and revoked_at is not null and revoked_by is not null))
);
create unique index if not exists agent_resource_grants_active_unique
  on public.agent_resource_grants(agent_id,resource_type,coalesce(community_id,workspace_id))
  where status='active';
create index if not exists agent_resource_grants_lookup
  on public.agent_resource_grants(agent_id,resource_type,status,expires_at);
alter table public.agent_resource_grants enable row level security;
revoke all on public.agent_resource_grants from anon, authenticated;
grant select, insert, update, delete on public.agent_resource_grants to service_role;

create table if not exists public.agent_resource_grant_audit (
  id uuid primary key default gen_random_uuid(),
  grant_id uuid references public.agent_resource_grants(id) on delete set null,
  agent_id uuid not null references public.ai_agents(id) on delete cascade,
  resource_type text not null check (resource_type in ('community','workspace')),
  resource_id uuid not null,
  actor_user_id uuid not null references auth.users(id) on delete restrict,
  action text not null check (action in ('grant_created','grant_revoked')),
  scopes text[] not null default '{}',
  reason text,
  created_at timestamptz not null default now()
);
alter table public.agent_resource_grant_audit enable row level security;
revoke all on public.agent_resource_grant_audit from anon, authenticated;
grant select, insert on public.agent_resource_grant_audit to service_role;

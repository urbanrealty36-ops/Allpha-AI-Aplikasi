-- ENG-P06: owner-scoped Agent Skills and declared capabilities.
-- Source-only migration for ENG-P06 implementation; apply through the official
-- migration lifecycle during the approved integration/release process, never as a test on production.

create table if not exists public.agent_skills (
  id uuid primary key default gen_random_uuid(),
  agent_id uuid not null references public.ai_agents(id) on delete cascade,
  created_by uuid not null references auth.users(id) on delete restrict,
  slug text not null check (slug ~ '^[a-z0-9][a-z0-9_-]{2,59}$'),
  name text not null check (char_length(name) between 2 and 100),
  description text not null default '' check (char_length(description) <= 2000),
  category text not null default 'general' check (char_length(category) between 2 and 60),
  inputs_schema jsonb not null default '{"type":"object"}'::jsonb check (jsonb_typeof(inputs_schema) = 'object'),
  outputs_schema jsonb not null default '{"type":"object"}'::jsonb check (jsonb_typeof(outputs_schema) = 'object'),
  instructions text not null default '' check (char_length(instructions) <= 12000),
  constraints jsonb not null default '{}'::jsonb check (jsonb_typeof(constraints) = 'object'),
  tool_dependencies text[] not null default '{}',
  required_permission_scopes text[] not null default '{}',
  model_requirements jsonb not null default '{}'::jsonb check (jsonb_typeof(model_requirements) = 'object'),
  budget_limits jsonb not null default '{"max_runtime_seconds":30,"max_tool_calls":5}'::jsonb check (jsonb_typeof(budget_limits) = 'object'),
  tests jsonb not null default '[]'::jsonb check (jsonb_typeof(tests) = 'array'),
  evaluation_rubric jsonb not null default '{}'::jsonb check (jsonb_typeof(evaluation_rubric) = 'object'),
  provenance jsonb not null default '{}'::jsonb check (jsonb_typeof(provenance) = 'object'),
  version integer not null default 1 check (version > 0),
  changelog text not null default '' check (char_length(changelog) <= 2000),
  publication_terms jsonb not null default '{}'::jsonb check (jsonb_typeof(publication_terms) = 'object'),
  status text not null default 'draft' check (status in ('draft','published','archived')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (agent_id, slug)
);

create table if not exists public.agent_capabilities (
  id uuid primary key default gen_random_uuid(),
  agent_id uuid not null references public.ai_agents(id) on delete cascade,
  created_by uuid not null references auth.users(id) on delete restrict,
  capability_key text not null check (capability_key ~ '^[a-z][a-z0-9_.:-]{2,99}$'),
  description text not null default '' check (char_length(description) <= 1000),
  required_permission_scopes text[] not null default '{}',
  risk_level text not null default 'low' check (risk_level in ('low','medium','high','critical')),
  status text not null default 'requested' check (status in ('requested','approved','denied','revoked')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (agent_id, capability_key)
);

create index if not exists agent_skills_agent_status_updated_idx
  on public.agent_skills(agent_id, status, updated_at desc);
create index if not exists agent_capabilities_agent_status_idx
  on public.agent_capabilities(agent_id, status, created_at desc);

alter table public.agent_skills enable row level security;
alter table public.agent_capabilities enable row level security;

drop policy if exists agent_skills_owner_select on public.agent_skills;
create policy agent_skills_owner_select on public.agent_skills
  for select to authenticated using (
    exists (
      select 1 from public.agent_ownerships o
      where o.agent_id = agent_skills.agent_id
        and o.owner_user_id = (select auth.uid())
        and o.ownership_role = 'owner' and o.status = 'active'
    )
  );
drop policy if exists agent_skills_owner_insert on public.agent_skills;
create policy agent_skills_owner_insert on public.agent_skills
  for insert to authenticated with check (
    created_by = (select auth.uid()) and exists (
      select 1 from public.agent_ownerships o
      where o.agent_id = agent_skills.agent_id
        and o.owner_user_id = (select auth.uid())
        and o.ownership_role = 'owner' and o.status = 'active'
    )
  );
drop policy if exists agent_skills_owner_update on public.agent_skills;
create policy agent_skills_owner_update on public.agent_skills
  for update to authenticated using (
    exists (
      select 1 from public.agent_ownerships o
      where o.agent_id = agent_skills.agent_id
        and o.owner_user_id = (select auth.uid())
        and o.ownership_role = 'owner' and o.status = 'active'
    )
  ) with check (
    created_by = (select auth.uid()) and exists (
      select 1 from public.agent_ownerships o
      where o.agent_id = agent_skills.agent_id
        and o.owner_user_id = (select auth.uid())
        and o.ownership_role = 'owner' and o.status = 'active'
    )
  );
drop policy if exists agent_skills_owner_delete on public.agent_skills;
create policy agent_skills_owner_delete on public.agent_skills
  for delete to authenticated using (
    exists (
      select 1 from public.agent_ownerships o
      where o.agent_id = agent_skills.agent_id
        and o.owner_user_id = (select auth.uid())
        and o.ownership_role = 'owner' and o.status = 'active'
    )
  );

drop policy if exists agent_capabilities_owner_select on public.agent_capabilities;
create policy agent_capabilities_owner_select on public.agent_capabilities
  for select to authenticated using (
    exists (
      select 1 from public.agent_ownerships o
      where o.agent_id = agent_capabilities.agent_id
        and o.owner_user_id = (select auth.uid())
        and o.ownership_role = 'owner' and o.status = 'active'
    )
  );
drop policy if exists agent_capabilities_owner_insert on public.agent_capabilities;
create policy agent_capabilities_owner_insert on public.agent_capabilities
  for insert to authenticated with check (
    created_by = (select auth.uid()) and status = 'requested' and exists (
      select 1 from public.agent_ownerships o
      where o.agent_id = agent_capabilities.agent_id
        and o.owner_user_id = (select auth.uid())
        and o.ownership_role = 'owner' and o.status = 'active'
    )
  );
drop policy if exists agent_capabilities_owner_update on public.agent_capabilities;
create policy agent_capabilities_owner_update on public.agent_capabilities
  for update to authenticated using (
    exists (
      select 1 from public.agent_ownerships o
      where o.agent_id = agent_capabilities.agent_id
        and o.owner_user_id = (select auth.uid())
        and o.ownership_role = 'owner' and o.status = 'active'
    )
  ) with check (
    created_by = (select auth.uid()) and status in ('requested','revoked') and exists (
      select 1 from public.agent_ownerships o
      where o.agent_id = agent_capabilities.agent_id
        and o.owner_user_id = (select auth.uid())
        and o.ownership_role = 'owner' and o.status = 'active'
    )
  );

revoke all on public.agent_skills, public.agent_capabilities from anon, public;
grant select, insert, update, delete on public.agent_skills to authenticated;
grant select, insert, update on public.agent_capabilities to authenticated;

comment on table public.agent_skills is 'Owner-scoped, versioned reusable Agent procedures; skill declarations never grant runtime authority.';
comment on table public.agent_capabilities is 'Owner-declared capability requests; requested/approved status does not bypass runtime policy authorization.';

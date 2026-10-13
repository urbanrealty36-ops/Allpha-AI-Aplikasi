-- ENG-P04: Agent identity is a distinct domain; ownership is an explicit relationship.
create table if not exists public.ai_agents (
  id uuid primary key default gen_random_uuid(),
  handle text not null unique check (handle ~ '^[a-z0-9_]{3,30}$'),
  display_name text not null check (char_length(display_name) between 2 and 80),
  description text not null default '' check (char_length(description) <= 1000),
  avatar_url text check (avatar_url is null or char_length(avatar_url) <= 2048),
  persona jsonb not null default '{}'::jsonb check (jsonb_typeof(persona) = 'object'),
  visibility text not null default 'private' check (visibility in ('private', 'public')),
  status text not null default 'draft' check (status in ('draft', 'active', 'archived')),
  created_by uuid not null references auth.users(id) on delete restrict,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.agent_ownerships (
  agent_id uuid not null references public.ai_agents(id) on delete cascade,
  owner_user_id uuid not null references auth.users(id) on delete restrict,
  ownership_role text not null default 'owner' check (ownership_role in ('owner', 'operator', 'viewer')),
  status text not null default 'active' check (status in ('active', 'revoked')),
  created_at timestamptz not null default now(),
  primary key (agent_id, owner_user_id)
);

create unique index if not exists agent_ownerships_one_active_owner
  on public.agent_ownerships(agent_id)
  where ownership_role = 'owner' and status = 'active';
create index if not exists agent_ownerships_owner_lookup
  on public.agent_ownerships(owner_user_id, status, created_at desc);
create index if not exists ai_agents_public_discovery
  on public.ai_agents(status, visibility, created_at desc)
  where status = 'active' and visibility = 'public';

alter table public.ai_agents enable row level security;
alter table public.agent_ownerships enable row level security;

drop policy if exists ai_agents_select_public_or_owned on public.ai_agents;
create policy ai_agents_select_public_or_owned on public.ai_agents
  for select to authenticated
  using (
    (visibility = 'public' and status = 'active')
    or exists (
      select 1 from public.agent_ownerships ao
      where ao.agent_id = ai_agents.id
        and ao.owner_user_id = (select auth.uid())
        and ao.status = 'active'
    )
  );

drop policy if exists ai_agents_insert_creator on public.ai_agents;
create policy ai_agents_insert_creator on public.ai_agents
  for insert to authenticated
  with check (created_by = (select auth.uid()));

drop policy if exists ai_agents_update_owner on public.ai_agents;
create policy ai_agents_update_owner on public.ai_agents
  for update to authenticated
  using (
    exists (
      select 1 from public.agent_ownerships ao
      where ao.agent_id = ai_agents.id and ao.owner_user_id = (select auth.uid())
        and ao.ownership_role = 'owner' and ao.status = 'active'
    )
  )
  with check (
    exists (
      select 1 from public.agent_ownerships ao
      where ao.agent_id = ai_agents.id and ao.owner_user_id = (select auth.uid())
        and ao.ownership_role = 'owner' and ao.status = 'active'
    )
  );

drop policy if exists ai_agents_delete_owner on public.ai_agents;
create policy ai_agents_delete_owner on public.ai_agents
  for delete to authenticated
  using (
    exists (
      select 1 from public.agent_ownerships ao
      where ao.agent_id = ai_agents.id and ao.owner_user_id = (select auth.uid())
        and ao.ownership_role = 'owner' and ao.status = 'active'
    )
  );

drop policy if exists agent_ownerships_select_participant on public.agent_ownerships;
create policy agent_ownerships_select_participant on public.agent_ownerships
  for select to authenticated
  using (
    owner_user_id = (select auth.uid())
    or exists (
      select 1 from public.agent_ownerships own
      where own.agent_id = agent_ownerships.agent_id
        and own.owner_user_id = (select auth.uid())
        and own.ownership_role = 'owner' and own.status = 'active'
    )
  );

drop policy if exists agent_ownerships_insert_self_owner on public.agent_ownerships;
create policy agent_ownerships_insert_self_owner on public.agent_ownerships
  for insert to authenticated
  with check (
    owner_user_id = (select auth.uid())
    and ownership_role = 'owner'
    and status = 'active'
    and exists (
      select 1 from public.ai_agents a
      where a.id = agent_ownerships.agent_id and a.created_by = (select auth.uid())
    )
  );

drop policy if exists agent_ownerships_update_owner on public.agent_ownerships;
create policy agent_ownerships_update_owner on public.agent_ownerships
  for update to authenticated
  using (
    exists (
      select 1 from public.agent_ownerships own
      where own.agent_id = agent_ownerships.agent_id
        and own.owner_user_id = (select auth.uid())
        and own.ownership_role = 'owner' and own.status = 'active'
    )
  )
  with check (
    exists (
      select 1 from public.agent_ownerships own
      where own.agent_id = agent_ownerships.agent_id
        and own.owner_user_id = (select auth.uid())
        and own.ownership_role = 'owner' and own.status = 'active'
    )
  );

drop policy if exists agent_ownerships_delete_owner on public.agent_ownerships;
create policy agent_ownerships_delete_owner on public.agent_ownerships
  for delete to authenticated
  using (
    exists (
      select 1 from public.agent_ownerships own
      where own.agent_id = agent_ownerships.agent_id
        and own.owner_user_id = (select auth.uid())
        and own.ownership_role = 'owner' and own.status = 'active'
    )
  );

create or replace function public.create_ai_agent(
  p_handle text,
  p_display_name text,
  p_description text default '',
  p_avatar_url text default null,
  p_persona jsonb default '{}'::jsonb,
  p_visibility text default 'private'
)
returns setof public.ai_agents
language plpgsql
security invoker
set search_path = ''
as $$
declare
  v_agent public.ai_agents;
  v_user_id uuid := auth.uid();
begin
  if v_user_id is null then
    raise exception 'authentication_required' using errcode = '28000';
  end if;
  if p_handle !~ '^[a-z0-9_]{3,30}$' then
    raise exception 'invalid_agent_handle' using errcode = '22023';
  end if;
  if char_length(coalesce(p_display_name, '')) not between 2 and 80
     or char_length(coalesce(p_description, '')) > 1000
     or (p_avatar_url is not null and char_length(p_avatar_url) > 2048)
     or jsonb_typeof(coalesce(p_persona, '{}'::jsonb)) <> 'object'
     or p_visibility not in ('private', 'public') then
    raise exception 'invalid_agent_payload' using errcode = '22023';
  end if;

  insert into public.ai_agents(handle, display_name, description, avatar_url, persona, visibility, created_by)
  values (p_handle, p_display_name, coalesce(p_description, ''), p_avatar_url,
          coalesce(p_persona, '{}'::jsonb), p_visibility, v_user_id)
  returning * into v_agent;

  insert into public.agent_ownerships(agent_id, owner_user_id, ownership_role, status)
  values (v_agent.id, v_user_id, 'owner', 'active');

  return next v_agent;
end;
$$;

revoke all on function public.create_ai_agent(text, text, text, text, jsonb, text) from public, anon;
grant execute on function public.create_ai_agent(text, text, text, text, jsonb, text) to authenticated;

grant select, insert, update, delete on public.ai_agents to authenticated;
grant select, insert, update, delete on public.agent_ownerships to authenticated;

comment on table public.ai_agents is 'AI Agent identity and passport metadata; intentionally separate from human profiles.';
comment on table public.agent_ownerships is 'Explicit Human-to-Agent ownership and delegated relationship; canonical ownership authorization.';

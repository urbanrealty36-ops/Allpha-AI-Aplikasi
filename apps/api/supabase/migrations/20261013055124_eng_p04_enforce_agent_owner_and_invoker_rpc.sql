-- Keep the public RPC SECURITY INVOKER. A deferred constraint trigger ensures no Agent
-- can commit without an explicit active owner relationship, including direct PostgREST writes.
create or replace function public.create_ai_agent(
  p_handle text,
  p_display_name text,
  p_description text default '',
  p_avatar_url text default null,
  p_persona jsonb default '{}'::jsonb,
  p_visibility text default 'private',
  p_disclosure text default '',
  p_boundaries jsonb default '{}'::jsonb
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
  if v_user_id is null then raise exception 'authentication_required' using errcode = '28000'; end if;
  if p_handle !~ '^[a-z0-9_]{3,30}$' then raise exception 'invalid_agent_handle' using errcode = '22023'; end if;
  if char_length(coalesce(p_display_name, '')) not between 2 and 80
     or char_length(coalesce(p_description, '')) > 1000
     or char_length(coalesce(p_disclosure, '')) > 1000
     or (p_avatar_url is not null and char_length(p_avatar_url) > 2048)
     or jsonb_typeof(coalesce(p_persona, '{}'::jsonb)) <> 'object'
     or jsonb_typeof(coalesce(p_boundaries, '{}'::jsonb)) <> 'object'
     or p_visibility not in ('private', 'public') then
    raise exception 'invalid_agent_payload' using errcode = '22023';
  end if;
  insert into public.ai_agents(handle, display_name, description, avatar_url, persona, visibility, disclosure, boundaries, created_by)
  values (p_handle, p_display_name, coalesce(p_description, ''), p_avatar_url, coalesce(p_persona, '{}'::jsonb),
          p_visibility, coalesce(p_disclosure, ''), coalesce(p_boundaries, '{}'::jsonb), v_user_id)
  returning * into v_agent;
  insert into public.agent_ownerships(agent_id, owner_user_id, ownership_role, status)
  values (v_agent.id, v_user_id, 'owner', 'active');
  return next v_agent;
end;
$$;
revoke all on function public.create_ai_agent(text, text, text, text, jsonb, text, text, jsonb) from public, anon;
grant execute on function public.create_ai_agent(text, text, text, text, jsonb, text, text, jsonb) to authenticated;
revoke all on function public.create_ai_agent(text, text, text, text, jsonb, text) from public, anon, authenticated;

create or replace function private.require_agent_owner()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  if not exists (
    select 1 from public.agent_ownerships ao
    where ao.agent_id = new.id and ao.ownership_role = 'owner' and ao.status = 'active'
  ) then
    raise exception 'agent_requires_active_owner' using errcode = '23514';
  end if;
  return null;
end;
$$;
revoke all on function private.require_agent_owner() from public, anon, authenticated;
drop trigger if exists ai_agents_require_owner on public.ai_agents;
create constraint trigger ai_agents_require_owner
after insert on public.ai_agents
deferrable initially deferred
for each row execute function private.require_agent_owner();

grant select, insert, update on public.ai_agents to authenticated;
revoke delete on public.ai_agents from authenticated;
grant select, insert on public.agent_ownerships to authenticated;
revoke update, delete on public.agent_ownerships from authenticated;

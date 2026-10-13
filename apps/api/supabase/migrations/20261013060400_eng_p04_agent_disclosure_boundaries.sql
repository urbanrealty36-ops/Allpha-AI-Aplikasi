-- ENG-P04: make owner-approved disclosure and Agent boundaries first-class identity fields.
alter table public.ai_agents
  add column if not exists disclosure text not null default '' check (char_length(disclosure) <= 1000),
  add column if not exists boundaries jsonb not null default '{}'::jsonb check (jsonb_typeof(boundaries) = 'object');

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

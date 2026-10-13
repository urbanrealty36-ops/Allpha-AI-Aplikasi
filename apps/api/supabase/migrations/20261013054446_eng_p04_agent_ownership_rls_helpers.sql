-- ENG-P04 follow-up: prevent recursive RLS evaluation on agent_ownerships.
create schema if not exists private;
revoke all on schema private from public, anon, authenticated;
grant usage on schema private to authenticated;

create or replace function private.has_agent_ownership(
  p_agent_id uuid,
  p_user_id uuid,
  p_role text default null
)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select exists (
    select 1
    from public.agent_ownerships ao
    where ao.agent_id = p_agent_id
      and ao.owner_user_id = p_user_id
      and ao.status = 'active'
      and (p_role is null or ao.ownership_role = p_role)
  );
$$;
revoke all on function private.has_agent_ownership(uuid, uuid, text) from public, anon;
grant execute on function private.has_agent_ownership(uuid, uuid, text) to authenticated;

drop policy if exists ai_agents_select_public_or_owned on public.ai_agents;
create policy ai_agents_select_public_or_owned on public.ai_agents
for select to authenticated
using (
  (visibility = 'public' and status = 'active')
  or private.has_agent_ownership(id, (select auth.uid()), null)
);

drop policy if exists ai_agents_update_owner on public.ai_agents;
create policy ai_agents_update_owner on public.ai_agents
for update to authenticated
using (private.has_agent_ownership(id, (select auth.uid()), 'owner'))
with check (private.has_agent_ownership(id, (select auth.uid()), 'owner'));

drop policy if exists ai_agents_delete_owner on public.ai_agents;
create policy ai_agents_delete_owner on public.ai_agents
for delete to authenticated
using (private.has_agent_ownership(id, (select auth.uid()), 'owner'));

drop policy if exists agent_ownerships_select_participant on public.agent_ownerships;
create policy agent_ownerships_select_participant on public.agent_ownerships
for select to authenticated
using (
  owner_user_id = (select auth.uid())
  or private.has_agent_ownership(agent_id, (select auth.uid()), 'owner')
);

drop policy if exists agent_ownerships_update_owner on public.agent_ownerships;
create policy agent_ownerships_update_owner on public.agent_ownerships
for update to authenticated
using (private.has_agent_ownership(agent_id, (select auth.uid()), 'owner'))
with check (private.has_agent_ownership(agent_id, (select auth.uid()), 'owner'));

drop policy if exists agent_ownerships_delete_owner on public.agent_ownerships;
create policy agent_ownerships_delete_owner on public.agent_ownerships
for delete to authenticated
using (private.has_agent_ownership(agent_id, (select auth.uid()), 'owner'));

create or replace function private.touch_updated_at()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;
revoke all on function private.touch_updated_at() from public, anon, authenticated;
drop trigger if exists ai_agents_touch_updated_at on public.ai_agents;
create trigger ai_agents_touch_updated_at before update on public.ai_agents
for each row execute function private.touch_updated_at();

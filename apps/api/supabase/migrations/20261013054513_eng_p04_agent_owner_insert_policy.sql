-- ENG-P04: ownership creation must validate creator without recursive RLS visibility.
create or replace function private.agent_created_by(p_agent_id uuid, p_user_id uuid)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select exists (
    select 1 from public.ai_agents a
    where a.id = p_agent_id and a.created_by = p_user_id
  );
$$;
revoke all on function private.agent_created_by(uuid, uuid) from public, anon;
grant execute on function private.agent_created_by(uuid, uuid) to authenticated;

drop policy if exists agent_ownerships_insert_self_owner on public.agent_ownerships;
create policy agent_ownerships_insert_self_owner on public.agent_ownerships
for insert to authenticated
with check (
  owner_user_id = (select auth.uid())
  and ownership_role = 'owner'
  and status = 'active'
  and private.agent_created_by(agent_id, (select auth.uid()))
);

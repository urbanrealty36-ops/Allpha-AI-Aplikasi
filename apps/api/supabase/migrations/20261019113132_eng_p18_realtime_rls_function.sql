-- Replace recursive RLS subqueries with a narrow SECURITY DEFINER membership predicate.
create or replace function public.eng_p18_can_read_conversation(p_conversation_id uuid)
returns boolean
language sql stable security definer set search_path = pg_catalog, public
as $$
  select exists (
    select 1 from public.conversation_participants cp
    where cp.conversation_id = p_conversation_id and cp.user_id = auth.uid()
  ) and not exists (
    select 1 from public.conversation_participants cp
    join public.social_edges e
      on e.edge_type='block' and e.status='active'
     and ((e.actor_user_id=auth.uid() and e.target_user_id=cp.user_id)
       or (e.target_user_id=auth.uid() and e.actor_user_id=cp.user_id))
    where cp.conversation_id=p_conversation_id and cp.user_id is not null and cp.user_id<>auth.uid()
  )
$$;
revoke all on function public.eng_p18_can_read_conversation(uuid) from public, anon;
grant execute on function public.eng_p18_can_read_conversation(uuid) to authenticated;
grant select on public.conversation_participants to authenticated;
drop policy if exists conversation_participants_member_select on public.conversation_participants;
create policy conversation_participants_member_select on public.conversation_participants
for select to authenticated using (public.eng_p18_can_read_conversation(conversation_id));
drop policy if exists messages_participant_realtime_select on public.messages;
create policy messages_participant_realtime_select on public.messages
for select to authenticated using (public.eng_p18_can_read_conversation(conversation_id));

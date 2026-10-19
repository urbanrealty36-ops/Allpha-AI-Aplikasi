-- Realtime authorization needs participant-scoped SELECT visibility to evaluate message RLS.
grant select on public.conversation_participants to authenticated;
drop policy if exists conversation_participants_member_select on public.conversation_participants;
create policy conversation_participants_member_select on public.conversation_participants
for select to authenticated using (
  exists (
    select 1 from public.conversation_participants self
    where self.conversation_id = conversation_participants.conversation_id
      and self.user_id = (select auth.uid())
  )
);

-- ENG-P18 Realtime reads are visible only to current participants and unblocked peers.
grant select on public.messages to authenticated;
drop policy if exists messages_participant_realtime_select on public.messages;
create policy messages_participant_realtime_select on public.messages
for select to authenticated using (
  exists (
    select 1 from public.conversation_participants cp
    where cp.conversation_id = messages.conversation_id
      and cp.user_id = (select auth.uid())
  )
  and not exists (
    select 1
    from public.conversation_participants cp
    join public.social_edges e
      on e.edge_type = 'block' and e.status = 'active'
     and (
       (e.actor_user_id = (select auth.uid()) and e.target_user_id = cp.user_id)
       or (e.target_user_id = (select auth.uid()) and e.actor_user_id = cp.user_id)
     )
    where cp.conversation_id = messages.conversation_id
      and cp.user_id is not null
      and cp.user_id <> (select auth.uid())
  )
);
create or replace function public.eng_p18_guard_message_delivery()
returns trigger language plpgsql security invoker set search_path = ''
as $$
declare old_rank integer; new_rank integer;
begin
  old_rank := case old.delivery_status when 'sent' then 1 when 'delivered' then 2 when 'read' then 3 else 0 end;
  new_rank := case new.delivery_status when 'sent' then 1 when 'delivered' then 2 when 'read' then 3 else 0 end;
  if new_rank < old_rank then
    raise exception 'message delivery status cannot move backwards' using errcode = '23514';
  end if;
  if new.delivery_status in ('delivered','read') and new.delivered_at is null then new.delivered_at := now(); end if;
  if new.delivery_status = 'read' and new.read_at is null then new.read_at := now(); end if;
  return new;
end $$;
drop trigger if exists eng_p18_guard_message_delivery on public.messages;
create trigger eng_p18_guard_message_delivery before update of delivery_status, delivered_at, read_at on public.messages
for each row execute function public.eng_p18_guard_message_delivery();
create unique index if not exists messages_agent_reply_idempotency
on public.messages(conversation_id,sender_agent_id,client_message_id)
where sender_agent_id is not null;

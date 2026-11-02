create or replace function public.apply_social_graph_event_effect(p_event_id uuid,p_lease_token uuid)
returns boolean language plpgsql security definer set search_path=''
as $$
declare v_event public.social_graph_events%rowtype; v_inserted integer;
begin
 select * into v_event from public.social_graph_events where id=p_event_id and delivery_state='processing'
  and lease_token=p_lease_token and lease_expires_at>now() for update;
 if not found then return false; end if;
 insert into public.social_graph_event_effects(event_id,effect_key,affected_viewer_id,details)
 values(v_event.id,'invalidate_viewer_feed_snapshots',v_event.actor_user_id,
  jsonb_build_object('event_type',v_event.event_type,'target_user_id',v_event.target_user_id))
 on conflict(event_id) do nothing;
 get diagnostics v_inserted=row_count;
 if v_inserted=1 then
  update public.feed_snapshots set invalidated_at=coalesce(invalidated_at,now())
   where invalidated_at is null
     and viewer_user_id in (v_event.actor_user_id,v_event.target_user_id);
 end if;
 update public.social_graph_events set delivery_state='processed',processed_at=now(),lease_token=null,
  lease_expires_at=null,last_error_code=null where id=v_event.id and delivery_state='processing' and lease_token=p_lease_token;
 return found;
end $$;
revoke all on function public.apply_social_graph_event_effect(uuid,uuid) from public,anon,authenticated;
grant execute on function public.apply_social_graph_event_effect(uuid,uuid) to service_role;
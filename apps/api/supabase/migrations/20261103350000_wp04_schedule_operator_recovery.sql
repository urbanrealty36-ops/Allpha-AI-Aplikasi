create or replace function public.retry_content_schedule(p_schedule_id uuid,p_operator_id uuid,p_reason text)
returns jsonb language plpgsql security definer set search_path=pg_catalog,public
as $$
declare v_schedule public.content_schedules%rowtype;v_content public.content_items%rowtype;
begin
 if char_length(coalesce(trim(p_reason),''))<8 then return jsonb_build_object('outcome','reason_required'); end if;
 select * into v_schedule from public.content_schedules where id=p_schedule_id for update;
 if not found or v_schedule.status<>'failed' then return jsonb_build_object('outcome','schedule_not_retryable'); end if;
 select * into v_content from public.content_items where id=v_schedule.content_id and owner_id=v_schedule.owner_id for update;
 if not found or v_content.status<>'scheduled' or v_content.moderation_status<>'approved'
  or v_content.version<>v_schedule.content_version
  or v_content.provenance->>'rights_confirmed' is distinct from 'true' then
  return jsonb_build_object('outcome','content_policy_blocked');
 end if;
 if exists(select 1 from public.content_media where content_id=v_content.id and status<>'ready') then
  return jsonb_build_object('outcome','media_not_ready');
 end if;
 update public.content_schedules set status='scheduled',attempts=0,publish_at=greatest(publish_at,now()+interval '1 minute'),
  last_error_code=null,updated_by=p_operator_id,updated_at=now()
 where id=p_schedule_id returning * into v_schedule;
 insert into public.content_lifecycle_events(event_key,event_type,content_id,owner_id,payload)
 values('content.schedule.retry:'||p_schedule_id::text||':'||v_schedule.updated_at::text,'content.schedule.retry',
  v_content.id,v_content.owner_id,jsonb_build_object('schedule_id',p_schedule_id,'operator_id',p_operator_id,'reason',trim(p_reason)))
 on conflict(event_key) do nothing;
 return jsonb_build_object('outcome','requeued','schedule',to_jsonb(v_schedule));
end;
$$;
revoke all on function public.retry_content_schedule(uuid,uuid,text) from public,anon,authenticated;
grant execute on function public.retry_content_schedule(uuid,uuid,text) to service_role;

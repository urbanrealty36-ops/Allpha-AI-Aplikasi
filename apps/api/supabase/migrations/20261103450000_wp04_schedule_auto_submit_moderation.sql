create or replace function public.create_content_schedule(
 p_content_id uuid,p_owner_id uuid,p_expected_version integer,p_publish_at timestamptz,
 p_creator_timezone text,p_idempotency_key text,p_rights_confirmed boolean,p_disclosure_confirmed boolean
) returns jsonb language plpgsql security definer set search_path=pg_catalog,public
as $$
declare v_content public.content_items%rowtype;v_schedule public.content_schedules%rowtype;v_provenance jsonb;
begin
 if p_publish_at<=now() or not p_rights_confirmed or not p_disclosure_confirmed then return jsonb_build_object('outcome','invalid_schedule'); end if;
 if not exists(select 1 from pg_catalog.pg_timezone_names where name=p_creator_timezone) then return jsonb_build_object('outcome','invalid_timezone'); end if;
 select * into v_content from public.content_items where id=p_content_id and owner_id=p_owner_id for update;
 if not found or v_content.status not in ('draft','failed') or v_content.version<>p_expected_version then
  return jsonb_build_object('outcome','content_conflict');
 end if;
 select * into v_schedule from public.content_schedules where idempotency_key=p_idempotency_key;
 if found then
  if v_schedule.content_id<>p_content_id or v_schedule.owner_id<>p_owner_id then return jsonb_build_object('outcome','idempotency_conflict'); end if;
  return jsonb_build_object('outcome','replayed','schedule',to_jsonb(v_schedule),'content',to_jsonb(v_content));
 end if;
 if exists(select 1 from public.content_schedules where content_id=p_content_id and status in ('scheduled','processing')) then
  return jsonb_build_object('outcome','schedule_exists');
 end if;
 if exists(select 1 from public.content_media where content_id=p_content_id and owner_id=p_owner_id and status<>'ready') then
  return jsonb_build_object('outcome','media_not_ready');
 end if;
 v_provenance:=coalesce(v_content.provenance,'{}'::jsonb)||jsonb_build_object(
  'rights_confirmed',true,'disclosure_confirmed',true,'rights_attested_at',now());
 update public.content_items set provenance=v_provenance,status='review',moderation_status='pending',
  version=version+1 where id=p_content_id returning * into v_content;
 insert into public.content_schedules(content_id,owner_id,content_version,publish_at,creator_timezone,status,idempotency_key)
 values(p_content_id,p_owner_id,v_content.version,p_publish_at,p_creator_timezone,'scheduled',p_idempotency_key)
 returning * into v_schedule;
 return jsonb_build_object('outcome','created','schedule',to_jsonb(v_schedule),'content',to_jsonb(v_content));
end;
$$;
revoke all on function public.create_content_schedule(uuid,uuid,integer,timestamptz,text,text,boolean,boolean) from public,anon,authenticated;
grant execute on function public.create_content_schedule(uuid,uuid,integer,timestamptz,text,text,boolean,boolean) to service_role;

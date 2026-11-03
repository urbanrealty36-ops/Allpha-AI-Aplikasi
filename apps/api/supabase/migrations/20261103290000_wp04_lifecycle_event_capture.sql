create or replace function public.capture_content_lifecycle_event()
returns trigger language plpgsql security definer set search_path=pg_catalog,public
as $$
declare v_key text; v_type text; v_content uuid; v_media uuid; v_owner uuid; v_payload jsonb;
begin
 if tg_table_name='content_items' then
  v_content:=new.id;v_owner:=new.owner_id;
  if tg_op='INSERT' then v_type:='content.created';
  elsif old.status is distinct from new.status then v_type:='content.status.'||new.status;
  elsif old.version is distinct from new.version then v_type:='content.version.updated';
  else return new; end if;
  v_key:=v_type||':'||new.id::text||':'||new.version::text;
  v_payload:=jsonb_build_object('status',new.status,'moderation_status',new.moderation_status,'version',new.version);
 elsif tg_table_name='content_media' then
  v_content:=new.content_id;v_media:=new.id;v_owner:=new.owner_id;
  if tg_op='INSERT' then v_type:='media.upload.reserved';
  elsif old.status is distinct from new.status then v_type:='media.status.'||new.status;
  else return new; end if;
  v_key:=v_type||':'||new.id::text||':'||coalesce(new.processing_version,0)::text;
  v_payload:=jsonb_build_object('status',new.status,'media_type',new.media_type,'size_bytes',new.size_bytes);
 elsif tg_table_name='content_appeals' then
  v_content:=new.content_id;v_owner:=new.owner_id;
  if tg_op='INSERT' then v_type:='content.appeal.submitted';
  elsif old.status is distinct from new.status then v_type:='content.appeal.'||new.status;
  else return new; end if;
  v_key:=v_type||':'||new.id::text;
  v_payload:=jsonb_build_object('appeal_id',new.id,'status',new.status,'submitted_version',new.submitted_version);
 elsif tg_table_name='content_schedules' then
  v_content:=new.content_id;v_owner:=new.owner_id;
  if tg_op='INSERT' then v_type:='content.schedule.created';
  elsif old.status is distinct from new.status then v_type:='content.schedule.'||new.status;
  elsif old.publish_at is distinct from new.publish_at then v_type:='content.schedule.rescheduled';
  else return new; end if;
  v_key:=v_type||':'||new.id::text||':'||new.updated_at::text;
  v_payload:=jsonb_build_object('schedule_id',new.id,'status',new.status,'publish_at',new.publish_at,'timezone',new.creator_timezone);
 else return null;
 end if;
 insert into public.content_lifecycle_events(event_key,event_type,content_id,media_id,owner_id,payload)
 values(v_key,v_type,v_content,v_media,v_owner,coalesce(v_payload,'{}'::jsonb))
 on conflict(event_key) do nothing;
 return new;
end;
$$;
revoke all on function public.capture_content_lifecycle_event() from public,anon,authenticated;
drop trigger if exists content_items_lifecycle_event on public.content_items;
create trigger content_items_lifecycle_event after insert or update on public.content_items
for each row execute function public.capture_content_lifecycle_event();
drop trigger if exists content_media_lifecycle_event on public.content_media;
create trigger content_media_lifecycle_event after insert or update on public.content_media
for each row execute function public.capture_content_lifecycle_event();
drop trigger if exists content_appeals_lifecycle_event on public.content_appeals;
create trigger content_appeals_lifecycle_event after insert or update on public.content_appeals
for each row execute function public.capture_content_lifecycle_event();
drop trigger if exists content_schedules_lifecycle_event on public.content_schedules;
create trigger content_schedules_lifecycle_event after insert or update on public.content_schedules
for each row execute function public.capture_content_lifecycle_event();

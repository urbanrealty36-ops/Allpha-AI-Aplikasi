create or replace function public.handoff_content_provider_job(
 p_job_id uuid,p_lease_token uuid,p_media_id uuid,p_provider_asset_id text,p_provider_public_id text,p_provider_batch_id text
) returns jsonb language plpgsql security definer set search_path=pg_catalog,public
as $$
declare v_job public.content_lifecycle_jobs%rowtype;v_media public.content_media%rowtype;
begin
 select * into v_job from public.content_lifecycle_jobs
 where id=p_job_id and status='processing' and lease_token=p_lease_token and lease_expires_at>now()
  and job_type='media_transcode' and media_id=p_media_id for update;
 if not found then return jsonb_build_object('outcome','lease_lost'); end if;
 select * into v_media from public.content_media where id=p_media_id and status='processing' for update;
 if not found then return jsonb_build_object('outcome','media_not_processing'); end if;
 update public.content_media set provider_asset_id=p_provider_asset_id,
  provider_public_id=p_provider_public_id,provider_batch_id=p_provider_batch_id
 where id=p_media_id returning * into v_media;
 update public.content_lifecycle_jobs set status='awaiting_provider',lease_token=null,lease_expires_at=null,
  payload=coalesce(payload,'{}'::jsonb)||jsonb_build_object('provider','cloudinary',
   'provider_asset_id',p_provider_asset_id,'provider_public_id',p_provider_public_id,'provider_batch_id',p_provider_batch_id),
  updated_at=now() where id=p_job_id returning * into v_job;
 return jsonb_build_object('outcome','handed_off','job',to_jsonb(v_job),'media',to_jsonb(v_media));
end;
$$;

create or replace function public.complete_content_image_job(
 p_job_id uuid,p_lease_token uuid,p_media_id uuid,p_derivatives jsonb,p_processing_version integer default 1
) returns jsonb language plpgsql security definer set search_path=pg_catalog,public
as $$
declare v_job public.content_lifecycle_jobs%rowtype;v_media public.content_media%rowtype;
begin
 select * into v_job from public.content_lifecycle_jobs
 where id=p_job_id and status='processing' and lease_token=p_lease_token and lease_expires_at>now()
  and job_type='image_process' and media_id=p_media_id for update;
 if not found then return jsonb_build_object('outcome','lease_lost'); end if;
 if jsonb_typeof(p_derivatives)<>'array' or jsonb_array_length(p_derivatives)<1 then return jsonb_build_object('outcome','derivatives_required'); end if;
 select * into v_media from public.content_media where id=p_media_id and status='processing' for update;
 if not found or v_media.media_type not like 'image/%' then return jsonb_build_object('outcome','media_not_processing'); end if;
 update public.content_media set status='ready',scan_status='clean',processed_at=now(),
  processing_version=greatest(1,processing_version+1),derivatives=p_derivatives
 where id=p_media_id returning * into v_media;
 update public.content_lifecycle_jobs set status='succeeded',lease_token=null,lease_expires_at=null,
  completed_at=now(),updated_at=now(),last_error_code=null where id=p_job_id;
 return jsonb_build_object('outcome','completed','media',to_jsonb(v_media));
end;
$$;

create or replace function public.fail_content_lifecycle_job(p_job_id uuid,p_lease_token uuid,p_error_code text)
returns text language plpgsql security definer set search_path=pg_catalog,public
as $$
declare v_state text;v_media uuid;
begin
 update public.content_lifecycle_jobs set
  status=case when attempts>=max_attempts then 'dead' else 'pending' end,
  run_at=case when attempts>=max_attempts then run_at else now()+make_interval(secs=>least(3600,(power(2,least(attempts,10))::integer)*5)) end,
  lease_token=null,lease_expires_at=null,last_error_code=left(coalesce(p_error_code,'UNKNOWN'),80),updated_at=now()
 where id=p_job_id and status='processing' and lease_token=p_lease_token and lease_expires_at>now()
 returning status,media_id into v_state,v_media;
 if v_state='dead' and v_media is not null then
  update public.content_media set status='failed',scan_status=case when scan_status='rejected' then 'rejected' else 'unavailable' end
  where id=v_media and status='processing';
 end if;
 return coalesce(v_state,'lease_lost');
end;
$$;

create or replace function public.fail_content_schedule(p_schedule_id uuid,p_lease_token uuid,p_error_code text)
returns text language plpgsql security definer set search_path=pg_catalog,public
as $$
declare v_state text;
begin
 update public.content_schedules set
  status=case when attempts>=max_attempts then 'failed' else 'scheduled' end,
  publish_at=case when attempts>=max_attempts then publish_at else now()+make_interval(secs=>least(3600,(power(2,least(attempts,10))::integer)*5)) end,
  lease_token=null,lease_expires_at=null,last_error_code=left(coalesce(p_error_code,'UNKNOWN'),80),updated_at=now()
 where id=p_schedule_id and status='processing' and lease_token=p_lease_token and lease_expires_at>now()
 returning status into v_state;
 return coalesce(v_state,'lease_lost');
end;
$$;

create or replace function public.publish_scheduled_content(p_schedule_id uuid,p_lease_token uuid)
returns jsonb language plpgsql security definer set search_path=pg_catalog,public
as $$
declare v_schedule public.content_schedules%rowtype;v_content public.content_items%rowtype;
begin
 select * into v_schedule from public.content_schedules
 where id=p_schedule_id and status='processing' and lease_token=p_lease_token and lease_expires_at>now()
 for update;
 if not found then return jsonb_build_object('outcome','lease_lost'); end if;
 select * into v_content from public.content_items where id=v_schedule.content_id and owner_id=v_schedule.owner_id for update;
 if not found then return jsonb_build_object('outcome','content_missing'); end if;
 if v_content.status<>'scheduled' or v_content.version<>v_schedule.content_version
  or v_content.moderation_status<>'approved' or v_content.provenance->>'rights_confirmed' is distinct from 'true'
  or v_content.provenance->>'disclosure_confirmed' is distinct from 'true' then
  return jsonb_build_object('outcome','policy_recheck_failed');
 end if;
 if exists(select 1 from public.content_media where content_id=v_content.id and status<>'ready') then
  return jsonb_build_object('outcome','media_not_ready');
 end if;
 update public.content_items set status='published',published_at=now(),deleted_at=null,version=version+1
 where id=v_content.id returning * into v_content;
 update public.content_schedules set status='published',published_at=now(),lease_token=null,lease_expires_at=null,updated_at=now()
 where id=v_schedule.id;
 insert into public.content_lifecycle_events(event_key,event_type,content_id,owner_id,payload)
 values('content.published:'||v_schedule.id::text,'content.published',v_content.id,v_content.owner_id,
  jsonb_build_object('schedule_id',v_schedule.id,'published_at',now(),'version',v_content.version))
 on conflict(event_key) do nothing;
 return jsonb_build_object('outcome','published','content',to_jsonb(v_content));
end;
$$;

create or replace function public.begin_content_retention_purge(p_job_id uuid,p_lease_token uuid)
returns jsonb language plpgsql security definer set search_path=pg_catalog,public
as $$
declare v_job public.content_lifecycle_jobs%rowtype;v_content public.content_items%rowtype;v_content_id uuid;
begin
 select * into v_job from public.content_lifecycle_jobs
 where id=p_job_id and status='processing' and lease_token=p_lease_token and lease_expires_at>now()
  and job_type='retention_purge' for update;
 if not found then return jsonb_build_object('outcome','lease_lost'); end if;
 if v_job.payload->>'scope'='content' then
  v_content_id:=(v_job.payload->>'content_id')::uuid;
  select * into v_content from public.content_items where id=v_content_id for update;
  if found then
   if v_content.status<>'deleted' or v_content.deleted_at>now()-interval '30 days' then return jsonb_build_object('outcome','not_expired'); end if;
   if exists(select 1 from public.content_retention_holds h where h.content_id=v_content.id and h.released_at is null) then return jsonb_build_object('outcome','legal_hold'); end if;
   update public.content_items set purge_started_at=coalesce(purge_started_at,now()) where id=v_content.id;
  end if;
 elsif v_job.payload->>'scope'='abandoned_upload' then
  v_content_id:=v_job.content_id;
  if v_content_id is not null then
   select * into v_content from public.content_items where id=v_content_id for update;
   if exists(select 1 from public.content_retention_holds h where h.content_id=v_content_id and h.released_at is null) then return jsonb_build_object('outcome','legal_hold'); end if;
  end if;
 else return jsonb_build_object('outcome','invalid_scope'); end if;
 if v_content_id is not null then
  insert into public.content_retention_purge_locks(content_id,job_id,scope)
  values(v_content_id,p_job_id,v_job.payload->>'scope')
  on conflict(content_id,job_id) do update set released_at=null;
 end if;
 return jsonb_build_object('outcome','authorized');
end;
$$;

create or replace function public.defer_content_retention_job(p_job_id uuid,p_lease_token uuid,p_reason text)
returns text language plpgsql security definer set search_path=pg_catalog,public
as $$
declare v_state text;
begin
 update public.content_lifecycle_jobs set status='pending',run_at=now()+interval '1 day',
  lease_token=null,lease_expires_at=null,last_error_code=left(coalesce(p_reason,'retention_deferred'),80),updated_at=now()
 where id=p_job_id and status='processing' and lease_token=p_lease_token and lease_expires_at>now()
 returning status into v_state;
 return coalesce(v_state,'lease_lost');
end;
$$;

create or replace function public.complete_content_retention_job(p_job_id uuid,p_lease_token uuid)
returns text language plpgsql security definer set search_path=pg_catalog,public
as $$
declare v_state text;
begin
 update public.content_lifecycle_jobs set status='succeeded',lease_token=null,lease_expires_at=null,
  completed_at=now(),updated_at=now()
 where id=p_job_id and status='processing' and lease_token=p_lease_token and lease_expires_at>now()
 returning status into v_state;
 if v_state='succeeded' then
  update public.content_retention_purge_locks set released_at=now()
  where job_id=p_job_id and released_at is null;
 end if;
 return coalesce(v_state,'lease_lost');
end;
$$;

create or replace function public.complete_content_provider_cleanup_job(p_job_id uuid,p_lease_token uuid)
returns text language plpgsql security definer set search_path=pg_catalog,public
as $$
declare v_state text;
begin
 update public.content_lifecycle_jobs set status='succeeded',lease_token=null,lease_expires_at=null,
  completed_at=now(),updated_at=now()
 where id=p_job_id and status='processing' and lease_token=p_lease_token and lease_expires_at>now()
 returning status into v_state;
 return coalesce(v_state,'lease_lost');
end;
$$;

revoke all on function public.handoff_content_provider_job(uuid,uuid,uuid,text,text,text) from public,anon,authenticated;
revoke all on function public.complete_content_retention_job(uuid,uuid) from public,anon,authenticated;
revoke all on function public.complete_content_provider_cleanup_job(uuid,uuid) from public,anon,authenticated;
grant execute on function public.handoff_content_provider_job(uuid,uuid,uuid,text,text,text) to service_role;
grant execute on function public.complete_content_retention_job(uuid,uuid) to service_role;
grant execute on function public.complete_content_provider_cleanup_job(uuid,uuid) to service_role;

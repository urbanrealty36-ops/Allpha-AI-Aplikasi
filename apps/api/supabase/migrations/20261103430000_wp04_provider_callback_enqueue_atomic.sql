create or replace function public.enqueue_content_provider_callback(
 p_provider_event_id text,p_media_id uuid,p_transcode_job_id uuid,p_payload_sha256 text,p_payload jsonb
) returns jsonb language plpgsql security definer set search_path=pg_catalog,public
as $$
declare v_media public.content_media%rowtype;v_job public.content_lifecycle_jobs%rowtype;v_callback public.content_provider_callbacks%rowtype;v_callback_job public.content_lifecycle_jobs%rowtype;
begin
 if char_length(p_provider_event_id)<1 or char_length(p_provider_event_id)>200
  or p_payload_sha256 !~ '^[0-9a-f]{64}$' or jsonb_typeof(p_payload)<>'object' then
  return jsonb_build_object('outcome','invalid_callback');
 end if;
 select * into v_media from public.content_media where id=p_media_id and status='processing' for update;
 if not found then return jsonb_build_object('outcome','media_not_processing'); end if;
 select * into v_job from public.content_lifecycle_jobs where id=p_transcode_job_id
  and media_id=p_media_id and job_type='media_transcode' and status='awaiting_provider' for update;
 if not found then return jsonb_build_object('outcome','transcode_job_not_waiting'); end if;
 if p_payload->>'public_id' is distinct from v_media.provider_public_id
  or p_payload->>'asset_id' is distinct from v_media.provider_asset_id
  or p_payload->>'batch_id' is distinct from v_media.provider_batch_id then
  return jsonb_build_object('outcome','provider_identity_mismatch');
 end if;
 insert into public.content_provider_callbacks(provider,provider_event_id,media_id,job_id,payload_sha256,payload,outcome)
 values('cloudinary',p_provider_event_id,p_media_id,p_transcode_job_id,p_payload_sha256,p_payload,'received')
 on conflict(provider,provider_event_id) do nothing;
 select * into v_callback from public.content_provider_callbacks
 where provider='cloudinary' and provider_event_id=p_provider_event_id for update;
 if v_callback.media_id<>p_media_id or v_callback.job_id<>p_transcode_job_id or v_callback.payload_sha256<>p_payload_sha256 then
  return jsonb_build_object('outcome','callback_replay_mismatch');
 end if;
 if v_callback.outcome='processed' then
  return jsonb_build_object('outcome','already_processed');
 end if;
 insert into public.content_lifecycle_jobs(job_type,content_id,media_id,owner_id,idempotency_key,payload)
 values('provider_callback',v_media.content_id,v_media.id,v_media.owner_id,
  'provider-callback:cloudinary:'||p_provider_event_id,
  jsonb_build_object('provider','cloudinary','provider_event_id',p_provider_event_id,
   'transcode_job_id',p_transcode_job_id,'payload_sha256',p_payload_sha256))
 on conflict(idempotency_key) do nothing;
 select * into v_callback_job from public.content_lifecycle_jobs
 where idempotency_key='provider-callback:cloudinary:'||p_provider_event_id;
 return jsonb_build_object('outcome','queued','callback_job_id',v_callback_job.id);
end;
$$;

create or replace function public.complete_content_provider_job(
 p_job_id uuid,p_media_id uuid,p_provider text,p_provider_asset_id text,
 p_provider_public_id text,p_provider_event_id text,p_payload_sha256 text,
 p_derivatives jsonb,p_scan_status text
) returns jsonb language plpgsql security definer set search_path=pg_catalog,public
as $$
declare v_job public.content_lifecycle_jobs%rowtype;v_media public.content_media%rowtype;v_callback public.content_provider_callbacks%rowtype;
begin
 select * into v_job from public.content_lifecycle_jobs
 where id=p_job_id and status='awaiting_provider' and job_type='media_transcode' and media_id=p_media_id
 for update;
 if not found then return jsonb_build_object('outcome','job_not_awaiting_provider'); end if;
 select * into v_media from public.content_media
 where id=p_media_id and status='processing' and provider_asset_id=p_provider_asset_id
 and provider_public_id=p_provider_public_id for update;
 if not found then return jsonb_build_object('outcome','provider_asset_mismatch'); end if;
 if p_scan_status<>'clean' or jsonb_typeof(p_derivatives)<>'array' or jsonb_array_length(p_derivatives)<1 then
  return jsonb_build_object('outcome','processing_incomplete');
 end if;
 select * into v_callback from public.content_provider_callbacks
 where provider=p_provider and provider_event_id=p_provider_event_id for update;
 if not found or v_callback.media_id<>p_media_id or v_callback.job_id<>p_job_id
  or v_callback.payload_sha256<>p_payload_sha256 or v_callback.outcome not in ('received','processed') then
  return jsonb_build_object('outcome','callback_replay_mismatch');
 end if;
 update public.content_media set status='ready',scan_status='clean',processed_at=now(),
  processing_version=greatest(1,processing_version+1),derivatives=p_derivatives,
  provider_callback_verified_at=now()
 where id=p_media_id returning * into v_media;
 update public.content_lifecycle_jobs set status='succeeded',lease_token=null,lease_expires_at=null,
  completed_at=now(),updated_at=now(),last_error_code=null where id=p_job_id;
 update public.content_provider_callbacks set outcome='processed',processed_at=now()
 where provider=p_provider and provider_event_id=p_provider_event_id;
 insert into public.content_lifecycle_events(event_key,event_type,content_id,media_id,owner_id,payload)
 values('media.ready:'||p_media_id::text,'media.ready',v_media.content_id,p_media_id,v_media.owner_id,
  jsonb_build_object('provider',p_provider,'processing_version',v_media.processing_version))
 on conflict(event_key) do nothing;
 return jsonb_build_object('outcome','completed','media',to_jsonb(v_media));
end;
$$;
revoke all on function public.enqueue_content_provider_callback(text,uuid,uuid,text,jsonb) from public,anon,authenticated;
grant execute on function public.enqueue_content_provider_callback(text,uuid,uuid,text,jsonb) to service_role;

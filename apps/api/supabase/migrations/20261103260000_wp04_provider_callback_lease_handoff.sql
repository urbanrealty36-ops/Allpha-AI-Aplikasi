alter table public.content_lifecycle_jobs drop constraint if exists content_lifecycle_jobs_status_check;
alter table public.content_lifecycle_jobs add constraint content_lifecycle_jobs_status_check
 check (status in ('pending','processing','awaiting_provider','succeeded','failed','dead','cancelled'));
alter table public.content_lifecycle_jobs drop constraint if exists content_lifecycle_jobs_lease_consistency;
alter table public.content_lifecycle_jobs add constraint content_lifecycle_jobs_lease_consistency check (
 (status='processing' and lease_token is not null and lease_expires_at is not null)
 or (status<>'processing' and lease_token is null and lease_expires_at is null)
);
create or replace function public.complete_content_provider_job(
 p_job_id uuid,p_media_id uuid,p_provider text,p_provider_asset_id text,
 p_provider_public_id text,p_provider_event_id text,p_payload_sha256 text,
 p_derivatives jsonb,p_scan_status text
) returns jsonb language plpgsql security definer set search_path=pg_catalog,public
as $$
declare v_job public.content_lifecycle_jobs%rowtype; v_media public.content_media%rowtype; v_callback public.content_provider_callbacks%rowtype;
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
 insert into public.content_provider_callbacks(provider,provider_event_id,media_id,job_id,payload_sha256,outcome,processed_at)
 values(p_provider,p_provider_event_id,p_media_id,p_job_id,p_payload_sha256,'processed',now())
 on conflict(provider,provider_event_id) do nothing;
 select * into v_callback from public.content_provider_callbacks where provider=p_provider and provider_event_id=p_provider_event_id;
 if v_callback.media_id<>p_media_id or v_callback.job_id<>p_job_id or v_callback.payload_sha256<>p_payload_sha256 then
  return jsonb_build_object('outcome','callback_replay_mismatch');
 end if;
 update public.content_media set status='ready',scan_status='clean',processed_at=now(),
  processing_version=greatest(1,processing_version+1),derivatives=p_derivatives,
  provider_callback_verified_at=now()
 where id=p_media_id returning * into v_media;
 update public.content_lifecycle_jobs set status='succeeded',completed_at=now(),updated_at=now(),last_error_code=null
 where id=p_job_id;
 insert into public.content_lifecycle_events(event_key,event_type,content_id,media_id,owner_id,payload)
 values('media.ready:'||p_media_id::text,'media.ready',v_media.content_id,p_media_id,v_media.owner_id,
  jsonb_build_object('provider',p_provider,'processing_version',v_media.processing_version))
 on conflict(event_key) do nothing;
 return jsonb_build_object('outcome','completed','media',to_jsonb(v_media));
end;
$$;
revoke all on function public.complete_content_provider_job(uuid,uuid,text,text,text,text,text,jsonb,text) from public,anon,authenticated;
grant execute on function public.complete_content_provider_job(uuid,uuid,text,text,text,text,text,jsonb,text) to service_role;

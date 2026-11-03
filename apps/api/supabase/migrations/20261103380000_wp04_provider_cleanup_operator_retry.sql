create or replace function public.retry_content_lifecycle_job(p_job_id uuid,p_operator_id uuid,p_reason text)
returns jsonb language plpgsql security definer set search_path=pg_catalog,public
as $$
declare v_job public.content_lifecycle_jobs%rowtype;v_media public.content_media%rowtype;
begin
 if char_length(coalesce(trim(p_reason),''))<8 then return jsonb_build_object('outcome','reason_required'); end if;
 select * into v_job from public.content_lifecycle_jobs where id=p_job_id for update;
 if not found or v_job.status not in ('dead','failed') then return jsonb_build_object('outcome','job_not_retryable'); end if;
 if v_job.media_id is not null and v_job.job_type<>'provider_cleanup' then
  select * into v_media from public.content_media where id=v_job.media_id for update;
  if not found or v_media.status not in ('failed','processing') then return jsonb_build_object('outcome','media_not_retryable'); end if;
  update public.content_media set status='processing',scan_status='pending',
   provider_asset_id=null,provider_public_id=null,provider_batch_id=null,provider_callback_verified_at=null
  where id=v_media.id;
 end if;
 update public.content_lifecycle_jobs set status='pending',attempts=0,run_at=now(),
  lease_token=null,lease_expires_at=null,last_error_code=null,updated_at=now()
 where id=p_job_id returning * into v_job;
 insert into public.content_lifecycle_events(event_key,event_type,content_id,media_id,owner_id,payload)
 values('lifecycle.job.retry:'||p_job_id::text||':'||v_job.updated_at::text,'lifecycle.job.retry',
  v_job.content_id,v_job.media_id,v_job.owner_id,jsonb_build_object('job_id',p_job_id,'operator_id',p_operator_id,'reason',trim(p_reason)))
 on conflict(event_key) do nothing;
 return jsonb_build_object('outcome','requeued','job',to_jsonb(v_job));
end;
$$;
revoke all on function public.retry_content_lifecycle_job(uuid,uuid,text) from public,anon,authenticated;
grant execute on function public.retry_content_lifecycle_job(uuid,uuid,text) to service_role;

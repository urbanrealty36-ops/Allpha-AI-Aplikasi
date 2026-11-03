-- Complete image processing and media readiness in one transaction.
create or replace function public.complete_content_image_job(
  p_job_id uuid,
  p_lease_token uuid,
  p_media_id uuid,
  p_derivatives jsonb,
  p_processing_version integer default 1
) returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
declare v_job public.content_lifecycle_jobs%rowtype; v_media public.content_media%rowtype;
begin
  select * into v_job from public.content_lifecycle_jobs
  where id=p_job_id and status='processing' and lease_token=p_lease_token
  for update;
  if not found or v_job.job_type<>'image_process' or v_job.media_id<>p_media_id then
    return jsonb_build_object('outcome','lease_lost');
  end if;
  if jsonb_typeof(p_derivatives)<>'array' or jsonb_array_length(p_derivatives)<1 then
    return jsonb_build_object('outcome','derivatives_required');
  end if;
  select * into v_media from public.content_media
  where id=p_media_id and status='processing'
  for update;
  if not found or v_media.media_type not like 'image/%' then
    return jsonb_build_object('outcome','media_not_processing');
  end if;
  update public.content_media
  set status='ready',scan_status='clean',processed_at=now(),
      processing_version=greatest(1,p_processing_version),derivatives=p_derivatives
  where id=p_media_id
  returning * into v_media;
  update public.content_lifecycle_jobs
  set status='succeeded',lease_token=null,lease_expires_at=null,
      completed_at=now(),updated_at=now(),last_error_code=null
  where id=p_job_id;
  return jsonb_build_object('outcome','completed','media',to_jsonb(v_media));
end;
$$;
revoke all on function public.complete_content_image_job(uuid,uuid,uuid,jsonb,integer) from public,anon,authenticated;
grant execute on function public.complete_content_image_job(uuid,uuid,uuid,jsonb,integer) to service_role;

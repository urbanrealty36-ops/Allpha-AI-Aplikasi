-- ENG-P03 forward repair: preserve the live lease-scoped export artifact path contract.
CREATE OR REPLACE FUNCTION public.complete_account_export_job(p_job_id uuid, p_lease_token uuid, p_storage_path text, p_file_sha256 text, p_file_size_bytes bigint, p_manifest jsonb)
 RETURNS boolean
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
declare v_user_id uuid;
begin
  if auth.role() <> 'service_role' then
    raise exception 'service_role_required' using errcode = '42501';
  end if;
  if p_storage_path is null
     or p_file_sha256 is null
     or p_file_sha256 !~ '^[a-f0-9]{64}$'
     or p_file_size_bytes is null or p_file_size_bytes <= 0
     or p_manifest is null or jsonb_typeof(p_manifest) <> 'object' then
    raise exception 'invalid_export_receipt' using errcode = '22023';
  end if;
  update public.account_export_jobs j
  set status = 'succeeded',
      storage_bucket = 'account-exports',
      storage_path = p_storage_path,
      file_sha256 = p_file_sha256,
      file_size_bytes = p_file_size_bytes,
      manifest = p_manifest,
      completed_at = pg_catalog.now(),
      lease_token = null,
      lease_owner = null,
      lease_expires_at = null,
      error_code = null,
      updated_at = pg_catalog.now()
  where j.id = p_job_id
    and j.status = 'running'
    and j.lease_token = p_lease_token
    and j.lease_expires_at > pg_catalog.now()
    and p_storage_path in (
      j.user_id::text || '/' || j.id::text || '.json.gz',
      j.user_id::text || '/' || j.id::text || '/' || p_lease_token::text || '.json.gz'
    );
  if not found then return false; end if;
  select j.user_id into v_user_id from public.account_export_jobs j where j.id = p_job_id;
  insert into public.account_lifecycle_events(export_job_id,user_id,subject_ref,event_type,metadata)
  values (p_job_id,v_user_id,encode(extensions.digest(v_user_id::text,'sha256'),'hex'),'export_completed',
          jsonb_build_object('file_size_bytes',p_file_size_bytes,'file_sha256',p_file_sha256));
  return true;
end;
$function$
;
revoke all on function public.complete_account_export_job(uuid,uuid,text,text,bigint,jsonb) from public, anon, authenticated;
grant execute on function public.complete_account_export_job(uuid,uuid,text,text,bigint,jsonb) to service_role;

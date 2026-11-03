create or replace function public.defer_content_retention_job(p_job_id uuid,p_lease_token uuid,p_reason text)
returns text language plpgsql security definer set search_path=pg_catalog,public
as $$
declare v_state text;
begin
 update public.content_lifecycle_jobs set status='pending',run_at=now()+interval '1 day',
  lease_token=null,lease_expires_at=null,last_error_code=left(coalesce(p_reason,'retention_deferred'),80),updated_at=now()
 where id=p_job_id and status='processing' and lease_token=p_lease_token
 returning status into v_state;
 return coalesce(v_state,'lease_lost');
end;
$$;
revoke all on function public.defer_content_retention_job(uuid,uuid,text) from public,anon,authenticated;
grant execute on function public.defer_content_retention_job(uuid,uuid,text) to service_role;

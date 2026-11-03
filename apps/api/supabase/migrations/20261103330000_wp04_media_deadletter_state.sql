create or replace function public.fail_content_lifecycle_job(
 p_job_id uuid,p_lease_token uuid,p_error_code text
) returns text language plpgsql security definer set search_path=pg_catalog,public
as $$
declare v_state text;v_media uuid;
begin
 update public.content_lifecycle_jobs
 set status=case when attempts>=max_attempts then 'dead' else 'pending' end,
  run_at=case when attempts>=max_attempts then run_at else now()+make_interval(secs=>least(3600,(power(2,least(attempts,10))::integer)*5)) end,
  lease_token=null,lease_expires_at=null,
  last_error_code=left(coalesce(p_error_code,'UNKNOWN'),80),updated_at=now()
 where id=p_job_id and status='processing' and lease_token=p_lease_token
 returning status,media_id into v_state,v_media;
 if v_state='dead' and v_media is not null then
  update public.content_media set status='failed',scan_status=case when scan_status='rejected' then 'rejected' else 'unavailable' end
  where id=v_media and status='processing';
 end if;
 return coalesce(v_state,'lease_lost');
end;
$$;
revoke all on function public.fail_content_lifecycle_job(uuid,uuid,text) from public,anon,authenticated;
grant execute on function public.fail_content_lifecycle_job(uuid,uuid,text) to service_role;

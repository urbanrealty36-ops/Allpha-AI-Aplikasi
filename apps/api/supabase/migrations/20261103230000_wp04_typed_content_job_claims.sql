-- Dedicated worker claims avoid consuming video/audio jobs until a provider is approved/configured.
create or replace function public.claim_content_lifecycle_jobs(
  p_worker_id text, p_limit integer, p_lease_seconds integer, p_job_type text
) returns setof public.content_lifecycle_jobs
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
begin
  if p_job_type not in ('image_process','media_transcode','scheduled_publish','retention_purge') then
    return;
  end if;
  return query
  with candidates as (
    select id from public.content_lifecycle_jobs
    where job_type=p_job_type and run_at<=now() and attempts<max_attempts
      and (status='pending' or (status='processing' and lease_expires_at<now()))
    order by run_at,created_at
    for update skip locked
    limit greatest(1,least(p_limit,50))
  )
  update public.content_lifecycle_jobs j
  set status='processing',attempts=j.attempts+1,lease_token=gen_random_uuid(),
      lease_expires_at=now()+make_interval(secs=>greatest(15,least(p_lease_seconds,300))),
      updated_at=now()
  from candidates c where j.id=c.id
  returning j.*;
end;
$$;
revoke all on function public.claim_content_lifecycle_jobs(text,integer,integer,text) from public,anon,authenticated;
grant execute on function public.claim_content_lifecycle_jobs(text,integer,integer,text) to service_role;

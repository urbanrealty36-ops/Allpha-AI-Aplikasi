alter table public.content_provider_callbacks
 add column if not exists payload jsonb not null default '{}'::jsonb
 check(jsonb_typeof(payload)='object');
alter table public.content_lifecycle_jobs drop constraint if exists content_lifecycle_jobs_job_type_check;
alter table public.content_lifecycle_jobs add constraint content_lifecycle_jobs_job_type_check
 check(job_type in ('image_process','media_transcode','scheduled_publish','retention_purge','provider_cleanup','provider_callback'));
create or replace function public.claim_content_lifecycle_jobs(
 p_worker_id text,p_limit integer,p_lease_seconds integer,p_job_type text
) returns setof public.content_lifecycle_jobs
language plpgsql security definer set search_path=pg_catalog,public
as $$
begin
 if p_job_type not in ('image_process','media_transcode','scheduled_publish','retention_purge','provider_cleanup','provider_callback') then return; end if;
 return query
 with candidates as (
  select id from public.content_lifecycle_jobs
  where job_type=p_job_type and run_at<=now() and attempts<max_attempts
   and (status='pending' or (status='processing' and lease_expires_at<now()))
  order by run_at,created_at for update skip locked limit greatest(1,least(p_limit,50))
 )
 update public.content_lifecycle_jobs j set status='processing',attempts=j.attempts+1,
  lease_token=gen_random_uuid(),lease_expires_at=now()+make_interval(secs=>greatest(15,least(p_lease_seconds,300))),updated_at=now()
 from candidates c where j.id=c.id returning j.*;
end;
$$;
create or replace function public.complete_content_lifecycle_job(p_job_id uuid,p_lease_token uuid)
returns text language plpgsql security definer set search_path=pg_catalog,public
as $$
declare v_state text;
begin
 update public.content_lifecycle_jobs set status='succeeded',lease_token=null,lease_expires_at=null,
  completed_at=now(),updated_at=now(),last_error_code=null
 where id=p_job_id and status='processing' and lease_token=p_lease_token and lease_expires_at>now()
 returning status into v_state;
 return coalesce(v_state,'lease_lost');
end;
$$;
revoke all on function public.claim_content_lifecycle_jobs(text,integer,integer,text) from public,anon,authenticated;
revoke all on function public.complete_content_lifecycle_job(uuid,uuid) from public,anon,authenticated;
grant execute on function public.claim_content_lifecycle_jobs(text,integer,integer,text) to service_role;
grant execute on function public.complete_content_lifecycle_job(uuid,uuid) to service_role;

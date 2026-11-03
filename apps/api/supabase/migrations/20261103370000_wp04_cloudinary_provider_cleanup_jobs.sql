alter table public.content_lifecycle_jobs drop constraint if exists content_lifecycle_jobs_job_type_check;
alter table public.content_lifecycle_jobs add constraint content_lifecycle_jobs_job_type_check
 check(job_type in ('image_process','media_transcode','scheduled_publish','retention_purge','provider_cleanup'));

create or replace function public.claim_content_lifecycle_jobs(
 p_worker_id text,p_limit integer,p_lease_seconds integer,p_job_type text
) returns setof public.content_lifecycle_jobs
language plpgsql security definer set search_path=pg_catalog,public
as $$
begin
 if p_job_type not in ('image_process','media_transcode','scheduled_publish','retention_purge','provider_cleanup') then return; end if;
 return query
 with candidates as (
  select id from public.content_lifecycle_jobs
  where job_type=p_job_type and run_at<=now() and attempts<max_attempts
   and (status='pending' or (status='processing' and lease_expires_at<now()))
  order by run_at,created_at for update skip locked limit greatest(1,least(p_limit,50))
 )
 update public.content_lifecycle_jobs j
 set status='processing',attempts=j.attempts+1,lease_token=gen_random_uuid(),
  lease_expires_at=now()+make_interval(secs=>greatest(15,least(p_lease_seconds,300))),updated_at=now()
 from candidates c where j.id=c.id returning j.*;
end;
$$;
revoke all on function public.claim_content_lifecycle_jobs(text,integer,integer,text) from public,anon,authenticated;
grant execute on function public.claim_content_lifecycle_jobs(text,integer,integer,text) to service_role;

create or replace function public.enqueue_cloudinary_asset_cleanup()
returns trigger language plpgsql security definer set search_path=pg_catalog,public
as $$
begin
 if new.status='ready' and old.status is distinct from new.status
  and new.provider_asset_id is not null and new.provider_public_id is not null then
  insert into public.content_lifecycle_jobs(job_type,content_id,media_id,owner_id,idempotency_key,payload)
  values('provider_cleanup',new.content_id,new.id,new.owner_id,
   'provider-cleanup:cloudinary:'||new.provider_asset_id,
   jsonb_build_object('provider','cloudinary','provider_asset_id',new.provider_asset_id,
    'provider_public_id',new.provider_public_id,'resource_type','video'))
  on conflict(idempotency_key) do nothing;
 end if;
 return new;
end;
$$;
revoke all on function public.enqueue_cloudinary_asset_cleanup() from public,anon,authenticated;
drop trigger if exists content_media_enqueue_provider_cleanup on public.content_media;
create trigger content_media_enqueue_provider_cleanup after update of status on public.content_media
for each row execute function public.enqueue_cloudinary_asset_cleanup();

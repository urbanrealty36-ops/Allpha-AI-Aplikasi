create or replace function public.capture_content_lifecycle_job_event()
returns trigger language plpgsql security definer set search_path=pg_catalog,public
as $$
declare v_type text;v_key text;
begin
 if tg_op='INSERT' then v_type:='lifecycle.job.queued';
 elsif old.status is distinct from new.status then v_type:='lifecycle.job.'||new.status;
 elsif old.attempts is distinct from new.attempts then v_type:='lifecycle.job.attempted';
 else return new; end if;
 v_key:=v_type||':'||new.id::text||':'||new.attempts::text;
 insert into public.content_lifecycle_events(event_key,event_type,content_id,media_id,owner_id,payload)
 values(v_key,v_type,new.content_id,new.media_id,new.owner_id,
  jsonb_build_object('job_id',new.id,'job_type',new.job_type,'status',new.status,'attempts',new.attempts,'error_code',new.last_error_code))
 on conflict(event_key) do nothing;
 return new;
end;
$$;
revoke all on function public.capture_content_lifecycle_job_event() from public,anon,authenticated;
drop trigger if exists content_lifecycle_jobs_capture_event on public.content_lifecycle_jobs;
create trigger content_lifecycle_jobs_capture_event after insert or update on public.content_lifecycle_jobs
for each row execute function public.capture_content_lifecycle_job_event();

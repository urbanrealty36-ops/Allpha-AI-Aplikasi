-- WP-04 lifecycle completion: recoverable delete, schedule leases, media provider receipts and audit outbox.
alter table public.content_items add column if not exists deleted_at timestamptz;
alter table public.content_items drop constraint if exists content_items_status_check;
alter table public.content_items add constraint content_items_status_check
  check (status in ('draft','review','scheduled','published','failed','archived','deleted'));

alter table public.content_schedules
  add column if not exists lease_token uuid,
  add column if not exists lease_expires_at timestamptz,
  add column if not exists max_attempts integer not null default 8 check (max_attempts between 1 and 20),
  add column if not exists last_attempt_at timestamptz,
  add column if not exists published_at timestamptz,
  add column if not exists cancelled_at timestamptz,
  add column if not exists updated_by uuid references auth.users(id);
create index if not exists content_schedules_recovery_idx
  on public.content_schedules(publish_at,lease_expires_at)
  where status in ('scheduled','processing');

create table if not exists public.content_lifecycle_events (
  id uuid primary key default gen_random_uuid(),
  event_key text not null unique,
  event_type text not null,
  content_id uuid,
  media_id uuid,
  owner_id uuid,
  payload jsonb not null default '{}'::jsonb check (jsonb_typeof(payload)='object'),
  created_at timestamptz not null default now()
);
create index if not exists content_lifecycle_events_content_idx on public.content_lifecycle_events(content_id,created_at desc);
alter table public.content_lifecycle_events enable row level security;
revoke all on public.content_lifecycle_events from public,anon,authenticated;
grant select,insert on public.content_lifecycle_events to service_role;

create table if not exists public.content_provider_callbacks (
  id uuid primary key default gen_random_uuid(),
  provider text not null,
  provider_event_id text not null,
  media_id uuid not null references public.content_media(id) on delete cascade,
  job_id uuid not null references public.content_lifecycle_jobs(id) on delete cascade,
  payload_sha256 text not null check (payload_sha256 ~ '^[0-9a-f]{64}$'),
  received_at timestamptz not null default now(),
  processed_at timestamptz,
  outcome text not null default 'received' check (outcome in ('received','processed','rejected','failed')),
  unique(provider,provider_event_id)
);
alter table public.content_provider_callbacks enable row level security;
revoke all on public.content_provider_callbacks from public,anon,authenticated;
grant select,insert,update on public.content_provider_callbacks to service_role;

create table if not exists public.content_retention_receipts (
  id uuid primary key default gen_random_uuid(),
  job_id uuid not null unique references public.content_lifecycle_jobs(id),
  content_id uuid,
  owner_id uuid,
  dry_run boolean not null default false,
  deleted_objects jsonb not null default '[]'::jsonb check (jsonb_typeof(deleted_objects)='array'),
  deleted_rows jsonb not null default '[]'::jsonb check (jsonb_typeof(deleted_rows)='array'),
  backup_expiry_policy text not null default 'immutable_backup_expiry',
  completed_at timestamptz not null default now()
);
alter table public.content_retention_receipts enable row level security;
revoke all on public.content_retention_receipts from public,anon,authenticated;
grant select,insert on public.content_retention_receipts to service_role;

create or replace function public.claim_due_content_schedules(p_worker_id text,p_limit integer default 20,p_lease_seconds integer default 60)
returns setof public.content_schedules
language plpgsql security definer set search_path=pg_catalog,public
as $$
begin
 return query
 with due as (
   select id from public.content_schedules
   where publish_at<=now() and attempts<max_attempts
    and (status='scheduled' or (status='processing' and lease_expires_at<now()))
   order by publish_at,created_at for update skip locked
   limit greatest(1,least(p_limit,50))
 )
 update public.content_schedules s
 set status='processing',attempts=s.attempts+1,last_attempt_at=now(),
     lease_token=gen_random_uuid(),
     lease_expires_at=now()+make_interval(secs=>greatest(15,least(p_lease_seconds,300))),
     updated_at=now()
 from due where s.id=due.id returning s.*;
end;
$$;

create or replace function public.publish_scheduled_content(p_schedule_id uuid,p_lease_token uuid)
returns jsonb language plpgsql security definer set search_path=pg_catalog,public
as $$
declare v_schedule public.content_schedules%rowtype; v_content public.content_items%rowtype;
begin
 select * into v_schedule from public.content_schedules
 where id=p_schedule_id and status='processing' and lease_token=p_lease_token
 for update;
 if not found then return jsonb_build_object('outcome','lease_lost'); end if;
 select * into v_content from public.content_items
 where id=v_schedule.content_id and owner_id=v_schedule.owner_id
 for update;
 if not found then return jsonb_build_object('outcome','content_missing'); end if;
 if v_content.status not in ('scheduled','draft','failed')
   or v_content.version<>v_schedule.content_version
   or v_content.moderation_status<>'approved'
   or v_content.provenance->>'rights_confirmed' is distinct from 'true'
 then return jsonb_build_object('outcome','policy_recheck_failed'); end if;
 if exists(select 1 from public.content_media m where m.content_id=v_content.id and m.status<>'ready') then
   return jsonb_build_object('outcome','media_not_ready');
 end if;
 update public.content_items set status='published',published_at=now(),deleted_at=null,version=version+1
 where id=v_content.id returning * into v_content;
 update public.content_schedules set status='published',published_at=now(),lease_token=null,lease_expires_at=null,updated_at=now()
 where id=v_schedule.id;
 insert into public.content_lifecycle_events(event_key,event_type,content_id,owner_id,payload)
 values ('content.published:'||v_schedule.id::text,'content.published',v_content.id,v_content.owner_id,
   jsonb_build_object('schedule_id',v_schedule.id,'published_at',now(),'version',v_content.version))
 on conflict(event_key) do nothing;
 return jsonb_build_object('outcome','published','content',to_jsonb(v_content));
end;
$$;

create or replace function public.fail_content_schedule(p_schedule_id uuid,p_lease_token uuid,p_error_code text)
returns text language plpgsql security definer set search_path=pg_catalog,public
as $$
declare v_state text;
begin
 update public.content_schedules
 set status=case when attempts>=max_attempts then 'failed' else 'scheduled' end,
     publish_at=case when attempts>=max_attempts then publish_at else now()+make_interval(secs=>least(3600,(power(2,least(attempts,10))::integer)*5)) end,
     lease_token=null,lease_expires_at=null,last_error_code=left(coalesce(p_error_code,'UNKNOWN'),80),updated_at=now()
 where id=p_schedule_id and status='processing' and lease_token=p_lease_token
 returning status into v_state;
 return coalesce(v_state,'lease_lost');
end;
$$;

create or replace function public.complete_content_provider_job(
 p_job_id uuid,p_lease_token uuid,p_media_id uuid,p_provider text,p_provider_asset_id text,
 p_provider_event_id text,p_payload_sha256 text,p_derivatives jsonb,p_scan_status text
) returns jsonb language plpgsql security definer set search_path=pg_catalog,public
as $$
declare v_job public.content_lifecycle_jobs%rowtype; v_media public.content_media%rowtype; v_callback public.content_provider_callbacks%rowtype;
begin
 select * into v_job from public.content_lifecycle_jobs
 where id=p_job_id and status='processing' and lease_token=p_lease_token
 for update;
 if not found or v_job.job_type<>'media_transcode' or v_job.media_id<>p_media_id then
  return jsonb_build_object('outcome','lease_lost');
 end if;
 if p_scan_status<>'clean' or jsonb_typeof(p_derivatives)<>'array' or jsonb_array_length(p_derivatives)<1 then
  return jsonb_build_object('outcome','processing_incomplete');
 end if;
 insert into public.content_provider_callbacks(provider,provider_event_id,media_id,job_id,payload_sha256,outcome,processed_at)
 values(p_provider,p_provider_event_id,p_media_id,p_job_id,p_payload_sha256,'processed',now())
 on conflict(provider,provider_event_id) do nothing;
 select * into v_callback from public.content_provider_callbacks
 where provider=p_provider and provider_event_id=p_provider_event_id;
 if v_callback.media_id<>p_media_id or v_callback.job_id<>p_job_id or v_callback.payload_sha256<>p_payload_sha256 then
  return jsonb_build_object('outcome','callback_replay_mismatch');
 end if;
 select * into v_media from public.content_media where id=p_media_id and status='processing' for update;
 if not found then return jsonb_build_object('outcome','media_not_processing'); end if;
 update public.content_media set status='ready',scan_status='clean',processed_at=now(),
  processing_version=greatest(1,processing_version+1),derivatives=p_derivatives,
  provider_asset_id=p_provider_asset_id,provider_callback_verified_at=now()
 where id=p_media_id returning * into v_media;
 update public.content_lifecycle_jobs set status='succeeded',lease_token=null,lease_expires_at=null,
  completed_at=now(),updated_at=now(),last_error_code=null where id=p_job_id;
 insert into public.content_lifecycle_events(event_key,event_type,content_id,media_id,owner_id,payload)
 values('media.ready:'||p_media_id::text,'media.ready',v_media.content_id,p_media_id,v_media.owner_id,
  jsonb_build_object('provider',p_provider,'processing_version',v_media.processing_version))
 on conflict(event_key) do nothing;
 return jsonb_build_object('outcome','completed','media',to_jsonb(v_media));
end;
$$;

create or replace function public.enqueue_expired_content_retention_jobs(p_limit integer default 100)
returns integer language plpgsql security definer set search_path=pg_catalog,public
as $$
declare v_count integer;
begin
 insert into public.content_lifecycle_jobs(job_type,content_id,media_id,owner_id,idempotency_key,payload)
 select 'retention_purge',c.id,null,c.owner_id,'retention:content:'||c.id::text||':'||c.version,
   jsonb_build_object('scope','content','content_id',c.id)
 from public.content_items c
 where c.status='deleted' and c.deleted_at is not null and c.deleted_at<=now()-interval '30 days'
 and not exists(select 1 from public.content_retention_holds h where h.content_id=c.id and h.released_at is null)
 order by c.deleted_at limit greatest(1,least(p_limit,500))
 on conflict(idempotency_key) do nothing;
 get diagnostics v_count=row_count;
 insert into public.content_lifecycle_jobs(job_type,content_id,media_id,owner_id,idempotency_key,payload)
 select 'retention_purge',m.content_id,m.id,m.owner_id,'retention:media:'||m.id::text,
   jsonb_build_object('scope','abandoned_upload','media_id',m.id,'bucket_id',m.bucket_id,'storage_path',m.storage_path)
 from public.content_media m
 where m.status in ('uploading','failed') and m.created_at<=now()-interval '7 days'
 order by m.created_at limit greatest(1,least(p_limit,500))
 on conflict(idempotency_key) do nothing;
 return v_count;
end;
$$;

revoke all on function public.claim_due_content_schedules(text,integer,integer) from public,anon,authenticated;
revoke all on function public.publish_scheduled_content(uuid,uuid) from public,anon,authenticated;
revoke all on function public.fail_content_schedule(uuid,uuid,text) from public,anon,authenticated;
revoke all on function public.complete_content_provider_job(uuid,uuid,uuid,text,text,text,text,jsonb,text) from public,anon,authenticated;
revoke all on function public.enqueue_expired_content_retention_jobs(integer) from public,anon,authenticated;
grant execute on function public.claim_due_content_schedules(text,integer,integer) to service_role;
grant execute on function public.publish_scheduled_content(uuid,uuid) to service_role;
grant execute on function public.fail_content_schedule(uuid,uuid,text) to service_role;
grant execute on function public.complete_content_provider_job(uuid,uuid,uuid,text,text,text,text,jsonb,text) to service_role;
grant execute on function public.enqueue_expired_content_retention_jobs(integer) to service_role;

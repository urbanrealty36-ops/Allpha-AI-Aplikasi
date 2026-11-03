-- WP-04 durable content lifecycle foundation: media processing, scheduling and retention.
-- All jobs are private service-owned records. No client access is granted.
create table if not exists public.content_lifecycle_jobs (
  id uuid primary key default gen_random_uuid(),
  job_type text not null check (job_type in ('image_process','media_transcode','scheduled_publish','retention_purge')),
  content_id uuid references public.content_items(id) on delete set null,
  media_id uuid references public.content_media(id) on delete set null,
  owner_id uuid references auth.users(id) on delete set null,
  idempotency_key text not null unique check (char_length(idempotency_key) between 8 and 200),
  payload jsonb not null default '{}'::jsonb check (jsonb_typeof(payload)='object'),
  status text not null default 'pending' check (status in ('pending','processing','succeeded','failed','dead','cancelled')),
  attempts integer not null default 0 check (attempts >= 0),
  max_attempts integer not null default 8 check (max_attempts between 1 and 20),
  run_at timestamptz not null default now(),
  lease_token uuid,
  lease_expires_at timestamptz,
  last_error_code text check (last_error_code is null or char_length(last_error_code)<=80),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  completed_at timestamptz,
  constraint content_lifecycle_jobs_lease_consistency check (
    (status='processing' and lease_token is not null and lease_expires_at is not null)
    or (status<>'processing' and lease_token is null and lease_expires_at is null)
  )
);
create index if not exists content_lifecycle_jobs_claim_idx
  on public.content_lifecycle_jobs(run_at,created_at)
  where status in ('pending','processing');
create index if not exists content_lifecycle_jobs_media_idx
  on public.content_lifecycle_jobs(media_id,created_at desc) where media_id is not null;
alter table public.content_lifecycle_jobs enable row level security;
revoke all on public.content_lifecycle_jobs from public,anon,authenticated;
grant select,update on public.content_lifecycle_jobs to service_role;

-- Processing metadata is authoritative: ready is impossible without successful
-- processing and a clean scan. Video/audio additionally require a verified provider callback.
alter table public.content_media
  add column if not exists scan_status text not null default 'pending'
    check (scan_status in ('pending','clean','rejected','unavailable')),
  add column if not exists processed_at timestamptz,
  add column if not exists derivatives jsonb not null default '[]'::jsonb
    check (jsonb_typeof(derivatives)='array'),
  add column if not exists processing_version integer not null default 0,
  add column if not exists provider_asset_id text,
  add column if not exists provider_callback_verified_at timestamptz;

create or replace function public.content_media_readiness_guard()
returns trigger language plpgsql
set search_path = pg_catalog, public
as $$
begin
  if new.status='ready' then
    if new.processed_at is null or new.scan_status <> 'clean' or new.processing_version < 1 then
      raise exception 'MEDIA_PROCESSING_NOT_COMPLETE' using errcode='23514';
    end if;
    if new.media_type like 'image/%' and jsonb_array_length(new.derivatives)=0 then
      raise exception 'MEDIA_DERIVATIVES_MISSING' using errcode='23514';
    end if;
    if (new.media_type like 'video/%' or new.media_type like 'audio/%')
       and (new.provider_asset_id is null or new.provider_callback_verified_at is null) then
      raise exception 'MEDIA_PROVIDER_CALLBACK_NOT_VERIFIED' using errcode='23514';
    end if;
  end if;
  return new;
end;
$$;
revoke all on function public.content_media_readiness_guard() from public,anon,authenticated;
drop trigger if exists content_media_readiness_guard on public.content_media;
create trigger content_media_readiness_guard before insert or update on public.content_media
for each row execute function public.content_media_readiness_guard();

create or replace function public.enqueue_content_media_processing()
returns trigger language plpgsql
security definer
set search_path = pg_catalog, public
as $$
declare v_job_type text;
begin
  if new.status='uploaded' and (tg_op='INSERT' or old.status is distinct from new.status) then
    v_job_type := case when new.media_type like 'image/%' then 'image_process' else 'media_transcode' end;
    insert into public.content_lifecycle_jobs(job_type,content_id,media_id,owner_id,idempotency_key,payload)
    values (
      v_job_type,new.content_id,new.id,new.owner_id,'media:'||new.id::text||':v1',
      jsonb_build_object('bucket_id',new.bucket_id,'storage_path',new.storage_path,'media_type',new.media_type,'sha256',new.sha256,'size_bytes',new.size_bytes)
    ) on conflict (idempotency_key) do nothing;
    update public.content_media set status='processing' where id=new.id and status='uploaded';
  end if;
  return new;
end;
$$;
revoke all on function public.enqueue_content_media_processing() from public,anon,authenticated;
drop trigger if exists content_media_enqueue_processing on public.content_media;
create trigger content_media_enqueue_processing after insert or update of status on public.content_media
for each row execute function public.enqueue_content_media_processing();

create or replace function public.claim_content_lifecycle_jobs(
  p_worker_id text, p_limit integer default 10, p_lease_seconds integer default 60
) returns setof public.content_lifecycle_jobs
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
begin
  return query
  with candidates as (
    select id from public.content_lifecycle_jobs
    where run_at <= now() and attempts < max_attempts
      and (status='pending' or (status='processing' and lease_expires_at < now()))
    order by run_at,created_at
    for update skip locked
    limit greatest(1,least(p_limit,50))
  )
  update public.content_lifecycle_jobs j
  set status='processing', attempts=j.attempts+1,
      lease_token=gen_random_uuid(),
      lease_expires_at=now()+make_interval(secs=>greatest(15,least(p_lease_seconds,300))),
      updated_at=now()
  from candidates c where j.id=c.id
  returning j.*;
end;
$$;

create or replace function public.fail_content_lifecycle_job(
  p_job_id uuid,p_lease_token uuid,p_error_code text
) returns text
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
declare v_state text;
begin
  update public.content_lifecycle_jobs
  set status=case when attempts>=max_attempts then 'dead' else 'pending' end,
      run_at=case when attempts>=max_attempts then run_at else now()+make_interval(secs=>least(3600,(power(2,least(attempts,10))::integer)*5)) end,
      lease_token=null,lease_expires_at=null,
      last_error_code=left(coalesce(p_error_code,'UNKNOWN'),80),updated_at=now()
  where id=p_job_id and status='processing' and lease_token=p_lease_token
  returning status into v_state;
  return coalesce(v_state,'lease_lost');
end;
$$;
revoke all on function public.claim_content_lifecycle_jobs(text,integer,integer) from public,anon,authenticated;
revoke all on function public.fail_content_lifecycle_job(uuid,uuid,text) from public,anon,authenticated;
grant execute on function public.claim_content_lifecycle_jobs(text,integer,integer) to service_role;
grant execute on function public.fail_content_lifecycle_job(uuid,uuid,text) to service_role;

-- Scheduled publication records are version-bound and retain creator timezone context.
create table if not exists public.content_schedules (
  id uuid primary key default gen_random_uuid(),
  content_id uuid not null references public.content_items(id) on delete cascade,
  owner_id uuid not null references auth.users(id) on delete cascade,
  content_version integer not null check (content_version>0),
  publish_at timestamptz not null,
  creator_timezone text not null,
  status text not null default 'scheduled' check (status in ('scheduled','processing','published','cancelled','failed')),
  idempotency_key text not null unique,
  attempts integer not null default 0 check (attempts>=0),
  last_error_code text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint content_schedules_content_owner_fk foreign key(content_id,owner_id)
    references public.content_items(id,owner_id) on delete cascade
);
create unique index if not exists content_schedules_one_active_per_content
  on public.content_schedules(content_id) where status in ('scheduled','processing');
create index if not exists content_schedules_due_idx
  on public.content_schedules(publish_at) where status='scheduled';
alter table public.content_schedules enable row level security;
revoke all on public.content_schedules from public,anon,authenticated;
grant select on public.content_schedules to authenticated;
create policy content_schedules_owner_select on public.content_schedules
  for select to authenticated using (owner_id=(select auth.uid()));

-- Legal/safety holds are operator-managed, immutable in scope, and block purge.
create table if not exists public.content_retention_holds (
  id uuid primary key default gen_random_uuid(),
  content_id uuid not null references public.content_items(id) on delete cascade,
  owner_id uuid not null references auth.users(id) on delete cascade,
  hold_type text not null check (hold_type in ('legal','safety','regulatory')),
  reason text not null check (char_length(reason) between 8 and 1000),
  created_by uuid not null references auth.users(id),
  released_by uuid references auth.users(id),
  released_at timestamptz,
  created_at timestamptz not null default now(),
  constraint content_retention_holds_content_owner_fk foreign key(content_id,owner_id)
    references public.content_items(id,owner_id) on delete cascade,
  constraint content_retention_holds_release_pair check ((released_at is null and released_by is null) or (released_at is not null and released_by is not null))
);
create index if not exists content_retention_holds_active_idx on public.content_retention_holds(content_id) where released_at is null;
alter table public.content_retention_holds enable row level security;
revoke all on public.content_retention_holds from public,anon,authenticated;
grant select,insert,update on public.content_retention_holds to service_role;

-- Published content cannot pass readiness with an uploaded/processing/failed media object.
create or replace function public.content_publish_media_guard()
returns trigger language plpgsql
set search_path = pg_catalog, public
as $$
begin
  if new.status='published' and exists (
    select 1 from public.content_media m
    where m.content_id=new.id and m.status<>'ready'
  ) then
    raise exception 'CONTENT_MEDIA_NOT_READY' using errcode='23514';
  end if;
  return new;
end;
$$;
revoke all on function public.content_publish_media_guard() from public,anon,authenticated;
drop trigger if exists content_publish_media_guard on public.content_items;
create trigger content_publish_media_guard before insert or update of status on public.content_items
for each row execute function public.content_publish_media_guard();

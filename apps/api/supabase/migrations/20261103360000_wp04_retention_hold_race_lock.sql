create table if not exists public.content_retention_purge_locks(
 content_id uuid not null references public.content_items(id) on delete cascade,
 job_id uuid not null references public.content_lifecycle_jobs(id) on delete cascade,
 scope text not null check(scope in ('content','abandoned_upload')),
 locked_at timestamptz not null default now(),
 released_at timestamptz,
 primary key(content_id,job_id)
);
alter table public.content_retention_purge_locks enable row level security;
revoke all on public.content_retention_purge_locks from public,anon,authenticated;
grant select,insert,update on public.content_retention_purge_locks to service_role;

create or replace function public.guard_content_retention_hold()
returns trigger language plpgsql security definer set search_path=pg_catalog,public
as $$
declare v_purge timestamptz;
begin
 select purge_started_at into v_purge from public.content_items
 where id=new.content_id and owner_id=new.owner_id for update;
 if not found or v_purge is not null or exists(
  select 1 from public.content_retention_purge_locks l
  where l.content_id=new.content_id and l.released_at is null
 ) then
  raise exception 'CONTENT_RETENTION_PURGE_LOCKED' using errcode='23514';
 end if;
 return new;
end;
$$;

create or replace function public.begin_content_retention_purge(p_job_id uuid,p_lease_token uuid)
returns jsonb language plpgsql security definer set search_path=pg_catalog,public
as $$
declare v_job public.content_lifecycle_jobs%rowtype;v_content public.content_items%rowtype;v_content_id uuid;
begin
 select * into v_job from public.content_lifecycle_jobs
 where id=p_job_id and status='processing' and lease_token=p_lease_token and job_type='retention_purge'
 for update;
 if not found then return jsonb_build_object('outcome','lease_lost'); end if;
 if v_job.payload->>'scope'='content' then
  v_content_id:=(v_job.payload->>'content_id')::uuid;
  select * into v_content from public.content_items where id=v_content_id for update;
  if found then
   if v_content.status<>'deleted' or v_content.deleted_at>now()-interval '30 days' then return jsonb_build_object('outcome','not_expired'); end if;
   if exists(select 1 from public.content_retention_holds h where h.content_id=v_content.id and h.released_at is null) then return jsonb_build_object('outcome','legal_hold'); end if;
   update public.content_items set purge_started_at=coalesce(purge_started_at,now()) where id=v_content.id;
  end if;
 elsif v_job.payload->>'scope'='abandoned_upload' then
  v_content_id:=v_job.content_id;
  if v_content_id is not null then
   select * into v_content from public.content_items where id=v_content_id for update;
   if exists(select 1 from public.content_retention_holds h where h.content_id=v_content_id and h.released_at is null) then return jsonb_build_object('outcome','legal_hold'); end if;
  end if;
 else return jsonb_build_object('outcome','invalid_scope'); end if;
 if v_content_id is not null then
  insert into public.content_retention_purge_locks(content_id,job_id,scope)
  values(v_content_id,p_job_id,v_job.payload->>'scope')
  on conflict(content_id,job_id) do update set released_at=null;
 end if;
 return jsonb_build_object('outcome','authorized');
end;
$$;

create or replace function public.release_content_retention_purge_lock(p_job_id uuid)
returns integer language plpgsql security definer set search_path=pg_catalog,public
as $$
declare v_count integer;
begin
 update public.content_retention_purge_locks set released_at=now()
 where job_id=p_job_id and released_at is null;
 get diagnostics v_count=row_count;
 return v_count;
end;
$$;
revoke all on function public.release_content_retention_purge_lock(uuid) from public,anon,authenticated;
grant execute on function public.release_content_retention_purge_lock(uuid) to service_role;

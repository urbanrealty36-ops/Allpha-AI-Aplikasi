alter table public.content_items add column if not exists purge_started_at timestamptz;
create or replace function public.guard_content_retention_hold()
returns trigger language plpgsql security definer set search_path=pg_catalog,public
as $$
declare v_purge timestamptz;
begin
 select purge_started_at into v_purge from public.content_items
 where id=new.content_id and owner_id=new.owner_id for update;
 if not found or v_purge is not null then
  raise exception 'CONTENT_RETENTION_PURGE_LOCKED' using errcode='23514';
 end if;
 return new;
end;
$$;
revoke all on function public.guard_content_retention_hold() from public,anon,authenticated;
drop trigger if exists content_retention_hold_guard on public.content_retention_holds;
create trigger content_retention_hold_guard before insert on public.content_retention_holds
for each row execute function public.guard_content_retention_hold();

create or replace function public.begin_content_retention_purge(p_job_id uuid,p_lease_token uuid)
returns jsonb language plpgsql security definer set search_path=pg_catalog,public
as $$
declare v_job public.content_lifecycle_jobs%rowtype; v_content public.content_items%rowtype;
begin
 select * into v_job from public.content_lifecycle_jobs where id=p_job_id and status='processing' and lease_token=p_lease_token and job_type='retention_purge' for update;
 if not found then return jsonb_build_object('outcome','lease_lost'); end if;
 if v_job.payload->>'scope'='content' then
  select * into v_content from public.content_items where id=(v_job.payload->>'content_id')::uuid for update;
  if not found or v_content.status<>'deleted' or v_content.deleted_at>now()-interval '30 days' then return jsonb_build_object('outcome','not_expired'); end if;
  if exists(select 1 from public.content_retention_holds h where h.content_id=v_content.id and h.released_at is null) then return jsonb_build_object('outcome','legal_hold'); end if;
  update public.content_items set purge_started_at=coalesce(purge_started_at,now()) where id=v_content.id;
 elsif v_job.payload->>'scope'='abandoned_upload' then
  if exists(select 1 from public.content_retention_holds h where h.content_id=v_job.content_id and h.released_at is null) then return jsonb_build_object('outcome','legal_hold'); end if;
 else return jsonb_build_object('outcome','invalid_scope'); end if;
 return jsonb_build_object('outcome','authorized');
end;
$$;
revoke all on function public.begin_content_retention_purge(uuid,uuid) from public,anon,authenticated;
grant execute on function public.begin_content_retention_purge(uuid,uuid) to service_role;

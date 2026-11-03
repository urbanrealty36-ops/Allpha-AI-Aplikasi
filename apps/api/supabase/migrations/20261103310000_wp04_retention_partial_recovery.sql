create or replace function public.begin_content_retention_purge(p_job_id uuid,p_lease_token uuid)
returns jsonb language plpgsql security definer set search_path=pg_catalog,public
as $$
declare v_job public.content_lifecycle_jobs%rowtype;v_content public.content_items%rowtype;
begin
 select * into v_job from public.content_lifecycle_jobs
 where id=p_job_id and status='processing' and lease_token=p_lease_token and job_type='retention_purge'
 for update;
 if not found then return jsonb_build_object('outcome','lease_lost'); end if;
 if v_job.payload->>'scope'='content' then
  select * into v_content from public.content_items where id=(v_job.payload->>'content_id')::uuid for update;
  if not found then return jsonb_build_object('outcome','authorized','resume_after_parent_delete',true); end if;
  if v_content.status<>'deleted' or v_content.deleted_at>now()-interval '30 days' then
   return jsonb_build_object('outcome','not_expired');
  end if;
  if exists(select 1 from public.content_retention_holds h where h.content_id=v_content.id and h.released_at is null) then
   return jsonb_build_object('outcome','legal_hold');
  end if;
  update public.content_items set purge_started_at=coalesce(purge_started_at,now()) where id=v_content.id;
 elsif v_job.payload->>'scope'='abandoned_upload' then
  if v_job.content_id is not null and exists(select 1 from public.content_retention_holds h where h.content_id=v_job.content_id and h.released_at is null) then
   return jsonb_build_object('outcome','legal_hold');
  end if;
 else return jsonb_build_object('outcome','invalid_scope'); end if;
 return jsonb_build_object('outcome','authorized');
end;
$$;
revoke all on function public.begin_content_retention_purge(uuid,uuid) from public,anon,authenticated;
grant execute on function public.begin_content_retention_purge(uuid,uuid) to service_role;

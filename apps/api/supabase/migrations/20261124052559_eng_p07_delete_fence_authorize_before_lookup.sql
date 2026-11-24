-- ENG-P07 forward repair: authorize the active owner before revealing source existence.
create or replace function public.begin_agent_knowledge_source_delete(
  p_source_id uuid,p_agent_id uuid,p_owner_id uuid
) returns jsonb
language plpgsql security definer set search_path=''
as $function$
declare v_source public.agent_knowledge_sources%rowtype; v_cancelled integer:=0;
begin
 if p_source_id is null or p_agent_id is null or p_owner_id is null then
  raise exception 'KNOWLEDGE_DELETE_ARGUMENTS_INVALID' using errcode='22023'; end if;
 if not exists(
  select 1 from public.agent_ownerships o
   where o.agent_id=p_agent_id and o.owner_user_id=p_owner_id
    and o.ownership_role='owner' and o.status='active'
 ) then
  raise exception 'AGENT_OWNER_REQUIRED' using errcode='42501';
 end if;
 select * into v_source from public.agent_knowledge_sources s
  where s.id=p_source_id and s.agent_id=p_agent_id and s.owner_id=p_owner_id for update;
 if not found then return jsonb_build_object('already_deleted',true); end if;
 update public.agent_knowledge_sources set status='deleting',processing_stage='source_deleting',
  error_code=null,updated_at=clock_timestamp()
 where id=v_source.id and agent_id=v_source.agent_id and owner_id=v_source.owner_id;
 update public.agent_knowledge_jobs set status='cancelled',stage='source_deleted',
  error_code='SOURCE_DELETED',lease_token=null,lease_expires_at=null,updated_at=clock_timestamp()
 where source_id=v_source.id and owner_id=v_source.owner_id and agent_id=v_source.agent_id
  and status in ('queued','processing');
 get diagnostics v_cancelled=row_count;
 return jsonb_build_object('already_deleted',false,'source_id',v_source.id,
  'storage_path',v_source.storage_path,'source_version',v_source.source_version,
  'cancelled_jobs',v_cancelled);
end;
$function$;
revoke all on function public.begin_agent_knowledge_source_delete(uuid,uuid,uuid) from public,anon,authenticated;
grant execute on function public.begin_agent_knowledge_source_delete(uuid,uuid,uuid) to service_role;
notify pgrst, 'reload schema';

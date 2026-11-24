-- ENG-P07: idempotent owner-scoped enqueue for quarantined Knowledge documents.
create or replace function public.enqueue_agent_knowledge_document_job(
  p_source_id uuid,p_agent_id uuid,p_owner_id uuid,p_reason text default null
) returns jsonb
language plpgsql security definer set search_path=''
as $function$
declare
  v_source public.agent_knowledge_sources%rowtype;
  v_existing public.agent_knowledge_jobs%rowtype;
  v_job public.agent_knowledge_jobs%rowtype;
  v_sequence integer;
  v_key text;
begin
  if p_source_id is null or p_agent_id is null or p_owner_id is null
     or (p_reason is not null and char_length(p_reason)>300) then
    raise exception 'KNOWLEDGE_ENQUEUE_ARGUMENTS_INVALID' using errcode='22023';
  end if;
  select * into v_source from public.agent_knowledge_sources s
   where s.id=p_source_id and s.agent_id=p_agent_id and s.owner_id=p_owner_id
   for update;
  if not found then raise exception 'KNOWLEDGE_SOURCE_NOT_FOUND' using errcode='P0002'; end if;
  if v_source.status not in ('quarantined','failed') then
    raise exception 'KNOWLEDGE_SOURCE_STATE_CONFLICT' using errcode='40001';
  end if;
  select * into v_existing from public.agent_knowledge_jobs j
   where j.source_id=p_source_id and j.source_version=v_source.source_version
     and j.owner_id=p_owner_id and j.stage='awaiting_malware_scan'
     and j.status in ('queued','processing')
   order by j.created_at desc limit 1 for update;
  if found then return to_jsonb(v_existing)||jsonb_build_object('idempotent_replay',true); end if;
  select count(*)+1 into v_sequence from public.agent_knowledge_jobs j
   where j.source_id=p_source_id and j.source_version=v_source.source_version
     and j.owner_id=p_owner_id and j.stage='awaiting_malware_scan';
  v_key:='knowledge:'||p_source_id::text||':v'||v_source.source_version::text||':document:'||v_sequence::text;
  insert into public.agent_knowledge_jobs(
    source_id,source_version,agent_id,owner_id,status,stage,attempt,progress,idempotency_key
  ) values(
    p_source_id,v_source.source_version,p_agent_id,p_owner_id,'queued','awaiting_malware_scan',0,0,v_key
  ) returning * into v_job;
  update public.agent_knowledge_sources set status='quarantined',
    processing_stage='awaiting_malware_scan',error_code=null,updated_at=clock_timestamp()
   where id=p_source_id and agent_id=p_agent_id and owner_id=p_owner_id
     and source_version=v_source.source_version;
  return to_jsonb(v_job)||jsonb_build_object('idempotent_replay',false,'retry_reason',p_reason);
end;
$function$;

revoke all on function public.enqueue_agent_knowledge_document_job(uuid,uuid,uuid,text) from public,anon,authenticated;
grant execute on function public.enqueue_agent_knowledge_document_job(uuid,uuid,uuid,text) to service_role;
notify pgrst, 'reload schema';

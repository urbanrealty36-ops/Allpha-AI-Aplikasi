-- ENG-P07: lease-fenced document chunk persistence and atomic embedding handoff.
create or replace function public.persist_agent_knowledge_chunk_batch(
  p_job_id uuid,
  p_lease_token uuid,
  p_source_version integer,
  p_reset boolean,
  p_chunks jsonb
) returns integer
language plpgsql security definer set search_path=''
as $function$
declare
  v_job public.agent_knowledge_jobs%rowtype;
  v_source public.agent_knowledge_sources%rowtype;
  v_item jsonb;
  v_content text;
  v_digest text;
  v_location jsonb;
  v_chunk_index integer;
  v_count integer:=0;
begin
  if p_source_version is null or p_source_version<1
     or jsonb_typeof(p_chunks)<>'array'
     or jsonb_array_length(p_chunks)>100 then
    raise exception 'KNOWLEDGE_CHUNK_BATCH_INVALID' using errcode='22023';
  end if;
  select * into v_job from public.agent_knowledge_jobs j where j.id=p_job_id for update;
  if not found or v_job.status<>'processing' or v_job.stage<>'awaiting_malware_scan'
     or v_job.lease_token is distinct from p_lease_token
     or v_job.lease_expires_at is null or v_job.lease_expires_at<=clock_timestamp()
     or v_job.source_version<>p_source_version then
    raise exception 'KNOWLEDGE_JOB_LEASE_INVALID' using errcode='42501';
  end if;
  select * into v_source from public.agent_knowledge_sources s
   where s.id=v_job.source_id and s.owner_id=v_job.owner_id and s.agent_id=v_job.agent_id
     and s.source_version=p_source_version and s.status in ('quarantined','processing','failed')
   for update;
  if not found then raise exception 'KNOWLEDGE_SOURCE_VERSION_INVALID' using errcode='40001'; end if;
  if p_reset then
    delete from public.agent_knowledge_chunks c
     where c.source_id=v_source.id and c.owner_id=v_source.owner_id and c.agent_id=v_source.agent_id;
  end if;
  for v_item in select value from jsonb_array_elements(p_chunks)
  loop
    v_content:=v_item->>'content';
    v_digest:=lower(coalesce(v_item->>'content_sha256',''));
    v_location:=v_item->'source_location';
    v_chunk_index:=nullif(v_item->>'chunk_index','')::integer;
    if v_content is null or length(v_content)=0 or length(v_content)>1800
       or v_chunk_index is null or v_chunk_index<0
       or jsonb_typeof(v_location)<>'object'
       or v_digest !~ '^[0-9a-f]{64}$'
       or encode(extensions.digest(convert_to(v_content,'UTF8'),'sha256'),'hex')<>v_digest then
      raise exception 'KNOWLEDGE_CHUNK_PROVENANCE_INVALID' using errcode='23514';
    end if;
    insert into public.agent_knowledge_chunks(
      source_id,agent_id,owner_id,chunk_index,content,source_location,source_version,content_sha256
    ) values(
      v_source.id,v_source.agent_id,v_source.owner_id,v_chunk_index,v_content,v_location,p_source_version,v_digest
    )
    on conflict(source_id,source_version,chunk_index) do update
      set content=excluded.content,source_location=excluded.source_location,
          content_sha256=excluded.content_sha256,created_at=clock_timestamp()
      where public.agent_knowledge_chunks.owner_id=excluded.owner_id
        and public.agent_knowledge_chunks.agent_id=excluded.agent_id;
    if not found then raise exception 'KNOWLEDGE_CHUNK_IDENTITY_CONFLICT' using errcode='23505'; end if;
    v_count:=v_count+1;
  end loop;
  return v_count;
end;
$function$;

create or replace function public.complete_agent_knowledge_document_parse(
  p_job_id uuid,
  p_lease_token uuid,
  p_source_version integer,
  p_expected_chunk_count integer
) returns jsonb
language plpgsql security definer set search_path=''
as $function$
declare
  v_job public.agent_knowledge_jobs%rowtype;
  v_source public.agent_knowledge_sources%rowtype;
  v_actual_count integer;
  v_embedding_job public.agent_knowledge_jobs%rowtype;
  v_idempotency_key text;
begin
  if p_source_version is null or p_source_version<1
     or p_expected_chunk_count is null or p_expected_chunk_count<1 then
    raise exception 'KNOWLEDGE_PARSE_COMPLETION_INVALID' using errcode='22023';
  end if;
  select * into v_job from public.agent_knowledge_jobs j where j.id=p_job_id for update;
  if not found or v_job.status<>'processing' or v_job.stage<>'awaiting_malware_scan'
     or v_job.lease_token is distinct from p_lease_token
     or v_job.lease_expires_at is null or v_job.lease_expires_at<=clock_timestamp()
     or v_job.source_version<>p_source_version then
    raise exception 'KNOWLEDGE_JOB_LEASE_INVALID' using errcode='42501';
  end if;
  select * into v_source from public.agent_knowledge_sources s
   where s.id=v_job.source_id and s.owner_id=v_job.owner_id and s.agent_id=v_job.agent_id
     and s.source_version=p_source_version and s.status in ('quarantined','processing','failed')
   for update;
  if not found then raise exception 'KNOWLEDGE_SOURCE_VERSION_INVALID' using errcode='40001'; end if;
  select count(*) into v_actual_count from public.agent_knowledge_chunks c
   where c.source_id=v_source.id and c.owner_id=v_source.owner_id and c.agent_id=v_source.agent_id
     and c.source_version=p_source_version;
  if v_actual_count<>p_expected_chunk_count then
    raise exception 'KNOWLEDGE_CHUNK_COUNT_MISMATCH' using errcode='23514';
  end if;
  v_idempotency_key:='knowledge:'||v_source.id::text||':v'||p_source_version::text||':embedding_indexing';
  insert into public.agent_knowledge_jobs(
    source_id,source_version,agent_id,owner_id,status,stage,attempt,progress,idempotency_key
  ) values(
    v_source.id,p_source_version,v_source.agent_id,v_source.owner_id,'queued','embedding_indexing',0,75,v_idempotency_key
  )
  on conflict(owner_id,idempotency_key) where idempotency_key is not null
  do update set
    status=case when public.agent_knowledge_jobs.status in ('failed','cancelled') then 'queued' else public.agent_knowledge_jobs.status end,
    stage='embedding_indexing',
    attempt=case when public.agent_knowledge_jobs.status in ('failed','cancelled') then 0 else public.agent_knowledge_jobs.attempt end,
    progress=case when public.agent_knowledge_jobs.status in ('failed','cancelled') then 75 else public.agent_knowledge_jobs.progress end,
    error_code=case when public.agent_knowledge_jobs.status in ('failed','cancelled') then null else public.agent_knowledge_jobs.error_code end,
    available_at=case when public.agent_knowledge_jobs.status in ('failed','cancelled') then clock_timestamp() else public.agent_knowledge_jobs.available_at end,
    lease_token=case when public.agent_knowledge_jobs.status in ('failed','cancelled') then null else public.agent_knowledge_jobs.lease_token end,
    lease_expires_at=case when public.agent_knowledge_jobs.status in ('failed','cancelled') then null else public.agent_knowledge_jobs.lease_expires_at end,
    updated_at=clock_timestamp()
  returning * into v_embedding_job;
  update public.agent_knowledge_sources
   set status='indexed_pending_embeddings',processing_stage='awaiting_model_router',error_code=null,updated_at=clock_timestamp()
   where id=v_source.id and owner_id=v_source.owner_id and agent_id=v_source.agent_id and source_version=p_source_version;
  update public.agent_knowledge_jobs
   set status='succeeded',stage='text_extracted',progress=70,error_code=null,
       lease_token=null,lease_expires_at=null,updated_at=clock_timestamp()
   where id=v_job.id and status='processing' and lease_token=p_lease_token;
  return jsonb_build_object(
    'source_id',v_source.id,'source_version',p_source_version,'chunks_created',v_actual_count,
    'embedding_job_id',v_embedding_job.id,'embedding_job_status',v_embedding_job.status,
    'retrieval_ready',false
  );
end;
$function$;

revoke all on function public.persist_agent_knowledge_chunk_batch(uuid,uuid,integer,boolean,jsonb) from public,anon,authenticated;
revoke all on function public.complete_agent_knowledge_document_parse(uuid,uuid,integer,integer) from public,anon,authenticated;
grant execute on function public.persist_agent_knowledge_chunk_batch(uuid,uuid,integer,boolean,jsonb) to service_role;
grant execute on function public.complete_agent_knowledge_document_parse(uuid,uuid,integer,integer) to service_role;

notify pgrst, 'reload schema';

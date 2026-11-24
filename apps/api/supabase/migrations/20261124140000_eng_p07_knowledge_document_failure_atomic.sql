-- ENG-P07: atomically persist document worker failure/retry state with the source.
create or replace function public.fail_agent_knowledge_document_job(
  p_job_id uuid,p_lease_token uuid,p_error_code text,p_stage text,
  p_retryable boolean default false,p_retry_delay_seconds integer default 30
) returns text
language plpgsql security definer set search_path=''
as $function$
declare
  v_job public.agent_knowledge_jobs%rowtype;
  v_source public.agent_knowledge_sources%rowtype;
  v_outcome text;
begin
  if p_error_code is null or p_error_code !~ '^[A-Z0-9_]{3,80}$'
     or p_stage not in ('malware_scan_failed','malware_scan_retry','storage_retry',
                        'document_parse_failed','chunk_persistence_retry','document_worker_failed')
     or p_retry_delay_seconds<0 or p_retry_delay_seconds>3600 then
    raise exception 'KNOWLEDGE_FAILURE_ARGUMENTS_INVALID' using errcode='22023';
  end if;
  select * into v_job from public.agent_knowledge_jobs j where j.id=p_job_id for update;
  if not found or v_job.status<>'processing' or v_job.stage<>'awaiting_malware_scan'
     or v_job.lease_token is distinct from p_lease_token
     or v_job.lease_expires_at is null or v_job.lease_expires_at<=clock_timestamp() then
    return 'lease_lost';
  end if;
  select * into v_source from public.agent_knowledge_sources s
   where s.id=v_job.source_id and s.owner_id=v_job.owner_id and s.agent_id=v_job.agent_id
   for update;
  if not found or v_source.source_version<>v_job.source_version or v_source.status='deleting' then
    update public.agent_knowledge_jobs set status='cancelled',stage='stale_source_version',
      error_code='STALE_SOURCE_VERSION',lease_token=null,lease_expires_at=null,updated_at=clock_timestamp()
     where id=v_job.id;
    return 'cancelled';
  end if;
  if coalesce(p_retryable,false) and v_job.attempt<v_job.max_attempts then
    update public.agent_knowledge_jobs set status='queued',stage='awaiting_malware_scan',
      progress=least(progress,20),error_code=p_error_code,
      available_at=clock_timestamp()+make_interval(secs=>p_retry_delay_seconds),
      lease_token=null,lease_expires_at=null,updated_at=clock_timestamp()
     where id=v_job.id;
    update public.agent_knowledge_sources set status='quarantined',processing_stage=p_stage,
      error_code=p_error_code,updated_at=clock_timestamp()
     where id=v_source.id and source_version=v_job.source_version;
    v_outcome:='queued';
  else
    update public.agent_knowledge_jobs set status='failed',stage=p_stage,progress=least(progress,99),
      error_code=p_error_code,lease_token=null,lease_expires_at=null,updated_at=clock_timestamp()
     where id=v_job.id;
    update public.agent_knowledge_sources set status='failed',processing_stage=p_stage,
      error_code=p_error_code,updated_at=clock_timestamp()
     where id=v_source.id and source_version=v_job.source_version;
    v_outcome:='failed';
  end if;
  return v_outcome;
end;
$function$;

revoke all on function public.fail_agent_knowledge_document_job(uuid,uuid,text,text,boolean,integer) from public,anon,authenticated;
grant execute on function public.fail_agent_knowledge_document_job(uuid,uuid,text,text,boolean,integer) to service_role;
notify pgrst, 'reload schema';

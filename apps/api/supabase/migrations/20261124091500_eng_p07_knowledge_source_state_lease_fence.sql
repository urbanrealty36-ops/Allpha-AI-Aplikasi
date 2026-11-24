-- ENG-P07: source processing-state changes must be fenced by the active document-job lease.
create or replace function public.update_agent_knowledge_source_processing_state(
  p_job_id uuid,
  p_lease_token uuid,
  p_source_version integer,
  p_stage text,
  p_scanner_receipt jsonb default null
)
returns boolean
language plpgsql
security definer
set search_path = ''
as $function$
declare
  v_job public.agent_knowledge_jobs%rowtype;
  v_source public.agent_knowledge_sources%rowtype;
begin
  if auth.role() is distinct from 'service_role' then
    raise exception 'KNOWLEDGE_WORKER_SERVICE_ROLE_REQUIRED';
  end if;
  if p_job_id is null or p_lease_token is null
     or p_source_version is null or p_source_version < 1
     or p_stage not in ('malware_scan', 'document_parsing', 'chunk_persistence') then
    raise exception 'KNOWLEDGE_SOURCE_STATE_ARGUMENTS_INVALID' using errcode = '22023';
  end if;
  if p_scanner_receipt is not null then
    if p_stage <> 'document_parsing'
       or jsonb_typeof(p_scanner_receipt) is distinct from 'object'
       or coalesce(p_scanner_receipt->>'scanner_id', '') = ''
       or coalesce(p_scanner_receipt->>'engine_version', '') = ''
       or coalesce(p_scanner_receipt->>'signature_version', '') = ''
       or coalesce(p_scanner_receipt->>'contract_version', '') = ''
       or coalesce(p_scanner_receipt->>'sha256', '') !~ '^[0-9a-f]{64}$' then
      raise exception 'KNOWLEDGE_SCANNER_RECEIPT_INVALID' using errcode = '23514';
    end if;
  end if;

  select * into v_job
    from public.agent_knowledge_jobs j
   where j.id = p_job_id
   for update;
  if not found
     or v_job.status <> 'processing'
     or v_job.stage <> 'awaiting_malware_scan'
     or v_job.lease_token is distinct from p_lease_token
     or v_job.lease_expires_at is null
     or v_job.lease_expires_at <= clock_timestamp()
     or v_job.source_version <> p_source_version then
    return false;
  end if;

  select * into v_source
    from public.agent_knowledge_sources s
   where s.id = v_job.source_id
     and s.owner_id = v_job.owner_id
     and s.agent_id = v_job.agent_id
     and s.source_version = p_source_version
     and s.status in ('quarantined', 'processing')
   for update;
  if not found then
    return false;
  end if;

  if p_scanner_receipt is not null
     and lower(p_scanner_receipt->>'sha256') <> lower(v_source.sha256) then
    raise exception 'KNOWLEDGE_SCANNER_RECEIPT_DIGEST_MISMATCH' using errcode = '23514';
  end if;

  update public.agent_knowledge_sources s
     set status = 'processing',
         processing_stage = p_stage,
         error_code = null,
         provenance = case
           when p_scanner_receipt is null then s.provenance
           else jsonb_set(coalesce(s.provenance, '{}'::jsonb), '{malware_scan}', p_scanner_receipt, true)
         end,
         updated_at = clock_timestamp()
   where s.id = v_source.id
     and s.owner_id = v_source.owner_id
     and s.agent_id = v_source.agent_id
     and s.source_version = p_source_version;

  return found;
end;
$function$;

revoke all on function public.update_agent_knowledge_source_processing_state(uuid, uuid, integer, text, jsonb)
  from public, anon, authenticated;
grant execute on function public.update_agent_knowledge_source_processing_state(uuid, uuid, integer, text, jsonb)
  to service_role;

comment on function public.update_agent_knowledge_source_processing_state(uuid, uuid, integer, text, jsonb) is
  'Updates Knowledge document processing stage and persists scanner receipt only while the current unexpired job lease and source version match.';

notify pgrst, 'reload schema';

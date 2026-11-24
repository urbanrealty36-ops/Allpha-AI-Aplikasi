-- ENG-P07 lease heartbeat shared by document parsing and embedding workers.
-- A heartbeat cannot resurrect an expired lease or extend a stale source version.
create or replace function public.heartbeat_agent_knowledge_job(
  p_job_id uuid,
  p_lease_token uuid,
  p_lease_seconds integer
)
returns boolean
language plpgsql
security definer
set search_path = ''
as $function$
begin
  if auth.role() is distinct from 'service_role' then
    raise exception 'KNOWLEDGE_WORKER_SERVICE_ROLE_REQUIRED';
  end if;
  if p_job_id is null or p_lease_token is null
     or p_lease_seconds < 10 or p_lease_seconds > 900 then
    raise exception 'KNOWLEDGE_JOB_HEARTBEAT_ARGUMENTS_INVALID';
  end if;

  update public.agent_knowledge_jobs as job
  set lease_expires_at = clock_timestamp() + make_interval(secs => p_lease_seconds),
      updated_at = clock_timestamp()
  where job.id = p_job_id
    and job.status = 'processing'
    and job.lease_token = p_lease_token
    and job.lease_expires_at > clock_timestamp()
    and exists (
      select 1
      from public.agent_knowledge_sources as source
      where source.id = job.source_id
        and source.owner_id = job.owner_id
        and source.agent_id = job.agent_id
        and source.source_version = job.source_version
        and source.status not in ('deleting', 'deleted')
    );

  return found;
end;
$function$;

revoke all on function public.heartbeat_agent_knowledge_job(uuid, uuid, integer)
  from public, anon, authenticated;
grant execute on function public.heartbeat_agent_knowledge_job(uuid, uuid, integer)
  to service_role;

comment on function public.heartbeat_agent_knowledge_job(uuid, uuid, integer) is
  'Extends only the current unexpired Knowledge job lease for the matching owner/Agent/source version.';

-- ENG-P03: qualify id references in the table-returning Storage claim RPC.
-- The function returns a column named id; every source-table id predicate must be qualified.
CREATE OR REPLACE FUNCTION public.claim_account_deletion_storage_jobs(p_execution_job_id uuid, p_job_lease_token uuid, p_limit integer DEFAULT 50, p_lease_seconds integer DEFAULT 300)
 RETURNS TABLE(id uuid, storage_bucket text, storage_path text, lease_token uuid, attempts integer)
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
declare v_job public.account_deletion_execution_jobs%rowtype;
        v_request public.account_deletion_requests%rowtype;
        v_retention_days integer;
        v_retention_until timestamptz;
        v_missing_classes integer;
begin
  if coalesce(auth.role(),'')<>'service_role' then raise exception 'service_role_required' using errcode='42501'; end if;
  select * into v_job from public.account_deletion_execution_jobs
   where public.account_deletion_execution_jobs.id=p_execution_job_id and status='running' and lease_token=p_job_lease_token
     and lease_expires_at>clock_timestamp() for update;
  if not found then raise exception 'account_deletion_execution_lease_lost' using errcode='40001'; end if;
  if exists(select 1 from public.account_legal_holds h where h.subject_ref=v_job.subject_ref and h.active) then
    update public.account_deletion_execution_jobs set status='blocked',error_code='LEGAL_HOLD_ACTIVE',
      lease_token=null,lease_owner=null,lease_expires_at=null,updated_at=clock_timestamp() where public.account_deletion_execution_jobs.id=v_job.id;
    update public.account_deletion_requests set status='blocked_legal_hold',error_code='LEGAL_HOLD_ACTIVE',
      updated_at=clock_timestamp() where public.account_deletion_requests.id=v_job.request_id;
    return;
  end if;
  select * into v_request from public.account_deletion_requests
   where public.account_deletion_requests.id=v_job.request_id for update;
  if not found or v_request.user_id is distinct from v_job.user_id then
    raise exception 'account_deletion_request_subject_mismatch' using errcode='23514';
  end if;
  select count(*) into v_missing_classes from (values
    ('owner_private'),('agent_operational'),('tenant_shared'),
    ('published_knowledge'),('session_scoped'),('public_catalog')
  ) required(data_class)
  where not exists(select 1 from public.account_data_retention_policies p
    where p.data_class=required.data_class and p.active=true
      and p.policy_version=v_job.policy_snapshot->>required.data_class);
  select coalesce(max(p.retention_days),0) into v_retention_days
    from public.account_data_retention_policies p where p.active=true;
  if v_missing_classes>0
     or v_retention_days <> coalesce((v_job.policy_snapshot->>'_retention_days')::integer,-1) then
    update public.account_deletion_execution_jobs set status='blocked',error_code='DELETION_POLICY_CHANGED',
      lease_token=null,lease_owner=null,lease_expires_at=null,updated_at=clock_timestamp() where public.account_deletion_execution_jobs.id=v_job.id;
    update public.account_deletion_requests set status='awaiting_policy',scheduled_for=null,
      error_code='DELETION_POLICY_CHANGED',updated_at=clock_timestamp() where public.account_deletion_requests.id=v_request.id;
    return;
  end if;
  v_retention_until := v_request.requested_at + pg_catalog.make_interval(days=>v_retention_days);
  if v_retention_until > pg_catalog.clock_timestamp() then
    update public.account_deletion_execution_jobs set status='blocked',error_code='RETENTION_PERIOD_ACTIVE',
      lease_token=null,lease_owner=null,lease_expires_at=null,updated_at=clock_timestamp() where public.account_deletion_execution_jobs.id=v_job.id;
    update public.account_deletion_requests set status='scheduled',scheduled_for=v_retention_until,
      error_code='RETENTION_PERIOD_ACTIVE',updated_at=clock_timestamp() where public.account_deletion_requests.id=v_request.id;
    return;
  end if;
  update public.account_deletion_storage_jobs s
     set status='preserved',completed_at=clock_timestamp(),
         error_code='PRESERVED_BY_DATA_CLASS_POLICY',lease_token=null,lease_expires_at=null,
         updated_at=clock_timestamp()
   where s.execution_job_id=p_execution_job_id and s.source_key<>'account_export_jobs'
     and s.status in ('pending','failed')
     and exists(select 1 from public.account_deletion_source_policies p
       where p.source_key=s.source_key and p.active=true and p.deletion_action in ('preserve','anonymize'));
  return query with picked as (
    select s.id from public.account_deletion_storage_jobs s
    where s.execution_job_id=p_execution_job_id
      and (s.status='pending' or (s.status='running' and s.lease_expires_at<=clock_timestamp()) or (s.status='failed' and s.attempts<12))
      and (s.source_key='account_export_jobs' or exists(
        select 1 from public.account_deletion_source_policies p
        where p.source_key=s.source_key and p.active=true and p.deletion_action='delete_rows'
      ))
    order by s.created_at,s.id limit p_limit for update skip locked
  )
  update public.account_deletion_storage_jobs s set status='running',attempts=s.attempts+1,
    lease_token=gen_random_uuid(),lease_expires_at=clock_timestamp()+make_interval(secs=>p_lease_seconds),
    updated_at=clock_timestamp()
  from picked where s.id=picked.id returning s.id,s.storage_bucket,s.storage_path,s.lease_token,s.attempts;
end;
$function$

revoke all on function public.claim_account_deletion_storage_jobs(uuid,uuid,integer,integer) from public, anon, authenticated;
grant execute on function public.claim_account_deletion_storage_jobs(uuid,uuid,integer,integer) to service_role;

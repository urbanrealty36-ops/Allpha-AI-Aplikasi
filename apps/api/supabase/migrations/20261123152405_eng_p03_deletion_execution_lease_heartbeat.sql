-- ENG-P03: renew a claimed account-deletion execution lease while bounded storage work runs.
create or replace function public.renew_account_deletion_execution_job_lease(
  p_job_id uuid, p_lease_token uuid, p_lease_seconds integer default 3600
)
returns boolean
language plpgsql
security definer
set search_path = ''
as $$
declare v_job public.account_deletion_execution_jobs%rowtype;
begin
  if coalesce(auth.role(), '') <> 'service_role' then
    raise exception 'service_role_required' using errcode = '42501';
  end if;
  if p_job_id is null or p_lease_token is null
     or p_lease_seconds is null or p_lease_seconds not between 30 and 3600 then
    raise exception 'invalid_account_deletion_lease_renewal' using errcode = '22023';
  end if;
  select * into v_job
    from public.account_deletion_execution_jobs
   where id = p_job_id and status = 'running'
     and lease_token = p_lease_token
     and lease_expires_at > clock_timestamp()
   for update;
  if not found then return false; end if;
  if exists (select 1 from public.account_legal_holds h
              where h.subject_ref = v_job.subject_ref and h.active = true) then
    update public.account_deletion_execution_jobs
       set status = 'blocked', error_code = 'LEGAL_HOLD_ACTIVE',
           lease_token = null, lease_owner = null, lease_expires_at = null,
           updated_at = clock_timestamp()
     where id = v_job.id;
    update public.account_deletion_requests
       set status = 'blocked_legal_hold', error_code = 'LEGAL_HOLD_ACTIVE',
           updated_at = clock_timestamp()
     where id = v_job.request_id;
    return false;
  end if;
  update public.account_deletion_execution_jobs
     set lease_expires_at = clock_timestamp() + make_interval(secs => p_lease_seconds),
         updated_at = clock_timestamp()
   where id = v_job.id and lease_token = p_lease_token;
  return found;
end;
$$;
revoke all on function public.renew_account_deletion_execution_job_lease(uuid, uuid, integer) from public, anon, authenticated;
grant execute on function public.renew_account_deletion_execution_job_lease(uuid, uuid, integer) to service_role;

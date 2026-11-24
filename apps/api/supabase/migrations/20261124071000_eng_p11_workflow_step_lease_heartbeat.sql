-- ENG-P11: keep long-running Agent Runtime workflow nodes under a live, fenced lease.
-- Forward-only additive RPC; no existing workflow/run data is rewritten.
begin;

create or replace function public.heartbeat_workflow_step(
  p_run_id uuid,
  p_owner_user_id uuid,
  p_step_id uuid,
  p_lease_token uuid,
  p_lease_seconds integer default 30
) returns setof public.workflow_steps
language plpgsql
security definer
set search_path = ''
as $$
declare
  run_row public.workflow_runs%rowtype;
  step_row public.workflow_steps%rowtype;
  run_deadline timestamptz;
  next_expiry timestamptz;
begin
  if (select auth.role()) <> 'service_role' then
    raise exception 'service_role_required' using errcode = '42501';
  end if;
  if p_lease_seconds < 5 or p_lease_seconds > 120 then
    raise exception 'workflow lease outside allowed bounds' using errcode = '22023';
  end if;

  perform pg_advisory_xact_lock(hashtextextended(p_run_id::text, 0));
  select * into run_row
    from public.workflow_runs
   where id = p_run_id and owner_user_id = p_owner_user_id
   for update;
  if not found
     or run_row.status not in ('queued','running')
     or run_row.cancel_requested then
    return;
  end if;

  run_deadline := coalesce(run_row.started_at, run_row.created_at)
    + make_interval(secs => coalesce(run_row.max_runtime_seconds, 60));
  if run_deadline <= now() then
    return;
  end if;

  select * into step_row
    from public.workflow_steps
   where id = p_step_id
     and run_id = p_run_id
     and owner_user_id = p_owner_user_id
   for update;
  if not found
     or step_row.status <> 'running'
     or step_row.lease_token is distinct from p_lease_token
     or step_row.lease_expires_at is null
     or step_row.lease_expires_at <= now() then
    return;
  end if;

  next_expiry := least(now() + make_interval(secs => p_lease_seconds), run_deadline);
  if next_expiry <= now() then
    return;
  end if;

  update public.workflow_steps
     set lease_expires_at = next_expiry,
         updated_at = now()
   where id = p_step_id
     and run_id = p_run_id
     and owner_user_id = p_owner_user_id
  returning * into step_row;

  return next step_row;
end;
$$;

revoke all on function public.heartbeat_workflow_step(uuid,uuid,uuid,uuid,integer)
  from public, anon, authenticated;
grant execute on function public.heartbeat_workflow_step(uuid,uuid,uuid,uuid,integer)
  to service_role;

comment on function public.heartbeat_workflow_step(uuid,uuid,uuid,uuid,integer) is
  'Extends only the current owner-scoped workflow step lease and never beyond the run deadline.';

commit;

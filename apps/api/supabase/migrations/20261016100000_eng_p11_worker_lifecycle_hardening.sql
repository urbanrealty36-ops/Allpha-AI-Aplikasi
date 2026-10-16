-- ENG-P11 worker lifecycle hardening: lease exhaustion, atomic timeout/finalize.
-- Source-only migration. Apply only on the approved isolated non-production target in ENG-P37.
-- This file is not authorization to mutate canonical production or create a paid DB branch.

create or replace function public.timeout_workflow_run(p_run_id uuid, p_owner_user_id uuid)
returns setof public.workflow_runs
language plpgsql security definer set search_path = ''
as $$
declare
  run_row public.workflow_runs%rowtype;
  next_seq bigint;
begin
  perform pg_advisory_xact_lock(hashtextextended(p_run_id::text, 0));
  select * into run_row from public.workflow_runs
   where id = p_run_id and owner_user_id = p_owner_user_id for update;
  if not found or run_row.status in ('succeeded','failed','cancelled','timed_out')
     or coalesce(run_row.started_at, run_row.created_at)
        + make_interval(secs => run_row.max_runtime_seconds) > now() then
    return;
  end if;

  update public.workflow_runs set status = 'timed_out', cancel_requested = true,
    completed_at = now(), updated_at = now(), run_version = run_version + 1
   where id = p_run_id and owner_user_id = p_owner_user_id returning * into run_row;
  update public.workflow_steps set status = 'cancelled', lease_token = null, lease_expires_at = null,
    error_code = 'RUN_TIMED_OUT', completed_at = now(), updated_at = now()
   where run_id = p_run_id and owner_user_id = p_owner_user_id
     and status in ('pending','retrying','running');
  select coalesce(max(sequence),0)+1 into next_seq from public.workflow_run_events where run_id = p_run_id;
  insert into public.workflow_run_events(run_id, owner_user_id, sequence, event_type, details)
  values (p_run_id, p_owner_user_id, next_seq, 'run_timed_out',
          jsonb_build_object('max_runtime_seconds', run_row.max_runtime_seconds));
  return next run_row;
end;
$$;
revoke all on function public.timeout_workflow_run(uuid, uuid) from public, anon, authenticated;
grant execute on function public.timeout_workflow_run(uuid, uuid) to service_role;

create or replace function public.claim_workflow_step(
  p_run_id uuid, p_owner_user_id uuid, p_lease_token uuid, p_lease_seconds integer default 30
) returns setof public.workflow_steps
language plpgsql security definer set search_path = ''
as $$
declare
  run_row public.workflow_runs%rowtype;
  step_row public.workflow_steps%rowtype;
  expired_step public.workflow_steps%rowtype;
  next_seq bigint;
begin
  if p_lease_seconds < 5 or p_lease_seconds > 120 then
    raise exception 'workflow lease outside allowed bounds' using errcode = '22023';
  end if;
  perform pg_advisory_xact_lock(hashtextextended(p_run_id::text, 0));
  select * into run_row from public.workflow_runs
   where id = p_run_id and owner_user_id = p_owner_user_id for update;
  if not found or run_row.status not in ('queued','running') or run_row.cancel_requested then
    return;
  end if;

  if coalesce(run_row.started_at, run_row.created_at)
       + make_interval(secs => run_row.max_runtime_seconds) <= now() then
    update public.workflow_runs set status = 'timed_out', cancel_requested = true,
      completed_at = now(), updated_at = now(), run_version = run_version + 1
     where id = p_run_id and owner_user_id = p_owner_user_id returning * into run_row;
    update public.workflow_steps set status = 'cancelled', lease_token = null, lease_expires_at = null,
      error_code = 'RUN_TIMED_OUT', completed_at = now(), updated_at = now()
     where run_id = p_run_id and owner_user_id = p_owner_user_id
       and status in ('pending','retrying','running');
    select coalesce(max(sequence),0)+1 into next_seq from public.workflow_run_events where run_id = p_run_id;
    insert into public.workflow_run_events(run_id, owner_user_id, sequence, event_type, details)
    values (p_run_id, p_owner_user_id, next_seq, 'run_timed_out',
            jsonb_build_object('max_runtime_seconds', run_row.max_runtime_seconds));
    return;
  end if;

  -- Expired deterministic work may be retried only within its declared attempt bound.
  -- All current node kinds are pure/no-side-effect. Future effectful nodes must not use this path.
  for expired_step in
    select * from public.workflow_steps
     where run_id = p_run_id and owner_user_id = p_owner_user_id
       and status = 'running' and lease_expires_at < now() and attempts >= max_attempts
     for update skip locked
  loop
    update public.workflow_steps set status = 'failed', error_code = 'LEASE_EXPIRED_RETRY_EXHAUSTED',
      lease_token = null, lease_expires_at = null, completed_at = now(), updated_at = now()
     where id = expired_step.id;
    select coalesce(max(sequence),0)+1 into next_seq from public.workflow_run_events where run_id = p_run_id;
    insert into public.workflow_run_events(run_id, owner_user_id, sequence, event_type, step_key, details)
    values (p_run_id, p_owner_user_id, next_seq, 'step_failed', expired_step.node_key,
            jsonb_build_object('error_code', 'LEASE_EXPIRED_RETRY_EXHAUSTED',
                               'attempts', expired_step.attempts));
  end loop;

  if exists (select 1 from public.workflow_steps
              where run_id = p_run_id and owner_user_id = p_owner_user_id and status = 'failed') then
    update public.workflow_runs set status = 'failed', completed_at = now(), updated_at = now(),
      run_version = run_version + 1 where id = p_run_id and status in ('queued','running');
    update public.workflow_steps set status = 'cancelled', error_code = 'RUN_FAILED',
      lease_token = null, lease_expires_at = null, completed_at = now(), updated_at = now()
     where run_id = p_run_id and owner_user_id = p_owner_user_id
       and status in ('pending','retrying','running');
    select coalesce(max(sequence),0)+1 into next_seq from public.workflow_run_events where run_id = p_run_id;
    insert into public.workflow_run_events(run_id, owner_user_id, sequence, event_type, details)
    values (p_run_id, p_owner_user_id, next_seq, 'run_failed',
            jsonb_build_object('reason', 'step retry limit exhausted'));
    return;
  end if;

  select s.* into step_row from public.workflow_steps s
  where s.run_id = p_run_id and s.owner_user_id = p_owner_user_id
    and (s.status in ('pending','retrying') or (s.status = 'running' and s.lease_expires_at < now()))
    and s.attempts < s.max_attempts
    and not exists (
      select 1 from unnest(s.depends_on) dep
      join public.workflow_steps parent on parent.run_id = s.run_id and parent.node_key = dep
      where parent.status <> 'succeeded'
    )
  order by s.created_at, s.node_key
  for update of s skip locked limit 1;
  if not found then return; end if;

  update public.workflow_steps set status = 'running', attempts = attempts + 1,
    lease_token = p_lease_token, lease_expires_at = now() + make_interval(secs => p_lease_seconds),
    updated_at = now(), completed_at = null
   where id = step_row.id returning * into step_row;
  update public.workflow_runs set status = 'running', started_at = coalesce(started_at, now()),
    updated_at = now(), run_version = run_version + 1 where id = p_run_id;
  return next step_row;
end;
$$;
revoke all on function public.claim_workflow_step(uuid, uuid, uuid, integer) from public, anon, authenticated;
grant execute on function public.claim_workflow_step(uuid, uuid, uuid, integer) to service_role;

create or replace function public.finalize_workflow_step(
  p_run_id uuid, p_owner_user_id uuid, p_step_id uuid, p_lease_token uuid,
  p_terminal_state text, p_output_payload jsonb, p_error_code text, p_checkpoint jsonb
) returns setof public.workflow_steps
language plpgsql security definer set search_path = ''
as $$
declare
  run_row public.workflow_runs%rowtype;
  step_row public.workflow_steps%rowtype;
  remaining_count integer;
  next_seq bigint;
begin
  if p_terminal_state not in ('succeeded','failed','retrying') then
    raise exception 'invalid workflow step final state' using errcode = '22023';
  end if;
  perform pg_advisory_xact_lock(hashtextextended(p_run_id::text, 0));
  select * into run_row from public.workflow_runs
   where id = p_run_id and owner_user_id = p_owner_user_id for update;
  if not found or run_row.status not in ('queued','running') or run_row.cancel_requested then
    raise exception 'workflow run is terminal or cancelled' using errcode = '40001';
  end if;
  select * into step_row from public.workflow_steps
   where id = p_step_id and run_id = p_run_id and owner_user_id = p_owner_user_id for update;
  if not found or step_row.status <> 'running' or step_row.lease_token is distinct from p_lease_token
     or step_row.lease_expires_at is null or step_row.lease_expires_at <= now() then
    raise exception 'stale workflow lease' using errcode = '40001';
  end if;
  if p_terminal_state = 'retrying' and step_row.attempts >= step_row.max_attempts then
    p_terminal_state := 'failed';
  end if;
  update public.workflow_steps set status = p_terminal_state,
    output_payload = case when p_terminal_state = 'succeeded' then p_output_payload else output_payload end,
    checkpoint = case when p_checkpoint is not null then p_checkpoint else checkpoint end,
    error_code = p_error_code, lease_token = null, lease_expires_at = null,
    completed_at = case when p_terminal_state in ('succeeded','failed') then now() else null end,
    updated_at = now() where id = p_step_id returning * into step_row;
  select coalesce(max(sequence),0)+1 into next_seq from public.workflow_run_events where run_id = p_run_id;
  insert into public.workflow_run_events(run_id, owner_user_id, sequence, event_type, step_key, details)
  values (p_run_id, p_owner_user_id, next_seq, 'step_' || p_terminal_state, step_row.node_key,
          jsonb_build_object('attempt', step_row.attempts, 'error_code', p_error_code));

  if p_terminal_state = 'failed' then
    update public.workflow_runs set status = 'failed', completed_at = now(), updated_at = now(),
      run_version = run_version + 1 where id = p_run_id;
    update public.workflow_steps set status = 'cancelled', error_code = 'RUN_FAILED',
      lease_token = null, lease_expires_at = null, completed_at = now(), updated_at = now()
     where run_id = p_run_id and owner_user_id = p_owner_user_id
       and id <> p_step_id and status in ('pending','retrying','running');
    select coalesce(max(sequence),0)+1 into next_seq from public.workflow_run_events where run_id = p_run_id;
    insert into public.workflow_run_events(run_id, owner_user_id, sequence, event_type, details)
    values (p_run_id, p_owner_user_id, next_seq, 'run_failed',
            jsonb_build_object('failed_step', step_row.node_key));
  elsif p_terminal_state = 'succeeded' then
    select count(*) into remaining_count from public.workflow_steps
     where run_id = p_run_id and owner_user_id = p_owner_user_id
       and status not in ('succeeded','skipped','cancelled');
    if remaining_count = 0 then
      update public.workflow_runs set status = 'succeeded', completed_at = now(), updated_at = now(),
        run_version = run_version + 1 where id = p_run_id and status in ('queued','running');
      select coalesce(max(sequence),0)+1 into next_seq from public.workflow_run_events where run_id = p_run_id;
      insert into public.workflow_run_events(run_id, owner_user_id, sequence, event_type, details)
      values (p_run_id, p_owner_user_id, next_seq, 'run_succeeded', '{}'::jsonb);
    end if;
  end if;
  return next step_row;
end;
$$;
revoke all on function public.finalize_workflow_step(uuid, uuid, uuid, uuid, text, jsonb, text, jsonb) from public, anon, authenticated;
grant execute on function public.finalize_workflow_step(uuid, uuid, uuid, uuid, text, jsonb, text, jsonb) to service_role;

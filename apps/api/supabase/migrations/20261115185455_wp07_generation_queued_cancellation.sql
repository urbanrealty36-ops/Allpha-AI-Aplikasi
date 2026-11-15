-- WP-07 requester cancellation before provider execution.
-- Explicit Product Owner approval recorded 2026-11-16.
begin;

create table if not exists public.generation_job_cancellation_events (
  id uuid primary key default gen_random_uuid(),
  generation_job_id uuid not null references public.generation_jobs(id) on delete cascade,
  owner_user_id uuid not null references auth.users(id) on delete cascade,
  outcome text not null check (outcome in ('cancelled','pending_reconciliation')),
  reason_code text not null check (length(reason_code) between 1 and 100),
  created_at timestamptz not null default now(),
  unique (generation_job_id)
);

alter table public.generation_job_cancellation_events enable row level security;
revoke all on public.generation_job_cancellation_events from public, anon, authenticated;
grant select, insert, update, delete on public.generation_job_cancellation_events to service_role;

create or replace function public.generation_cancel_queued_job(p_command jsonb)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_job public.generation_jobs;
  v_event public.generation_job_cancellation_events;
  v_job_id uuid;
  v_owner_id uuid;
  v_reason text;
  v_outcome text;
begin
  if jsonb_typeof(p_command) <> 'object'
    or coalesce(p_command->>'job_id','') = ''
    or coalesce(p_command->>'owner_user_id','') = '' then
    raise exception 'GENERATION_CANCEL_COMMAND_INVALID' using errcode='22023';
  end if;

  v_job_id := (p_command->>'job_id')::uuid;
  v_owner_id := (p_command->>'owner_user_id')::uuid;
  v_reason := left(coalesce(nullif(p_command->>'reason_code',''),'cancelled_by_requester'),100);

  select * into v_job
  from public.generation_jobs
  where id = v_job_id and owner_user_id = v_owner_id
  for update;

  if not found then
    raise exception 'GENERATION_JOB_NOT_FOUND' using errcode='P0002';
  end if;

  select * into v_event
  from public.generation_job_cancellation_events
  where generation_job_id = v_job_id and owner_user_id = v_owner_id;

  if found then
    return jsonb_build_object(
      'job_id', v_job_id,
      'status', v_event.outcome,
      'cancellation_recorded', true,
      'idempotent_replay', true
    );
  end if;

  -- Only queued jobs are cancellable. A running worker may already have
  -- submitted the request to a provider; that outcome must never be guessed.
  if v_job.status <> 'queued' then
    raise exception 'GENERATION_JOB_NOT_CANCELLABLE' using errcode='40001';
  end if;

  if v_job.allow_definitive_failure_release then
    perform public.credit_ledger_release(jsonb_build_object(
      'reservation_id', v_job.reservation_id,
      'idempotency_key', 'generation-cancel:' || v_job.task_id::text,
      'policy_version', v_job.policy_version,
      'reason_code', v_reason
    ));
    v_outcome := 'cancelled';
  else
    -- Do not release a reservation unless the effective credit policy allows
    -- definitive failure release. Preserve the reservation for reconciliation.
    perform public.credit_ledger_mark_pending(jsonb_build_object(
      'reservation_id', v_job.reservation_id,
      'reason_code', 'generation_cancel_release_policy_not_approved'
    ));
    v_outcome := 'pending_reconciliation';
  end if;

  update public.generation_jobs
  set status = v_outcome,
      error_code = case
        when v_outcome = 'cancelled' then 'cancelled_by_requester'
        else 'cancel_release_policy_not_approved'
      end,
      completed_at = now(),
      lease_token = null,
      lease_expires_at = null,
      updated_at = now()
  where id = v_job_id and owner_user_id = v_owner_id and status = 'queued';

  if not found then
    raise exception 'GENERATION_JOB_CANCEL_RACE' using errcode='40001';
  end if;

  insert into public.generation_job_cancellation_events(
    generation_job_id, owner_user_id, outcome, reason_code
  ) values (v_job_id, v_owner_id, v_outcome, v_reason)
  returning * into v_event;

  return jsonb_build_object(
    'job_id', v_job_id,
    'status', v_outcome,
    'cancellation_recorded', true,
    'idempotent_replay', false
  );
end;
$$;

revoke all on function public.generation_cancel_queued_job(jsonb)
  from public, anon, authenticated;
grant execute on function public.generation_cancel_queued_job(jsonb)
  to service_role;

comment on table public.generation_job_cancellation_events is
  'Owner-initiated cancellation audit for jobs cancelled before provider execution; release is policy-gated and uncertain reservations remain pending reconciliation.';

commit;

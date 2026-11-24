-- ENG-P11: durable owner approval checkpoints for workflow steps.
-- Additive state expansion; existing run/step rows remain unchanged.
alter table public.workflow_runs
  drop constraint if exists workflow_runs_status_check;
alter table public.workflow_runs
  add constraint workflow_runs_status_check
  check (status in ('queued','running','waiting_for_approval','succeeded','failed','cancelled','timed_out'));

alter table public.workflow_steps
  drop constraint if exists workflow_steps_status_check;
alter table public.workflow_steps
  add constraint workflow_steps_status_check
  check (status in ('pending','running','retrying','waiting_for_approval','succeeded','failed','cancelled','skipped'));

alter table public.workflow_steps
  drop constraint if exists workflow_steps_node_kind_check;
alter table public.workflow_steps
  add constraint workflow_steps_node_kind_check
  check (node_kind in ('input','constant','pass_through','concat','merge','agent_task','approval'));

create table if not exists public.workflow_step_approvals (
  id uuid primary key default gen_random_uuid(),
  run_id uuid not null references public.workflow_runs(id) on delete cascade,
  step_id uuid not null references public.workflow_steps(id) on delete cascade,
  owner_user_id uuid not null references auth.users(id) on delete cascade,
  requested_by uuid not null references auth.users(id),
  message text not null check (length(btrim(message)) between 1 and 1000),
  context jsonb not null default '{}'::jsonb check (jsonb_typeof(context) = 'object'),
  status text not null default 'pending'
    check (status in ('pending','approved','rejected','cancelled')),
  decision_note text check (decision_note is null or length(decision_note) <= 1000),
  decided_by uuid references auth.users(id),
  decided_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create unique index if not exists workflow_step_approvals_one_pending_per_step_idx
  on public.workflow_step_approvals(step_id) where status = 'pending';
create index if not exists workflow_step_approvals_owner_run_created_idx
  on public.workflow_step_approvals(owner_user_id,run_id,created_at desc);

alter table public.workflow_step_approvals enable row level security;
revoke all on public.workflow_step_approvals from public, anon, authenticated;
grant select on public.workflow_step_approvals to service_role;

create or replace function public.finalize_workflow_step(
  p_run_id uuid,
  p_owner_user_id uuid,
  p_step_id uuid,
  p_lease_token uuid,
  p_terminal_state text,
  p_output_payload jsonb,
  p_error_code text,
  p_checkpoint jsonb
)
returns setof public.workflow_steps
language plpgsql
security definer
set search_path = ''
as $function$
declare
  run_row public.workflow_runs%rowtype;
  step_row public.workflow_steps%rowtype;
  remaining_count integer;
  next_seq bigint;
  approval_id uuid;
  approval_message text;
begin
  if p_terminal_state not in ('succeeded','failed','retrying','waiting_for_approval') then
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

  if p_terminal_state = 'waiting_for_approval' then
    approval_message := nullif(btrim(p_checkpoint->>'approval_message'),'');
    if approval_message is null or length(approval_message) > 1000 then
      raise exception 'workflow approval message is required' using errcode = '22023';
    end if;
    approval_id := gen_random_uuid();
    insert into public.workflow_step_approvals(
      id,run_id,step_id,owner_user_id,requested_by,message,context
    ) values (
      approval_id,p_run_id,p_step_id,p_owner_user_id,p_owner_user_id,approval_message,
      coalesce(p_checkpoint->'approval_context','{}'::jsonb)
    );
    p_checkpoint := coalesce(p_checkpoint,'{}'::jsonb)
      || jsonb_build_object('approval_id',approval_id,'approval_status','pending');
  end if;

  update public.workflow_steps set status = p_terminal_state,
    output_payload = case when p_terminal_state = 'succeeded' then p_output_payload else output_payload end,
    checkpoint = case when p_checkpoint is not null then p_checkpoint else checkpoint end,
    error_code = p_error_code, lease_token = null, lease_expires_at = null,
    completed_at = case when p_terminal_state in ('succeeded','failed') then now() else null end,
    updated_at = now()
   where id = p_step_id returning * into step_row;

  select coalesce(max(sequence),0)+1 into next_seq
    from public.workflow_run_events where run_id = p_run_id;
  insert into public.workflow_run_events(run_id,owner_user_id,sequence,event_type,step_key,details)
  values (p_run_id,p_owner_user_id,next_seq,'step_' || p_terminal_state,step_row.node_key,
          jsonb_build_object('attempt',step_row.attempts,'error_code',p_error_code,
                             'approval_id',approval_id));

  if p_terminal_state = 'waiting_for_approval' then
    update public.workflow_runs set status='waiting_for_approval',completed_at=null,
      updated_at=now(),run_version=run_version+1
     where id=p_run_id and owner_user_id=p_owner_user_id;
  elsif p_terminal_state = 'failed' then
    update public.workflow_runs set status='failed',completed_at=now(),updated_at=now(),
      run_version=run_version+1 where id=p_run_id and owner_user_id=p_owner_user_id;
    update public.workflow_steps set status='cancelled',error_code='RUN_FAILED',
      lease_token=null,lease_expires_at=null,completed_at=now(),updated_at=now()
     where run_id=p_run_id and owner_user_id=p_owner_user_id
       and id<>p_step_id and status in ('pending','retrying','running','waiting_for_approval');
    update public.workflow_step_approvals set status='cancelled',decided_by=p_owner_user_id,
      decided_at=now(),decision_note='run_failed',updated_at=now()
     where run_id=p_run_id and owner_user_id=p_owner_user_id and status='pending';
    select coalesce(max(sequence),0)+1 into next_seq
      from public.workflow_run_events where run_id=p_run_id;
    insert into public.workflow_run_events(run_id,owner_user_id,sequence,event_type,details)
    values (p_run_id,p_owner_user_id,next_seq,'run_failed',
            jsonb_build_object('failed_step',step_row.node_key));
  elsif p_terminal_state = 'succeeded' then
    select count(*) into remaining_count from public.workflow_steps
     where run_id=p_run_id and owner_user_id=p_owner_user_id
       and status not in ('succeeded','skipped','cancelled');
    if remaining_count=0 then
      update public.workflow_runs set status='succeeded',completed_at=now(),updated_at=now(),
        run_version=run_version+1 where id=p_run_id and status in ('queued','running');
      select coalesce(max(sequence),0)+1 into next_seq
        from public.workflow_run_events where run_id=p_run_id;
      insert into public.workflow_run_events(run_id,owner_user_id,sequence,event_type,details)
      values (p_run_id,p_owner_user_id,next_seq,'run_succeeded','{}'::jsonb);
    end if;
  end if;
  return next step_row;
end;
$function$;

create or replace function public.approve_workflow_step(
  p_run_id uuid,
  p_owner_user_id uuid,
  p_step_id uuid,
  p_approval_id uuid,
  p_decision_note text default null
)
returns setof public.workflow_steps
language plpgsql
security definer
set search_path = ''
as $function$
declare
  run_row public.workflow_runs%rowtype;
  step_row public.workflow_steps%rowtype;
  approval_row public.workflow_step_approvals%rowtype;
  next_seq bigint;
begin
  perform pg_advisory_xact_lock(hashtextextended(p_run_id::text,0));
  select * into run_row from public.workflow_runs
   where id=p_run_id and owner_user_id=p_owner_user_id for update;
  if not found or run_row.status<>'waiting_for_approval' or run_row.cancel_requested then
    return;
  end if;
  select * into step_row from public.workflow_steps
   where id=p_step_id and run_id=p_run_id and owner_user_id=p_owner_user_id for update;
  if not found or step_row.status<>'waiting_for_approval'
     or step_row.checkpoint->>'approval_id'<>p_approval_id::text then
    return;
  end if;
  select * into approval_row from public.workflow_step_approvals
   where id=p_approval_id and run_id=p_run_id and step_id=p_step_id
     and owner_user_id=p_owner_user_id for update;
  if not found or approval_row.status<>'pending' then
    return;
  end if;
  update public.workflow_step_approvals set status='approved',decision_note=p_decision_note,
    decided_by=p_owner_user_id,decided_at=now(),updated_at=now() where id=p_approval_id;
  update public.workflow_steps set status='pending',error_code=null,
    checkpoint=coalesce(checkpoint,'{}'::jsonb)
      || jsonb_build_object('approval_status','approved','approval_decision_note',p_decision_note),
    updated_at=now() where id=p_step_id returning * into step_row;
  update public.workflow_runs set status='queued',completed_at=null,updated_at=now(),
    run_version=run_version+1 where id=p_run_id and owner_user_id=p_owner_user_id;
  select coalesce(max(sequence),0)+1 into next_seq
    from public.workflow_run_events where run_id=p_run_id;
  insert into public.workflow_run_events(run_id,owner_user_id,sequence,event_type,step_key,details)
  values (p_run_id,p_owner_user_id,next_seq,'step_approved',step_row.node_key,
          jsonb_build_object('approval_id',p_approval_id,'decision_note',p_decision_note));
  return next step_row;
end;
$function$;

create or replace function public.reject_workflow_step(
  p_run_id uuid,
  p_owner_user_id uuid,
  p_step_id uuid,
  p_approval_id uuid,
  p_decision_note text default null
)
returns setof public.workflow_steps
language plpgsql
security definer
set search_path = ''
as $function$
declare
  run_row public.workflow_runs%rowtype;
  step_row public.workflow_steps%rowtype;
  approval_row public.workflow_step_approvals%rowtype;
  next_seq bigint;
begin
  perform pg_advisory_xact_lock(hashtextextended(p_run_id::text,0));
  select * into run_row from public.workflow_runs
   where id=p_run_id and owner_user_id=p_owner_user_id for update;
  if not found or run_row.status<>'waiting_for_approval' or run_row.cancel_requested then
    return;
  end if;
  select * into step_row from public.workflow_steps
   where id=p_step_id and run_id=p_run_id and owner_user_id=p_owner_user_id for update;
  if not found or step_row.status<>'waiting_for_approval'
     or step_row.checkpoint->>'approval_id'<>p_approval_id::text then
    return;
  end if;
  select * into approval_row from public.workflow_step_approvals
   where id=p_approval_id and run_id=p_run_id and step_id=p_step_id
     and owner_user_id=p_owner_user_id for update;
  if not found or approval_row.status<>'pending' then
    return;
  end if;
  update public.workflow_step_approvals set status='rejected',decision_note=p_decision_note,
    decided_by=p_owner_user_id,decided_at=now(),updated_at=now() where id=p_approval_id;
  update public.workflow_steps set status='failed',error_code='APPROVAL_REJECTED',
    checkpoint=coalesce(checkpoint,'{}'::jsonb)
      || jsonb_build_object('approval_status','rejected','approval_decision_note',p_decision_note),
    completed_at=now(),updated_at=now() where id=p_step_id returning * into step_row;
  update public.workflow_runs set status='failed',completed_at=now(),updated_at=now(),
    run_version=run_version+1 where id=p_run_id and owner_user_id=p_owner_user_id;
  update public.workflow_steps set status='cancelled',error_code='RUN_FAILED',
    lease_token=null,lease_expires_at=null,completed_at=now(),updated_at=now()
   where run_id=p_run_id and owner_user_id=p_owner_user_id
     and id<>p_step_id and status in ('pending','retrying','running','waiting_for_approval');
  update public.workflow_step_approvals set status='cancelled',decided_by=p_owner_user_id,
    decided_at=now(),decision_note='run_failed',updated_at=now()
   where run_id=p_run_id and owner_user_id=p_owner_user_id and status='pending';
  select coalesce(max(sequence),0)+1 into next_seq
    from public.workflow_run_events where run_id=p_run_id;
  insert into public.workflow_run_events(run_id,owner_user_id,sequence,event_type,step_key,details)
  values (p_run_id,p_owner_user_id,next_seq,'step_rejected',step_row.node_key,
          jsonb_build_object('approval_id',p_approval_id,'decision_note',p_decision_note));
  select coalesce(max(sequence),0)+1 into next_seq
    from public.workflow_run_events where run_id=p_run_id;
  insert into public.workflow_run_events(run_id,owner_user_id,sequence,event_type,details)
  values (p_run_id,p_owner_user_id,next_seq,'run_failed',
          jsonb_build_object('failed_step',step_row.node_key,'reason','approval_rejected'));
  return next step_row;
end;
$function$;

create or replace function public.cancel_workflow_run(p_run_id uuid,p_owner_user_id uuid)
returns setof public.workflow_runs
language plpgsql
security definer
set search_path = ''
as $function$
declare run_row public.workflow_runs%rowtype;
begin
  perform pg_advisory_xact_lock(hashtextextended(p_run_id::text,0));
  select * into run_row from public.workflow_runs
   where id=p_run_id and owner_user_id=p_owner_user_id for update;
  if not found or run_row.status in ('succeeded','failed','cancelled','timed_out') then
    return;
  end if;
  update public.workflow_runs set status='cancelled',cancel_requested=true,
    completed_at=now(),updated_at=now(),run_version=run_version+1
   where id=p_run_id and owner_user_id=p_owner_user_id returning * into run_row;
  update public.workflow_steps set status='cancelled',lease_token=null,lease_expires_at=null,
    updated_at=now(),completed_at=now()
   where run_id=p_run_id and owner_user_id=p_owner_user_id
     and status in ('pending','retrying','running','waiting_for_approval');
  update public.workflow_step_approvals set status='cancelled',decided_by=p_owner_user_id,
    decided_at=now(),decision_note='run_cancelled',updated_at=now()
   where run_id=p_run_id and owner_user_id=p_owner_user_id and status='pending';
  insert into public.workflow_run_events(run_id,owner_user_id,sequence,event_type,details)
  select r.id,r.owner_user_id,
    coalesce((select max(e.sequence) from public.workflow_run_events e where e.run_id=r.id),0)+1,
    'run_cancelled',jsonb_build_object('requested_by_owner',true)
  from public.workflow_runs r where r.id=p_run_id and r.owner_user_id=p_owner_user_id;
  return next run_row;
end;
$function$;

create or replace function public.timeout_workflow_run(p_run_id uuid,p_owner_user_id uuid)
returns setof public.workflow_runs
language plpgsql
security definer
set search_path = ''
as $function$
declare run_row public.workflow_runs%rowtype; next_seq bigint;
begin
  perform pg_advisory_xact_lock(hashtextextended(p_run_id::text,0));
  select * into run_row from public.workflow_runs
   where id=p_run_id and owner_user_id=p_owner_user_id for update;
  if not found or run_row.status in ('succeeded','failed','cancelled','timed_out')
     or coalesce(run_row.started_at,run_row.created_at)
        + make_interval(secs => run_row.max_runtime_seconds) > now() then
    return;
  end if;
  update public.workflow_runs set status='timed_out',cancel_requested=true,
    completed_at=now(),updated_at=now(),run_version=run_version+1
   where id=p_run_id and owner_user_id=p_owner_user_id returning * into run_row;
  update public.workflow_steps set status='cancelled',lease_token=null,lease_expires_at=null,
    error_code='RUN_TIMED_OUT',completed_at=now(),updated_at=now()
   where run_id=p_run_id and owner_user_id=p_owner_user_id
     and status in ('pending','retrying','running','waiting_for_approval');
  update public.workflow_step_approvals set status='cancelled',decided_by=p_owner_user_id,
    decided_at=now(),decision_note='run_timed_out',updated_at=now()
   where run_id=p_run_id and owner_user_id=p_owner_user_id and status='pending';
  select coalesce(max(sequence),0)+1 into next_seq
    from public.workflow_run_events where run_id=p_run_id;
  insert into public.workflow_run_events(run_id,owner_user_id,sequence,event_type,details)
  values (p_run_id,p_owner_user_id,next_seq,'run_timed_out',
          jsonb_build_object('max_runtime_seconds',run_row.max_runtime_seconds));
  return next run_row;
end;
$function$;

revoke all on function public.finalize_workflow_step(uuid,uuid,uuid,uuid,text,jsonb,text,jsonb)
  from public,anon,authenticated;
revoke all on function public.approve_workflow_step(uuid,uuid,uuid,uuid,text)
  from public,anon,authenticated;
revoke all on function public.reject_workflow_step(uuid,uuid,uuid,uuid,text)
  from public,anon,authenticated;
revoke all on function public.cancel_workflow_run(uuid,uuid)
  from public,anon,authenticated;
revoke all on function public.timeout_workflow_run(uuid,uuid)
  from public,anon,authenticated;
grant execute on function public.finalize_workflow_step(uuid,uuid,uuid,uuid,text,jsonb,text,jsonb)
  to service_role;
grant execute on function public.approve_workflow_step(uuid,uuid,uuid,uuid,text)
  to service_role;
grant execute on function public.reject_workflow_step(uuid,uuid,uuid,uuid,text)
  to service_role;
grant execute on function public.cancel_workflow_run(uuid,uuid)
  to service_role;
grant execute on function public.timeout_workflow_run(uuid,uuid)
  to service_role;

notify pgrst, 'reload schema';

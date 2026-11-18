-- WP-07: bounded durable retries, attempt accounting and safe unclaimed-task terminalization.
-- Source-only. Requires the canonical ENG-P10 agent_runtime_tasks schema.
begin;

alter table public.agent_runtime_tasks
  add column if not exists execution_attempts integer not null default 0,
  add column if not exists max_execution_attempts integer not null default 3,
  add column if not exists next_attempt_at timestamptz;

do $$
begin
  if not exists (select 1 from pg_constraint where conname='agent_runtime_tasks_execution_attempts_check'
                 and conrelid='public.agent_runtime_tasks'::regclass) then
    alter table public.agent_runtime_tasks add constraint agent_runtime_tasks_execution_attempts_check
      check (execution_attempts >= 0 and max_execution_attempts between 1 and 5);
  end if;
end
$$;

create index if not exists agent_runtime_tasks_retry_due_idx
  on public.agent_runtime_tasks(state,next_attempt_at,created_at)
  where state in ('created','queued','retrying');

create or replace function public.claim_agent_runtime_task(
  p_task_id uuid,
  p_owner_user_id uuid,
  p_lease_token uuid,
  p_lease_seconds integer default 60
) returns setof public.agent_runtime_tasks
language plpgsql
security definer
set search_path = ''
as $$
begin
  if (select auth.role()) <> 'service_role' then
    raise exception 'service_role_required' using errcode='42501';
  end if;
  if p_lease_seconds < 5 or p_lease_seconds > 300 then
    raise exception 'lease_duration_out_of_bounds' using errcode='22023';
  end if;
  return query
  update public.agent_runtime_tasks t
     set state='executing',
         event_log=t.event_log || jsonb_build_array(jsonb_build_object(
           'event','execution_claimed','at',now(),'trace_id',t.trace_id,
           'attempt',t.execution_attempts+1)),
         execution_lease_token=p_lease_token,
         lease_expires_at=now()+make_interval(secs=>p_lease_seconds),
         updated_at=now(),
         task_version=t.task_version+1,
         execution_attempts=t.execution_attempts+1,
         next_attempt_at=null
   where t.id=p_task_id
     and t.owner_user_id=p_owner_user_id
     and t.execution_attempts<t.max_execution_attempts
     and (
       (t.state in ('created','queued','retrying')
         and (t.next_attempt_at is null or t.next_attempt_at<=now()))
       or
       (t.state='executing' and t.lease_expires_at<now()
         and coalesce(t.effect_outcome,'none') not in ('started','unknown'))
     )
  returning t.*;
end;
$$;

create or replace function public.schedule_agent_runtime_retry(
  p_task_id uuid,
  p_owner_user_id uuid,
  p_lease_token uuid,
  p_task_version integer,
  p_error_code text,
  p_retry_after_seconds integer,
  p_output_payload jsonb,
  p_event_log jsonb
) returns setof public.agent_runtime_tasks
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_task public.agent_runtime_tasks%rowtype;
begin
  if (select auth.role()) <> 'service_role' then
    raise exception 'service_role_required' using errcode='42501';
  end if;
  if p_error_code not in ('TOOL_TIMEOUT','RUNTIME_TRANSIENT_FAILURE')
     or p_retry_after_seconds not between 1 and 60
     or (p_output_payload is not null and jsonb_typeof(p_output_payload)<>'object')
     or jsonb_typeof(coalesce(p_event_log,'[]'::jsonb))<>'array' then
    raise exception 'runtime_retry_command_invalid' using errcode='22023';
  end if;

  select * into v_task from public.agent_runtime_tasks
   where id=p_task_id and owner_user_id=p_owner_user_id for update;
  if not found or v_task.state<>'executing'
     or v_task.execution_lease_token is distinct from p_lease_token
     or v_task.lease_expires_at is null or v_task.lease_expires_at<=now()
     or v_task.task_version<>p_task_version
     or coalesce(v_task.effect_outcome,'none') in ('started','unknown') then
    raise exception 'runtime_retry_stale_or_uncertain_effect' using errcode='40001';
  end if;

  if v_task.execution_attempts>=v_task.max_execution_attempts then
    return query update public.agent_runtime_tasks t
      set state='failed',error_code='RUNTIME_RETRY_EXHAUSTED',
          output_payload=p_output_payload,completed_at=now(),updated_at=now(),
          execution_lease_token=null,lease_expires_at=null,next_attempt_at=null,
          event_log=coalesce(p_event_log,'[]'::jsonb)||jsonb_build_array(jsonb_build_object(
            'state','failed','at',now(),'trace_id',t.trace_id,'reason_code','retry_attempt_limit_reached')),
          task_version=t.task_version+1
      where t.id=p_task_id and t.owner_user_id=p_owner_user_id
      returning t.*;
  else
    return query update public.agent_runtime_tasks t
      set state='retrying',error_code=p_error_code,output_payload=p_output_payload,
          completed_at=null,updated_at=now(),execution_lease_token=null,lease_expires_at=null,
          next_attempt_at=now()+make_interval(secs=>p_retry_after_seconds),
          event_log=coalesce(p_event_log,'[]'::jsonb)||jsonb_build_array(jsonb_build_object(
            'state','retrying','at',now(),'trace_id',t.trace_id,
            'reason_code',p_error_code,'retry_after_seconds',p_retry_after_seconds,
            'attempt',t.execution_attempts,'max_attempts',t.max_execution_attempts)),
          task_version=t.task_version+1
      where t.id=p_task_id and t.owner_user_id=p_owner_user_id
      returning t.*;
  end if;
end;
$$;

create or replace function public.reap_agent_runtime_retry_exhaustion()
returns integer
language plpgsql
security definer
set search_path = ''
as $$
declare v_count integer;
begin
  if (select auth.role()) <> 'service_role' then
    raise exception 'service_role_required' using errcode='42501';
  end if;
  update public.agent_runtime_tasks t
     set state='failed',error_code='RUNTIME_RETRY_EXHAUSTED',
         completed_at=now(),updated_at=now(),execution_lease_token=null,
         lease_expires_at=null,next_attempt_at=null,task_version=t.task_version+1,
         event_log=t.event_log||jsonb_build_array(jsonb_build_object(
           'state','failed','at',now(),'trace_id',t.trace_id,
           'reason_code','retry_attempt_limit_reached'))
   where t.execution_attempts>=t.max_execution_attempts
     and coalesce(t.effect_outcome,'none') not in ('started','unknown')
     and (
       (t.state='executing' and t.lease_expires_at<=now())
       or (t.state in ('created','queued','retrying')
           and (t.next_attempt_at is null or t.next_attempt_at<=now()))
     );
  get diagnostics v_count=row_count;
  return v_count;
end;
$$;

create or replace function public.fail_unclaimed_agent_runtime_task(
  p_task_id uuid,
  p_owner_user_id uuid,
  p_task_version integer,
  p_error_code text,
  p_lease_token uuid default null
) returns setof public.agent_runtime_tasks
language plpgsql
security definer
set search_path = ''
as $$
begin
  if (select auth.role()) <> 'service_role' then
    raise exception 'service_role_required' using errcode='42501';
  end if;
  if p_error_code !~ '^[A-Z0-9_]{1,80}$' then
    raise exception 'runtime_failure_code_invalid' using errcode='22023';
  end if;
  return query
  update public.agent_runtime_tasks t
     set state='failed',error_code=p_error_code,completed_at=now(),updated_at=now(),
         execution_lease_token=null,lease_expires_at=null,next_attempt_at=null,task_version=t.task_version+1,
         event_log=t.event_log||jsonb_build_array(jsonb_build_object(
           'state','failed','at',now(),'trace_id',t.trace_id,'reason_code',p_error_code))
   where t.id=p_task_id and t.owner_user_id=p_owner_user_id
     and t.task_version=p_task_version
     and (
       (t.state in ('created','queued','retrying') and t.execution_lease_token is null)
       or
       (t.state='executing' and t.lease_expires_at<=now()
         and t.execution_lease_token is not distinct from p_lease_token
         and coalesce(t.effect_outcome,'none') not in ('started','unknown'))
     )
  returning t.*;
end;
$$;

revoke all on function public.claim_agent_runtime_task(uuid,uuid,uuid,integer)
  from public,anon,authenticated;
revoke all on function public.schedule_agent_runtime_retry(uuid,uuid,uuid,integer,text,integer,jsonb,jsonb)
  from public,anon,authenticated;
revoke all on function public.reap_agent_runtime_retry_exhaustion()
  from public,anon,authenticated;
revoke all on function public.fail_unclaimed_agent_runtime_task(uuid,uuid,integer,text,uuid)
  from public,anon,authenticated;
grant execute on function public.claim_agent_runtime_task(uuid,uuid,uuid,integer) to service_role;
grant execute on function public.schedule_agent_runtime_retry(uuid,uuid,uuid,integer,text,integer,jsonb,jsonb) to service_role;
grant execute on function public.reap_agent_runtime_retry_exhaustion() to service_role;
grant execute on function public.fail_unclaimed_agent_runtime_task(uuid,uuid,integer,text,uuid) to service_role;

comment on column public.agent_runtime_tasks.execution_attempts is
  'Durable claim count. Incremented atomically by claim_agent_runtime_task.';
comment on column public.agent_runtime_tasks.max_execution_attempts is
  'Bounded maximum claims before safe retry exhaustion; defaults to three.';
comment on column public.agent_runtime_tasks.next_attempt_at is
  'Durable not-before time for a retrying task.';

commit;

-- ENG-P10 / WP-07: append-only durable Agent Runtime execution trace.
-- Source implementation only. Do not apply to the canonical database before ENG-P37
-- and the approved isolated migration/security review.
begin;

alter table public.agent_runtime_tasks
  add column if not exists execution_event_seq bigint not null default 0
    check (execution_event_seq >= 0);

create unique index if not exists agent_runtime_tasks_id_owner_uq
  on public.agent_runtime_tasks(id,owner_user_id);

create table if not exists public.agent_runtime_execution_events (
  id uuid primary key default gen_random_uuid(),
  task_id uuid not null references public.agent_runtime_tasks(id) on delete cascade,
  owner_user_id uuid not null references auth.users(id) on delete cascade,
  sequence bigint not null check (sequence > 0),
  task_version integer not null check (task_version > 0),
  trace_id text not null check (char_length(trace_id) between 8 and 160),
  event_type text not null check (event_type in (
    'state_transition','checkpoint_resumed','execution_reconciled'
  )),
  state text not null check (state in (
    'created','policy_check','budget_reserved','context_building','planning',
    'executing','validating','succeeded','waiting_for_approval','waiting_for_input',
    'retrying','partially_succeeded','failed','cancelled','timed_out','budget_exhausted'
  )),
  step_key text not null check (char_length(step_key) between 1 and 160),
  details jsonb not null default '{}'::jsonb
    check (jsonb_typeof(details)='object' and octet_length(details::text)<=2048),
  created_at timestamptz not null default now(),
  unique(task_id,sequence),
  foreign key(task_id,owner_user_id)
    references public.agent_runtime_tasks(id,owner_user_id) on delete cascade
);
create index if not exists agent_runtime_execution_events_owner_task_idx
  on public.agent_runtime_execution_events(owner_user_id,task_id,sequence asc);

alter table public.agent_runtime_execution_events enable row level security;
revoke all on public.agent_runtime_execution_events from public,anon,authenticated;
grant select,insert on public.agent_runtime_execution_events to service_role;

create or replace function public.prevent_agent_runtime_execution_event_mutation()
returns trigger language plpgsql security invoker set search_path=''
as $$
begin
  raise exception 'agent_runtime_execution_events_are_append_only' using errcode='42501';
end;
$$;
revoke all on function public.prevent_agent_runtime_execution_event_mutation() from public,anon,authenticated;
drop trigger if exists agent_runtime_execution_events_append_only on public.agent_runtime_execution_events;
create trigger agent_runtime_execution_events_append_only
before update or delete on public.agent_runtime_execution_events
for each row execute function public.prevent_agent_runtime_execution_event_mutation();

create or replace function public.append_agent_runtime_execution_event(
  p_task_id uuid,p_owner_user_id uuid,p_lease_token uuid,p_task_version integer,
  p_event_type text,p_state text,p_step_key text,p_details jsonb default '{}'::jsonb
) returns setof public.agent_runtime_execution_events
language plpgsql security definer set search_path=''
as $$
declare
  v_task public.agent_runtime_tasks%rowtype;
  v_event public.agent_runtime_execution_events%rowtype;
  v_sequence bigint;
  v_key text;
begin
  if (select auth.role()) <> 'service_role' then
    raise exception 'service_role_required' using errcode='42501';
  end if;
  if p_event_type not in ('state_transition','checkpoint_resumed','execution_reconciled')
     or p_state not in ('created','policy_check','budget_reserved','context_building','planning',
       'executing','validating','succeeded','waiting_for_approval','waiting_for_input',
       'retrying','partially_succeeded','failed','cancelled','timed_out','budget_exhausted')
     or char_length(coalesce(p_step_key,'')) not between 1 and 160
     or jsonb_typeof(coalesce(p_details,'{}'::jsonb)) <> 'object'
     or octet_length(coalesce(p_details,'{}'::jsonb)::text)>2048
  then raise exception 'runtime_execution_event_invalid' using errcode='22023'; end if;

  for v_key in select jsonb_object_keys(coalesce(p_details,'{}'::jsonb)) loop
    if v_key not in ('reason_code','tool_key','attempt','duration_ms','input_sha256',
                     'output_sha256','checkpoint_seq','resume_source','outcome') then
      raise exception 'runtime_execution_event_detail_key_denied' using errcode='22023';
    end if;
  end loop;

  select * into v_task from public.agent_runtime_tasks
   where id=p_task_id and owner_user_id=p_owner_user_id for update;
  if not found or v_task.state<>'executing'
     or v_task.execution_lease_token is distinct from p_lease_token
     or v_task.lease_expires_at is null or v_task.lease_expires_at<=now()
     or v_task.task_version<>p_task_version
  then raise exception 'runtime_execution_event_stale_lease' using errcode='40001'; end if;

  v_sequence:=v_task.execution_event_seq+1;
  insert into public.agent_runtime_execution_events(
    task_id,owner_user_id,sequence,task_version,trace_id,event_type,state,step_key,details
  ) values(
    p_task_id,p_owner_user_id,v_sequence,p_task_version,v_task.trace_id,
    p_event_type,p_state,p_step_key,coalesce(p_details,'{}'::jsonb)
  ) returning * into v_event;
  update public.agent_runtime_tasks
   set execution_event_seq=v_sequence,updated_at=now()
   where id=p_task_id and owner_user_id=p_owner_user_id;
  return next v_event;
end;
$$;
revoke all on function public.append_agent_runtime_execution_event(uuid,uuid,uuid,integer,text,text,text,jsonb)
  from public,anon,authenticated;
grant execute on function public.append_agent_runtime_execution_event(uuid,uuid,uuid,integer,text,text,text,jsonb)
  to service_role;

comment on table public.agent_runtime_execution_events is
  'Append-only, owner-scoped, lease-fenced runtime trace. Details allowlist excludes prompts, tool inputs, outputs and private Memory text.';
commit;

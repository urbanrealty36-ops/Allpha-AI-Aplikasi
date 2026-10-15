-- ENG-P10: accepted Postgres-backed durable checkpoint and policy contract.
-- Source-only: execute only against the approved isolated staging target in ENG-P37.
-- No production migration or data mutation is performed by this commit.

create table if not exists public.agent_runtime_policies (
  id uuid primary key default gen_random_uuid(),
  agent_id uuid not null references public.ai_agents(id) on delete cascade,
  policy_version text not null check (char_length(policy_version) between 1 and 120),
  policy_document jsonb not null check (jsonb_typeof(policy_document) = 'object'),
  policy_digest text not null check (policy_digest ~ '^[a-f0-9]{64}$'),
  approved_tool_keys text[] not null default '{}',
  required_permission_scopes text[] not null default '{}',
  risk_constraints jsonb not null default '{}'::jsonb check (jsonb_typeof(risk_constraints) = 'object'),
  status text not null default 'draft' check (status in ('draft','approved','revoked')),
  created_by uuid not null references auth.users(id),
  approved_by uuid references auth.users(id),
  approved_at timestamptz,
  revoked_by uuid references auth.users(id),
  revoked_at timestamptz,
  created_at timestamptz not null default now(),
  unique (agent_id, policy_version),
  unique (id, agent_id),
  check (status <> 'approved' or (approved_by is not null and approved_at is not null)),
  check (status <> 'revoked' or (revoked_by is not null and revoked_at is not null))
);
create index if not exists agent_runtime_policies_active_idx
  on public.agent_runtime_policies(agent_id, policy_version) where status = 'approved';

create or replace function public.guard_agent_runtime_policy_immutability()
returns trigger
language plpgsql
security invoker
set search_path = ''
as $$
begin
  if new.id is distinct from old.id
    or new.agent_id is distinct from old.agent_id
    or new.policy_version is distinct from old.policy_version
    or new.policy_document is distinct from old.policy_document
    or new.policy_digest is distinct from old.policy_digest
    or new.approved_tool_keys is distinct from old.approved_tool_keys
    or new.required_permission_scopes is distinct from old.required_permission_scopes
    or new.risk_constraints is distinct from old.risk_constraints
    or new.created_by is distinct from old.created_by
    or new.created_at is distinct from old.created_at then
    raise exception 'runtime policy content is immutable; create a new version';
  end if;
  if old.status = 'revoked' and new.status <> 'revoked' then
    raise exception 'revoked runtime policy cannot be reactivated';
  end if;
  if old.status = 'approved' and new.status = 'draft' then
    raise exception 'approved runtime policy cannot return to draft';
  end if;
  return new;
end;
$$;
revoke all on function public.guard_agent_runtime_policy_immutability() from public, anon, authenticated;
drop trigger if exists agent_runtime_policy_immutable on public.agent_runtime_policies;
create trigger agent_runtime_policy_immutable before update on public.agent_runtime_policies
for each row execute function public.guard_agent_runtime_policy_immutability();

alter table public.agent_runtime_tasks
  add column if not exists execution_lease_token uuid,
  add column if not exists lease_expires_at timestamptz,
  add column if not exists checkpoint_seq bigint not null default 0 check (checkpoint_seq >= 0),
  add column if not exists checkpoint_hash text,
  add column if not exists current_step_key text,
  add column if not exists effect_outcome text check (effect_outcome is null or effect_outcome in ('none','started','completed','unknown'));

alter table public.agent_capabilities
  add column if not exists runtime_policy_id uuid;

do $$
begin
  if not exists (
    select 1 from pg_constraint
    where conname = 'agent_capabilities_runtime_policy_agent_fk'
      and conrelid = 'public.agent_capabilities'::regclass
  ) then
    alter table public.agent_capabilities
      add constraint agent_capabilities_runtime_policy_agent_fk
      foreign key (runtime_policy_id, agent_id)
      references public.agent_runtime_policies(id, agent_id)
      on delete restrict;
  end if;
end $$;

create table if not exists public.agent_runtime_checkpoints (
  id uuid primary key default gen_random_uuid(),
  task_id uuid not null references public.agent_runtime_tasks(id) on delete cascade,
  task_version integer not null check (task_version > 0),
  sequence bigint not null check (sequence > 0),
  step_key text not null check (char_length(step_key) between 1 and 160),
  input_fingerprint text not null check (input_fingerprint ~ '^[a-f0-9]{64}$'),
  checkpoint_hash text not null check (checkpoint_hash ~ '^[a-f0-9]{64}$'),
  result_payload jsonb not null check (jsonb_typeof(result_payload) = 'object'),
  created_at timestamptz not null default now(),
  unique (task_id, sequence),
  unique (task_id, step_key, input_fingerprint, sequence)
);
create index if not exists agent_runtime_checkpoints_task_latest_idx
  on public.agent_runtime_checkpoints(task_id, sequence desc);

create table if not exists public.agent_runtime_effect_receipts (
  id uuid primary key default gen_random_uuid(),
  task_id uuid not null references public.agent_runtime_tasks(id) on delete cascade,
  task_version integer not null check (task_version > 0),
  step_key text not null check (char_length(step_key) between 1 and 160),
  idempotency_key text not null check (char_length(idempotency_key) between 8 and 200),
  input_fingerprint text not null check (input_fingerprint ~ '^[a-f0-9]{64}$'),
  status text not null check (status in ('started','completed','unknown')),
  result_payload jsonb check (result_payload is null or jsonb_typeof(result_payload) = 'object'),
  started_at timestamptz not null default now(),
  completed_at timestamptz,
  updated_at timestamptz not null default now(),
  unique (task_id, step_key, idempotency_key),
  check ((status = 'completed') = (completed_at is not null)),
  check ((status = 'completed') = (result_payload is not null))
);
create index if not exists agent_runtime_effect_receipts_recovery_idx
  on public.agent_runtime_effect_receipts(task_id, status, updated_at);

alter table public.agent_runtime_policies enable row level security;
alter table public.agent_runtime_checkpoints enable row level security;
alter table public.agent_runtime_effect_receipts enable row level security;
revoke all on public.agent_runtime_policies, public.agent_runtime_checkpoints,
  public.agent_runtime_effect_receipts from public, anon, authenticated;
grant select, insert, update on public.agent_runtime_policies to service_role;
grant select, insert on public.agent_runtime_checkpoints to service_role;
grant select, insert, update on public.agent_runtime_effect_receipts to service_role;

create or replace function public.claim_agent_runtime_task(
  p_task_id uuid, p_owner_user_id uuid, p_lease_token uuid, p_lease_seconds integer default 60
)
returns setof public.agent_runtime_tasks
language plpgsql
security definer
set search_path = ''
as $$
begin
  if p_lease_seconds < 5 or p_lease_seconds > 300 then
    raise exception 'lease duration outside allowed bounds' using errcode = '22023';
  end if;
  return query
  update public.agent_runtime_tasks t
     set state = 'executing',
         event_log = t.event_log || jsonb_build_array(jsonb_build_object('event', 'execution_claimed', 'at', now(), 'trace_id', t.trace_id)),
         execution_lease_token = p_lease_token,
         lease_expires_at = now() + make_interval(secs => p_lease_seconds),
         updated_at = now(),
         task_version = t.task_version + 1
   where t.id = p_task_id
     and t.owner_user_id = p_owner_user_id
     and (
       t.state in ('created','queued','retrying')
       or (t.state = 'executing' and t.lease_expires_at < now()
           and coalesce(t.effect_outcome, 'none') not in ('started','unknown'))
     )
  returning t.*;
end;
$$;
revoke all on function public.claim_agent_runtime_task(uuid, uuid, uuid, integer) from public, anon, authenticated;
grant execute on function public.claim_agent_runtime_task(uuid, uuid, uuid, integer) to service_role;

create or replace function public.append_agent_runtime_checkpoint(
  p_task_id uuid, p_owner_user_id uuid, p_lease_token uuid, p_task_version integer,
  p_sequence bigint, p_step_key text, p_input_fingerprint text,
  p_checkpoint_hash text, p_result_payload jsonb
)
returns setof public.agent_runtime_checkpoints
language plpgsql
security definer
set search_path = ''
as $$
declare
  task_row public.agent_runtime_tasks%rowtype;
  checkpoint_row public.agent_runtime_checkpoints%rowtype;
begin
  select * into task_row from public.agent_runtime_tasks
   where id = p_task_id and owner_user_id = p_owner_user_id for update;
  if not found or task_row.state <> 'executing'
     or task_row.execution_lease_token is distinct from p_lease_token
     or task_row.lease_expires_at is null or task_row.lease_expires_at <= now()
     or task_row.task_version <> p_task_version
     or task_row.checkpoint_seq + 1 <> p_sequence then
    raise exception 'stale lease, task version, or checkpoint sequence' using errcode = '40001';
  end if;
  insert into public.agent_runtime_checkpoints
    (task_id, task_version, sequence, step_key, input_fingerprint, checkpoint_hash, result_payload)
  values
    (p_task_id, p_task_version, p_sequence, p_step_key, p_input_fingerprint, p_checkpoint_hash, p_result_payload)
  returning * into checkpoint_row;
  update public.agent_runtime_tasks
     set checkpoint_seq = p_sequence, checkpoint_hash = p_checkpoint_hash,
         current_step_key = p_step_key, effect_outcome = 'completed', updated_at = now()
   where id = p_task_id;
  return next checkpoint_row;
end;
$$;
revoke all on function public.append_agent_runtime_checkpoint(uuid, uuid, uuid, integer, bigint, text, text, text, jsonb) from public, anon, authenticated;
grant execute on function public.append_agent_runtime_checkpoint(uuid, uuid, uuid, integer, bigint, text, text, text, jsonb) to service_role;

create or replace function public.begin_agent_runtime_effect(
  p_task_id uuid, p_owner_user_id uuid, p_lease_token uuid, p_task_version integer,
  p_step_key text, p_idempotency_key text, p_input_fingerprint text
)
returns setof public.agent_runtime_effect_receipts
language plpgsql
security definer
set search_path = ''
as $$
declare
  task_row public.agent_runtime_tasks%rowtype;
  receipt public.agent_runtime_effect_receipts%rowtype;
begin
  select * into task_row from public.agent_runtime_tasks
   where id = p_task_id and owner_user_id = p_owner_user_id for update;
  if not found or task_row.state <> 'executing'
     or task_row.execution_lease_token is distinct from p_lease_token
     or task_row.lease_expires_at is null or task_row.lease_expires_at <= now()
     or task_row.task_version <> p_task_version then
    raise exception 'stale lease or task version' using errcode = '40001';
  end if;

  insert into public.agent_runtime_effect_receipts
    (task_id, task_version, step_key, idempotency_key, input_fingerprint, status)
  values
    (p_task_id, p_task_version, p_step_key, p_idempotency_key, p_input_fingerprint, 'started')
  on conflict (task_id, step_key, idempotency_key) do nothing;

  select * into receipt from public.agent_runtime_effect_receipts
   where task_id = p_task_id and step_key = p_step_key
     and idempotency_key = p_idempotency_key for update;
  if receipt.input_fingerprint <> p_input_fingerprint then
    raise exception 'idempotency key reused with a different input fingerprint' using errcode = '23505';
  end if;
  update public.agent_runtime_tasks set effect_outcome = receipt.status, current_step_key = p_step_key,
    updated_at = now() where id = p_task_id;
  return next receipt;
end;
$$;
revoke all on function public.begin_agent_runtime_effect(uuid, uuid, uuid, integer, text, text, text) from public, anon, authenticated;
grant execute on function public.begin_agent_runtime_effect(uuid, uuid, uuid, integer, text, text, text) to service_role;

create or replace function public.complete_agent_runtime_effect(
  p_task_id uuid, p_owner_user_id uuid, p_lease_token uuid, p_task_version integer,
  p_step_key text, p_idempotency_key text, p_input_fingerprint text, p_result_payload jsonb
)
returns setof public.agent_runtime_effect_receipts
language plpgsql
security definer
set search_path = ''
as $$
declare
  task_row public.agent_runtime_tasks%rowtype;
  receipt public.agent_runtime_effect_receipts%rowtype;
begin
  select * into task_row from public.agent_runtime_tasks
   where id = p_task_id and owner_user_id = p_owner_user_id for update;
  if not found or task_row.state <> 'executing'
     or task_row.execution_lease_token is distinct from p_lease_token
     or task_row.lease_expires_at is null or task_row.lease_expires_at <= now()
     or task_row.task_version <> p_task_version then
    raise exception 'stale lease or task version' using errcode = '40001';
  end if;
  update public.agent_runtime_effect_receipts
     set status = 'completed', result_payload = p_result_payload,
         completed_at = now(), updated_at = now()
   where task_id = p_task_id and step_key = p_step_key
     and idempotency_key = p_idempotency_key
     and input_fingerprint = p_input_fingerprint and status = 'started'
  returning * into receipt;
  if not found then
    select * into receipt from public.agent_runtime_effect_receipts
     where task_id = p_task_id and step_key = p_step_key
       and idempotency_key = p_idempotency_key and input_fingerprint = p_input_fingerprint;
    if not found or receipt.status <> 'completed' then
      raise exception 'effect receipt cannot be completed; outcome remains unknown' using errcode = '40001';
    end if;
  end if;
  update public.agent_runtime_tasks set effect_outcome = 'completed', updated_at = now()
   where id = p_task_id;
  return next receipt;
end;
$$;
revoke all on function public.complete_agent_runtime_effect(uuid, uuid, uuid, integer, text, text, text, jsonb) from public, anon, authenticated;
grant execute on function public.complete_agent_runtime_effect(uuid, uuid, uuid, integer, text, text, text, jsonb) to service_role;

create or replace function public.finalize_agent_runtime_task(
  p_task_id uuid, p_owner_user_id uuid, p_lease_token uuid, p_task_version integer,
  p_terminal_state text, p_output_payload jsonb, p_error_code text, p_event_log jsonb
)
returns setof public.agent_runtime_tasks
language plpgsql
security definer
set search_path = ''
as $$
begin
  if p_terminal_state not in ('succeeded','partially_succeeded','failed','cancelled','timed_out','budget_exhausted') then
    raise exception 'state is not terminal' using errcode = '22023';
  end if;
  return query
  update public.agent_runtime_tasks t
     set state = p_terminal_state,
         output_payload = p_output_payload,
         error_code = p_error_code,
         event_log = p_event_log,
         completed_at = now(),
         updated_at = now(),
         execution_lease_token = null,
         lease_expires_at = null,
         effect_outcome = case when p_terminal_state = 'succeeded' then 'completed' else coalesce(t.effect_outcome,'unknown') end,
         task_version = t.task_version + 1
   where t.id = p_task_id and t.owner_user_id = p_owner_user_id
     and t.state = 'executing'
     and t.execution_lease_token = p_lease_token
     and t.lease_expires_at > now()
     and t.task_version = p_task_version
  returning t.*;
end;
$$;
revoke all on function public.finalize_agent_runtime_task(uuid, uuid, uuid, integer, text, jsonb, text, jsonb) from public, anon, authenticated;
grant execute on function public.finalize_agent_runtime_task(uuid, uuid, uuid, integer, text, jsonb, text, jsonb) to service_role;

create or replace function public.mark_agent_runtime_effect_unknown(
  p_task_id uuid, p_owner_user_id uuid
)
returns setof public.agent_runtime_tasks
language plpgsql
security definer
set search_path = ''
as $$
declare
  task_row public.agent_runtime_tasks%rowtype;
begin
  select * into task_row from public.agent_runtime_tasks
   where id = p_task_id and owner_user_id = p_owner_user_id for update;
  if not found or task_row.state <> 'executing'
     or task_row.lease_expires_at is null or task_row.lease_expires_at > now()
     or coalesce(task_row.effect_outcome, 'none') not in ('started','unknown') then
    return;
  end if;
  update public.agent_runtime_effect_receipts
     set status = 'unknown', updated_at = now()
   where task_id = p_task_id and step_key = task_row.current_step_key and status = 'started';
  return query
  update public.agent_runtime_tasks t
     set state = 'failed', error_code = 'EXECUTION_OUTCOME_UNKNOWN',
         effect_outcome = 'unknown',
         event_log = t.event_log || jsonb_build_array(jsonb_build_object(
           'state', 'failed', 'at', now(), 'trace_id', t.trace_id,
           'reason_code', 'execution_outcome_unknown_no_replay')),
         execution_lease_token = null, lease_expires_at = null,
         completed_at = now(), updated_at = now(), task_version = t.task_version + 1
   where t.id = p_task_id and t.owner_user_id = p_owner_user_id
  returning t.*;
end;
$$;
revoke all on function public.mark_agent_runtime_effect_unknown(uuid, uuid) from public, anon, authenticated;
grant execute on function public.mark_agent_runtime_effect_unknown(uuid, uuid) to service_role;

comment on table public.agent_runtime_policies is
  'Agent-scoped immutable policy versions; only approved active versions can authorize tools.';
comment on table public.agent_runtime_checkpoints is
  'Append-only, ordered task checkpoints; only the current non-expired lease can append.';
comment on table public.agent_runtime_effect_receipts is
  'Durable idempotency receipts. started/unknown outcomes must never be blindly replayed.';

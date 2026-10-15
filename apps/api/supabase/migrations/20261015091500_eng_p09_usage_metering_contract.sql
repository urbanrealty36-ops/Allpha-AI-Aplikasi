-- ENG-P09 provider-neutral usage metering persistence.
-- SOURCE ONLY: do not apply to canonical production. Validate in an approved isolated
-- non-production environment before adoption. This table records usage/cost attribution
-- only; it does not convert usage to AI Credits or settle a credit ledger.
create table if not exists public.agent_model_usage_metering (
  id uuid primary key default gen_random_uuid(),
  idempotency_key text not null unique check (length(idempotency_key) between 1 and 256),
  task_id text not null check (length(task_id) between 1 and 128),
  trace_id text not null check (length(trace_id) between 1 and 128),
  owner_id text not null check (length(owner_id) between 1 and 128),
  agent_id text not null check (length(agent_id) between 1 and 128),
  source_id text not null check (length(source_id) between 1 and 128),
  source_version integer not null check (source_version > 0),
  sensitivity text not null check (sensitivity in ('public','internal','confidential','restricted')),
  provider_id text not null check (length(provider_id) between 1 and 128),
  model_id text not null check (length(model_id) between 1 and 128),
  model_version text not null check (length(model_version) between 1 and 128),
  usage_units bigint not null check (usage_units >= 0),
  usage_unit text not null check (length(usage_unit) between 1 and 80),
  cost_microunits bigint not null check (cost_microunits >= 0),
  cost_unit text not null check (length(cost_unit) between 1 and 80),
  pricing_version text not null check (length(pricing_version) between 1 and 80),
  completed_at timestamptz not null,
  payload_fingerprint text not null check (payload_fingerprint ~ '^[0-9a-f]{64}$'),
  created_at timestamptz not null default now()
);

create index if not exists agent_model_usage_metering_owner_created_idx
  on public.agent_model_usage_metering(owner_id, created_at desc);
create index if not exists agent_model_usage_metering_agent_created_idx
  on public.agent_model_usage_metering(agent_id, created_at desc);

alter table public.agent_model_usage_metering enable row level security;
revoke all on table public.agent_model_usage_metering from public, anon, authenticated;
grant select, insert on table public.agent_model_usage_metering to service_role;

create or replace function public.record_agent_model_usage_metering(p_record jsonb)
returns boolean
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  v_existing_fingerprint text;
  v_key text;
begin
  if p_record is null or jsonb_typeof(p_record) <> 'object' then
    raise exception 'INVALID_METERING_RECORD' using errcode = '22023';
  end if;

  v_key := p_record->>'idempotency_key';
  if v_key is null or length(v_key) not between 1 and 256 then
    raise exception 'INVALID_METERING_IDEMPOTENCY_KEY' using errcode = '22023';
  end if;
  if coalesce(p_record->>'payload_fingerprint','') !~ '^[0-9a-f]{64}$' then
    raise exception 'INVALID_METERING_FINGERPRINT' using errcode = '22023';
  end if;

  insert into public.agent_model_usage_metering (
    idempotency_key, task_id, trace_id, owner_id, agent_id, source_id,
    source_version, sensitivity, provider_id, model_id, model_version,
    usage_units, usage_unit, cost_microunits, cost_unit, pricing_version,
    completed_at, payload_fingerprint
  ) values (
    v_key,
    p_record->>'task_id',
    p_record->>'trace_id',
    p_record->>'owner_id',
    p_record->>'agent_id',
    p_record->>'source_id',
    (p_record->>'source_version')::integer,
    p_record->>'sensitivity',
    p_record->>'provider_id',
    p_record->>'model_id',
    p_record->>'model_version',
    (p_record->>'usage_units')::bigint,
    p_record->>'usage_unit',
    (p_record->>'cost_microunits')::bigint,
    p_record->>'cost_unit',
    p_record->>'pricing_version',
    (p_record->>'completed_at')::timestamptz,
    p_record->>'payload_fingerprint'
  )
  on conflict (idempotency_key) do nothing
  returning payload_fingerprint into v_existing_fingerprint;

  if found then
    return true;
  end if;

  -- ON CONFLICT waits for a concurrent insert. The subsequent read distinguishes
  -- a safe replay from key reuse with a different payload.
  select payload_fingerprint into v_existing_fingerprint
  from public.agent_model_usage_metering
  where idempotency_key = v_key;

  if v_existing_fingerprint = p_record->>'payload_fingerprint' then
    return true;
  end if;

  raise exception 'METERING_IDEMPOTENCY_CONFLICT'
    using errcode = '23505';
end;
$$;

revoke all on function public.record_agent_model_usage_metering(jsonb) from public, anon, authenticated;
grant execute on function public.record_agent_model_usage_metering(jsonb) to service_role;

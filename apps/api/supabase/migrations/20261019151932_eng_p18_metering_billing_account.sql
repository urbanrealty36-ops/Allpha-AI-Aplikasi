-- ENG-P18: make durable usage evidence explicitly attributable to the ledger payer.
-- Existing metering rows retain their original owner attribution; the billing account
-- is backfilled to owner_id for legacy records and required for all subsequent writes.
alter table public.agent_model_usage_metering add column if not exists billing_account_id text;
update public.agent_model_usage_metering set billing_account_id = owner_id where billing_account_id is null;
alter table public.agent_model_usage_metering alter column billing_account_id set not null;
create index if not exists agent_model_usage_metering_billing_task_idx
  on public.agent_model_usage_metering(billing_account_id, task_id, idempotency_key);

create or replace function public.record_agent_model_usage_metering(p_record jsonb)
returns boolean
language plpgsql
security definer
set search_path = ''
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
    idempotency_key, task_id, trace_id, owner_id, billing_account_id, agent_id, source_id,
    source_version, sensitivity, provider_id, model_id, model_version,
    usage_units, usage_unit, cost_microunits, cost_unit, pricing_version,
    completed_at, payload_fingerprint
  ) values (
    v_key,
    p_record->>'task_id',
    p_record->>'trace_id',
    p_record->>'owner_id',
    coalesce(nullif(p_record->>'billing_account_id',''), p_record->>'owner_id'),
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

create or replace function public.credit_ledger_settle(p_command jsonb)
returns jsonb language plpgsql security definer set search_path = ''
as $$
declare
  v_res_id uuid := (p_command->>'reservation_id')::uuid;
  v_key text := p_command->>'idempotency_key';
  v_policy text := p_command->>'policy_version';
  v_source text := p_command->>'source_event_id';
  v_actual bigint := (p_command->>'actual_credits')::bigint;
  v_actual_units bigint := (p_command->>'actual_usage_units')::bigint;
  v_usage_unit text := p_command->>'usage_unit';
  v_fp text := encode(extensions.digest(p_command::text, 'sha256'), 'hex');
  v_res public.credit_reservations;
  v_existing public.credit_ledger_entries;
  v_entry public.credit_ledger_entries;
  v_policy_row public.credit_policy_versions;
  v_cap jsonb;
  v_metering public.agent_model_usage_metering;
  v_unused bigint;
begin
  if v_res_id is null or coalesce(v_key,'') = '' or coalesce(v_source,'') = ''
    or v_actual is null or v_actual <= 0 then
    raise exception 'INVALID_CREDIT_SETTLEMENT' using errcode = '22023';
  end if;
  select * into v_res from public.credit_reservations where id = v_res_id for update;
  if not found then raise exception 'CREDIT_RESERVATION_NOT_FOUND' using errcode = 'P0002'; end if;
  perform 1 from public.credit_ledger_accounts where owner_user_id = v_res.owner_user_id for update;
  select * into v_existing from public.credit_ledger_entries where owner_user_id = v_res.owner_user_id and idempotency_key = v_key;
  if found then
    if v_existing.payload_fingerprint <> v_fp or v_existing.entry_type <> 'settlement' then
      raise exception 'CREDIT_LEDGER_IDEMPOTENCY_CONFLICT' using errcode = '23505';
    end if;
    return jsonb_build_object('reservation_id',v_res.id,'idempotency_key',v_key,
      'account_id',v_res.owner_user_id,'task_id',v_res.task_id,'reserved_credits',v_res.reserved_credits,'state','settled','policy_version',v_res.policy_version,'estimated_usage_units',v_res.estimated_usage_units,'usage_unit',v_res.usage_unit);
  end if;
  if v_res.state not in ('reserved','pending_reconciliation') then
    raise exception 'CREDIT_RESERVATION_NOT_SETTLEABLE' using errcode = '23514';
  end if;
  if v_policy <> v_res.policy_version or v_actual > v_res.reserved_credits
    or v_actual_units is null or v_actual_units <= 0 or coalesce(v_usage_unit,'') = ''
    or coalesce((p_command->>'release_unused')::boolean,false) <> (v_actual < v_res.reserved_credits) then
    raise exception 'CREDIT_SETTLEMENT_POLICY_OR_AMOUNT_MISMATCH' using errcode = '22023';
  end if;
  select * into v_policy_row from public.credit_policy_versions
    where policy_version = v_res.policy_version
      and approval_reference = v_res.policy_approval_reference
      and status in ('approved','retired') for share;
  if not found then raise exception 'CREDIT_SETTLEMENT_POLICY_NOT_FOUND' using errcode = '42501'; end if;
  v_cap := v_policy_row.configuration->'capabilities'->v_res.capability_id;
  select * into v_metering from public.agent_model_usage_metering
    where idempotency_key=v_source and billing_account_id=v_res.owner_user_id::text
      and task_id=v_res.task_id;
  if not found then raise exception 'CREDIT_SETTLEMENT_METERING_NOT_FOUND' using errcode = '23503'; end if;
  if v_metering.usage_units <> v_actual_units or v_metering.usage_unit <> v_usage_unit then
    raise exception 'CREDIT_SETTLEMENT_METERING_USAGE_MISMATCH' using errcode = '22023';
  end if;
  if v_metering.cost_unit <> (v_cap->>'cost_unit')
    or v_metering.pricing_version <> (v_cap->>'cost_pricing_version')
    or not (v_cap ? 'max_cost_microunits')
    or coalesce((v_cap->>'max_cost_microunits')::bigint,-1) < 0
    or v_metering.cost_microunits > (v_cap->>'max_cost_microunits')::bigint then
    raise exception 'CREDIT_ACTUAL_COST_GUARDRAIL_EXCEEDED_OR_MISMATCH' using errcode = '23514';
  end if;
  if jsonb_typeof(v_cap) <> 'object'
    or v_cap->>'tariff_version' <> v_res.tariff_version
    or (v_cap->>'usage_unit') <> v_usage_unit

    or v_usage_unit <> v_res.usage_unit
    or v_actual <> v_actual_units * coalesce((v_cap->>'credits_per_usage_unit')::bigint,0) then
    raise exception 'CREDIT_ACTUAL_USAGE_TARIFF_MISMATCH' using errcode = '22023';
  end if;
  if v_actual_units < v_res.estimated_usage_units then
    if not coalesce((v_policy_row.configuration->>'allow_partial_settlement')::boolean,false) then
      raise exception 'CREDIT_PARTIAL_SETTLEMENT_NOT_APPROVED' using errcode = '42501';
    end if;
  elsif not coalesce((v_policy_row.configuration->>'allow_success_settlement')::boolean,false) then
    raise exception 'CREDIT_SUCCESS_SETTLEMENT_NOT_APPROVED' using errcode = '42501';
  end if;
  insert into public.credit_ledger_entries(
    owner_user_id,idempotency_key,entry_type,credits,balance_delta,credit_scheme_version,
    policy_version,tariff_version,entitlement_version,capability_id,task_id,source_event_id,
    related_entry_id,payload_fingerprint,metadata
  ) values (
    v_res.owner_user_id,v_key,'settlement',v_actual,0,v_res.credit_scheme_version,
    v_policy,v_res.tariff_version,v_res.entitlement_version,v_res.capability_id,v_res.task_id,
    v_source,v_res.reservation_entry_id,v_fp,
    jsonb_build_object('actual_usage_units',v_actual_units,'usage_unit',v_usage_unit,
      'actual_cost_microunits',v_metering.cost_microunits,'cost_unit',v_metering.cost_unit,
      'cost_pricing_version',v_metering.pricing_version)
  ) returning * into v_entry;
  v_unused := v_res.reserved_credits - v_actual;
  if v_unused > 0 then
    insert into public.credit_ledger_entries(
      owner_user_id,idempotency_key,entry_type,credits,balance_delta,credit_scheme_version,
      policy_version,tariff_version,entitlement_version,capability_id,task_id,source_event_id,
      related_entry_id,payload_fingerprint
    ) values (
      v_res.owner_user_id,left(v_key || ':unused-release',256),'release',v_unused,v_unused,
      v_res.credit_scheme_version,v_policy,v_res.tariff_version,v_res.entitlement_version,
      v_res.capability_id,v_res.task_id,v_source,v_res.reservation_entry_id,
      encode(extensions.digest((p_command || jsonb_build_object('release_unused',v_unused))::text,'sha256'),'hex')
    );
  end if;
  update public.credit_reservations set state='settled', settled_credits=v_actual,
    source_event_id=v_source, updated_at=now() where id=v_res.id;
  update public.credit_balance_projection set available_credits=available_credits+v_unused,
    ledger_entry_count=ledger_entry_count+1+(case when v_unused > 0 then 1 else 0 end),updated_at=now()
    where owner_user_id=v_res.owner_user_id;
  return jsonb_build_object('reservation_id',v_res.id,'idempotency_key',v_key,
    'account_id',v_res.owner_user_id,'task_id',v_res.task_id,'reserved_credits',v_res.reserved_credits,'state','settled','policy_version',v_res.policy_version,'estimated_usage_units',v_res.estimated_usage_units,'usage_unit',v_res.usage_unit);
end;
$$;

comment on column public.agent_model_usage_metering.billing_account_id is
  'Server-derived credit account payer. owner_id continues to identify the Agent owner for attribution.';

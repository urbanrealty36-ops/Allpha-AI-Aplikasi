-- ENG-P09 durable AI Credit ledger.
-- SOURCE ONLY: validate and apply only to an approved isolated non-production branch.
-- Financial policy values are intentionally NOT seeded; no charging is possible until
-- a versioned policy is explicitly configured and approved in the Financial phase.
create table public.credit_policy_versions (
  policy_version text primary key check (length(policy_version) between 1 and 80),
  credit_scheme_version text not null check (length(credit_scheme_version) between 1 and 80),
  approval_reference text not null check (length(approval_reference) between 1 and 160),
  status text not null check (status in ('draft','approved','retired')),
  configuration jsonb not null check (jsonb_typeof(configuration) = 'object'),
  created_by uuid references auth.users(id) on delete restrict,
  approved_by uuid references auth.users(id) on delete restrict,
  approved_at timestamptz,
  effective_at timestamptz,
  expires_at timestamptz,
  created_at timestamptz not null default now(),
  check (expires_at is null or effective_at is null or expires_at > effective_at),
  check ((status = 'approved' and approved_by is not null and approved_at is not null)
      or status <> 'approved')
);

create table public.credit_ledger_accounts (
  owner_user_id uuid primary key references auth.users(id) on delete restrict,
  created_at timestamptz not null default now()
);

create table public.credit_ledger_entries (
  id uuid primary key default gen_random_uuid(),
  owner_user_id uuid not null references public.credit_ledger_accounts(owner_user_id) on delete restrict,
  idempotency_key text not null check (length(idempotency_key) between 1 and 256),
  entry_type text not null check (entry_type in ('grant','promotional_grant','reservation','settlement','release','expiry','refund','reversal','adjustment')),
  credits bigint not null check (credits > 0),
  balance_delta bigint not null,
  credit_scheme_version text not null check (length(credit_scheme_version) between 1 and 80),
  policy_version text not null references public.credit_policy_versions(policy_version) on delete restrict,
  tariff_version text,
  entitlement_version text,
  capability_id text not null check (length(capability_id) between 1 and 128),
  task_id text,
  source_event_id text not null check (length(source_event_id) between 1 and 160),
  related_entry_id uuid references public.credit_ledger_entries(id) on delete restrict,
  payload_fingerprint text not null check (payload_fingerprint ~ '^[0-9a-f]{64}$'),
  metadata jsonb not null default '{}'::jsonb check (jsonb_typeof(metadata) = 'object'),
  created_at timestamptz not null default now(),
  unique (owner_user_id, idempotency_key)
);
create index credit_ledger_entries_owner_created_idx on public.credit_ledger_entries(owner_user_id, created_at desc, id desc);
create index credit_ledger_entries_task_idx on public.credit_ledger_entries(owner_user_id, task_id) where task_id is not null;
create unique index credit_ledger_entries_one_settlement_per_reservation
  on public.credit_ledger_entries(related_entry_id) where entry_type = 'settlement';

create table public.credit_reservations (
  id uuid primary key default gen_random_uuid(),
  owner_user_id uuid not null references public.credit_ledger_accounts(owner_user_id) on delete restrict,
  reservation_entry_id uuid not null unique references public.credit_ledger_entries(id) on delete restrict,
  idempotency_key text not null check (length(idempotency_key) between 1 and 256),
  task_id text not null check (length(task_id) between 1 and 160),
  capability_id text not null check (length(capability_id) between 1 and 128),
  reserved_credits bigint not null check (reserved_credits > 0),
  estimated_usage_units bigint not null check (estimated_usage_units > 0),
  usage_unit text not null check (length(usage_unit) between 1 and 80),
  settled_credits bigint not null default 0 check (settled_credits >= 0),
  credit_scheme_version text not null,
  tariff_version text not null,
  entitlement_version text not null,
  policy_version text not null references public.credit_policy_versions(policy_version) on delete restrict,
  policy_approval_reference text not null,
  state text not null check (state in ('reserved','settled','released','pending_reconciliation')),
  source_event_id text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (owner_user_id, idempotency_key),
  check (settled_credits <= reserved_credits)
);
create index credit_reservations_recovery_idx on public.credit_reservations(state, updated_at) where state = 'pending_reconciliation';

create table public.credit_balance_projection (
  owner_user_id uuid primary key references public.credit_ledger_accounts(owner_user_id) on delete restrict,
  available_credits bigint not null default 0 check (available_credits >= 0),
  ledger_entry_count bigint not null default 0 check (ledger_entry_count >= 0),
  updated_at timestamptz not null default now()
);

create table public.credit_reconciliation_events (
  id uuid primary key default gen_random_uuid(),
  owner_user_id uuid not null references public.credit_ledger_accounts(owner_user_id) on delete restrict,
  reservation_id uuid references public.credit_reservations(id) on delete restrict,
  event_type text not null check (event_type in ('outcome_unknown','release','settlement','projection_repair','manual_review')),
  reason_code text not null check (length(reason_code) between 1 and 100),
  idempotency_key text not null check (length(idempotency_key) between 1 and 256),
  actor_type text not null check (actor_type in ('system','operator')),
  actor_id uuid references auth.users(id) on delete restrict,
  details jsonb not null default '{}'::jsonb check (jsonb_typeof(details) = 'object'),
  payload_fingerprint text not null check (payload_fingerprint ~ '^[0-9a-f]{64}
  unique (owner_user_id, idempotency_key)
);

alter table public.credit_policy_versions enable row level security;
alter table public.credit_ledger_accounts enable row level security;
alter table public.credit_ledger_entries enable row level security;
alter table public.credit_reservations enable row level security;
alter table public.credit_balance_projection enable row level security;
alter table public.credit_reconciliation_events enable row level security;
revoke all on table public.credit_policy_versions, public.credit_ledger_accounts,
  public.credit_ledger_entries, public.credit_reservations,
  public.credit_balance_projection, public.credit_reconciliation_events
  from public, anon, authenticated, service_role;

-- The API uses service-role credentials only server-side after deriving owner_user_id
-- from verified Supabase Auth. No client role can call these mutation RPCs or write tables.

create or replace function public.credit_ledger_get_balance(p_owner_user_id uuid)
returns jsonb language plpgsql security definer set search_path = ''
as $$
declare
  v_available bigint;
  v_reserved bigint;
  v_count bigint;
begin
  if p_owner_user_id is null then
    raise exception 'CREDIT_ACCOUNT_REQUIRED' using errcode = '22023';
  end if;
  select coalesce(available_credits,0), coalesce(ledger_entry_count,0)
    into v_available,v_count
    from public.credit_balance_projection where owner_user_id=p_owner_user_id;
  if not found then v_available := 0; v_count := 0; end if;
  select coalesce(sum(reserved_credits - settled_credits),0) into v_reserved
    from public.credit_reservations where owner_user_id=p_owner_user_id
      and state in ('reserved','pending_reconciliation');
  return jsonb_build_object(
    'available_credits',v_available,
    'reserved_credits',v_reserved,
    'ledger_entry_count',v_count,
    'as_of',now()
  );
end;
$$;

create or replace function public.credit_ledger_grant(p_command jsonb)
returns jsonb language plpgsql security definer set search_path = ''
as $$
declare
  v_owner uuid := (p_command->>'owner_user_id')::uuid;
  v_key text := p_command->>'idempotency_key';
  v_policy text := p_command->>'policy_version';
  v_approval text := p_command->>'policy_approval_reference';
  v_type text := p_command->>'entry_type';
  v_credits bigint := (p_command->>'credits')::bigint;
  v_fingerprint text := encode(extensions.digest(p_command::text, 'sha256'), 'hex');
  v_existing public.credit_ledger_entries;
  v_policy_row public.credit_policy_versions;
  v_entry public.credit_ledger_entries;
begin
  if v_owner is null or v_key is null or length(v_key) not between 1 and 256
    or v_credits is null or v_credits <= 0
    or v_type not in ('grant','promotional_grant')
    or coalesce(p_command->>'source_event_id','') = ''
    or coalesce(p_command->>'capability_id','') = '' then
    raise exception 'INVALID_CREDIT_GRANT' using errcode = '22023';
  end if;
  select * into v_policy_row from public.credit_policy_versions
    where policy_version = v_policy and approval_reference = v_approval
      and status = 'approved' and (effective_at is null or effective_at <= now())
      and (expires_at is null or expires_at > now()) for share;
  if not found or not coalesce((v_policy_row.configuration->>'allow_grants')::boolean, false)
    or not coalesce((v_policy_row.configuration->'allowed_grant_types') ? v_type, false) then
    raise exception 'CREDIT_POLICY_NOT_APPROVED_FOR_GRANT' using errcode = '42501';
  end if;
  insert into public.credit_ledger_accounts(owner_user_id) values (v_owner) on conflict do nothing;
  perform 1 from public.credit_ledger_accounts where owner_user_id = v_owner for update;
  select * into v_existing from public.credit_ledger_entries
    where owner_user_id = v_owner and idempotency_key = v_key;
  if found then
    if v_existing.payload_fingerprint <> v_fingerprint then
      raise exception 'CREDIT_LEDGER_IDEMPOTENCY_CONFLICT' using errcode = '23505';
    end if;
    return jsonb_build_object('entry_id',v_existing.id,'idempotent_replay',true);
  end if;
  insert into public.credit_balance_projection(owner_user_id) values (v_owner) on conflict do nothing;
  insert into public.credit_ledger_entries(
    owner_user_id,idempotency_key,entry_type,credits,balance_delta,credit_scheme_version,
    policy_version,capability_id,source_event_id,payload_fingerprint,metadata
  ) values (
    v_owner,v_key,v_type,v_credits,v_credits,v_policy_row.credit_scheme_version,
    v_policy,coalesce(p_command->>'capability_id','account_grant'),
    p_command->>'source_event_id',v_fingerprint,
    coalesce(p_command->'metadata','{}'::jsonb)
  ) returning * into v_entry;
  update public.credit_balance_projection set available_credits = available_credits + v_credits,
    ledger_entry_count = ledger_entry_count + 1, updated_at = now() where owner_user_id = v_owner;
  return jsonb_build_object('entry_id',v_entry.id,'idempotent_replay',false);
end;
$$;

create or replace function public.credit_ledger_reserve(p_command jsonb)
returns jsonb language plpgsql security definer set search_path = ''
as $$
declare
  v_owner uuid := (p_command->>'owner_user_id')::uuid;
  v_key text := p_command->>'idempotency_key';
  v_policy text := p_command->>'policy_version';
  v_approval text := p_command->>'policy_approval_reference';
  v_capability text := p_command->>'capability_id';
  v_tariff text := p_command->>'tariff_version';
  v_units bigint := (p_command->>'estimated_usage_units')::bigint;
  v_usage_unit text := p_command->>'usage_unit';
  v_estimated_cost bigint := (p_command->>'estimated_cost_microunits')::bigint;
  v_cost_unit text := p_command->>'cost_unit';
  v_credits bigint := (p_command->>'credits_to_reserve')::bigint;
  v_task text := p_command->>'task_id';
  v_fingerprint text := encode(extensions.digest(p_command::text, 'sha256'), 'hex');
  v_existing public.credit_ledger_entries;
  v_policy_row public.credit_policy_versions;
  v_cap jsonb;
  v_entitlement jsonb;
  v_active_reservations bigint;
  v_available bigint;
  v_entry public.credit_ledger_entries;
  v_res public.credit_reservations;
begin
  if v_owner is null or v_key is null or length(v_key) not between 1 and 256
    or v_credits is null or v_credits <= 0 or v_units is null or v_units <= 0
    or coalesce(v_capability,'') = '' or coalesce(v_task,'') = ''
    or coalesce(v_usage_unit,'') = '' or v_estimated_cost is null
    or v_estimated_cost < 0 or coalesce(v_cost_unit,'') = '' then
    raise exception 'INVALID_CREDIT_RESERVATION' using errcode = '22023';
  end if;
  select * into v_policy_row from public.credit_policy_versions
    where policy_version = v_policy and approval_reference = v_approval
      and status = 'approved' and (effective_at is null or effective_at <= now())
      and (expires_at is null or expires_at > now()) for share;
  if not found then raise exception 'CREDIT_POLICY_NOT_APPROVED' using errcode = '42501'; end if;
  if p_command->>'credit_scheme_version' <> v_policy_row.credit_scheme_version
    or coalesce(p_command->>'entitlement_version','') = '' then
    raise exception 'CREDIT_RESERVATION_VERSION_MISMATCH' using errcode = '22023';
  end if;
  v_cap := v_policy_row.configuration->'capabilities'->v_capability;
  v_entitlement := v_policy_row.configuration->'entitlements'->(p_command->>'entitlement_version');
  if jsonb_typeof(v_cap) <> 'object' or v_cap->>'tariff_version' <> v_tariff
    or v_cap->>'usage_unit' <> v_usage_unit
    or coalesce((v_cap->>'credits_per_usage_unit')::bigint,0) <= 0 then
    raise exception 'CREDIT_CAPABILITY_TARIFF_UNAVAILABLE' using errcode = '42501';
  end if;
  if jsonb_typeof(v_entitlement) <> 'object'
    or coalesce((v_entitlement->>'max_credits_per_request')::bigint,0) <= 0
    or coalesce((v_entitlement->>'max_concurrent_reservations')::bigint,0) <= 0
    or v_credits > (v_entitlement->>'max_credits_per_request')::bigint then
    raise exception 'CREDIT_ENTITLEMENT_LIMITS_NOT_CONFIGURED' using errcode = '42501';
  end if;
  if not (v_cap ? 'max_cost_microunits')
    or coalesce(v_cap->>'cost_unit','') <> v_cost_unit
    or coalesce(v_cap->>'cost_pricing_version','') = ''
    or coalesce((v_cap->>'max_cost_microunits')::bigint,-1) < 0
    or v_estimated_cost > (v_cap->>'max_cost_microunits')::bigint then
    raise exception 'CREDIT_COST_GUARDRAIL_NOT_CONFIGURED_OR_EXCEEDED' using errcode = '42501';
  end if;
  if v_credits <> v_units * (v_cap->>'credits_per_usage_unit')::bigint then
    raise exception 'CREDIT_RESERVATION_ESTIMATE_MISMATCH' using errcode = '22023';
  end if;
  insert into public.credit_ledger_accounts(owner_user_id) values (v_owner) on conflict do nothing;
  perform 1 from public.credit_ledger_accounts where owner_user_id = v_owner for update;
  select * into v_existing from public.credit_ledger_entries where owner_user_id = v_owner and idempotency_key = v_key;
  if found then
    if v_existing.payload_fingerprint <> v_fingerprint or v_existing.entry_type <> 'reservation' then
      raise exception 'CREDIT_LEDGER_IDEMPOTENCY_CONFLICT' using errcode = '23505';
    end if;
    select * into v_res from public.credit_reservations where reservation_entry_id = v_existing.id;
    return jsonb_build_object('reservation_id',v_res.id,'idempotency_key',v_res.idempotency_key,
      'account_id',v_owner,'task_id',v_res.task_id,'reserved_credits',v_res.reserved_credits,'state',v_res.state,'policy_version',v_res.policy_version);
  end if;
  insert into public.credit_balance_projection(owner_user_id) values (v_owner) on conflict do nothing;
  select available_credits into v_available from public.credit_balance_projection where owner_user_id = v_owner for update;
  select count(*) into v_active_reservations from public.credit_reservations
    where owner_user_id=v_owner and state in ('reserved','pending_reconciliation');
  if v_active_reservations >= (v_entitlement->>'max_concurrent_reservations')::bigint then
    raise exception 'CREDIT_CONCURRENT_RESERVATION_LIMIT' using errcode = '23514';
  end if;
  if v_available < v_credits then raise exception 'INSUFFICIENT_AI_CREDITS' using errcode = '23514'; end if;
  insert into public.credit_ledger_entries(
    owner_user_id,idempotency_key,entry_type,credits,balance_delta,credit_scheme_version,
    policy_version,tariff_version,entitlement_version,capability_id,task_id,source_event_id,
    payload_fingerprint,metadata
  ) values (
    v_owner,v_key,'reservation',v_credits,-v_credits,v_policy_row.credit_scheme_version,
    v_policy,v_tariff,p_command->>'entitlement_version',v_capability,v_task,v_task,
    v_fingerprint,'{}'::jsonb
  ) returning * into v_entry;
  insert into public.credit_reservations(
    owner_user_id,reservation_entry_id,idempotency_key,task_id,capability_id,reserved_credits,
    estimated_usage_units,usage_unit,credit_scheme_version,tariff_version,entitlement_version,
    policy_version,policy_approval_reference,state
  ) values (
    v_owner,v_entry.id,v_key,v_task,v_capability,v_credits,v_units,v_usage_unit,
    v_policy_row.credit_scheme_version,v_tariff,p_command->>'entitlement_version',v_policy,v_approval,'reserved'
  ) returning * into v_res;
  update public.credit_balance_projection set available_credits = available_credits - v_credits,
    ledger_entry_count = ledger_entry_count + 1, updated_at = now() where owner_user_id = v_owner;
  return jsonb_build_object('reservation_id',v_res.id,'idempotency_key',v_res.idempotency_key,
    'account_id',v_owner,'task_id',v_res.task_id,'reserved_credits',v_res.reserved_credits,'state',v_res.state,'policy_version',v_res.policy_version);
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
      'account_id',v_res.owner_user_id,'task_id',v_res.task_id,'reserved_credits',v_res.reserved_credits,'state','settled','policy_version',v_res.policy_version);
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
    where idempotency_key=v_source and owner_id=v_res.owner_user_id::text
      and task_id=v_res.task_id;
  if not found then raise exception 'CREDIT_SETTLEMENT_METERING_NOT_FOUND' using errcode = '23503'; end if;
  if v_metering.usage_units <> v_actual_units or v_metering.usage_unit <> v_usage_unit then
    raise exception 'CREDIT_SETTLEMENT_METERING_USAGE_MISMATCH' using errcode = '22023';
  end if;
  if v_metering.cost_unit <> v_cap->>'cost_unit'
    or v_metering.pricing_version <> v_cap->>'cost_pricing_version'
    or not (v_cap ? 'max_cost_microunits')
    or coalesce((v_cap->>'max_cost_microunits')::bigint,-1) < 0
    or v_metering.cost_microunits > (v_cap->>'max_cost_microunits')::bigint then
    raise exception 'CREDIT_ACTUAL_COST_GUARDRAIL_EXCEEDED_OR_MISMATCH' using errcode = '23514';
  end if;
  if jsonb_typeof(v_cap) <> 'object'
    or v_cap->>'tariff_version' <> v_res.tariff_version
    or v_cap->>'usage_unit' <> v_usage_unit

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
    related_entry_id,payload_fingerprint
  ) values (
    v_res.owner_user_id,v_key,'settlement',v_actual,0,v_res.credit_scheme_version,
    v_policy,v_res.tariff_version,v_res.entitlement_version,v_res.capability_id,v_res.task_id,
    v_source,v_res.reservation_entry_id,v_fp
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
    'account_id',v_res.owner_user_id,'task_id',v_res.task_id,'reserved_credits',v_res.reserved_credits,'state','settled','policy_version',v_res.policy_version);
end;
$$;

create or replace function public.credit_ledger_release(p_command jsonb)
returns jsonb language plpgsql security definer set search_path = ''
as $$
declare
  v_res_id uuid := (p_command->>'reservation_id')::uuid;
  v_key text := p_command->>'idempotency_key';
  v_policy text := p_command->>'policy_version';
  v_reason text := p_command->>'reason_code';
  v_fp text := encode(extensions.digest(p_command::text, 'sha256'), 'hex');
  v_res public.credit_reservations;
  v_existing public.credit_ledger_entries;
  v_amount bigint;
begin
  if v_res_id is null or coalesce(v_key,'') = '' or coalesce(v_reason,'') = '' then
    raise exception 'INVALID_CREDIT_RELEASE' using errcode = '22023';
  end if;
  select * into v_res from public.credit_reservations where id=v_res_id for update;
  if not found then raise exception 'CREDIT_RESERVATION_NOT_FOUND' using errcode = 'P0002'; end if;
  perform 1 from public.credit_ledger_accounts where owner_user_id=v_res.owner_user_id for update;
  select * into v_existing from public.credit_ledger_entries where owner_user_id=v_res.owner_user_id and idempotency_key=v_key;
  if found then
    if v_existing.payload_fingerprint <> v_fp or v_existing.entry_type <> 'release' then
      raise exception 'CREDIT_LEDGER_IDEMPOTENCY_CONFLICT' using errcode = '23505';
    end if;
    return jsonb_build_object('reservation_id',v_res.id,'idempotency_key',v_key,
      'account_id',v_res.owner_user_id,'task_id',v_res.task_id,'reserved_credits',v_res.reserved_credits,'state',v_res.state,'policy_version',v_res.policy_version);
  end if;
  if v_res.state not in ('reserved','pending_reconciliation') or v_policy <> v_res.policy_version then
    raise exception 'CREDIT_RESERVATION_NOT_RELEASABLE' using errcode = '23514';
  end if;
  if not exists (
    select 1 from public.credit_policy_versions p
    where p.policy_version=v_res.policy_version
      and p.approval_reference=v_res.policy_approval_reference
      and p.status in ('approved','retired')
      and coalesce((p.configuration->>'allow_definitive_failure_release')::boolean,false)
  ) then
    raise exception 'CREDIT_FAILURE_RELEASE_NOT_APPROVED' using errcode = '42501';
  end if;
  v_amount := v_res.reserved_credits - v_res.settled_credits;
  if v_amount <= 0 then raise exception 'CREDIT_RESERVATION_HAS_NO_REMAINDER' using errcode = '23514'; end if;
  insert into public.credit_ledger_entries(
    owner_user_id,idempotency_key,entry_type,credits,balance_delta,credit_scheme_version,
    policy_version,tariff_version,entitlement_version,capability_id,task_id,source_event_id,
    related_entry_id,payload_fingerprint,metadata
  ) values (
    v_res.owner_user_id,v_key,'release',v_amount,v_amount,v_res.credit_scheme_version,
    v_policy,v_res.tariff_version,v_res.entitlement_version,v_res.capability_id,v_res.task_id,
    coalesce(v_res.source_event_id,v_res.task_id),v_res.reservation_entry_id,v_fp,
    jsonb_build_object('reason_code',v_reason)
  );
  update public.credit_reservations set state='released',updated_at=now() where id=v_res.id;
  update public.credit_balance_projection set available_credits=available_credits+v_amount,
    ledger_entry_count=ledger_entry_count+1,updated_at=now() where owner_user_id=v_res.owner_user_id;
  return jsonb_build_object('reservation_id',v_res.id,'idempotency_key',v_key,
    'account_id',v_res.owner_user_id,'task_id',v_res.task_id,'reserved_credits',v_res.reserved_credits,'state','released','policy_version',v_res.policy_version);
end;
$$;



create or replace function public.credit_ledger_reverse(p_command jsonb)
returns jsonb language plpgsql security definer set search_path = ''
as $$
declare
  v_owner uuid := (p_command->>'owner_user_id')::uuid;
  v_original_id uuid := (p_command->>'original_entry_id')::uuid;
  v_key text := p_command->>'idempotency_key';
  v_policy text := p_command->>'policy_version';
  v_approval text := p_command->>'policy_approval_reference';
  v_reason text := p_command->>'reason_code';
  v_credits bigint := (p_command->>'credits')::bigint;
  v_fp text := encode(extensions.digest(p_command::text,'sha256'),'hex');
  v_original public.credit_ledger_entries;
  v_policy_row public.credit_policy_versions;
  v_existing public.credit_ledger_entries;
  v_entry public.credit_ledger_entries;
  v_reversed bigint;
begin
  if v_owner is null or v_original_id is null or coalesce(v_key,'') = ''
    or coalesce(v_reason,'') = '' or coalesce(p_command->>'source_event_id','') = ''
    or coalesce(p_command->>'entry_type','reversal') not in ('refund','reversal')
    or v_credits is null or v_credits <= 0 then
    raise exception 'INVALID_CREDIT_REVERSAL' using errcode = '22023';
  end if;
  select * into v_policy_row from public.credit_policy_versions
    where policy_version=v_policy and approval_reference=v_approval
      and status='approved' and (effective_at is null or effective_at <= now())
      and (expires_at is null or expires_at > now()) for share;
  if not found or not coalesce((v_policy_row.configuration->>'allow_refunds')::boolean,false) then
    raise exception 'CREDIT_REFUND_POLICY_NOT_APPROVED' using errcode = '42501';
  end if;
  insert into public.credit_ledger_accounts(owner_user_id) values(v_owner) on conflict do nothing;
  perform 1 from public.credit_ledger_accounts where owner_user_id=v_owner for update;
  select * into v_existing from public.credit_ledger_entries where owner_user_id=v_owner and idempotency_key=v_key;
  if found then
    if v_existing.payload_fingerprint <> v_fp or v_existing.entry_type not in ('refund','reversal') then
      raise exception 'CREDIT_LEDGER_IDEMPOTENCY_CONFLICT' using errcode = '23505';
    end if;
    return jsonb_build_object('entry_id',v_existing.id,'idempotent_replay',true);
  end if;
  select * into v_original from public.credit_ledger_entries
    where id=v_original_id and owner_user_id=v_owner for update;
  if not found or v_original.entry_type <> 'settlement' then
    raise exception 'CREDIT_REVERSAL_SOURCE_NOT_REVERSIBLE' using errcode = '22023';
  end if;
  select coalesce(sum(credits),0) into v_reversed from public.credit_ledger_entries
    where owner_user_id=v_owner and related_entry_id=v_original.id and entry_type in ('refund','reversal');
  if not (v_policy_row.configuration ? 'max_reversal_credits')
    or coalesce((v_policy_row.configuration->>'max_reversal_credits')::bigint,0) <= 0
    or v_credits + v_reversed > v_original.credits
    or v_credits > (v_policy_row.configuration->>'max_reversal_credits')::bigint then
    raise exception 'CREDIT_REVERSAL_LIMIT_EXCEEDED' using errcode = '23514';
  end if;
  insert into public.credit_balance_projection(owner_user_id) values(v_owner) on conflict do nothing;
  insert into public.credit_ledger_entries(
    owner_user_id,idempotency_key,entry_type,credits,balance_delta,credit_scheme_version,
    policy_version,tariff_version,entitlement_version,capability_id,task_id,source_event_id,
    related_entry_id,payload_fingerprint,metadata
  ) values (
    v_owner,v_key,coalesce(nullif(p_command->>'entry_type',''),'reversal'),v_credits,v_credits,
    v_original.credit_scheme_version,v_policy,v_original.tariff_version,v_original.entitlement_version,
    v_original.capability_id,v_original.task_id,p_command->>'source_event_id',v_original.id,v_fp,
    jsonb_build_object('reason_code',v_reason)
  ) returning * into v_entry;
  update public.credit_balance_projection set available_credits=available_credits+v_credits,
    ledger_entry_count=ledger_entry_count+1,updated_at=now() where owner_user_id=v_owner;
  insert into public.credit_reconciliation_events(
    owner_user_id,event_type,reason_code,idempotency_key,actor_type,actor_id,
    details,payload_fingerprint
  ) values (
    v_owner,case when v_entry.entry_type='refund' then 'settlement' else 'manual_review' end,
    v_reason,'reverse:'||v_key,coalesce(p_command->>'actor_type','operator'),
    nullif(p_command->>'actor_id','')::uuid,
    jsonb_build_object('original_entry_id',v_original.id,'compensating_entry_id',v_entry.id,'credits',v_credits),
    v_fp
  );
  return jsonb_build_object('entry_id',v_entry.id,'idempotent_replay',false);
end;
$$;


create or replace function public.credit_ledger_reconcile_projection(p_command jsonb)
returns jsonb language plpgsql security definer set search_path = ''
as $
declare
  v_owner uuid := (p_command->>'owner_user_id')::uuid;
  v_key text := p_command->>'idempotency_key';
  v_reason text := p_command->>'reason_code';
  v_actor uuid := nullif(p_command->>'actor_id','')::uuid;
  v_fp text := encode(extensions.digest(p_command::text,'sha256'),'hex');
  v_before bigint;
  v_after bigint;
  v_count bigint;
  v_event public.credit_reconciliation_events;
begin
  if v_owner is null or coalesce(v_key,'') = '' or coalesce(v_reason,'') = '' then
    raise exception 'INVALID_CREDIT_RECONCILIATION_COMMAND' using errcode = '22023';
  end if;
  insert into public.credit_ledger_accounts(owner_user_id) values(v_owner) on conflict do nothing;
  perform 1 from public.credit_ledger_accounts where owner_user_id=v_owner for update;
  select * into v_event from public.credit_reconciliation_events
    where owner_user_id=v_owner and idempotency_key=v_key;
  if found then
    if v_event.payload_fingerprint <> v_fp then
      raise exception 'CREDIT_RECONCILIATION_IDEMPOTENCY_CONFLICT' using errcode = '23505';
    end if;
    return jsonb_build_object('event_id',v_event.id,'idempotent_replay',true);
  end if;
  insert into public.credit_balance_projection(owner_user_id) values(v_owner) on conflict do nothing;
  select available_credits into v_before from public.credit_balance_projection
    where owner_user_id=v_owner for update;
  select coalesce(sum(balance_delta),0),count(*) into v_after,v_count
    from public.credit_ledger_entries where owner_user_id=v_owner;
  if v_after < 0 then
    raise exception 'CREDIT_LEDGER_NEGATIVE_RECONCILED_BALANCE' using errcode = '23514';
  end if;
  update public.credit_balance_projection set available_credits=v_after,
    ledger_entry_count=v_count,updated_at=now() where owner_user_id=v_owner;
  insert into public.credit_reconciliation_events(
    owner_user_id,event_type,reason_code,idempotency_key,actor_type,actor_id,
    details,payload_fingerprint
  ) values (
    v_owner,'projection_repair',v_reason,v_key,'operator',v_actor,
    jsonb_build_object('before_available_credits',v_before,'after_available_credits',v_after,'ledger_entry_count',v_count),
    v_fp
  ) returning * into v_event;
  return jsonb_build_object('event_id',v_event.id,'idempotent_replay',false,
    'before_available_credits',v_before,'after_available_credits',v_after,'ledger_entry_count',v_count);
end;
$;

create or replace function public.credit_ledger_mark_pending(p_command jsonb)
returns jsonb language plpgsql security definer set search_path = ''
as $$
declare
  v_res_id uuid := (p_command->>'reservation_id')::uuid;
  v_reason text := coalesce(p_command->>'reason_code','provider_outcome_unknown');
  v_fp text := encode(extensions.digest(jsonb_build_object('reservation_id',p_command->>'reservation_id','reason_code',coalesce(p_command->>'reason_code','provider_outcome_unknown'))::text,'sha256'),'hex');
  v_res public.credit_reservations;
begin
  if v_res_id is null then raise exception 'INVALID_CREDIT_RESERVATION_ID' using errcode = '22023'; end if;
  select * into v_res from public.credit_reservations where id=v_res_id for update;
  if not found then raise exception 'CREDIT_RESERVATION_NOT_FOUND' using errcode = 'P0002'; end if;
  if v_res.state in ('settled','released') then
    raise exception 'CREDIT_RESERVATION_ALREADY_TERMINAL' using errcode = '23514';
  end if;
  if v_res.state <> 'pending_reconciliation' then
    update public.credit_reservations set state='pending_reconciliation',updated_at=now() where id=v_res.id;
    insert into public.credit_reconciliation_events(
      owner_user_id,reservation_id,event_type,reason_code,idempotency_key,actor_type,payload_fingerprint
    ) values (v_res.owner_user_id,v_res.id,'outcome_unknown',v_reason,'pending:'||v_res.id::text,'system',v_fp)
    on conflict (owner_user_id,idempotency_key) do nothing;
  end if;
  return jsonb_build_object('reservation_id',v_res.id,'idempotency_key',v_res.idempotency_key,
    'account_id',v_res.owner_user_id,'task_id',v_res.task_id,'reserved_credits',v_res.reserved_credits,'state','pending_reconciliation','policy_version',v_res.policy_version);
end;
$$;

revoke all on function public.credit_ledger_get_balance(uuid) from public, anon, authenticated;
grant execute on function public.credit_ledger_get_balance(uuid) to service_role;

revoke all on function public.credit_ledger_reconcile_projection(jsonb) from public, anon, authenticated;
grant execute on function public.credit_ledger_reconcile_projection(jsonb) to service_role;

revoke all on function public.credit_ledger_grant(jsonb), public.credit_ledger_reserve(jsonb),
  public.credit_ledger_settle(jsonb), public.credit_ledger_release(jsonb),
  public.credit_ledger_reverse(jsonb), public.credit_ledger_mark_pending(jsonb) from public, anon, authenticated;
grant execute on function public.credit_ledger_grant(jsonb), public.credit_ledger_reserve(jsonb),
  public.credit_ledger_settle(jsonb), public.credit_ledger_release(jsonb),
  public.credit_ledger_reverse(jsonb), public.credit_ledger_mark_pending(jsonb) to service_role;

comment on table public.credit_ledger_entries is 'Append-only AI Credit accounting entries; source of truth for credit movements.';
comment on table public.credit_balance_projection is 'Derived available balance; updated in the same transaction as ledger entries.';
comment on table public.credit_policy_versions is 'Versioned financial policy configuration; values are entered and approved in the Financial phase.';


-- Approved policy versions are immutable. A published policy may only be retired;
-- a retired version can never be reactivated or edited in place.
create or replace function public.guard_credit_policy_version_mutation()
returns trigger language plpgsql set search_path = ''
as $$
begin
  if tg_op = 'DELETE' then
    raise exception 'CREDIT_POLICY_VERSIONS_ARE_IMMUTABLE' using errcode = '55000';
  end if;
  if old.status in ('approved','retired') then
    if new.policy_version <> old.policy_version
      or new.credit_scheme_version <> old.credit_scheme_version
      or new.approval_reference <> old.approval_reference
      or new.configuration <> old.configuration
      or new.created_by is distinct from old.created_by
      or new.approved_by is distinct from old.approved_by
      or new.approved_at is distinct from old.approved_at
      or new.effective_at is distinct from old.effective_at
      or new.expires_at is distinct from old.expires_at
      or (old.status = 'retired' and new.status <> 'retired')
      or (old.status = 'approved' and new.status not in ('approved','retired')) then
      raise exception 'CREDIT_POLICY_VERSIONS_ARE_IMMUTABLE' using errcode = '55000';
    end if;
  end if;
  return new;
end;
$$;
create trigger credit_policy_versions_immutable
before update or delete on public.credit_policy_versions
for each row execute function public.guard_credit_policy_version_mutation();

create or replace function public.reject_credit_ledger_mutation()
returns trigger language plpgsql set search_path = ''
as $$
begin
  raise exception 'CREDIT_LEDGER_IS_APPEND_ONLY' using errcode = '55000';
end;
$$;
create trigger credit_ledger_entries_append_only
before update or delete on public.credit_ledger_entries
for each row execute function public.reject_credit_ledger_mutation();

revoke all on function public.guard_credit_policy_version_mutation(), public.reject_credit_ledger_mutation()
  from public, anon, authenticated, service_role;
),
  created_at timestamptz not null default now(),
  unique (owner_user_id, idempotency_key)
);

alter table public.credit_policy_versions enable row level security;
alter table public.credit_ledger_accounts enable row level security;
alter table public.credit_ledger_entries enable row level security;
alter table public.credit_reservations enable row level security;
alter table public.credit_balance_projection enable row level security;
alter table public.credit_reconciliation_events enable row level security;
revoke all on table public.credit_policy_versions, public.credit_ledger_accounts,
  public.credit_ledger_entries, public.credit_reservations,
  public.credit_balance_projection, public.credit_reconciliation_events
  from public, anon, authenticated, service_role;

-- The API uses service-role credentials only server-side after deriving owner_user_id
-- from verified Supabase Auth. No client role can call these mutation RPCs or write tables.

create or replace function public.credit_ledger_get_balance(p_owner_user_id uuid)
returns jsonb language plpgsql security definer set search_path = ''
as $$
declare
  v_available bigint;
  v_reserved bigint;
  v_count bigint;
begin
  if p_owner_user_id is null then
    raise exception 'CREDIT_ACCOUNT_REQUIRED' using errcode = '22023';
  end if;
  select coalesce(available_credits,0), coalesce(ledger_entry_count,0)
    into v_available,v_count
    from public.credit_balance_projection where owner_user_id=p_owner_user_id;
  if not found then v_available := 0; v_count := 0; end if;
  select coalesce(sum(reserved_credits - settled_credits),0) into v_reserved
    from public.credit_reservations where owner_user_id=p_owner_user_id
      and state in ('reserved','pending_reconciliation');
  return jsonb_build_object(
    'available_credits',v_available,
    'reserved_credits',v_reserved,
    'ledger_entry_count',v_count,
    'as_of',now()
  );
end;
$$;

create or replace function public.credit_ledger_grant(p_command jsonb)
returns jsonb language plpgsql security definer set search_path = ''
as $$
declare
  v_owner uuid := (p_command->>'owner_user_id')::uuid;
  v_key text := p_command->>'idempotency_key';
  v_policy text := p_command->>'policy_version';
  v_approval text := p_command->>'policy_approval_reference';
  v_type text := p_command->>'entry_type';
  v_credits bigint := (p_command->>'credits')::bigint;
  v_fingerprint text := encode(extensions.digest(p_command::text, 'sha256'), 'hex');
  v_existing public.credit_ledger_entries;
  v_policy_row public.credit_policy_versions;
  v_entry public.credit_ledger_entries;
begin
  if v_owner is null or v_key is null or length(v_key) not between 1 and 256
    or v_credits is null or v_credits <= 0
    or v_type not in ('grant','promotional_grant')
    or coalesce(p_command->>'source_event_id','') = ''
    or coalesce(p_command->>'capability_id','') = '' then
    raise exception 'INVALID_CREDIT_GRANT' using errcode = '22023';
  end if;
  select * into v_policy_row from public.credit_policy_versions
    where policy_version = v_policy and approval_reference = v_approval
      and status = 'approved' and (effective_at is null or effective_at <= now())
      and (expires_at is null or expires_at > now()) for share;
  if not found or not coalesce((v_policy_row.configuration->>'allow_grants')::boolean, false)
    or not coalesce((v_policy_row.configuration->'allowed_grant_types') ? v_type, false) then
    raise exception 'CREDIT_POLICY_NOT_APPROVED_FOR_GRANT' using errcode = '42501';
  end if;
  insert into public.credit_ledger_accounts(owner_user_id) values (v_owner) on conflict do nothing;
  perform 1 from public.credit_ledger_accounts where owner_user_id = v_owner for update;
  select * into v_existing from public.credit_ledger_entries
    where owner_user_id = v_owner and idempotency_key = v_key;
  if found then
    if v_existing.payload_fingerprint <> v_fingerprint then
      raise exception 'CREDIT_LEDGER_IDEMPOTENCY_CONFLICT' using errcode = '23505';
    end if;
    return jsonb_build_object('entry_id',v_existing.id,'idempotent_replay',true);
  end if;
  insert into public.credit_balance_projection(owner_user_id) values (v_owner) on conflict do nothing;
  insert into public.credit_ledger_entries(
    owner_user_id,idempotency_key,entry_type,credits,balance_delta,credit_scheme_version,
    policy_version,capability_id,source_event_id,payload_fingerprint,metadata
  ) values (
    v_owner,v_key,v_type,v_credits,v_credits,v_policy_row.credit_scheme_version,
    v_policy,coalesce(p_command->>'capability_id','account_grant'),
    p_command->>'source_event_id',v_fingerprint,
    coalesce(p_command->'metadata','{}'::jsonb)
  ) returning * into v_entry;
  update public.credit_balance_projection set available_credits = available_credits + v_credits,
    ledger_entry_count = ledger_entry_count + 1, updated_at = now() where owner_user_id = v_owner;
  return jsonb_build_object('entry_id',v_entry.id,'idempotent_replay',false);
end;
$$;

create or replace function public.credit_ledger_reserve(p_command jsonb)
returns jsonb language plpgsql security definer set search_path = ''
as $$
declare
  v_owner uuid := (p_command->>'owner_user_id')::uuid;
  v_key text := p_command->>'idempotency_key';
  v_policy text := p_command->>'policy_version';
  v_approval text := p_command->>'policy_approval_reference';
  v_capability text := p_command->>'capability_id';
  v_tariff text := p_command->>'tariff_version';
  v_units bigint := (p_command->>'estimated_usage_units')::bigint;
  v_usage_unit text := p_command->>'usage_unit';
  v_estimated_cost bigint := (p_command->>'estimated_cost_microunits')::bigint;
  v_cost_unit text := p_command->>'cost_unit';
  v_credits bigint := (p_command->>'credits_to_reserve')::bigint;
  v_task text := p_command->>'task_id';
  v_fingerprint text := encode(extensions.digest(p_command::text, 'sha256'), 'hex');
  v_existing public.credit_ledger_entries;
  v_policy_row public.credit_policy_versions;
  v_cap jsonb;
  v_entitlement jsonb;
  v_active_reservations bigint;
  v_available bigint;
  v_entry public.credit_ledger_entries;
  v_res public.credit_reservations;
begin
  if v_owner is null or v_key is null or length(v_key) not between 1 and 256
    or v_credits is null or v_credits <= 0 or v_units is null or v_units <= 0
    or coalesce(v_capability,'') = '' or coalesce(v_task,'') = ''
    or coalesce(v_usage_unit,'') = '' or v_estimated_cost is null
    or v_estimated_cost < 0 or coalesce(v_cost_unit,'') = '' then
    raise exception 'INVALID_CREDIT_RESERVATION' using errcode = '22023';
  end if;
  select * into v_policy_row from public.credit_policy_versions
    where policy_version = v_policy and approval_reference = v_approval
      and status = 'approved' and (effective_at is null or effective_at <= now())
      and (expires_at is null or expires_at > now()) for share;
  if not found then raise exception 'CREDIT_POLICY_NOT_APPROVED' using errcode = '42501'; end if;
  if p_command->>'credit_scheme_version' <> v_policy_row.credit_scheme_version
    or coalesce(p_command->>'entitlement_version','') = '' then
    raise exception 'CREDIT_RESERVATION_VERSION_MISMATCH' using errcode = '22023';
  end if;
  v_cap := v_policy_row.configuration->'capabilities'->v_capability;
  v_entitlement := v_policy_row.configuration->'entitlements'->(p_command->>'entitlement_version');
  if jsonb_typeof(v_cap) <> 'object' or v_cap->>'tariff_version' <> v_tariff
    or v_cap->>'usage_unit' <> v_usage_unit
    or coalesce((v_cap->>'credits_per_usage_unit')::bigint,0) <= 0 then
    raise exception 'CREDIT_CAPABILITY_TARIFF_UNAVAILABLE' using errcode = '42501';
  end if;
  if jsonb_typeof(v_entitlement) <> 'object'
    or coalesce((v_entitlement->>'max_credits_per_request')::bigint,0) <= 0
    or coalesce((v_entitlement->>'max_concurrent_reservations')::bigint,0) <= 0
    or v_credits > (v_entitlement->>'max_credits_per_request')::bigint then
    raise exception 'CREDIT_ENTITLEMENT_LIMITS_NOT_CONFIGURED' using errcode = '42501';
  end if;
  if not (v_cap ? 'max_cost_microunits')
    or coalesce(v_cap->>'cost_unit','') <> v_cost_unit
    or coalesce(v_cap->>'cost_pricing_version','') = ''
    or coalesce((v_cap->>'max_cost_microunits')::bigint,-1) < 0
    or v_estimated_cost > (v_cap->>'max_cost_microunits')::bigint then
    raise exception 'CREDIT_COST_GUARDRAIL_NOT_CONFIGURED_OR_EXCEEDED' using errcode = '42501';
  end if;
  if v_credits <> v_units * (v_cap->>'credits_per_usage_unit')::bigint then
    raise exception 'CREDIT_RESERVATION_ESTIMATE_MISMATCH' using errcode = '22023';
  end if;
  insert into public.credit_ledger_accounts(owner_user_id) values (v_owner) on conflict do nothing;
  perform 1 from public.credit_ledger_accounts where owner_user_id = v_owner for update;
  select * into v_existing from public.credit_ledger_entries where owner_user_id = v_owner and idempotency_key = v_key;
  if found then
    if v_existing.payload_fingerprint <> v_fingerprint or v_existing.entry_type <> 'reservation' then
      raise exception 'CREDIT_LEDGER_IDEMPOTENCY_CONFLICT' using errcode = '23505';
    end if;
    select * into v_res from public.credit_reservations where reservation_entry_id = v_existing.id;
    return jsonb_build_object('reservation_id',v_res.id,'idempotency_key',v_res.idempotency_key,
      'account_id',v_owner,'task_id',v_res.task_id,'reserved_credits',v_res.reserved_credits,'state',v_res.state,'policy_version',v_res.policy_version);
  end if;
  insert into public.credit_balance_projection(owner_user_id) values (v_owner) on conflict do nothing;
  select available_credits into v_available from public.credit_balance_projection where owner_user_id = v_owner for update;
  select count(*) into v_active_reservations from public.credit_reservations
    where owner_user_id=v_owner and state in ('reserved','pending_reconciliation');
  if v_active_reservations >= (v_entitlement->>'max_concurrent_reservations')::bigint then
    raise exception 'CREDIT_CONCURRENT_RESERVATION_LIMIT' using errcode = '23514';
  end if;
  if v_available < v_credits then raise exception 'INSUFFICIENT_AI_CREDITS' using errcode = '23514'; end if;
  insert into public.credit_ledger_entries(
    owner_user_id,idempotency_key,entry_type,credits,balance_delta,credit_scheme_version,
    policy_version,tariff_version,entitlement_version,capability_id,task_id,source_event_id,
    payload_fingerprint,metadata
  ) values (
    v_owner,v_key,'reservation',v_credits,-v_credits,v_policy_row.credit_scheme_version,
    v_policy,v_tariff,p_command->>'entitlement_version',v_capability,v_task,v_task,
    v_fingerprint,'{}'::jsonb
  ) returning * into v_entry;
  insert into public.credit_reservations(
    owner_user_id,reservation_entry_id,idempotency_key,task_id,capability_id,reserved_credits,
    estimated_usage_units,usage_unit,credit_scheme_version,tariff_version,entitlement_version,
    policy_version,policy_approval_reference,state
  ) values (
    v_owner,v_entry.id,v_key,v_task,v_capability,v_credits,v_units,v_usage_unit,
    v_policy_row.credit_scheme_version,v_tariff,p_command->>'entitlement_version',v_policy,v_approval,'reserved'
  ) returning * into v_res;
  update public.credit_balance_projection set available_credits = available_credits - v_credits,
    ledger_entry_count = ledger_entry_count + 1, updated_at = now() where owner_user_id = v_owner;
  return jsonb_build_object('reservation_id',v_res.id,'idempotency_key',v_res.idempotency_key,
    'account_id',v_owner,'task_id',v_res.task_id,'reserved_credits',v_res.reserved_credits,'state',v_res.state,'policy_version',v_res.policy_version);
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
      'account_id',v_res.owner_user_id,'task_id',v_res.task_id,'reserved_credits',v_res.reserved_credits,'state','settled','policy_version',v_res.policy_version);
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
    where idempotency_key=v_source and owner_id=v_res.owner_user_id::text
      and task_id=v_res.task_id;
  if not found then raise exception 'CREDIT_SETTLEMENT_METERING_NOT_FOUND' using errcode = '23503'; end if;
  if v_metering.usage_units <> v_actual_units or v_metering.usage_unit <> v_usage_unit then
    raise exception 'CREDIT_SETTLEMENT_METERING_USAGE_MISMATCH' using errcode = '22023';
  end if;
  if v_metering.cost_unit <> v_cap->>'cost_unit'
    or v_metering.pricing_version <> v_cap->>'cost_pricing_version'
    or not (v_cap ? 'max_cost_microunits')
    or coalesce((v_cap->>'max_cost_microunits')::bigint,-1) < 0
    or v_metering.cost_microunits > (v_cap->>'max_cost_microunits')::bigint then
    raise exception 'CREDIT_ACTUAL_COST_GUARDRAIL_EXCEEDED_OR_MISMATCH' using errcode = '23514';
  end if;
  if jsonb_typeof(v_cap) <> 'object'
    or v_cap->>'tariff_version' <> v_res.tariff_version
    or v_cap->>'usage_unit' <> v_usage_unit

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
    related_entry_id,payload_fingerprint
  ) values (
    v_res.owner_user_id,v_key,'settlement',v_actual,0,v_res.credit_scheme_version,
    v_policy,v_res.tariff_version,v_res.entitlement_version,v_res.capability_id,v_res.task_id,
    v_source,v_res.reservation_entry_id,v_fp
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
    'account_id',v_res.owner_user_id,'task_id',v_res.task_id,'reserved_credits',v_res.reserved_credits,'state','settled','policy_version',v_res.policy_version);
end;
$$;

create or replace function public.credit_ledger_release(p_command jsonb)
returns jsonb language plpgsql security definer set search_path = ''
as $$
declare
  v_res_id uuid := (p_command->>'reservation_id')::uuid;
  v_key text := p_command->>'idempotency_key';
  v_policy text := p_command->>'policy_version';
  v_reason text := p_command->>'reason_code';
  v_fp text := encode(extensions.digest(p_command::text, 'sha256'), 'hex');
  v_res public.credit_reservations;
  v_existing public.credit_ledger_entries;
  v_amount bigint;
begin
  if v_res_id is null or coalesce(v_key,'') = '' or coalesce(v_reason,'') = '' then
    raise exception 'INVALID_CREDIT_RELEASE' using errcode = '22023';
  end if;
  select * into v_res from public.credit_reservations where id=v_res_id for update;
  if not found then raise exception 'CREDIT_RESERVATION_NOT_FOUND' using errcode = 'P0002'; end if;
  perform 1 from public.credit_ledger_accounts where owner_user_id=v_res.owner_user_id for update;
  select * into v_existing from public.credit_ledger_entries where owner_user_id=v_res.owner_user_id and idempotency_key=v_key;
  if found then
    if v_existing.payload_fingerprint <> v_fp or v_existing.entry_type <> 'release' then
      raise exception 'CREDIT_LEDGER_IDEMPOTENCY_CONFLICT' using errcode = '23505';
    end if;
    return jsonb_build_object('reservation_id',v_res.id,'idempotency_key',v_key,
      'account_id',v_res.owner_user_id,'task_id',v_res.task_id,'reserved_credits',v_res.reserved_credits,'state',v_res.state,'policy_version',v_res.policy_version);
  end if;
  if v_res.state not in ('reserved','pending_reconciliation') or v_policy <> v_res.policy_version then
    raise exception 'CREDIT_RESERVATION_NOT_RELEASABLE' using errcode = '23514';
  end if;
  if not exists (
    select 1 from public.credit_policy_versions p
    where p.policy_version=v_res.policy_version
      and p.approval_reference=v_res.policy_approval_reference
      and p.status in ('approved','retired')
      and coalesce((p.configuration->>'allow_definitive_failure_release')::boolean,false)
  ) then
    raise exception 'CREDIT_FAILURE_RELEASE_NOT_APPROVED' using errcode = '42501';
  end if;
  v_amount := v_res.reserved_credits - v_res.settled_credits;
  if v_amount <= 0 then raise exception 'CREDIT_RESERVATION_HAS_NO_REMAINDER' using errcode = '23514'; end if;
  insert into public.credit_ledger_entries(
    owner_user_id,idempotency_key,entry_type,credits,balance_delta,credit_scheme_version,
    policy_version,tariff_version,entitlement_version,capability_id,task_id,source_event_id,
    related_entry_id,payload_fingerprint,metadata
  ) values (
    v_res.owner_user_id,v_key,'release',v_amount,v_amount,v_res.credit_scheme_version,
    v_policy,v_res.tariff_version,v_res.entitlement_version,v_res.capability_id,v_res.task_id,
    coalesce(v_res.source_event_id,v_res.task_id),v_res.reservation_entry_id,v_fp,
    jsonb_build_object('reason_code',v_reason)
  );
  update public.credit_reservations set state='released',updated_at=now() where id=v_res.id;
  update public.credit_balance_projection set available_credits=available_credits+v_amount,
    ledger_entry_count=ledger_entry_count+1,updated_at=now() where owner_user_id=v_res.owner_user_id;
  return jsonb_build_object('reservation_id',v_res.id,'idempotency_key',v_key,
    'account_id',v_res.owner_user_id,'task_id',v_res.task_id,'reserved_credits',v_res.reserved_credits,'state','released','policy_version',v_res.policy_version);
end;
$$;



create or replace function public.credit_ledger_reverse(p_command jsonb)
returns jsonb language plpgsql security definer set search_path = ''
as $$
declare
  v_owner uuid := (p_command->>'owner_user_id')::uuid;
  v_original_id uuid := (p_command->>'original_entry_id')::uuid;
  v_key text := p_command->>'idempotency_key';
  v_policy text := p_command->>'policy_version';
  v_approval text := p_command->>'policy_approval_reference';
  v_reason text := p_command->>'reason_code';
  v_credits bigint := (p_command->>'credits')::bigint;
  v_fp text := encode(extensions.digest(p_command::text,'sha256'),'hex');
  v_original public.credit_ledger_entries;
  v_policy_row public.credit_policy_versions;
  v_existing public.credit_ledger_entries;
  v_entry public.credit_ledger_entries;
  v_reversed bigint;
begin
  if v_owner is null or v_original_id is null or coalesce(v_key,'') = ''
    or coalesce(v_reason,'') = '' or coalesce(p_command->>'source_event_id','') = ''
    or coalesce(p_command->>'entry_type','reversal') not in ('refund','reversal')
    or v_credits is null or v_credits <= 0 then
    raise exception 'INVALID_CREDIT_REVERSAL' using errcode = '22023';
  end if;
  select * into v_policy_row from public.credit_policy_versions
    where policy_version=v_policy and approval_reference=v_approval
      and status='approved' and (effective_at is null or effective_at <= now())
      and (expires_at is null or expires_at > now()) for share;
  if not found or not coalesce((v_policy_row.configuration->>'allow_refunds')::boolean,false) then
    raise exception 'CREDIT_REFUND_POLICY_NOT_APPROVED' using errcode = '42501';
  end if;
  insert into public.credit_ledger_accounts(owner_user_id) values(v_owner) on conflict do nothing;
  perform 1 from public.credit_ledger_accounts where owner_user_id=v_owner for update;
  select * into v_existing from public.credit_ledger_entries where owner_user_id=v_owner and idempotency_key=v_key;
  if found then
    if v_existing.payload_fingerprint <> v_fp or v_existing.entry_type not in ('refund','reversal') then
      raise exception 'CREDIT_LEDGER_IDEMPOTENCY_CONFLICT' using errcode = '23505';
    end if;
    return jsonb_build_object('entry_id',v_existing.id,'idempotent_replay',true);
  end if;
  select * into v_original from public.credit_ledger_entries
    where id=v_original_id and owner_user_id=v_owner for update;
  if not found or v_original.entry_type <> 'settlement' then
    raise exception 'CREDIT_REVERSAL_SOURCE_NOT_REVERSIBLE' using errcode = '22023';
  end if;
  select coalesce(sum(credits),0) into v_reversed from public.credit_ledger_entries
    where owner_user_id=v_owner and related_entry_id=v_original.id and entry_type in ('refund','reversal');
  if not (v_policy_row.configuration ? 'max_reversal_credits')
    or coalesce((v_policy_row.configuration->>'max_reversal_credits')::bigint,0) <= 0
    or v_credits + v_reversed > v_original.credits
    or v_credits > (v_policy_row.configuration->>'max_reversal_credits')::bigint then
    raise exception 'CREDIT_REVERSAL_LIMIT_EXCEEDED' using errcode = '23514';
  end if;
  insert into public.credit_balance_projection(owner_user_id) values(v_owner) on conflict do nothing;
  insert into public.credit_ledger_entries(
    owner_user_id,idempotency_key,entry_type,credits,balance_delta,credit_scheme_version,
    policy_version,tariff_version,entitlement_version,capability_id,task_id,source_event_id,
    related_entry_id,payload_fingerprint,metadata
  ) values (
    v_owner,v_key,coalesce(nullif(p_command->>'entry_type',''),'reversal'),v_credits,v_credits,
    v_original.credit_scheme_version,v_policy,v_original.tariff_version,v_original.entitlement_version,
    v_original.capability_id,v_original.task_id,p_command->>'source_event_id',v_original.id,v_fp,
    jsonb_build_object('reason_code',v_reason)
  ) returning * into v_entry;
  update public.credit_balance_projection set available_credits=available_credits+v_credits,
    ledger_entry_count=ledger_entry_count+1,updated_at=now() where owner_user_id=v_owner;
  insert into public.credit_reconciliation_events(
    owner_user_id,event_type,reason_code,idempotency_key,actor_type,actor_id,
    details
  ) values (
    v_owner,case when v_entry.entry_type='refund' then 'settlement' else 'manual_review' end,
    v_reason,'reverse:'||v_key,coalesce(p_command->>'actor_type','operator'),
    nullif(p_command->>'actor_id','')::uuid,
    jsonb_build_object('original_entry_id',v_original.id,'compensating_entry_id',v_entry.id,'credits',v_credits)
  );
  return jsonb_build_object('entry_id',v_entry.id,'idempotent_replay',false);
end;
$$;

create or replace function public.credit_ledger_mark_pending(p_command jsonb)
returns jsonb language plpgsql security definer set search_path = ''
as $$
declare
  v_res_id uuid := (p_command->>'reservation_id')::uuid;
  v_reason text := coalesce(p_command->>'reason_code','provider_outcome_unknown');
  v_res public.credit_reservations;
begin
  if v_res_id is null then raise exception 'INVALID_CREDIT_RESERVATION_ID' using errcode = '22023'; end if;
  select * into v_res from public.credit_reservations where id=v_res_id for update;
  if not found then raise exception 'CREDIT_RESERVATION_NOT_FOUND' using errcode = 'P0002'; end if;
  if v_res.state in ('settled','released') then
    raise exception 'CREDIT_RESERVATION_ALREADY_TERMINAL' using errcode = '23514';
  end if;
  if v_res.state <> 'pending_reconciliation' then
    update public.credit_reservations set state='pending_reconciliation',updated_at=now() where id=v_res.id;
    insert into public.credit_reconciliation_events(
      owner_user_id,reservation_id,event_type,reason_code,idempotency_key,actor_type
    ) values (v_res.owner_user_id,v_res.id,'outcome_unknown',v_reason,'pending:'||v_res.id::text,'system')
    on conflict (owner_user_id,idempotency_key) do nothing;
  end if;
  return jsonb_build_object('reservation_id',v_res.id,'idempotency_key',v_res.idempotency_key,
    'account_id',v_res.owner_user_id,'task_id',v_res.task_id,'reserved_credits',v_res.reserved_credits,'state','pending_reconciliation','policy_version',v_res.policy_version);
end;
$$;

revoke all on function public.credit_ledger_get_balance(uuid) from public, anon, authenticated;
grant execute on function public.credit_ledger_get_balance(uuid) to service_role;

revoke all on function public.credit_ledger_grant(jsonb), public.credit_ledger_reserve(jsonb),
  public.credit_ledger_settle(jsonb), public.credit_ledger_release(jsonb),
  public.credit_ledger_reverse(jsonb), public.credit_ledger_mark_pending(jsonb) from public, anon, authenticated;
grant execute on function public.credit_ledger_grant(jsonb), public.credit_ledger_reserve(jsonb),
  public.credit_ledger_settle(jsonb), public.credit_ledger_release(jsonb),
  public.credit_ledger_reverse(jsonb), public.credit_ledger_mark_pending(jsonb) to service_role;

comment on table public.credit_ledger_entries is 'Append-only AI Credit accounting entries; source of truth for credit movements.';
comment on table public.credit_balance_projection is 'Derived available balance; updated in the same transaction as ledger entries.';
comment on table public.credit_policy_versions is 'Versioned financial policy configuration; values are entered and approved in the Financial phase.';


-- Approved policy versions are immutable. A published policy may only be retired;
-- a retired version can never be reactivated or edited in place.
create or replace function public.guard_credit_policy_version_mutation()
returns trigger language plpgsql set search_path = ''
as $$
begin
  if tg_op = 'DELETE' then
    raise exception 'CREDIT_POLICY_VERSIONS_ARE_IMMUTABLE' using errcode = '55000';
  end if;
  if old.status in ('approved','retired') then
    if new.policy_version <> old.policy_version
      or new.credit_scheme_version <> old.credit_scheme_version
      or new.approval_reference <> old.approval_reference
      or new.configuration <> old.configuration
      or new.created_by is distinct from old.created_by
      or new.approved_by is distinct from old.approved_by
      or new.approved_at is distinct from old.approved_at
      or new.effective_at is distinct from old.effective_at
      or new.expires_at is distinct from old.expires_at
      or (old.status = 'retired' and new.status <> 'retired')
      or (old.status = 'approved' and new.status not in ('approved','retired')) then
      raise exception 'CREDIT_POLICY_VERSIONS_ARE_IMMUTABLE' using errcode = '55000';
    end if;
  end if;
  return new;
end;
$$;
create trigger credit_policy_versions_immutable
before update or delete on public.credit_policy_versions
for each row execute function public.guard_credit_policy_version_mutation();

create or replace function public.reject_credit_ledger_mutation()
returns trigger language plpgsql set search_path = ''
as $$
begin
  raise exception 'CREDIT_LEDGER_IS_APPEND_ONLY' using errcode = '55000';
end;
$$;
create trigger credit_ledger_entries_append_only
before update or delete on public.credit_ledger_entries
for each row execute function public.reject_credit_ledger_mutation();

revoke all on function public.guard_credit_policy_version_mutation(), public.reject_credit_ledger_mutation()
  from public, anon, authenticated, service_role;

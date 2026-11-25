-- ENG-P09: persist exact input/output token counts for text-generation usage.
-- Forward-only, source-only until the ADR-0024 recovery gate and isolated non-production
-- migration/concurrency validation are complete. No production DDL is performed here.
begin;

alter table public.agent_model_usage_metering
  add column if not exists input_tokens bigint,
  add column if not exists output_tokens bigint;

alter table public.agent_model_usage_metering
  drop constraint if exists agent_model_usage_metering_input_tokens_nonnegative;
alter table public.agent_model_usage_metering
  add constraint agent_model_usage_metering_input_tokens_nonnegative
  check (input_tokens is null or input_tokens >= 0);

alter table public.agent_model_usage_metering
  drop constraint if exists agent_model_usage_metering_output_tokens_nonnegative;
alter table public.agent_model_usage_metering
  add constraint agent_model_usage_metering_output_tokens_nonnegative
  check (output_tokens is null or output_tokens >= 0);

create or replace function public.record_agent_model_usage_metering(p_record jsonb)
returns boolean
language plpgsql
security definer
set search_path = ''
as $function$
declare
  v_existing_fingerprint text;
  v_key text;
  v_capability text;
  v_billing_account_id text;
  v_input_tokens bigint;
  v_output_tokens bigint;
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

  v_capability := p_record->>'capability';
  if v_capability is null or v_capability not in ('text_generation','embedding','image_generation','video_generation','reranking') then
    raise exception 'INVALID_METERING_CAPABILITY' using errcode = '22023';
  end if;

  if coalesce(p_record->>'input_tokens','') <> ''
     and coalesce(p_record->>'input_tokens','') !~ '^[0-9]{1,18}$' then
    raise exception 'INVALID_METERING_INPUT_TOKENS' using errcode = '22023';
  end if;
  if coalesce(p_record->>'output_tokens','') <> ''
     and coalesce(p_record->>'output_tokens','') !~ '^[0-9]{1,18}$' then
    raise exception 'INVALID_METERING_OUTPUT_TOKENS' using errcode = '22023';
  end if;

  v_input_tokens := nullif(p_record->>'input_tokens','')::bigint;
  v_output_tokens := nullif(p_record->>'output_tokens','')::bigint;
  if v_capability = 'text_generation'
     and (v_input_tokens is null or v_output_tokens is null) then
    raise exception 'TEXT_GENERATION_TOKEN_USAGE_REQUIRED' using errcode = '22023';
  end if;

  v_billing_account_id := coalesce(nullif(p_record->>'billing_account_id',''), p_record->>'owner_id');
  if v_billing_account_id is null or length(v_billing_account_id) not between 1 and 128 then
    raise exception 'INVALID_METERING_BILLING_ACCOUNT' using errcode = '22023';
  end if;

  insert into public.agent_model_usage_metering (
    idempotency_key, task_id, trace_id, owner_id, billing_account_id,
    agent_id, source_id, source_version, sensitivity, capability,
    provider_id, model_id, model_version, usage_units, usage_unit,
    input_tokens, output_tokens, cost_microunits, cost_unit, pricing_version,
    completed_at, payload_fingerprint
  ) values (
    v_key,
    p_record->>'task_id',
    p_record->>'trace_id',
    p_record->>'owner_id',
    v_billing_account_id,
    p_record->>'agent_id',
    p_record->>'source_id',
    (p_record->>'source_version')::integer,
    p_record->>'sensitivity',
    v_capability,
    p_record->>'provider_id',
    p_record->>'model_id',
    p_record->>'model_version',
    (p_record->>'usage_units')::bigint,
    p_record->>'usage_unit',
    v_input_tokens,
    v_output_tokens,
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

  select payload_fingerprint into v_existing_fingerprint
  from public.agent_model_usage_metering
  where idempotency_key = v_key;

  if v_existing_fingerprint = p_record->>'payload_fingerprint' then
    return true;
  end if;

  raise exception 'METERING_IDEMPOTENCY_CONFLICT'
    using errcode = '23505';
end;
$function$;

create or replace function public.get_agent_model_usage_summary(
  p_since timestamptz default (now() - interval '30 days'),
  p_until timestamptz default now()
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $function$
declare
  v_result jsonb;
begin
  if p_since is null or p_until is null or p_since >= p_until
     or p_until - p_since > interval '90 days' then
    raise exception 'MODEL_USAGE_PERIOD_INVALID' using errcode='22023';
  end if;

  select jsonb_build_object(
    'since',p_since,
    'until',p_until,
    'totals',jsonb_build_object(
      'runs',count(*),
      'input_tokens',coalesce(sum(input_tokens),0),
      'output_tokens',coalesce(sum(output_tokens),0)
    ),
    'by_capability',coalesce((
      select jsonb_agg(jsonb_build_object(
        'capability',g.capability,
        'runs',g.runs,
        'usage_units',g.usage_units,
        'input_tokens',g.input_tokens,
        'output_tokens',g.output_tokens,
        'cost_microunits',g.cost_microunits,
        'cost_unit',g.cost_unit
      ) order by g.cost_microunits desc)
      from (
        select capability,count(*) as runs,sum(usage_units) as usage_units,
          coalesce(sum(input_tokens),0) as input_tokens,
          coalesce(sum(output_tokens),0) as output_tokens,
          sum(cost_microunits) as cost_microunits,cost_unit
        from public.agent_model_usage_metering
        where completed_at>=p_since and completed_at<p_until
        group by capability,cost_unit
      ) g
    ),'[]'::jsonb),
    'by_provider_model',coalesce((
      select jsonb_agg(jsonb_build_object(
        'capability',g.capability,
        'provider_id',g.provider_id,
        'model_id',g.model_id,
        'usage_unit',g.usage_unit,
        'runs',g.runs,
        'usage_units',g.usage_units,
        'input_tokens',g.input_tokens,
        'output_tokens',g.output_tokens,
        'cost_microunits',g.cost_microunits,
        'cost_unit',g.cost_unit,
        'pricing_version',g.pricing_version
      ) order by g.cost_microunits desc)
      from (
        select capability,provider_id,model_id,usage_unit,count(*) as runs,
          sum(usage_units) as usage_units,
          coalesce(sum(input_tokens),0) as input_tokens,
          coalesce(sum(output_tokens),0) as output_tokens,
          sum(cost_microunits) as cost_microunits,
          cost_unit,pricing_version
        from public.agent_model_usage_metering
        where completed_at>=p_since and completed_at<p_until
        group by capability,provider_id,model_id,usage_unit,cost_unit,pricing_version
      ) g
    ),'[]'::jsonb)
  ) into v_result
  from public.agent_model_usage_metering
  where completed_at>=p_since and completed_at<p_until;

  return v_result;
end;
$function$;

revoke all on function public.record_agent_model_usage_metering(jsonb)
  from public, anon, authenticated;
grant execute on function public.record_agent_model_usage_metering(jsonb)
  to service_role;

revoke all on function public.get_agent_model_usage_summary(timestamptz,timestamptz)
  from public, anon, authenticated;
grant execute on function public.get_agent_model_usage_summary(timestamptz,timestamptz)
  to service_role;

comment on column public.agent_model_usage_metering.input_tokens is
  'Provider-reported input/prompt token count; null only for capabilities that do not expose token detail.';
comment on column public.agent_model_usage_metering.output_tokens is
  'Provider-reported output/completion token count; null only for capabilities that do not expose token detail.';

commit;

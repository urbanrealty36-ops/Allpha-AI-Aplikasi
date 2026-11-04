-- ENG-P18: pin every Consumer grant to the approved capability, entitlement and pricing contract.
-- Additive and fail-closed. Existing rows without a complete snapshot are not resolvable.
alter table public.agent_consumer_grants
  add column if not exists capability_id text,
  add column if not exists credit_scheme_version text,
  add column if not exists approval_reference text,
  add column if not exists tariff_version text,
  add column if not exists entitlement_version text,
  add column if not exists max_usage_units bigint,
  add column if not exists max_cost_microunits bigint,
  add column if not exists cost_unit text,
  add column if not exists pricing_version text,
  add column if not exists payer_role text,
  add column if not exists allow_success_settlement boolean,
  add column if not exists allow_definitive_failure_release boolean,
  add column if not exists allow_partial_settlement boolean;

alter table public.agent_consumer_grants
  add constraint agent_consumer_grant_policy_snapshot_complete
  check (
    capability_id is not null and length(capability_id) between 1 and 128
    and credit_scheme_version is not null and length(credit_scheme_version) between 1 and 80
    and approval_reference is not null and length(approval_reference) between 1 and 160
    and tariff_version is not null and length(tariff_version) between 1 and 80
    and entitlement_version is not null and length(entitlement_version) between 1 and 80
    and max_usage_units is not null and max_usage_units > 0
    and max_cost_microunits is not null and max_cost_microunits >= 0
    and cost_unit is not null and length(cost_unit) between 1 and 80
    and pricing_version is not null and length(pricing_version) between 1 and 80
    and payer_role is not null and payer_role in ('consumer','agent_owner')
    and allow_success_settlement is not null
    and allow_definitive_failure_release is not null
    and allow_partial_settlement is not null
  ) not valid;

create index if not exists agent_consumer_grants_policy_snapshot_idx
  on public.agent_consumer_grants(
    requester_user_id, agent_id, skill_id, runtime_policy_version,
    capability_id, entitlement_version, tariff_version, status
  );

comment on constraint agent_consumer_grant_policy_snapshot_complete on public.agent_consumer_grants
  is 'New grants must pin the complete approved Consumer financial contract; legacy incomplete grants fail closed.';

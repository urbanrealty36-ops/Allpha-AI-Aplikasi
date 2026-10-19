-- ENG-P18 forward repair: PostgreSQL CHECK accepts UNKNOWN, so explicitly reject NULL payer roles.
alter table public.agent_consumer_grants
  drop constraint if exists agent_consumer_grant_policy_snapshot_complete;
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

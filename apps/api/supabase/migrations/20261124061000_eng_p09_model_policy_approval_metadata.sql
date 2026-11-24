-- ENG-P09: make model execution-policy approval explicit and auditable.
-- Pricing activation alone remains insufficient to enable a provider route.
alter table public.ai_model_cost_configs
  add column if not exists policy_version text not null default '1',
  add column if not exists policy_approval_reference text,
  add column if not exists policy_approved_by uuid references auth.users(id) on delete restrict,
  add column if not exists policy_approved_at timestamptz;

alter table public.ai_model_cost_configs
  drop constraint if exists ai_model_cost_policy_approval_consistency;
alter table public.ai_model_cost_configs
  add constraint ai_model_cost_policy_approval_consistency
  check (
    (policy_approved = true
      and policy_approval_reference is not null
      and char_length(policy_approval_reference) between 8 and 200
      and policy_approved_by is not null
      and policy_approved_at is not null)
    or
    (policy_approved = false
      and policy_approval_reference is null
      and policy_approved_by is null
      and policy_approved_at is null)
  );

alter table public.ai_model_cost_configs
  drop constraint if exists ai_model_cost_policy_requires_active;
alter table public.ai_model_cost_configs
  add constraint ai_model_cost_policy_requires_active
  check (policy_approved = false or status = 'active');

alter table public.ai_model_cost_configs
  drop constraint if exists ai_model_cost_policy_version_valid;
alter table public.ai_model_cost_configs
  add constraint ai_model_cost_policy_version_valid
  check (policy_version ~ '^[A-Za-z0-9][A-Za-z0-9._:-]{0,79}$');

create index if not exists ai_model_cost_approved_route_idx
  on public.ai_model_cost_configs(provider_id,model_id,model_version,policy_version)
  where status='active' and policy_approved=true;

comment on column public.ai_model_cost_configs.policy_approved is
  'Explicit model execution-policy approval; activating a tariff alone never enables a model route.';
comment on column public.ai_model_cost_configs.policy_approval_reference is
  'Auditable operator approval reference for the exact model/policy/pricing version.';

-- Operator usage dashboard: aggregate provider/model usage without exposing owner IDs.
create or replace function public.get_agent_model_usage_summary(
  p_since timestamptz default now() - interval '30 days',
  p_until timestamptz default now()
) returns jsonb
language plpgsql
security definer
set search_path = ''
as $usage$
declare
  v_result jsonb;
begin
  if p_since is null or p_until is null or p_since >= p_until
     or p_until - p_since > interval '90 days' then
    raise exception 'MODEL_USAGE_PERIOD_INVALID' using errcode='22023';
  end if;

  select jsonb_build_object(
    'since',p_since,'until',p_until,
    'totals',jsonb_build_object('runs',count(*)),
    'by_provider_model',coalesce((
      select jsonb_agg(jsonb_build_object(
        'provider_id',g.provider_id,'model_id',g.model_id,'usage_unit',g.usage_unit,
        'runs',g.runs,'usage_units',g.usage_units,'cost_microunits',g.cost_microunits,
        'cost_unit',g.cost_unit,'pricing_version',g.pricing_version
      ) order by g.cost_microunits desc)
      from (
        select provider_id,model_id,usage_unit,count(*) as runs,sum(usage_units) as usage_units,
          sum(cost_microunits) as cost_microunits,cost_unit,pricing_version
        from public.agent_model_usage_metering
        where completed_at>=p_since and completed_at<p_until
        group by provider_id,model_id,usage_unit,cost_unit,pricing_version
      ) g
    ),'[]'::jsonb)
  ) into v_result
  from public.agent_model_usage_metering
  where completed_at>=p_since and completed_at<p_until;
  return v_result;
end;
$usage$;

revoke all on function public.get_agent_model_usage_summary(timestamptz,timestamptz)
  from public,anon,authenticated,service_role;
grant execute on function public.get_agent_model_usage_summary(timestamptz,timestamptz)
  to service_role;

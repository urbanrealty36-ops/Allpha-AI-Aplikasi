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

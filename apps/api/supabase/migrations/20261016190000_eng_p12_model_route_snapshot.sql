-- ENG-P12: pin each executable challenge to an approved deployment-owned model route.
-- Source-only; validate in isolated non-production at ENG-P37.
alter table public.agent_skill_challenge_runs
  add column if not exists model_route_snapshot jsonb;

alter table public.agent_skill_challenge_runs
  add constraint agent_skill_challenge_model_route_snapshot_object
    check (model_route_snapshot is null or jsonb_typeof(model_route_snapshot) = 'object');

comment on column public.agent_skill_challenge_runs.model_route_snapshot is
  'Approved provider/model/version and cost/latency policy snapshot captured when the challenge is issued; execution rejects drift.';

-- ENG-P12: durable prior-version comparison and owner release decision.
-- Source-only; apply and validate only in the authorized ENG-P37 non-production target.
alter table public.agent_skill_challenge_runs
  add column if not exists previous_version_comparison jsonb,
  add column if not exists release_decision text,
  add column if not exists release_decision_reason text,
  add column if not exists release_decided_by uuid references auth.users(id) on delete restrict,
  add column if not exists release_decided_at timestamptz;

alter table public.agent_skill_challenge_runs
  add constraint agent_skill_challenge_previous_comparison_object
    check (previous_version_comparison is null or jsonb_typeof(previous_version_comparison) = 'object'),
  add constraint agent_skill_challenge_release_decision_valid
    check (release_decision is null or release_decision in ('release', 'hold')),
  add constraint agent_skill_challenge_release_decision_fields
    check (
      (release_decision is null and release_decision_reason is null and release_decided_by is null and release_decided_at is null)
      or
      (release_decision is not null and release_decision_reason is not null and release_decided_by is not null and release_decided_at is not null)
    );

comment on column public.agent_skill_challenge_runs.previous_version_comparison is
  'Owner-scoped comparison against a completed, runtime-evidenced challenge for the immediately previous Skill version.';
comment on column public.agent_skill_challenge_runs.release_decision is
  'Explicit owner decision for release evidence; does not publish or activate a Skill by itself.';

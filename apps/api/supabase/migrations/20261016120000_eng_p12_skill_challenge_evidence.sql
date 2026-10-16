-- ENG-P12: durable, owner-scoped Skill Challenge runs and achievement evidence.
-- Source-only migration: do not apply to production or staging before ENG-P37.
-- Reward settlement intentionally remains delegated to the canonical financial policy and ledger.

create table if not exists public.agent_skill_challenge_runs (
  id uuid primary key default gen_random_uuid(),
  owner_user_id uuid not null references auth.users(id) on delete cascade,
  agent_id uuid not null references public.ai_agents(id) on delete cascade,
  skill_id uuid not null references public.agent_skills(id) on delete cascade,
  agent_version integer not null check (agent_version > 0),
  skill_version integer not null check (skill_version > 0),
  skill_version_id uuid references public.agent_skill_versions(id) on delete set null,
  challenge_key text not null check (challenge_key ~ '^[a-z][a-z0-9_-]{2,79}$'),
  evaluation_set_version integer not null check (evaluation_set_version > 0),
  evaluation_set_digest text not null check (evaluation_set_digest ~ '^[a-f0-9]{64}$'),
  rubric_key text not null check (rubric_key ~ '^[a-z][a-z0-9_-]{2,59}$'),
  rubric_version integer not null check (rubric_version > 0),
  rubric_digest text not null check (rubric_digest ~ '^[a-f0-9]{64}$'),
  evaluator_version text not null check (char_length(evaluator_version) between 1 and 80),
  agent_snapshot jsonb not null check (jsonb_typeof(agent_snapshot) = 'object'),
  skill_snapshot jsonb not null check (jsonb_typeof(skill_snapshot) = 'object'),
  challenge_input jsonb not null check (jsonb_typeof(challenge_input) = 'object'),
  expected_output jsonb not null check (jsonb_typeof(expected_output) = 'object'),
  nonce_hash text not null check (nonce_hash ~ '^[a-f0-9]{64}$'),
  nonce_expires_at timestamptz not null,
  idempotency_key text not null check (char_length(idempotency_key) between 8 and 160),
  request_fingerprint text not null check (request_fingerprint ~ '^[a-f0-9]{64}$'),
  submission_fingerprint text check (submission_fingerprint is null or submission_fingerprint ~ '^[a-f0-9]{64}$'),
  submission_payload jsonb check (submission_payload is null or jsonb_typeof(submission_payload) = 'object'),
  evaluation_result jsonb check (evaluation_result is null or jsonb_typeof(evaluation_result) = 'object'),
  evidence_digest text check (evidence_digest is null or evidence_digest ~ '^[a-f0-9]{64} check (status in ('issued','evaluating','passed','failed','expired','rejected')),
  submitted_at timestamptz,
  completed_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (owner_user_id, idempotency_key),
  unique (id, owner_user_id),
  check ((status in ('passed','failed')) = (completed_at is not null)),
  check ((submission_payload is not null) = (submission_fingerprint is not null))
);
create index if not exists agent_skill_challenge_runs_owner_created_idx
  on public.agent_skill_challenge_runs(owner_user_id, created_at desc);
create index if not exists agent_skill_challenge_runs_skill_version_idx
  on public.agent_skill_challenge_runs(skill_id, skill_version, created_at desc);
create index if not exists agent_skill_challenge_runs_expiry_idx
  on public.agent_skill_challenge_runs(nonce_expires_at) where status = 'issued';

create table if not exists public.agent_skill_challenge_achievement_evidence (
  id uuid primary key default gen_random_uuid(),
  owner_user_id uuid not null references auth.users(id) on delete cascade,
  challenge_run_id uuid not null,
  achievement_key text not null check (achievement_key ~ '^[a-z][a-z0-9_-]{2,79}$'),
  evidence_digest text not null check (evidence_digest ~ '^[a-f0-9]{64}$'),
  awarded_at timestamptz not null default now(),
  unique (owner_user_id, challenge_run_id, achievement_key),
  foreign key (challenge_run_id, owner_user_id)
    references public.agent_skill_challenge_runs(id, owner_user_id) on delete cascade
);
create index if not exists agent_skill_challenge_achievement_owner_idx
  on public.agent_skill_challenge_achievement_evidence(owner_user_id, awarded_at desc);

alter table public.agent_skill_challenge_runs enable row level security;
alter table public.agent_skill_challenge_achievement_evidence enable row level security;
revoke all on public.agent_skill_challenge_runs, public.agent_skill_challenge_achievement_evidence from public, anon, authenticated;
grant select, insert, update, delete on public.agent_skill_challenge_runs, public.agent_skill_challenge_achievement_evidence to service_role;

comment on table public.agent_skill_challenge_runs is
  'Backend-only durable challenge runs pinning Agent/Skill/evaluation/rubric versions and replay-resistant evidence; clients access through FastAPI.';
comment on table public.agent_skill_challenge_achievement_evidence is
  'Non-monetary achievement evidence derived from completed passing challenge runs. This table is not a reward or credit ledger.';
),
  repeated_submission boolean not null default false,
  status text not null default 'issued' check (status in ('issued','evaluating','passed','failed','expired','rejected')),
  submitted_at timestamptz,
  completed_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (owner_user_id, idempotency_key),
  unique (id, owner_user_id),
  check ((status in ('passed','failed')) = (completed_at is not null)),
  check ((submission_payload is not null) = (submission_fingerprint is not null))
);
create index if not exists agent_skill_challenge_runs_owner_created_idx
  on public.agent_skill_challenge_runs(owner_user_id, created_at desc);
create index if not exists agent_skill_challenge_runs_skill_version_idx
  on public.agent_skill_challenge_runs(skill_id, skill_version, created_at desc);
create index if not exists agent_skill_challenge_runs_expiry_idx
  on public.agent_skill_challenge_runs(nonce_expires_at) where status = 'issued';

create table if not exists public.agent_skill_challenge_achievement_evidence (
  id uuid primary key default gen_random_uuid(),
  owner_user_id uuid not null references auth.users(id) on delete cascade,
  challenge_run_id uuid not null,
  achievement_key text not null check (achievement_key ~ '^[a-z][a-z0-9_-]{2,79}$'),
  evidence_digest text not null check (evidence_digest ~ '^[a-f0-9]{64}$'),
  awarded_at timestamptz not null default now(),
  unique (owner_user_id, challenge_run_id, achievement_key),
  foreign key (challenge_run_id, owner_user_id)
    references public.agent_skill_challenge_runs(id, owner_user_id) on delete cascade
);
create index if not exists agent_skill_challenge_achievement_owner_idx
  on public.agent_skill_challenge_achievement_evidence(owner_user_id, awarded_at desc);

alter table public.agent_skill_challenge_runs enable row level security;
alter table public.agent_skill_challenge_achievement_evidence enable row level security;
revoke all on public.agent_skill_challenge_runs, public.agent_skill_challenge_achievement_evidence from public, anon, authenticated;
grant select, insert, update, delete on public.agent_skill_challenge_runs, public.agent_skill_challenge_achievement_evidence to service_role;

comment on table public.agent_skill_challenge_runs is
  'Backend-only durable challenge runs pinning Agent/Skill/evaluation/rubric versions and replay-resistant evidence; clients access through FastAPI.';
comment on table public.agent_skill_challenge_achievement_evidence is
  'Non-monetary achievement evidence derived from completed passing challenge runs. This table is not a reward or credit ledger.';


-- Atomic per-owner issuance rate limit. This is a technical anti-abuse guard,
-- not an economic tariff or reward policy. API calls it with a bounded limit.
create table if not exists public.agent_skill_challenge_issue_windows (
  owner_user_id uuid not null references auth.users(id) on delete cascade,
  action_key text not null check (action_key in ('issue','submit')),
  window_started_at timestamptz not null,
  issue_count integer not null default 0 check (issue_count >= 0),
  updated_at timestamptz not null default now(),
  primary key (owner_user_id, action_key)
);
alter table public.agent_skill_challenge_issue_windows enable row level security;
revoke all on public.agent_skill_challenge_issue_windows from public, anon, authenticated;
grant select, insert, update, delete on public.agent_skill_challenge_issue_windows to service_role;

create or replace function public.reserve_agent_skill_challenge_action(
  p_owner_user_id uuid,
  p_action_key text,
  p_limit integer
) returns boolean
language plpgsql
security invoker
set search_path = ''
as $$
declare
  v_window timestamptz := date_trunc('minute', now());
  v_count integer;
begin
  if p_owner_user_id is null or p_action_key not in ('issue','submit') or p_limit < 1 or p_limit > 60 then
    return false;
  end if;
  insert into public.agent_skill_challenge_issue_windows(owner_user_id, action_key, window_started_at, issue_count, updated_at)
  values (p_owner_user_id, p_action_key, v_window, 1, now())
  on conflict (owner_user_id, action_key)
  do update set
    window_started_at = case
      when public.agent_skill_challenge_issue_windows.window_started_at < v_window then v_window
      else public.agent_skill_challenge_issue_windows.window_started_at
    end,
    issue_count = case
      when public.agent_skill_challenge_issue_windows.window_started_at < v_window then 1
      else public.agent_skill_challenge_issue_windows.issue_count + 1
    end,
    updated_at = now()
  where public.agent_skill_challenge_issue_windows.window_started_at < v_window
     or public.agent_skill_challenge_issue_windows.issue_count < p_limit
  returning issue_count into v_count;
  return v_count is not null;
end;
$$;
revoke all on function public.reserve_agent_skill_challenge_action(uuid, text, integer) from public, anon, authenticated;
grant execute on function public.reserve_agent_skill_challenge_action(uuid, text, integer) to service_role;

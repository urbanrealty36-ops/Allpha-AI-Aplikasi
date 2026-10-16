-- ENG-P12: bind Skill Challenge evaluation to a server-side Model Router execution.
-- Source-only. Do not apply against production; isolated SQL/RLS/concurrency validation remains ENG-P37.
alter table public.agent_skill_challenge_runs
  add column if not exists runtime_output jsonb,
  add column if not exists runtime_evidence jsonb,
  add column if not exists runtime_evidence_digest text,
  add column if not exists runtime_executed_at timestamptz;

alter table public.agent_skill_challenge_runs
  add constraint agent_skill_challenge_runtime_output_object
    check (runtime_output is null or jsonb_typeof(runtime_output) = 'object'),
  add constraint agent_skill_challenge_runtime_evidence_object
    check (runtime_evidence is null or jsonb_typeof(runtime_evidence) = 'object'),
  add constraint agent_skill_challenge_runtime_digest_format
    check (runtime_evidence_digest is null or runtime_evidence_digest ~ '^[a-f0-9]{64}$'),
  add constraint agent_skill_challenge_runtime_evidence_pair
    check (
      (runtime_output is null and runtime_evidence is null and runtime_evidence_digest is null and runtime_executed_at is null)
      or
      (runtime_output is not null and runtime_evidence is not null and runtime_evidence_digest is not null and runtime_executed_at is not null)
    );

comment on column public.agent_skill_challenge_runs.runtime_evidence is
  'Server-side, Model Router-produced usage/route evidence; never accepted from client submission.';
comment on column public.agent_skill_challenge_runs.runtime_output is
  'Structured output produced by the canonical server-side text-generation route, pinned to runtime evidence.';

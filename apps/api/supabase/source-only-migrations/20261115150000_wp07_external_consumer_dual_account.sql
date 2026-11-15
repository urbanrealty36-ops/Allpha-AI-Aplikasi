-- SOURCE ONLY — WP-07 external Agent consumer generation and dual-account settlement fields.
-- Depends on 20261019134319_eng_p18_agent_consumer_grants.sql and
-- 20261105130000_eng_p09_durable_generation_jobs.sql.
-- Do not apply to canonical production or staging during the current source-only work window.
begin;

alter table public.agent_consumer_grants
  drop constraint if exists agent_consumer_grant_scopes;
alter table public.agent_consumer_grants
  add constraint agent_consumer_grant_scopes check (
    cardinality(granted_scopes) > 0
    and granted_scopes <@ array['public_invoke','generation_invoke','knowledge_public_read']::text[]
    and (not ('knowledge_public_read' = any(granted_scopes))
      or 'generation_invoke' = any(granted_scopes))
  );

alter table public.generation_jobs
  add column if not exists agent_owner_user_id uuid references auth.users(id) on delete restrict,
  add column if not exists payer_user_id uuid references auth.users(id) on delete restrict,
  add column if not exists consumer_grant_id uuid references public.agent_consumer_grants(id) on delete restrict,
  add column if not exists agent_version integer check (agent_version is null or agent_version > 0),
  add column if not exists runtime_policy_version text,
  add column if not exists agent_snapshot jsonb not null default '{}'::jsonb
    check (jsonb_typeof(agent_snapshot)='object'),
  add column if not exists skill_snapshot jsonb not null default '{}'::jsonb
    check (jsonb_typeof(skill_snapshot)='object'),
  add column if not exists skill_instructions_sha256 text
    check (skill_instructions_sha256 is null or skill_instructions_sha256 ~ '^[0-9a-f]{64}    check (owner_reward_status in ('pending_policy','settled','not_eligible','reconciliation_required'));

update public.generation_jobs j
set agent_owner_user_id = coalesce(j.agent_owner_user_id, j.owner_user_id),
    payer_user_id = coalesce(j.payer_user_id, j.owner_user_id),
    agent_version = coalesce(j.agent_version, a.version)
from public.ai_agents a
where a.id = j.agent_id
  and (j.agent_owner_user_id is null or j.payer_user_id is null or j.agent_version is null);

alter table public.generation_jobs
  alter column agent_owner_user_id set not null,
  alter column payer_user_id set not null,
  alter column agent_version set not null;

alter table public.generation_jobs
  drop constraint if exists generation_jobs_external_policy_snapshot;
alter table public.generation_jobs
  add constraint generation_jobs_external_policy_snapshot
  check (consumer_grant_id is null or
    (agent_version is not null and runtime_policy_version is not null)) not valid;

create index if not exists generation_jobs_agent_owner_created_idx
  on public.generation_jobs(agent_owner_user_id, created_at desc);
create index if not exists generation_jobs_payer_created_idx
  on public.generation_jobs(payer_user_id, created_at desc);
create index if not exists generation_jobs_consumer_grant_idx
  on public.generation_jobs(consumer_grant_id, created_at desc)
  where consumer_grant_id is not null;

comment on column public.generation_jobs.owner_user_id is
  'Authenticated requester and private artifact recipient; not necessarily the Agent owner or credit payer.';
comment on column public.generation_jobs.agent_owner_user_id is
  'Canonical Human owner of the selected Agent, derived and verified by FastAPI and the generation RPC.';
comment on column public.generation_jobs.payer_user_id is
  'Credit account selected only from the approved consumer generation policy; never client supplied.';
comment on column public.generation_jobs.owner_reward_status is
  'Creator reward is pending until an approved generation_owner_reward policy permits an idempotent owner credit.';

commit;
),
  add column if not exists owner_reward_status text not null default 'pending_policy'
    check (owner_reward_status in ('pending_policy','settled','not_eligible','reconciliation_required'));

update public.generation_jobs j
set agent_owner_user_id = coalesce(j.agent_owner_user_id, j.owner_user_id),
    payer_user_id = coalesce(j.payer_user_id, j.owner_user_id),
    agent_version = coalesce(j.agent_version, a.version)
from public.ai_agents a
where a.id = j.agent_id
  and (j.agent_owner_user_id is null or j.payer_user_id is null or j.agent_version is null);

alter table public.generation_jobs
  alter column agent_owner_user_id set not null,
  alter column payer_user_id set not null,
  alter column agent_version set not null;

alter table public.generation_jobs
  drop constraint if exists generation_jobs_external_policy_snapshot;
alter table public.generation_jobs
  add constraint generation_jobs_external_policy_snapshot
  check (consumer_grant_id is null or
    (agent_version is not null and runtime_policy_version is not null)) not valid;

create index if not exists generation_jobs_agent_owner_created_idx
  on public.generation_jobs(agent_owner_user_id, created_at desc);
create index if not exists generation_jobs_payer_created_idx
  on public.generation_jobs(payer_user_id, created_at desc);
create index if not exists generation_jobs_consumer_grant_idx
  on public.generation_jobs(consumer_grant_id, created_at desc)
  where consumer_grant_id is not null;

comment on column public.generation_jobs.owner_user_id is
  'Authenticated requester and private artifact recipient; not necessarily the Agent owner or credit payer.';
comment on column public.generation_jobs.agent_owner_user_id is
  'Canonical Human owner of the selected Agent, derived and verified by FastAPI and the generation RPC.';
comment on column public.generation_jobs.payer_user_id is
  'Credit account selected only from the approved consumer generation policy; never client supplied.';
comment on column public.generation_jobs.owner_reward_status is
  'Creator reward is pending until an approved generation_owner_reward policy permits an idempotent owner credit.';

commit;

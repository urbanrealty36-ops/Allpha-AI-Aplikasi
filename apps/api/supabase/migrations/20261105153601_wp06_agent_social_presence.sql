-- WP-06: owner-governed Human + AI Agent social presence.
-- Additive only. Runtime approval is required before a co-authored draft can be submitted.
create table if not exists public.agent_social_presence_policies (
  id uuid primary key default gen_random_uuid(),
  owner_user_id uuid not null references auth.users(id) on delete cascade,
  agent_id uuid not null references public.ai_agents(id) on delete cascade,
  allowed_actions text[] not null default array['draft_post']::text[],
  approval_mode text not null default 'every_post'
    check (approval_mode in ('every_post','high_risk_only','disabled')),
  disclosure_text text not null default 'Dibuat bersama AI Agent',
  is_enabled boolean not null default true,
  version integer not null default 1 check (version > 0),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  revoked_at timestamptz,
  unique(owner_user_id, agent_id),
  check (cardinality(allowed_actions) <= 12),
  check (allowed_actions <@ array['draft_post','draft_comment','draft_reply','suggest_repost','draft_story']::text[])
);
create table if not exists public.agent_social_action_approvals (
  id uuid primary key default gen_random_uuid(),
  owner_user_id uuid not null references auth.users(id) on delete cascade,
  agent_id uuid not null references public.ai_agents(id) on delete cascade,
  content_id uuid not null references public.content_items(id) on delete cascade,
  runtime_task_id uuid not null references public.agent_runtime_tasks(id) on delete restrict,
  target_content_id uuid references public.content_items(id) on delete set null,
  action_type text not null check (action_type in ('draft_post','draft_comment','draft_reply','suggest_repost','draft_story')),
  content_version integer not null check (content_version > 0),
  status text not null default 'pending'
    check (status in ('pending','approved','rejected','revoked','superseded')),
  disclosure_snapshot text not null,
  idempotency_key text not null,
  requested_at timestamptz not null default now(),
  decided_at timestamptz,
  decided_by uuid references auth.users(id) on delete set null,
  decision_reason text,
  unique(owner_user_id,idempotency_key),
  unique(content_id,content_version),
  unique(runtime_task_id)
);
create index if not exists idx_agent_social_policy_owner on public.agent_social_presence_policies(owner_user_id,agent_id);
create index if not exists idx_agent_social_approval_runtime_task on public.agent_social_action_approvals(runtime_task_id);
create index if not exists idx_agent_social_approval_owner_status on public.agent_social_action_approvals(owner_user_id,status,requested_at desc);
create index if not exists idx_agent_social_approval_content on public.agent_social_action_approvals(content_id,content_version);
alter table public.agent_social_presence_policies enable row level security;
alter table public.agent_social_action_approvals enable row level security;
revoke all on public.agent_social_presence_policies from anon,authenticated;
revoke all on public.agent_social_action_approvals from anon,authenticated;
grant select,insert,update,delete on public.agent_social_presence_policies to service_role;
grant select,insert,update,delete on public.agent_social_action_approvals to service_role;


create table if not exists public.agent_social_audit_events (
 id uuid primary key default gen_random_uuid(), owner_user_id uuid not null references auth.users(id) on delete cascade,
 agent_id uuid not null references public.ai_agents(id) on delete cascade,
 approval_id uuid references public.agent_social_action_approvals(id) on delete set null,
 actor_user_id uuid references auth.users(id) on delete set null,
 event_type text not null check (event_type in ('policy_created','policy_updated','policy_disabled','draft_requested','approval_approved','approval_rejected','approval_revoked')),
 outcome text not null check (outcome in ('allowed','denied','error')), metadata jsonb not null default '{}'::jsonb, created_at timestamptz not null default now()
);
create index if not exists idx_agent_social_audit_owner_created on public.agent_social_audit_events(owner_user_id,created_at desc);
create index if not exists idx_agent_social_audit_agent_created on public.agent_social_audit_events(agent_id,created_at desc);
alter table public.agent_social_audit_events enable row level security;
revoke all on public.agent_social_audit_events from anon,authenticated;
grant select,insert on public.agent_social_audit_events to service_role;

-- ENG-P05/P06/P34: official Allpha bot control-plane registry.
-- Source-only. Do not apply to canonical production; validate through approved ENG-P37 staging.
-- This is an operator-controlled roster overlay, not a duplicate Agent identity or runtime.

create table if not exists public.official_agent_bots (
  id uuid primary key default gen_random_uuid(),
  skill_key text not null unique check (skill_key ~ '^[a-z0-9][a-z0-9._-]{2,120}$'),
  display_name text not null check (char_length(display_name) between 2 and 160),
  category_key text not null check (char_length(category_key) between 2 and 80),
  category_label text not null check (char_length(category_label) between 2 and 120),
  skill_description text not null default '' check (char_length(skill_description) <= 2000),
  character_archetype_key text not null check (char_length(character_archetype_key) between 2 and 120),
  character_asset_key text,
  asset_validation_status text not null default 'unverified'
    check (asset_validation_status in ('unverified','verified','rejected')),
  agent_id uuid references public.ai_agents(id) on delete restrict,
  runtime_policy_id uuid,
  status text not null default 'draft'
    check (status in ('draft','pending_approval','approved','active','stopped','isolated','blocked')),
  autonomy_mode text not null default 'supervised'
    check (autonomy_mode in ('disabled','supervised','bounded')),
  isolation_reason text,
  created_by uuid references auth.users(id) on delete set null,
  approved_by uuid references auth.users(id) on delete set null,
  approved_at timestamptz,
  activated_by uuid references auth.users(id) on delete set null,
  activated_at timestamptz,
  stopped_by uuid references auth.users(id) on delete set null,
  stopped_at timestamptz,
  last_action text not null default 'provisioned',
  metadata jsonb not null default '{}'::jsonb check (jsonb_typeof(metadata) = 'object'),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (status <> 'active' or (agent_id is not null and runtime_policy_id is not null
    and character_asset_key is not null and asset_validation_status = 'verified'
    and autonomy_mode in ('supervised','bounded'))),
  check (status <> 'isolated' or nullif(trim(isolation_reason), '') is not null)
);

create index if not exists official_agent_bots_status_category_idx
  on public.official_agent_bots(status, category_key, updated_at desc);
create index if not exists official_agent_bots_agent_id_idx
  on public.official_agent_bots(agent_id) where agent_id is not null;

alter table public.official_agent_bots enable row level security;
revoke all on public.official_agent_bots from anon, authenticated, public;
-- Only the backend service role can access this roster; operator routes enforce grants,
-- high-risk scope, durable audit, and lifecycle preconditions before service-role writes.
grant select, insert, update on public.official_agent_bots to service_role;

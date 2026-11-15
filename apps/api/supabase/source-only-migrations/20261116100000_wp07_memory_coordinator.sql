-- WP-07 / ENG-P06 Memory Coordinator. SOURCE ONLY; do not apply to production before Privacy/Security + Data Platform review.
create table if not exists public.agent_memory_policies (
 id uuid primary key default gen_random_uuid(),
 owner_user_id uuid not null references auth.users(id) on delete cascade,
 agent_id uuid references public.ai_agents(id) on delete cascade,
 memory_type text not null check(memory_type in ('working','episodic','semantic','procedural','long_term')),
 enabled boolean not null default false, consent_version text, consent_granted_at timestamptz, consent_revoked_at timestamptz,
 allowed_purposes text[] not null default '{}', allowed_sensitivities text[] not null default '{}',
 retention_days integer not null default 30 check(retention_days between 1 and 3650),
 write_mode text not null default 'manual_only' check(write_mode='manual_only'),
 policy_version integer not null default 1 check(policy_version>0),
 created_at timestamptz not null default now(), updated_at timestamptz not null default now(),
 check(not enabled or (consent_version is not null and consent_granted_at is not null and consent_revoked_at is null and cardinality(allowed_purposes)>0 and cardinality(allowed_sensitivities)>0))
);
create unique index if not exists agent_memory_policy_personal_uq on public.agent_memory_policies(owner_user_id,memory_type) where agent_id is null;
create unique index if not exists agent_memory_policy_agent_uq on public.agent_memory_policies(owner_user_id,agent_id,memory_type) where agent_id is not null;
create table if not exists public.agent_memory_items (
 id uuid primary key default gen_random_uuid(), policy_id uuid not null references public.agent_memory_policies(id) on delete restrict,
 owner_user_id uuid not null references auth.users(id) on delete cascade, agent_id uuid references public.ai_agents(id) on delete cascade,
 memory_type text not null check(memory_type in ('working','episodic','semantic','procedural','long_term')),
 visibility_scope text not null check(visibility_scope in ('owner_private','agent_private')),
 purpose text not null, classification text not null check(classification in ('public','internal','confidential','restricted')),
 content text not null check(char_length(content) between 1 and 8000), content_sha256 text not null check(content_sha256 ~ '^[0-9a-f]{64}$'),
 source_ref jsonb not null default '{}'::jsonb check(jsonb_typeof(source_ref)='object'),
 provenance jsonb not null default '{}'::jsonb check(jsonb_typeof(provenance)='object'),
 confidence numeric(5,4) check(confidence is null or confidence between 0 and 1),
 version integer not null default 1, policy_version integer not null,
 status text not null default 'proposed' check(status in ('proposed','active','rejected','deleted','expired')),
 retention_expires_at timestamptz not null, search_vector tsvector generated always as (to_tsvector('simple'::regconfig,content)) stored,
 created_by uuid not null references auth.users(id), approved_by uuid references auth.users(id), approved_at timestamptz,
 deleted_at timestamptz, created_at timestamptz not null default now(), updated_at timestamptz not null default now(),
 check((agent_id is null and visibility_scope='owner_private') or (agent_id is not null and visibility_scope='agent_private')),
 check((status='active' and approved_by is not null and approved_at is not null) or status<>'active')
);
create index if not exists agent_memory_items_scope_idx on public.agent_memory_items(owner_user_id,agent_id,memory_type,status,created_at desc);
create index if not exists agent_memory_items_policy_idx on public.agent_memory_items(policy_id,policy_version,status,retention_expires_at);
create index if not exists agent_memory_items_search_idx on public.agent_memory_items using gin(search_vector);
create unique index if not exists agent_memory_items_digest_uq on public.agent_memory_items(owner_user_id,coalesce(agent_id,'00000000-0000-0000-0000-000000000000'::uuid),memory_type,policy_version,content_sha256) where status in ('proposed','active');
create table if not exists public.agent_memory_events (
 id uuid primary key default gen_random_uuid(), owner_user_id uuid not null references auth.users(id) on delete cascade,
 agent_id uuid references public.ai_agents(id) on delete cascade, policy_id uuid references public.agent_memory_policies(id) on delete set null,
 item_id uuid references public.agent_memory_items(id) on delete set null, actor_user_id uuid references auth.users(id) on delete set null,
 event_type text not null check(event_type in ('policy_enabled','policy_disabled','memory_proposed','memory_approved','memory_rejected','memory_corrected','memory_deleted','memory_expired')),
 details jsonb not null default '{}'::jsonb check(jsonb_typeof(details)='object'), created_at timestamptz not null default now()
);
create index if not exists agent_memory_events_owner_idx on public.agent_memory_events(owner_user_id,created_at desc);
alter table public.agent_memory_policies enable row level security;
alter table public.agent_memory_items enable row level security;
alter table public.agent_memory_events enable row level security;
create policy agent_memory_policies_owner_select on public.agent_memory_policies for select to authenticated using(owner_user_id=(select auth.uid()));
create policy agent_memory_items_owner_select on public.agent_memory_items for select to authenticated using(owner_user_id=(select auth.uid()));
create policy agent_memory_events_owner_select on public.agent_memory_events for select to authenticated using(owner_user_id=(select auth.uid()));
revoke all on public.agent_memory_policies,public.agent_memory_items,public.agent_memory_events from public,anon,authenticated;
grant select on public.agent_memory_policies,public.agent_memory_items,public.agent_memory_events to authenticated;
grant all on public.agent_memory_policies,public.agent_memory_items,public.agent_memory_events to service_role;
comment on table public.agent_memory_policies is 'Owner-controlled per-Agent/per-class consent and retention policy; disabled by default.';
comment on table public.agent_memory_items is 'Private Agent Memory; Knowledge corpus and Conversation messages remain separate.';
comment on table public.agent_memory_events is 'Content-minimized Memory lifecycle audit events.';

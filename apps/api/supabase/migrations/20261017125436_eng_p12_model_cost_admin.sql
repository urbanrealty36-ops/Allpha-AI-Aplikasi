-- ENG-P34 cross-cutting operator cost configuration.
-- Canonical Supabase migration path. Source-only until approved ENG-P37 staging.
-- Do not apply to Production without an approved isolated non-production target.
create table if not exists public.ai_model_cost_configs (
    id uuid primary key default gen_random_uuid(),
    provider_id text not null check (provider_id ~ '^[a-z0-9][a-z0-9._-]{1,79}$'),
    model_id text not null check (char_length(model_id) between 2 and 180),
    model_version text not null check (char_length(model_version) between 1 and 180),
    pricing_version text not null check (pricing_version ~ '^[A-Za-z0-9][A-Za-z0-9._:-]{0,79}$'),
    cost_unit text not null check (char_length(cost_unit) between 2 and 40),
    input_micro_cost_per_token bigint not null check (input_micro_cost_per_token >= 0),
    output_micro_cost_per_token bigint not null check (output_micro_cost_per_token >= 0),
    max_cost_microunits bigint not null check (max_cost_microunits > 0),
    max_prompt_bytes integer not null default 16384 check (max_prompt_bytes between 1 and 1000000),
    max_output_tokens integer not null default 1024 check (max_output_tokens between 1 and 100000),
    max_latency_ms integer not null default 30000 check (max_latency_ms between 100 and 300000),
    status text not null default 'draft' check (status in ('draft','active','archived')),
    policy_approved boolean not null default false,
    effective_at timestamptz,
    created_by uuid references auth.users(id) on delete set null,
    updated_by uuid references auth.users(id) on delete set null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique(provider_id, model_id, pricing_version)
);
create unique index if not exists ai_model_cost_one_active_version
    on public.ai_model_cost_configs(provider_id, model_id) where status = 'active';
create index if not exists ai_model_cost_status_effective_idx
    on public.ai_model_cost_configs(status, effective_at desc);
alter table public.ai_model_cost_configs enable row level security;
revoke all on public.ai_model_cost_configs from anon, authenticated;
grant select, insert, update, delete on public.ai_model_cost_configs to service_role;
comment on table public.ai_model_cost_configs is
    'Versioned operator-managed provider/model cost and runtime budget configuration. Never implies model policy approval.';

-- Restored 2026-11-24 from pg_stat_statements and the live retention catalog.
-- Retention periods are intentionally not seeded. No legal retention duration
-- is inferred by engineering. Deletion scheduling requires approved rows for
-- every data class and an independently recorded legal-hold review.
create table if not exists public.account_data_retention_policies (
  id uuid primary key default gen_random_uuid(),
  data_class text not null,
  retention_days integer not null check (retention_days >= 0),
  policy_version text not null check (char_length(policy_version) between 1 and 40),
  legal_basis text not null check (char_length(legal_basis) between 1 and 500),
  approved_by uuid not null,
  approved_at timestamptz not null,
  active boolean not null default false,
  updated_at timestamptz not null default now(),
  unique (data_class, policy_version)
);
alter table public.account_data_retention_policies enable row level security;
revoke all on table public.account_data_retention_policies from public,anon,authenticated;
grant select,insert,update,delete on table public.account_data_retention_policies to service_role;
drop trigger if exists account_deletion_retention_policy_requeue on public.account_data_retention_policies;
create trigger account_deletion_retention_policy_requeue after insert or update or delete on public.account_data_retention_policies for each statement execute function private.requeue_blocked_account_deletion_requests();


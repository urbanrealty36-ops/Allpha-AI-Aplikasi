-- ENG-P06: canonical platform operator grants and append-only privileged audit.
-- Source migration only. Apply through the approved Supabase migration lifecycle
-- after schema review in an isolated non-production environment; never test on production.

create schema if not exists private;

create table if not exists public.platform_operator_grants (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete restrict,
  scopes text[] not null check (
    cardinality(scopes) > 0
    and scopes <@ array[
      'platform:operations.read',
      'platform:security.audit.read',
      'platform:capabilities.review',
      'platform:operators.manage'
    ]::text[]
  ),
  status text not null default 'active' check (status in ('active', 'revoked')),
  reason text not null check (char_length(reason) between 8 and 500),
  granted_by uuid not null references auth.users(id) on delete restrict,
  expires_at timestamptz,
  created_at timestamptz not null default now(),
  revoked_at timestamptz,
  revoked_by uuid references auth.users(id) on delete restrict,
  revocation_reason text check (revocation_reason is null or char_length(revocation_reason) between 8 and 500),
  check (
    (status = 'active' and revoked_at is null and revoked_by is null)
    or (status = 'revoked' and revoked_at is not null and revoked_by is not null)
  )
);
create index if not exists platform_operator_grants_user_active_idx
  on public.platform_operator_grants(user_id, created_at desc)
  where status = 'active';
create index if not exists platform_operator_grants_expiry_idx
  on public.platform_operator_grants(expires_at)
  where status = 'active' and expires_at is not null;

create table if not exists public.platform_operator_audit_events (
  id uuid primary key default gen_random_uuid(),
  actor_user_id uuid references auth.users(id) on delete set null,
  action text not null check (char_length(action) between 1 and 120),
  resource_type text not null check (char_length(resource_type) between 1 and 80),
  resource_id text,
  outcome text not null check (outcome in ('allowed', 'denied', 'error')),
  request_id text not null check (char_length(request_id) between 1 and 128),
  metadata jsonb not null default '{}'::jsonb check (jsonb_typeof(metadata) = 'object'),
  created_at timestamptz not null default now()
);
create index if not exists platform_operator_audit_created_idx
  on public.platform_operator_audit_events(created_at desc);
create index if not exists platform_operator_audit_actor_created_idx
  on public.platform_operator_audit_events(actor_user_id, created_at desc);

alter table public.platform_operator_grants enable row level security;
alter table public.platform_operator_audit_events enable row level security;

drop policy if exists platform_operator_grants_self_active_select on public.platform_operator_grants;
create policy platform_operator_grants_self_active_select
  on public.platform_operator_grants for select to authenticated
  using (
    user_id = (select auth.uid())
    and status = 'active'
    and (expires_at is null or expires_at > now())
  );

-- Grant rows are provisioned/revoked only through trusted server-side operations.
revoke all on public.platform_operator_grants from public, anon, authenticated;
grant select on public.platform_operator_grants to authenticated;
grant select, insert, update on public.platform_operator_grants to service_role;

-- Audit is private and append-only for the application. No client-side writes.
revoke all on public.platform_operator_audit_events from public, anon, authenticated, service_role;
grant select, insert on public.platform_operator_audit_events to service_role;

create or replace function private.audit_platform_operator_grant_change()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  event_action text;
  event_actor uuid;
begin
  if tg_op = 'INSERT' then
    event_action := 'operator.grant.created';
    event_actor := new.granted_by;
    insert into public.platform_operator_audit_events
      (actor_user_id, action, resource_type, resource_id, outcome, request_id, metadata)
    values
      (event_actor, event_action, 'platform_operator_grant', new.id::text, 'allowed',
       coalesce(nullif(current_setting('request.headers', true), '')::jsonb ->> 'x-request-id', 'db-grant'),
       jsonb_build_object('target_user_id', new.user_id, 'scopes', new.scopes,
                          'expires_at', new.expires_at, 'reason', new.reason));
    return new;
  end if;

  if tg_op = 'UPDATE' and old.status = 'active' and new.status = 'revoked' then
    event_action := 'operator.grant.revoked';
    event_actor := new.revoked_by;
    insert into public.platform_operator_audit_events
      (actor_user_id, action, resource_type, resource_id, outcome, request_id, metadata)
    values
      (event_actor, event_action, 'platform_operator_grant', new.id::text, 'allowed',
       coalesce(nullif(current_setting('request.headers', true), '')::jsonb ->> 'x-request-id', 'db-revoke'),
       jsonb_build_object('target_user_id', new.user_id, 'scopes', new.scopes,
                          'reason', new.revocation_reason));
  end if;
  return new;
end;
$$;
revoke all on function private.audit_platform_operator_grant_change() from public, anon, authenticated, service_role;

drop trigger if exists platform_operator_grants_audit_insert on public.platform_operator_grants;
create trigger platform_operator_grants_audit_insert
  after insert on public.platform_operator_grants
  for each row execute function private.audit_platform_operator_grant_change();
drop trigger if exists platform_operator_grants_audit_revoke on public.platform_operator_grants;
create trigger platform_operator_grants_audit_revoke
  after update on public.platform_operator_grants
  for each row execute function private.audit_platform_operator_grant_change();

comment on table public.platform_operator_grants is
  'Trusted platform operator grants; a Supabase user session alone never grants operator authority.';
comment on table public.platform_operator_audit_events is
  'Server-owned append-only audit trail for privileged platform operations and operator grant lifecycle.';

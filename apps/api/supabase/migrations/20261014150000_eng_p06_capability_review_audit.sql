-- ENG-P06: capability review provenance and atomic audit.
-- Freeze grant identity/scope fields after creation; service-role updates are revocation-only.
alter table public.platform_operator_grants
  drop constraint if exists platform_operator_grants_revocation_reason_check;
alter table public.platform_operator_grants
  add constraint platform_operator_grants_revocation_reason_check
  check (
    (status = 'active' and revocation_reason is null)
    or (status = 'revoked' and revocation_reason is not null and char_length(revocation_reason) between 8 and 500)
  );

revoke update on public.platform_operator_grants from service_role;
grant update (status, revoked_at, revoked_by, revocation_reason)
  on public.platform_operator_grants to service_role;

create or replace function private.guard_platform_operator_grant_update()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if old.status <> 'active' or new.status <> 'revoked' then
    raise exception using errcode = '42501', message = 'Operator grants may only transition from active to revoked';
  end if;
  if new.user_id is distinct from old.user_id
     or new.scopes is distinct from old.scopes
     or new.reason is distinct from old.reason
     or new.granted_by is distinct from old.granted_by
     or new.expires_at is distinct from old.expires_at
     or new.created_at is distinct from old.created_at
     or new.revoked_at is null
     or new.revoked_by is null
     or new.revocation_reason is null then
    raise exception using errcode = '42501', message = 'Operator grant identity and scopes are immutable';
  end if;
  return new;
end;
$$;
revoke all on function private.guard_platform_operator_grant_update() from public, anon, authenticated, service_role;
drop trigger if exists platform_operator_grants_guard_update on public.platform_operator_grants;
create trigger platform_operator_grants_guard_update
  before update on public.platform_operator_grants
  for each row execute function private.guard_platform_operator_grant_update();

-- The separate high-risk review scope is intentionally not implied by the base review scope.
alter table public.platform_operator_grants
  drop constraint if exists platform_operator_grants_scopes_check;
alter table public.platform_operator_grants
  add constraint platform_operator_grants_scopes_check
  check (
    cardinality(scopes) > 0
    and scopes <@ array[
      'platform:operations.read',
      'platform:security.audit.read',
      'platform:capabilities.review',
      'platform:capabilities.review.high_risk',
      'platform:operators.manage'
    ]::text[]
  );

grant select, update on public.agent_capabilities to service_role;

-- Forward migration; source-only until verified through the approved isolated non-production lifecycle.
-- Never apply to production as a test.

alter table public.agent_capabilities
  add column if not exists reviewed_by uuid references auth.users(id) on delete restrict,
  add column if not exists reviewed_at timestamptz,
  add column if not exists review_reason text;

do $$
begin
  if not exists (
    select 1 from pg_constraint
    where conname = 'agent_capabilities_review_fields_consistent'
      and conrelid = 'public.agent_capabilities'::regclass
  ) then
    alter table public.agent_capabilities
      add constraint agent_capabilities_review_fields_consistent
      check (
        (reviewed_by is null and reviewed_at is null and review_reason is null)
        or (
          reviewed_by is not null
          and reviewed_at is not null
          and review_reason is not null
          and char_length(review_reason) between 8 and 500
          and status in ('approved','denied','revoked')
        )
      );
  end if;
end;
$$;

create or replace function private.guard_agent_capability_review_fields()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if coalesce((select auth.role()), '') <> 'service_role'
     and (
       new.reviewed_by is distinct from old.reviewed_by
       or new.reviewed_at is distinct from old.reviewed_at
       or new.review_reason is distinct from old.review_reason
     ) then
    raise exception using
      errcode = '42501',
      message = 'Capability review fields are server-managed';
  end if;
  return new;
end;
$$;
revoke all on function private.guard_agent_capability_review_fields() from public, anon, authenticated, service_role;

drop trigger if exists agent_capabilities_guard_review_fields on public.agent_capabilities;
create trigger agent_capabilities_guard_review_fields
  before update on public.agent_capabilities
  for each row execute function private.guard_agent_capability_review_fields();

create or replace function private.audit_agent_capability_review()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  if old.status = 'requested' and new.status in ('approved','denied') then
    insert into public.platform_operator_audit_events
      (actor_user_id, action, resource_type, resource_id, outcome, request_id, metadata)
    values (
      new.reviewed_by,
      'agent.capability.review.' || new.status,
      'agent_capability',
      new.id::text,
      'allowed',
      coalesce(nullif(current_setting('request.headers', true), '')::jsonb ->> 'x-request-id', 'db-capability-review'),
      jsonb_build_object(
        'agent_id', new.agent_id,
        'capability_key', new.capability_key,
        'risk_level', new.risk_level,
        'reason', new.review_reason
      )
    );
  end if;
  return new;
end;
$$;
revoke all on function private.audit_agent_capability_review() from public, anon, authenticated, service_role;

drop trigger if exists agent_capabilities_audit_review on public.agent_capabilities;
create trigger agent_capabilities_audit_review
  after update on public.agent_capabilities
  for each row execute function private.audit_agent_capability_review();

comment on column public.agent_capabilities.reviewed_by is 'Trusted operator identity that reviewed the capability request; never client-writable.';
comment on column public.agent_capabilities.reviewed_at is 'Server timestamp for the capability review decision.';
comment on column public.agent_capabilities.review_reason is 'Bounded reason captured with the durable review audit event.';

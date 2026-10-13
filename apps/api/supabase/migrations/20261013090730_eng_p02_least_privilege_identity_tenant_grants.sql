-- ENG-P02: minimize PostgREST table privileges and close owner_id escalation.
-- RLS remains the row-level boundary; SQL grants are the first least-privilege layer.
-- Keep service_role privileges unchanged for trusted server-side operations.

revoke all privileges on table public.profiles from anon, authenticated;
revoke all privileges on table public.organizations from anon, authenticated;
revoke all privileges on table public.organization_memberships from anon, authenticated;
revoke all privileges on table public.audit_events from anon, authenticated;

-- Users may read profiles under RLS, insert only self-editable fields, and update
-- only profile fields exposed by the API. account_status and timestamps are server-owned.
grant select on table public.profiles to authenticated;
grant insert (id, username, display_name, avatar_url, bio, visibility, locale)
  on table public.profiles to authenticated;
grant update (username, display_name, avatar_url, bio, visibility, locale)
  on table public.profiles to authenticated;

-- Organization creation is permitted only when owner_id = auth.uid() under RLS.
-- Do not expose direct update/delete/truncate to clients until a validated API
-- contract explicitly owns those transitions.
grant select, insert (slug, name, owner_id) on table public.organizations to authenticated;
drop policy if exists organizations_update_admins on public.organizations;

-- Memberships are readable only through their RLS policy; membership mutations
-- remain backend-controlled and trigger-managed.
grant select on table public.organization_memberships to authenticated;

-- Audit events are read-only to authorized tenant administrators. Trigger-owned
-- writes remain available through the SECURITY DEFINER trigger function.
grant select on table public.audit_events to authenticated;

-- Cover the invited_by FK for efficient auth-user deletion/set-null checks.
create index if not exists organization_memberships_invited_by_idx
  on public.organization_memberships (invited_by)
  where invited_by is not null;

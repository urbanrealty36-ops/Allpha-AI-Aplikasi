create schema if not exists private;
revoke all on schema private from public, anon;
grant usage on schema private to authenticated;

create or replace function private.is_organization_member(target_organization uuid)
returns boolean language sql stable security definer set search_path = ''
as $$
  select exists (select 1 from public.organization_memberships m
    where m.organization_id = target_organization and m.user_id = (select auth.uid()));
$$;
create or replace function private.is_organization_admin(target_organization uuid)
returns boolean language sql stable security definer set search_path = ''
as $$
  select exists (select 1 from public.organization_memberships m
    where m.organization_id = target_organization and m.user_id = (select auth.uid())
      and m.role in ('owner','admin'));
$$;
revoke all on function private.is_organization_member(uuid) from public, anon;
revoke all on function private.is_organization_admin(uuid) from public, anon;
grant execute on function private.is_organization_member(uuid) to authenticated;
grant execute on function private.is_organization_admin(uuid) to authenticated;

drop policy if exists organizations_select_members on public.organizations;
create policy organizations_select_members on public.organizations for select to authenticated
using (private.is_organization_member(id) or owner_id = (select auth.uid()));
drop policy if exists organizations_update_admins on public.organizations;
create policy organizations_update_admins on public.organizations for update to authenticated
using (private.is_organization_admin(id)) with check (private.is_organization_admin(id));

drop policy if exists memberships_select_self_or_admin on public.organization_memberships;
drop policy if exists organization_memberships_select_self_or_admin on public.organization_memberships;
create policy memberships_select_self_or_admin on public.organization_memberships for select to authenticated
using (user_id = (select auth.uid()) or private.is_organization_admin(organization_id));

drop policy if exists audit_events_select_org_admins on public.audit_events;
create policy audit_events_select_org_admins on public.audit_events for select to authenticated
using (organization_id is not null and private.is_organization_admin(organization_id));

drop function if exists public.is_organization_member(uuid);
drop function if exists public.is_organization_admin(uuid);

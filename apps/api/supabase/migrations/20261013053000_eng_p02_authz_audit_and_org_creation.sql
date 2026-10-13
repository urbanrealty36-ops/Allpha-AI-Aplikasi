-- ENG-P02 additive hardening against the existing canonical schema.
create extension if not exists pgcrypto;
create table if not exists public.audit_events (
  id uuid primary key default gen_random_uuid(),
  actor_user_id uuid references auth.users(id) on delete set null,
  organization_id uuid references public.organizations(id) on delete set null,
  action text not null check (char_length(action) between 1 and 120),
  resource_type text not null check (char_length(resource_type) between 1 and 80),
  resource_id text, request_id text,
  metadata jsonb not null default '{}'::jsonb check (jsonb_typeof(metadata) = 'object'),
  created_at timestamptz not null default now()
);
create index if not exists audit_events_org_created_idx on public.audit_events(organization_id, created_at desc);
create index if not exists audit_events_actor_created_idx on public.audit_events(actor_user_id, created_at desc);
alter table public.audit_events enable row level security;

create or replace function public.is_organization_admin(target_organization uuid)
returns boolean language sql stable security definer set search_path = ''
as $$
  select exists (
    select 1 from public.organization_memberships m
    where m.organization_id = target_organization
      and m.user_id = (select auth.uid())
      and m.role in ('owner','admin')
  );
$$;

create or replace function public.create_organization_owner_membership()
returns trigger language plpgsql security definer set search_path = ''
as $$
begin
  insert into public.organization_memberships (organization_id, user_id, role, invited_by)
  values (new.id, new.owner_id, 'owner', new.owner_id)
  on conflict (organization_id, user_id) do nothing;
  return new;
end;
$$;
drop trigger if exists organizations_add_creator_as_owner on public.organizations;
create trigger organizations_add_creator_as_owner after insert on public.organizations
for each row execute function public.create_organization_owner_membership();

drop policy if exists organizations_insert_owner on public.organizations;
create policy organizations_insert_owner on public.organizations for insert to authenticated
with check (owner_id = (select auth.uid()));
drop policy if exists organizations_update_admins on public.organizations;
create policy organizations_update_admins on public.organizations for update to authenticated
using (public.is_organization_admin(id)) with check (public.is_organization_admin(id));

drop policy if exists memberships_select_self_or_admin on public.organization_memberships;
create policy memberships_select_self_or_admin on public.organization_memberships for select to authenticated
using (user_id = (select auth.uid()) or public.is_organization_admin(organization_id));
drop policy if exists memberships_no_client_insert on public.organization_memberships;
create policy memberships_no_client_insert on public.organization_memberships for insert to authenticated with check (false);
drop policy if exists memberships_no_client_update on public.organization_memberships;
create policy memberships_no_client_update on public.organization_memberships for update to authenticated using (false) with check (false);
drop policy if exists memberships_no_client_delete on public.organization_memberships;
create policy memberships_no_client_delete on public.organization_memberships for delete to authenticated using (false);

drop policy if exists audit_events_select_org_admins on public.audit_events;
create policy audit_events_select_org_admins on public.audit_events for select to authenticated
using (organization_id is not null and public.is_organization_admin(organization_id));
drop policy if exists audit_events_no_client_insert on public.audit_events;
create policy audit_events_no_client_insert on public.audit_events for insert to authenticated with check (false);
drop policy if exists audit_events_no_client_update on public.audit_events;
create policy audit_events_no_client_update on public.audit_events for update to authenticated using (false) with check (false);
drop policy if exists audit_events_no_client_delete on public.audit_events;
create policy audit_events_no_client_delete on public.audit_events for delete to authenticated using (false);

grant usage on schema public to authenticated;
grant select, insert, update on public.organizations to authenticated;
grant select on public.organization_memberships, public.audit_events to authenticated;
grant execute on function public.is_organization_admin(uuid) to authenticated;
revoke all on function public.create_organization_owner_membership() from public, anon, authenticated;

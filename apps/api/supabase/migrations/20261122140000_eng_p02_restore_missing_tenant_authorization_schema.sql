-- ENG-P02 forward repair: restore the canonical tenant and audit relations
-- when the migration ledger exists but the live public schema is missing them.
-- Non-destructive and idempotent; apply only after the ADR-0024 recovery gate.
create extension if not exists pgcrypto;
create schema if not exists private;
revoke all on schema private from public, anon;
grant usage on schema private to authenticated;

create table if not exists public.organizations (
  id uuid primary key default gen_random_uuid(),
  slug text not null unique check (slug ~ '^[a-z0-9][a-z0-9-]{1,62}$'),
  name text not null check (char_length(name) between 2 and 120),
  owner_id uuid not null references auth.users(id) on delete restrict,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.organization_memberships (
  organization_id uuid not null references public.organizations(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  role text not null default 'member' check (role in ('owner','admin','member')),
  invited_by uuid references auth.users(id) on delete set null,
  created_at timestamptz not null default now(),
  primary key (organization_id,user_id)
);
create index if not exists organization_memberships_user_idx
  on public.organization_memberships(user_id,organization_id);

create table if not exists public.audit_events (
  id uuid primary key default gen_random_uuid(),
  actor_user_id uuid references auth.users(id) on delete set null,
  organization_id uuid references public.organizations(id) on delete set null,
  action text not null check (char_length(action) between 1 and 120),
  resource_type text not null check (char_length(resource_type) between 1 and 80),
  resource_id text,
  request_id text,
  metadata jsonb not null default '{}'::jsonb check (jsonb_typeof(metadata) = 'object'),
  created_at timestamptz not null default now()
);
create index if not exists audit_events_org_created_idx
  on public.audit_events(organization_id,created_at desc);
create index if not exists audit_events_actor_created_idx
  on public.audit_events(actor_user_id,created_at desc);

create or replace function private.is_organization_member(target_organization uuid)
returns boolean language sql stable security definer set search_path = ''
as $$
  select exists (
    select 1 from public.organization_memberships m
     where m.organization_id = target_organization
       and m.user_id = (select auth.uid())
  );
$$;

create or replace function private.is_organization_admin(target_organization uuid)
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
  insert into public.organization_memberships(organization_id,user_id,role,invited_by)
  values (new.id,new.owner_id,'owner',new.owner_id)
  on conflict (organization_id,user_id) do nothing;
  return new;
end;
$$;

create or replace function public.audit_organization_created()
returns trigger language plpgsql security definer set search_path = ''
as $$
begin
  insert into public.audit_events(actor_user_id,organization_id,action,resource_type,resource_id,metadata)
  values ((select auth.uid()),new.id,'organization.created','organization',new.id::text,
          jsonb_build_object('slug',new.slug));
  return new;
end;
$$;

alter table public.organizations enable row level security;
alter table public.organization_memberships enable row level security;
alter table public.audit_events enable row level security;

drop policy if exists organizations_select_members on public.organizations;
create policy organizations_select_members on public.organizations for select to authenticated
using (private.is_organization_member(id) or owner_id = (select auth.uid()));
drop policy if exists organizations_insert_owner on public.organizations;
create policy organizations_insert_owner on public.organizations for insert to authenticated
with check (owner_id = (select auth.uid()));
drop policy if exists organizations_update_admins on public.organizations;
create policy organizations_update_admins on public.organizations for update to authenticated
using (private.is_organization_admin(id)) with check (private.is_organization_admin(id));

drop policy if exists memberships_select_self_or_admin on public.organization_memberships;
drop policy if exists organization_memberships_select_self_or_admin on public.organization_memberships;
create policy memberships_select_self_or_admin on public.organization_memberships for select to authenticated
using (user_id = (select auth.uid()) or private.is_organization_admin(organization_id));
drop policy if exists memberships_no_client_insert on public.organization_memberships;
create policy memberships_no_client_insert on public.organization_memberships for insert to authenticated with check (false);
drop policy if exists memberships_no_client_update on public.organization_memberships;
create policy memberships_no_client_update on public.organization_memberships for update to authenticated using (false) with check (false);
drop policy if exists memberships_no_client_delete on public.organization_memberships;
create policy memberships_no_client_delete on public.organization_memberships for delete to authenticated using (false);

drop policy if exists audit_events_select_org_admins on public.audit_events;
create policy audit_events_select_org_admins on public.audit_events for select to authenticated
using (organization_id is not null and private.is_organization_admin(organization_id));
drop policy if exists audit_events_no_client_insert on public.audit_events;
create policy audit_events_no_client_insert on public.audit_events for insert to authenticated with check (false);
drop policy if exists audit_events_no_client_update on public.audit_events;
create policy audit_events_no_client_update on public.audit_events for update to authenticated using (false) with check (false);
drop policy if exists audit_events_no_client_delete on public.audit_events;
create policy audit_events_no_client_delete on public.audit_events for delete to authenticated using (false);

drop trigger if exists organizations_add_creator_as_owner on public.organizations;
create trigger organizations_add_creator_as_owner after insert on public.organizations
for each row execute function public.create_organization_owner_membership();
drop trigger if exists organizations_audit_created on public.organizations;
create trigger organizations_audit_created after insert on public.organizations
for each row execute function public.audit_organization_created();

revoke all on function private.is_organization_member(uuid) from public,anon;
revoke all on function private.is_organization_admin(uuid) from public,anon;
grant execute on function private.is_organization_member(uuid) to authenticated;
grant execute on function private.is_organization_admin(uuid) to authenticated;
revoke all on function public.create_organization_owner_membership() from public,anon,authenticated;
revoke all on function public.audit_organization_created() from public,anon,authenticated;

grant usage on schema public to authenticated;
grant select,insert,update on public.organizations to authenticated;
grant select on public.organization_memberships,public.audit_events to authenticated;

-- Reconstructed ENG-P02 baseline from the live canonical schema.
-- The database already records this version as applied; this file makes fresh setup reproducible.
create extension if not exists pgcrypto;

create table if not exists public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  username text unique,
  display_name text not null default '' check (char_length(display_name) <= 80),
  avatar_url text check (avatar_url is null or char_length(avatar_url) <= 2048),
  bio text not null default '' check (char_length(bio) <= 500),
  visibility text not null default 'public' check (visibility in ('public','private')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint profiles_username_format check (username is null or username ~ '^[a-z0-9_]{3,30}$')
);

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
create index if not exists organization_memberships_user_idx on public.organization_memberships(user_id,organization_id);

create or replace function public.set_updated_at()
returns trigger language plpgsql set search_path = ''
as $$ begin new.updated_at := pg_catalog.now(); return new; end; $$;

create or replace function public.handle_new_auth_user()
returns trigger language plpgsql security definer set search_path = ''
as $$
declare requested_name text;
begin
  requested_name := coalesce(
    nullif(pg_catalog.trim(new.raw_user_meta_data ->> 'display_name'), ''),
    nullif(pg_catalog.trim(new.raw_user_meta_data ->> 'full_name'), ''),
    ''
  );
  insert into public.profiles (id,display_name)
  values (new.id,pg_catalog.left(requested_name,80))
  on conflict (id) do nothing;
  return new;
end;
$$;

create or replace function public.is_organization_member(target_organization uuid)
returns boolean language sql stable security definer set search_path = ''
as $$
  select exists (select 1 from public.organization_memberships m
    where m.organization_id = target_organization and m.user_id = (select auth.uid()));
$$;

create or replace function public.is_organization_admin(target_organization uuid)
returns boolean language sql stable security definer set search_path = ''
as $$
  select exists (select 1 from public.organization_memberships m
    where m.organization_id = target_organization and m.user_id = (select auth.uid())
      and m.role in ('owner','admin'));
$$;

create or replace function public.create_organization_owner_membership()
returns trigger language plpgsql security definer set search_path = ''
as $$
begin
  insert into public.organization_memberships (organization_id,user_id,role,invited_by)
  values (new.id,new.owner_id,'owner',new.owner_id)
  on conflict (organization_id,user_id) do nothing;
  return new;
end;
$$;

drop trigger if exists on_auth_user_created_profile on auth.users;
create trigger on_auth_user_created_profile after insert on auth.users
for each row execute function public.handle_new_auth_user();
drop trigger if exists profiles_set_updated_at on public.profiles;
create trigger profiles_set_updated_at before update on public.profiles
for each row execute function public.set_updated_at();
drop trigger if exists organizations_set_updated_at on public.organizations;
create trigger organizations_set_updated_at before update on public.organizations
for each row execute function public.set_updated_at();
drop trigger if exists organizations_add_creator_as_owner on public.organizations;
create trigger organizations_add_creator_as_owner after insert on public.organizations
for each row execute function public.create_organization_owner_membership();

alter table public.profiles enable row level security;
alter table public.organizations enable row level security;
alter table public.organization_memberships enable row level security;

drop policy if exists profiles_insert_self on public.profiles;
create policy profiles_insert_self on public.profiles for insert to authenticated
with check (id = (select auth.uid()));
drop policy if exists profiles_select_visible on public.profiles;
create policy profiles_select_visible on public.profiles for select to authenticated
using (visibility = 'public' or id = (select auth.uid()));
drop policy if exists profiles_update_self on public.profiles;
create policy profiles_update_self on public.profiles for update to authenticated
using (id = (select auth.uid())) with check (id = (select auth.uid()));

drop policy if exists organizations_select_members on public.organizations;
create policy organizations_select_members on public.organizations for select to authenticated
using (public.is_organization_member(id) or owner_id = (select auth.uid()));
drop policy if exists organization_memberships_select_self_or_admin on public.organization_memberships;
create policy organization_memberships_select_self_or_admin on public.organization_memberships for select to authenticated
using (user_id = (select auth.uid()) or public.is_organization_admin(organization_id));

grant usage on schema public to authenticated;
grant select,insert,update on public.profiles to authenticated;
grant select on public.organizations,public.organization_memberships to authenticated;
revoke all on function public.handle_new_auth_user() from public,anon,authenticated;
revoke all on function public.create_organization_owner_membership() from public,anon,authenticated;
revoke all on function public.set_updated_at() from public,anon,authenticated;
revoke all on function public.is_organization_member(uuid) from public,anon;
revoke all on function public.is_organization_admin(uuid) from public,anon;
grant execute on function public.is_organization_member(uuid) to authenticated;
grant execute on function public.is_organization_admin(uuid) to authenticated;

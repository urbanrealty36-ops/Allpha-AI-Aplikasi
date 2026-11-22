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

create or replace function public.set_updated_at()
returns trigger language plpgsql set search_path = ''
as $$
begin
  new.updated_at := pg_catalog.now();
  return new;
end;
$$;

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

create or replace function public.revoke_my_auth_session(p_session_id uuid)
returns boolean
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_revoked uuid;
begin
  if (select auth.uid()) is null then
    raise exception using errcode = '28000', message = 'authentication_required';
  end if;

  update auth.sessions
     set not_after = pg_catalog.now(),
         updated_at = pg_catalog.now()
   where id = p_session_id
     and user_id = (select auth.uid())
     and (not_after is null or not_after > pg_catalog.now())
  returning id into v_revoked;

  if v_revoked is null then
    return false;
  end if;

  insert into public.audit_events(actor_user_id,action,resource_type,resource_id,metadata)
  values ((select auth.uid()),'auth.session.revoked','auth_session',v_revoked::text,
          jsonb_build_object('scope','selected'));
  return true;
end;
$$;

create or replace function public.revoke_my_other_auth_sessions(p_current_session_id uuid)
returns integer
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_revoked integer;
begin
  if (select auth.uid()) is null then
    raise exception using errcode = '28000', message = 'authentication_required';
  end if;

  if not exists (
    select 1 from auth.sessions s
     where s.id = p_current_session_id
       and s.user_id = (select auth.uid())
       and (s.not_after is null or s.not_after > pg_catalog.now())
  ) then
    raise exception using errcode = '28000', message = 'current_session_invalid';
  end if;

  with revoked as (
    update auth.sessions
       set not_after = pg_catalog.now(),
           updated_at = pg_catalog.now()
     where user_id = (select auth.uid())
       and id <> p_current_session_id
       and (not_after is null or not_after > pg_catalog.now())
     returning id
  )
  insert into public.audit_events(actor_user_id,action,resource_type,resource_id,metadata)
  select (select auth.uid()),'auth.session.revoked','auth_session',revoked.id::text,
         jsonb_build_object('scope','other_devices')
    from revoked;

  get diagnostics v_revoked = row_count;
  return v_revoked;
end;
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


-- Server-only organization command boundary. Clients receive SELECT only;
-- all tenant mutations are authorized here and invoked by FastAPI with service_role.
-- Server-only organization command boundary. Clients receive SELECT only; all tenant mutations run through FastAPI.
create or replace function private.organization_role_for_user(p_organization_id uuid,p_user_id uuid)
returns text language sql stable security definer set search_path = ''
as $$
  select m.role from public.organization_memberships m
   where m.organization_id=p_organization_id and m.user_id=p_user_id limit 1;
$$;

create or replace function public.create_organization_for_user(p_actor_user_id uuid,p_name text,p_slug text)
returns table(id uuid,name text,slug text,owner_id uuid,created_at timestamptz,updated_at timestamptz)
language plpgsql security definer set search_path = ''
as $$
begin
  if p_actor_user_id is null then raise exception using errcode='28000',message='actor_required'; end if;
  if p_name is null or pg_catalog.char_length(p_name) not between 2 and 120
     or p_slug is null or pg_catalog.char_length(p_slug) not between 2 and 63 then
    raise exception using errcode='22023',message='organization_input_invalid';
  end if;
  perform pg_catalog.set_config('request.jwt.claim.sub',p_actor_user_id::text,true);
  return query
    insert into public.organizations as o(name,slug,owner_id)
    values(p_name,p_slug,p_actor_user_id)
    returning o.id,o.name,o.slug,o.owner_id,o.created_at,o.updated_at;
end;
$$;

create or replace function public.add_organization_member_for_actor(p_organization_id uuid,p_actor_user_id uuid,p_target_user_id uuid,p_role text)
returns table(organization_id uuid,user_id uuid,role text,invited_by uuid,created_at timestamptz)
language plpgsql security definer set search_path = ''
as $$
declare v_actor_role text;
begin
  v_actor_role := private.organization_role_for_user(p_organization_id,p_actor_user_id);
  if coalesce(v_actor_role,'') not in ('owner','admin') then raise exception using errcode='42501',message='organization_management_forbidden'; end if;
  if p_target_user_id is null or p_role is null or p_role not in ('member','admin') then raise exception using errcode='22023',message='organization_member_input_invalid'; end if;
  if v_actor_role='admin' and p_role<>'member' then raise exception using errcode='42501',message='admin_cannot_grant_admin'; end if;
  insert into public.organization_memberships(organization_id,user_id,role,invited_by)
  values(p_organization_id,p_target_user_id,p_role,p_actor_user_id);
  insert into public.audit_events(actor_user_id,organization_id,action,resource_type,resource_id,metadata)
  values(p_actor_user_id,p_organization_id,'organization.member.added','organization_membership',p_target_user_id::text,jsonb_build_object('role',p_role));
  return query select m.organization_id,m.user_id,m.role,m.invited_by,m.created_at
    from public.organization_memberships m where m.organization_id=p_organization_id and m.user_id=p_target_user_id;
end;
$$;

create or replace function public.update_organization_member_role_for_actor(p_organization_id uuid,p_actor_user_id uuid,p_target_user_id uuid,p_role text)
returns table(organization_id uuid,user_id uuid,role text,invited_by uuid,created_at timestamptz)
language plpgsql security definer set search_path = ''
as $$
declare v_actor_role text; v_target_role text;
begin
  v_actor_role := private.organization_role_for_user(p_organization_id,p_actor_user_id);
  if coalesce(v_actor_role,'')<>'owner' then raise exception using errcode='42501',message='only_owner_can_change_member_roles'; end if;
  if p_role is null or p_role not in ('member','admin') then raise exception using errcode='22023',message='organization_member_role_invalid'; end if;
  select m.role into v_target_role from public.organization_memberships m where m.organization_id=p_organization_id and m.user_id=p_target_user_id;
  if not found then raise exception using errcode='P0002',message='organization_member_not_found'; end if;
  if v_target_role='owner' then raise exception using errcode='42501',message='organization_owner_role_is_immutable'; end if;
  update public.organization_memberships m set role=p_role where m.organization_id=p_organization_id and m.user_id=p_target_user_id;
  insert into public.audit_events(actor_user_id,organization_id,action,resource_type,resource_id,metadata)
  values(p_actor_user_id,p_organization_id,'organization.member.role_changed','organization_membership',p_target_user_id::text,jsonb_build_object('from',v_target_role,'to',p_role));
  return query select m.organization_id,m.user_id,m.role,m.invited_by,m.created_at
    from public.organization_memberships m where m.organization_id=p_organization_id and m.user_id=p_target_user_id;
end;
$$;

create or replace function public.remove_organization_member_for_actor(p_organization_id uuid,p_actor_user_id uuid,p_target_user_id uuid)
returns boolean language plpgsql security definer set search_path = ''
as $$
declare v_actor_role text; v_target_role text;
begin
  v_actor_role := private.organization_role_for_user(p_organization_id,p_actor_user_id);
  if coalesce(v_actor_role,'') not in ('owner','admin') then raise exception using errcode='42501',message='organization_management_forbidden'; end if;
  select m.role into v_target_role from public.organization_memberships m where m.organization_id=p_organization_id and m.user_id=p_target_user_id;
  if not found then raise exception using errcode='P0002',message='organization_member_not_found'; end if;
  if v_target_role='owner' or (v_actor_role='admin' and v_target_role<>'member') then raise exception using errcode='42501',message='organization_member_removal_forbidden'; end if;
  delete from public.organization_memberships m where m.organization_id=p_organization_id and m.user_id=p_target_user_id;
  insert into public.audit_events(actor_user_id,organization_id,action,resource_type,resource_id,metadata)
  values(p_actor_user_id,p_organization_id,'organization.member.removed','organization_membership',p_target_user_id::text,jsonb_build_object('role',v_target_role));
  return true;
end;
$$;

revoke all on function private.organization_role_for_user(uuid,uuid) from public,anon,authenticated,service_role;
revoke all on function public.create_organization_for_user(uuid,text,text) from public,anon,authenticated;
revoke all on function public.add_organization_member_for_actor(uuid,uuid,uuid,text) from public,anon,authenticated;
revoke all on function public.update_organization_member_role_for_actor(uuid,uuid,uuid,text) from public,anon,authenticated;
revoke all on function public.remove_organization_member_for_actor(uuid,uuid,uuid) from public,anon,authenticated;

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

drop trigger if exists organizations_set_updated_at on public.organizations;
create trigger organizations_set_updated_at before update on public.organizations
for each row execute function public.set_updated_at();
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
revoke all on function public.set_updated_at() from public,anon,authenticated;
revoke all on function public.revoke_my_auth_session(uuid) from public,anon;
grant execute on function public.revoke_my_auth_session(uuid) to authenticated;
revoke all on function public.revoke_my_other_auth_sessions(uuid) from public,anon;
grant execute on function public.revoke_my_other_auth_sessions(uuid) to authenticated;
revoke all on function public.create_organization_owner_membership() from public,anon,authenticated;
revoke all on function public.audit_organization_created() from public,anon,authenticated;

grant usage on schema public to authenticated,service_role;
grant select on public.organizations,public.organization_memberships,public.audit_events to authenticated;
revoke insert,update,delete on public.organizations,public.organization_memberships,public.audit_events from authenticated;
revoke insert (id,slug,name,owner_id,created_at,updated_at), update (id,slug,name,owner_id,created_at,updated_at)
  on public.organizations from authenticated;
grant execute on function public.create_organization_for_user(uuid,text,text) to service_role;
grant execute on function public.add_organization_member_for_actor(uuid,uuid,uuid,text) to service_role;
grant execute on function public.update_organization_member_role_for_actor(uuid,uuid,uuid,text) to service_role;
grant execute on function public.remove_organization_member_for_actor(uuid,uuid,uuid) to service_role;

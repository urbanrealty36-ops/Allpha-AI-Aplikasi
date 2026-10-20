-- ENG-P19 / ADR-0020: explicit resource-scoped Agent participation grants.
-- Proposal only. Do not apply to Production until schema reconciliation and Security/Privacy + Platform approval.
create table if not exists public.agent_resource_grants (
  id uuid primary key default gen_random_uuid(),
  agent_id uuid not null references public.ai_agents(id) on delete cascade,
  agent_version integer not null check (agent_version > 0),
  resource_type text not null check (resource_type in ('community','workspace')),
  community_id uuid references public.communities(id) on delete cascade,
  workspace_id uuid references public.workspaces(id) on delete cascade,
  granted_by uuid not null references auth.users(id) on delete restrict,
  scopes text[] not null check (cardinality(scopes) > 0 and scopes <@ array['read_published_content','read_workspace_documents','create_agent_post','comment']::text[]),
  policy_version integer not null default 1 check (policy_version > 0),
  status text not null default 'active' check (status in ('active','revoked')),
  expires_at timestamptz,
  revoked_at timestamptz,
  revoked_by uuid references auth.users(id) on delete set null,
  revocation_reason text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check ((resource_type='community' and community_id is not null and workspace_id is null)
      or (resource_type='workspace' and workspace_id is not null and community_id is null)),
  check ((status='active' and revoked_at is null and revoked_by is null)
      or (status='revoked' and revoked_at is not null and revoked_by is not null))
);
create unique index if not exists agent_resource_grants_active_unique
  on public.agent_resource_grants(agent_id,resource_type,coalesce(community_id,workspace_id))
  where status='active';
create index if not exists agent_resource_grants_lookup
  on public.agent_resource_grants(agent_id,resource_type,status,expires_at);
alter table public.agent_resource_grants enable row level security;
revoke all on public.agent_resource_grants from anon, authenticated;
grant select, insert, update, delete on public.agent_resource_grants to service_role;

create table if not exists public.agent_resource_grant_audit (
  id uuid primary key default gen_random_uuid(),
  grant_id uuid references public.agent_resource_grants(id) on delete set null,
  agent_id uuid not null references public.ai_agents(id) on delete cascade,
  agent_version integer not null check (agent_version > 0),
  resource_type text not null check (resource_type in ('community','workspace')),
  resource_id uuid not null,
  actor_user_id uuid not null references auth.users(id) on delete restrict,
  action text not null check (action in ('grant_created','grant_revoked')),
  scopes text[] not null default '{}',
  reason text,
  created_at timestamptz not null default now()
);
alter table public.agent_resource_grant_audit enable row level security;
revoke all on public.agent_resource_grant_audit from anon, authenticated;
grant select, insert on public.agent_resource_grant_audit to service_role;

-- All grant mutation and its audit event commit or roll back together.
create or replace function public.grant_agent_resource_access(
  p_agent_id uuid,
  p_resource_type text,
  p_resource_id uuid,
  p_granted_by uuid,
  p_scopes text[],
  p_expires_at timestamptz default null
)
returns setof public.agent_resource_grants
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_agent public.ai_agents;
  v_grant public.agent_resource_grants;
begin
  if p_resource_type not in ('community','workspace')
     or cardinality(coalesce(p_scopes, array[]::text[])) < 1
     or not (coalesce(p_scopes, array[]::text[]) <@ array['read_published_content','read_workspace_documents','create_agent_post','comment']::text[])
     or (p_resource_type='community' and p_scopes && array['read_workspace_documents']::text[])
     or (p_resource_type='workspace' and p_scopes && array['read_published_content','create_agent_post']::text[])
     or (p_expires_at is not null and p_expires_at <= now()) then
    raise exception 'agent_resource_grant_invalid' using errcode='22023';
  end if;
  if (select auth.role()) <> 'service_role' then
    raise exception 'service_role_required' using errcode='42501';
  end if;

  select * into v_agent from public.ai_agents
   where id=p_agent_id and status='active' for share;
  if not found then raise exception 'agent_not_active' using errcode='P0002'; end if;
  if not exists (select 1 from public.agent_ownerships ao where ao.agent_id=p_agent_id and ao.ownership_role='owner' and ao.status='active') then
    raise exception 'agent_owner_required' using errcode='42501';
  end if;

  if p_resource_type='community' then
    if not exists (select 1 from public.communities c where c.id=p_resource_id and c.status='active') then
      raise exception 'community_not_active' using errcode='P0002';
    end if;
    if not exists (select 1 from public.community_memberships cm where cm.community_id=p_resource_id and cm.user_id=p_granted_by and cm.status='active' and cm.role in ('owner','moderator')) then
      raise exception 'resource_grant_approver_required' using errcode='42501';
    end if;
    insert into public.agent_resource_grants(agent_id,agent_version,resource_type,community_id,granted_by,scopes,policy_version,expires_at)
    values (p_agent_id,v_agent.version,p_resource_type,p_resource_id,p_granted_by,p_scopes,1,p_expires_at)
    returning * into v_grant;
  else
    if not exists (select 1 from public.workspaces w where w.id=p_resource_id and w.status='active') then
      raise exception 'workspace_not_active' using errcode='P0002';
    end if;
    if not exists (select 1 from public.workspace_memberships wm where wm.workspace_id=p_resource_id and wm.user_id=p_granted_by and wm.status='active' and wm.role='owner') then
      raise exception 'resource_grant_approver_required' using errcode='42501';
    end if;
    insert into public.agent_resource_grants(agent_id,agent_version,resource_type,workspace_id,granted_by,scopes,policy_version,expires_at)
    values (p_agent_id,v_agent.version,p_resource_type,p_resource_id,p_granted_by,p_scopes,1,p_expires_at)
    returning * into v_grant;
  end if;

  insert into public.agent_resource_grant_audit(grant_id,agent_id,agent_version,resource_type,resource_id,actor_user_id,action,scopes)
  values (v_grant.id,p_agent_id,v_agent.version,p_resource_type,p_resource_id,p_granted_by,'grant_created',p_scopes);
  return next v_grant;
end;
$$;
revoke all on function public.grant_agent_resource_access(uuid,text,uuid,uuid,text[],timestamptz) from public, anon, authenticated;
grant execute on function public.grant_agent_resource_access(uuid,text,uuid,uuid,text[],timestamptz) to service_role;

create or replace function public.revoke_agent_resource_access(
  p_agent_id uuid,
  p_grant_id uuid,
  p_actor_user_id uuid,
  p_reason text
)
returns setof public.agent_resource_grants
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_grant public.agent_resource_grants;
  v_agent_version integer;
  v_resource_id uuid;
begin
  if (select auth.role()) <> 'service_role' then raise exception 'service_role_required' using errcode='42501'; end if;
  if char_length(trim(coalesce(p_reason,''))) < 8 or char_length(p_reason) > 500 then
    raise exception 'agent_resource_revoke_reason_invalid' using errcode='22023';
  end if;
  select * into v_grant from public.agent_resource_grants
   where id=p_grant_id and agent_id=p_agent_id and status='active' for update;
  if not found then raise exception 'agent_resource_grant_not_active' using errcode='P0002'; end if;
  v_resource_id := coalesce(v_grant.community_id,v_grant.workspace_id);
  if v_grant.resource_type='community' then
    if not exists (select 1 from public.community_memberships cm where cm.community_id=v_resource_id and cm.user_id=p_actor_user_id and cm.status='active' and cm.role in ('owner','moderator')) then
      raise exception 'resource_grant_approver_required' using errcode='42501';
    end if;
  else
    if not exists (select 1 from public.workspace_memberships wm where wm.workspace_id=v_resource_id and wm.user_id=p_actor_user_id and wm.status='active' and wm.role='owner') then
      raise exception 'resource_grant_approver_required' using errcode='42501';
    end if;
  end if;
  select version into v_agent_version from public.ai_agents where id=p_agent_id;
  update public.agent_resource_grants set status='revoked',revoked_at=now(),revoked_by=p_actor_user_id,revocation_reason=trim(p_reason),updated_at=now()
   where id=p_grant_id and status='active' returning * into v_grant;
  if not found then raise exception 'agent_resource_grant_conflict' using errcode='40001'; end if;
  insert into public.agent_resource_grant_audit(grant_id,agent_id,agent_version,resource_type,resource_id,actor_user_id,action,scopes,reason)
  values (v_grant.id,p_agent_id,coalesce(v_agent_version,v_grant.agent_version),v_grant.resource_type,v_resource_id,p_actor_user_id,'grant_revoked',v_grant.scopes,trim(p_reason));
  return next v_grant;
end;
$$;
revoke all on function public.revoke_agent_resource_access(uuid,uuid,uuid,text) from public, anon, authenticated;
grant execute on function public.revoke_agent_resource_access(uuid,uuid,uuid,text) to service_role;

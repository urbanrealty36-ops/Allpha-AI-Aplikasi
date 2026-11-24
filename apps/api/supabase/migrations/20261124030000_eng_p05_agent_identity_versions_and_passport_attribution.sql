-- ENG-P05: owner-consented Agent Passport attribution and immutable identity version history.
alter table public.ai_agents
  add column if not exists public_owner_attribution boolean not null default false,
  add column if not exists published_at timestamptz,
  add column if not exists revoked_at timestamptz;

create table if not exists public.agent_identity_versions (
  id uuid primary key default gen_random_uuid(),
  agent_id uuid not null references public.ai_agents(id) on delete cascade,
  version integer not null check (version > 0),
  event_type text not null check (event_type in ('baseline','created','updated','published','revoked','archived')),
  snapshot jsonb not null check (jsonb_typeof(snapshot)='object'),
  snapshot_sha256 text not null check (snapshot_sha256 ~ '^[0-9a-f]{64}$'),
  recorded_at timestamptz not null default clock_timestamp(),
  constraint agent_identity_versions_agent_version_key unique(agent_id,version)
);

alter table public.agent_identity_versions enable row level security;
revoke all on table public.agent_identity_versions from public, anon, authenticated;
grant select on table public.agent_identity_versions to authenticated;
grant all on table public.agent_identity_versions to service_role;
drop policy if exists agent_identity_versions_select_owner on public.agent_identity_versions;
create policy agent_identity_versions_select_owner
  on public.agent_identity_versions for select to authenticated
  using (private.has_agent_ownership(agent_id,(select auth.uid()),'owner'));

create or replace function private.set_agent_publication_timestamps()
returns trigger
language plpgsql
security definer
set search_path=''
as $function$
begin
  if new.status='active' and new.visibility='public' then
    if char_length(btrim(coalesce(new.disclosure,''))) < 8 then
      raise exception 'AGENT_DISCLOSURE_REQUIRED_FOR_PUBLICATION' using errcode='23514';
    end if;
    if new.public_owner_attribution and not exists (
      select 1
      from public.agent_ownerships o
      join public.profiles p on p.id=o.owner_user_id
      where o.agent_id=new.id
        and o.ownership_role='owner'
        and o.status='active'
        and p.visibility='public'
        and p.account_status='active'
    ) then
      raise exception 'PUBLIC_OWNER_ATTRIBUTION_REQUIRES_PUBLIC_OWNER_PROFILE' using errcode='23514';
    end if;
  end if;

  if tg_op='INSERT' then
    if new.status='active' and new.visibility='public' then
      new.published_at:=coalesce(new.published_at,clock_timestamp());
    end if;
  else
    if new.status='active' and new.visibility='public'
       and (old.status is distinct from new.status or old.visibility is distinct from new.visibility) then
      new.published_at:=clock_timestamp();
      new.revoked_at:=null;
    elsif old.status='active' and old.visibility='public'
       and (new.status is distinct from old.status or new.visibility is distinct from old.visibility) then
      new.revoked_at:=clock_timestamp();
      new.public_owner_attribution:=false;
    end if;
  end if;
  return new;
end;
$function$;

drop trigger if exists ai_agents_set_publication_timestamps on public.ai_agents;
create trigger ai_agents_set_publication_timestamps
before insert or update on public.ai_agents
for each row execute function private.set_agent_publication_timestamps();

create or replace function private.capture_agent_identity_version()
returns trigger
language plpgsql
security definer
set search_path=''
as $function$
declare
  v_event text;
  v_snapshot jsonb;
begin
  if tg_op='INSERT' then
    v_event:='created';
  elsif old.status is distinct from new.status
        and new.status='active' and new.visibility='public' then
    v_event:='published';
  elsif old.status='active' and old.visibility='public'
        and (new.status is distinct from old.status or new.visibility is distinct from old.visibility) then
    v_event:='revoked';
  elsif new.status='archived' and old.status is distinct from new.status then
    v_event:='archived';
  else
    v_event:='updated';
  end if;

  v_snapshot:=jsonb_build_object(
    'id',new.id,
    'version',new.version,
    'handle',new.handle,
    'display_name',new.display_name,
    'description',new.description,
    'avatar_url',new.avatar_url,
    'persona',new.persona,
    'disclosure',new.disclosure,
    'boundaries',new.boundaries,
    'visibility',new.visibility,
    'status',new.status,
    'public_owner_attribution',new.public_owner_attribution,
    'published_at',new.published_at,
    'revoked_at',new.revoked_at,
    'recorded_at',clock_timestamp()
  );

  insert into public.agent_identity_versions(agent_id,version,event_type,snapshot,snapshot_sha256)
  values(new.id,new.version,v_event,v_snapshot,encode(extensions.digest(v_snapshot::text,'sha256'),'hex'))
  on conflict(agent_id,version) do nothing;
  return new;
end;
$function$;

drop trigger if exists ai_agents_capture_identity_version on public.ai_agents;
create trigger ai_agents_capture_identity_version
after insert or update on public.ai_agents
for each row execute function private.capture_agent_identity_version();

-- Backfill a factual baseline for existing Agent identities without changing ai_agents.version.
insert into public.agent_identity_versions(agent_id,version,event_type,snapshot,snapshot_sha256,recorded_at)
select a.id,a.version,'baseline',
  jsonb_build_object(
    'id',a.id,'version',a.version,'handle',a.handle,'display_name',a.display_name,
    'description',a.description,'avatar_url',a.avatar_url,'persona',a.persona,
    'disclosure',a.disclosure,'boundaries',a.boundaries,'visibility',a.visibility,
    'status',a.status,'public_owner_attribution',a.public_owner_attribution,
    'published_at',a.published_at,'revoked_at',a.revoked_at,'recorded_at',a.created_at
  ),
  encode(extensions.digest(jsonb_build_object(
    'id',a.id,'version',a.version,'handle',a.handle,'display_name',a.display_name,
    'description',a.description,'avatar_url',a.avatar_url,'persona',a.persona,
    'disclosure',a.disclosure,'boundaries',a.boundaries,'visibility',a.visibility,
    'status',a.status,'public_owner_attribution',a.public_owner_attribution,
    'published_at',a.published_at,'revoked_at',a.revoked_at,'recorded_at',a.created_at
  )::text,'sha256'),'hex'),
  a.created_at
from public.ai_agents a
on conflict(agent_id,version) do nothing;

create or replace function public.update_my_ai_agent(
  p_agent_id uuid,
  p_expected_version integer,
  p_changes jsonb
)
returns setof public.ai_agents
language plpgsql
security invoker
set search_path=''
as $function$
declare
  v_agent public.ai_agents%rowtype;
  v_key text;
begin
  if auth.uid() is null then
    raise exception 'AUTHENTICATION_REQUIRED' using errcode='42501';
  end if;
  if p_changes is null or jsonb_typeof(p_changes)<>'object' or p_changes='{}'::jsonb then
    raise exception 'AGENT_UPDATE_EMPTY_OR_INVALID' using errcode='22023';
  end if;
  for v_key in select jsonb_object_keys(p_changes) loop
    if v_key not in ('handle','display_name','description','avatar_url','persona','disclosure','boundaries','visibility','status','public_owner_attribution') then
      raise exception 'AGENT_UPDATE_FIELD_NOT_ALLOWED: %',v_key using errcode='22023';
    end if;
  end loop;

  update public.ai_agents a
  set handle=case when p_changes ? 'handle' then p_changes->>'handle' else a.handle end,
      display_name=case when p_changes ? 'display_name' then p_changes->>'display_name' else a.display_name end,
      description=case when p_changes ? 'description' then p_changes->>'description' else a.description end,
      avatar_url=case when p_changes ? 'avatar_url' then p_changes->>'avatar_url' else a.avatar_url end,
      persona=case when p_changes ? 'persona' then p_changes->'persona' else a.persona end,
      disclosure=case when p_changes ? 'disclosure' then p_changes->>'disclosure' else a.disclosure end,
      boundaries=case when p_changes ? 'boundaries' then p_changes->'boundaries' else a.boundaries end,
      visibility=case when p_changes ? 'visibility' then p_changes->>'visibility' else a.visibility end,
      status=case when p_changes ? 'status' then p_changes->>'status' else a.status end,
      public_owner_attribution=case when p_changes ? 'public_owner_attribution' then (p_changes->>'public_owner_attribution')::boolean else a.public_owner_attribution end
  where a.id=p_agent_id
    and a.version=p_expected_version
    and private.has_agent_ownership(a.id,auth.uid(),'owner')
  returning a.* into v_agent;
  if not found then
    return;
  end if;
  return next v_agent;
end;
$function$;

create or replace function public.publish_my_ai_agent(
  p_agent_id uuid,
  p_expected_version integer,
  p_public_owner_attribution boolean default false
)
returns setof public.ai_agents
language sql
security invoker
set search_path=''
as $function$
  update public.ai_agents a
     set visibility='public',
         status='active',
         public_owner_attribution=coalesce(p_public_owner_attribution,false)
   where a.id=p_agent_id
     and a.version=p_expected_version
     and private.has_agent_ownership(a.id,auth.uid(),'owner')
  returning a.*;
$function$;

create or replace function public.revoke_my_ai_agent_publication(
  p_agent_id uuid,
  p_expected_version integer
)
returns setof public.ai_agents
language sql
security invoker
set search_path=''
as $function$
  update public.ai_agents a
     set visibility='private',
         status='draft',
         public_owner_attribution=false
   where a.id=p_agent_id
     and a.version=p_expected_version
     and private.has_agent_ownership(a.id,auth.uid(),'owner')
  returning a.*;
$function$;

create or replace function public.get_public_agent_owner_attribution(p_agent_id uuid)
returns table(username text,display_name text,avatar_url text)
language sql
stable
security definer
set search_path=''
as $function$
  select p.username,p.display_name,p.avatar_url
    from public.ai_agents a
    join public.agent_ownerships o
      on o.agent_id=a.id and o.ownership_role='owner' and o.status='active'
    join public.profiles p on p.id=o.owner_user_id
   where a.id=p_agent_id
     and a.status='active'
     and a.visibility='public'
     and a.public_owner_attribution=true
     and p.visibility='public'
     and p.account_status='active'
   limit 1;
$function$;

revoke all on function private.set_agent_publication_timestamps() from public,anon,authenticated;
revoke all on function private.capture_agent_identity_version() from public,anon,authenticated;
revoke all on function public.update_my_ai_agent(uuid,integer,jsonb) from public,anon;
revoke all on function public.publish_my_ai_agent(uuid,integer,boolean) from public,anon;
revoke all on function public.revoke_my_ai_agent_publication(uuid,integer) from public,anon;
revoke all on function public.get_public_agent_owner_attribution(uuid) from public;
grant execute on function public.update_my_ai_agent(uuid,integer,jsonb) to authenticated;
grant execute on function public.publish_my_ai_agent(uuid,integer,boolean) to authenticated;
grant execute on function public.revoke_my_ai_agent_publication(uuid,integer) to authenticated;
grant execute on function public.get_public_agent_owner_attribution(uuid) to anon,authenticated;

insert into private.account_export_sources(source_key,table_name,filter_kind,owner_columns,sort_order,enabled)
values ('agent_identity_versions','agent_identity_versions','agent_owner',array['agent_id'],53,true)
on conflict(source_key) do update
set table_name=excluded.table_name,filter_kind=excluded.filter_kind,owner_columns=excluded.owner_columns,sort_order=excluded.sort_order,enabled=true;

insert into public.account_deletion_source_policies(
 source_key,data_class,deletion_action,dependency_order,policy_version,reason,approved_by,approved_at,active,
 table_name,filter_kind,owner_columns,decision_source,decision_reference
)
select 'agent_identity_versions','agent_operational','preserve',53,policy_version,
 'Agent identity history is part of the persistent Agent operational identity; it contains no Human Owner identifier and follows the same ownership-transfer preservation policy as ai_agents.',
 approved_by,approved_at,true,'agent_identity_versions','agent_owner',array['agent_id'],
 decision_source,decision_reference
from public.account_deletion_source_policies
where source_key='agents_created'
on conflict(source_key) do update
set data_class=excluded.data_class,deletion_action=excluded.deletion_action,dependency_order=excluded.dependency_order,
 policy_version=excluded.policy_version,reason=excluded.reason,active=true,table_name=excluded.table_name,
 filter_kind=excluded.filter_kind,owner_columns=excluded.owner_columns,decision_source=excluded.decision_source,
 decision_reference=excluded.decision_reference,updated_at=clock_timestamp();

insert into public.account_deletion_dependency_rules(
 child_schema,child_table,constraint_name,fk_column,delete_rule,resolution_action,reason,active
)
select 'public','agent_identity_versions',c.conname,'agent_id','CASCADE','database_cascade',
 'Agent identity version history is owned by the Agent entity and cascades only if that Agent entity is deleted; Human account deletion preserves the Agent under the existing ownership-transfer policy.',
 true
from pg_constraint c
where c.conrelid='public.agent_identity_versions'::regclass
  and c.contype='f'
  and not exists (
    select 1 from public.account_deletion_dependency_rules r
    where r.child_schema='public' and r.child_table='agent_identity_versions' and r.constraint_name=c.conname
  );


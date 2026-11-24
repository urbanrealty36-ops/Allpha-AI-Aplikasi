-- ENG-P06: licensed Skill installation, owner acceptance, immutable terms and runtime revocation.
create table if not exists public.agent_skill_installations (
  id uuid primary key default gen_random_uuid(),
  agent_id uuid not null references public.ai_agents(id) on delete restrict,
  source_agent_id uuid not null references public.ai_agents(id) on delete restrict,
  source_skill_id uuid not null references public.agent_skills(id) on delete restrict,
  source_version integer not null check(source_version>0),
  source_snapshot_digest text not null check(source_snapshot_digest ~ '^[0-9a-f]{64}$'),
  installed_skill_id uuid not null references public.agent_skills(id) on delete restrict,
  installed_by uuid references auth.users(id) on delete set null,
  installer_subject_ref text not null check(installer_subject_ref ~ '^[0-9a-f]{64}$'),
  license_terms_snapshot jsonb not null check(jsonb_typeof(license_terms_snapshot)='object'),
  license_terms_digest text not null check(license_terms_digest ~ '^[0-9a-f]{64}$'),
  license_expires_at timestamptz,
  accepted_at timestamptz not null default clock_timestamp(),
  status text not null default 'active' check(status in ('active','revoked','expired')),
  revoked_by uuid references auth.users(id) on delete set null,
  revoked_at timestamptz,
  revocation_reason text,
  idempotency_key text not null check(char_length(idempotency_key) between 8 and 160),
  created_at timestamptz not null default clock_timestamp(),
  updated_at timestamptz not null default clock_timestamp(),
  constraint agent_skill_installation_idempotency unique(agent_id,idempotency_key),
  constraint agent_skill_installation_revocation_state check(
    (status='active' and revoked_at is null and revoked_by is null and revocation_reason is null)
    or (status in ('revoked','expired') and revoked_at is not null)
  )
);
create unique index if not exists agent_skill_installation_one_active_source_version
  on public.agent_skill_installations(agent_id,source_skill_id,source_version) where status='active';
create index if not exists agent_skill_installations_runtime_lookup
  on public.agent_skill_installations(agent_id,installed_skill_id,status);

create table if not exists public.agent_skill_installation_events (
  id uuid primary key default gen_random_uuid(),
  installation_id uuid not null references public.agent_skill_installations(id) on delete restrict,
  agent_id uuid not null references public.ai_agents(id) on delete restrict,
  source_agent_id uuid not null references public.ai_agents(id) on delete restrict,
  source_skill_id uuid not null references public.agent_skills(id) on delete restrict,
  event_type text not null check(event_type in ('installed','revoked','expired')),
  actor_user_id uuid references auth.users(id) on delete set null,
  actor_subject_ref text not null check(actor_subject_ref ~ '^[0-9a-f]{64}$'),
  source_version integer not null check(source_version>0),
  source_snapshot_digest text not null check(source_snapshot_digest ~ '^[0-9a-f]{64}$'),
  license_terms_digest text not null check(license_terms_digest ~ '^[0-9a-f]{64}$'),
  details jsonb not null default '{}'::jsonb check(jsonb_typeof(details)='object'),
  created_at timestamptz not null default clock_timestamp(),
  constraint agent_skill_installation_event_once unique(installation_id,event_type)
);
create index if not exists agent_skill_installation_events_agent_idx
  on public.agent_skill_installation_events(agent_id,created_at desc);

alter table public.agent_skill_installations enable row level security;
alter table public.agent_skill_installation_events enable row level security;
revoke all on table public.agent_skill_installations,public.agent_skill_installation_events from public,anon,authenticated;
grant select on table public.agent_skill_installations,public.agent_skill_installation_events to authenticated;
grant all on table public.agent_skill_installations,public.agent_skill_installation_events to service_role;

drop policy if exists agent_skill_installations_owner_select on public.agent_skill_installations;
create policy agent_skill_installations_owner_select on public.agent_skill_installations
for select to authenticated using(private.has_agent_ownership(agent_id,(select auth.uid()),'owner'));
drop policy if exists agent_skill_installation_events_owner_select on public.agent_skill_installation_events;
create policy agent_skill_installation_events_owner_select on public.agent_skill_installation_events
for select to authenticated using(private.has_agent_ownership(agent_id,(select auth.uid()),'owner'));

create or replace function public.install_agent_skill(
  p_agent_id uuid,
  p_source_agent_id uuid,
  p_source_skill_id uuid,
  p_source_version integer,
  p_accept_license boolean,
  p_idempotency_key text
) returns jsonb
language plpgsql security definer set search_path=''
as $function$
declare
  v_actor uuid:=auth.uid();
  v_source_agent public.ai_agents%rowtype;
  v_source_skill public.agent_skills%rowtype;
  v_snapshot jsonb;
  v_terms jsonb;
  v_license text;
  v_license_expiry timestamptz;
  v_snapshot_digest text;
  v_terms_digest text;
  v_existing public.agent_skill_installations%rowtype;
  v_installation public.agent_skill_installations%rowtype;
  v_installed_skill_id uuid:=gen_random_uuid();
  v_slug text;
begin
  if v_actor is null or coalesce(auth.role(),'')<>'authenticated' then
    raise exception 'AUTHENTICATED_AGENT_OWNER_REQUIRED' using errcode='42501';
  end if;
  if not coalesce(p_accept_license,false) then
    raise exception 'SKILL_LICENSE_ACCEPTANCE_REQUIRED' using errcode='42501';
  end if;
  if p_agent_id is null or p_source_agent_id is null or p_source_skill_id is null
     or p_source_version is null or p_source_version<1
     or p_idempotency_key is null or char_length(p_idempotency_key) not between 8 and 160 then
    raise exception 'SKILL_INSTALL_ARGUMENTS_INVALID' using errcode='22023';
  end if;
  if not private.has_agent_ownership(p_agent_id,v_actor,'owner') then
    raise exception 'TARGET_AGENT_OWNER_REQUIRED' using errcode='42501';
  end if;
  select * into v_source_agent from public.ai_agents a
   where a.id=p_source_agent_id and a.status='active' and a.visibility='public';
  if not found then raise exception 'SOURCE_AGENT_NOT_PUBLIC' using errcode='40400'; end if;
  select * into v_source_skill from public.agent_skills s
   where s.id=p_source_skill_id and s.agent_id=p_source_agent_id and s.status<>'archived';
  if not found then raise exception 'SOURCE_SKILL_NOT_AVAILABLE' using errcode='40400'; end if;
  select v.snapshot into v_snapshot
    from public.agent_skill_versions v
   where v.skill_id=p_source_skill_id and v.agent_id=p_source_agent_id and v.version=p_source_version
     and v.snapshot->>'status'='published'
   limit 1;
  if v_snapshot is null then raise exception 'PUBLISHED_SKILL_VERSION_NOT_FOUND' using errcode='40400'; end if;

  v_terms:=coalesce(v_snapshot->'publication_terms','{}'::jsonb);
  v_license:=nullif(btrim(coalesce(v_terms->>'license_key',v_terms->>'license',v_terms->>'license_type')),'');
  if jsonb_typeof(v_terms)<>'object' or v_terms='{}'::jsonb or v_license is null then
    raise exception 'SKILL_PUBLICATION_LICENSE_TERMS_REQUIRED' using errcode='23514';
  end if;
  if nullif(v_terms->>'expires_at','') is not null then
    begin v_license_expiry:=(v_terms->>'expires_at')::timestamptz;
    exception when others then raise exception 'SKILL_LICENSE_EXPIRY_INVALID' using errcode='22023'; end;
    if v_license_expiry<=clock_timestamp() then raise exception 'SKILL_LICENSE_EXPIRED' using errcode='23514'; end if;
  end if;
  v_snapshot_digest:=encode(extensions.digest(v_snapshot::text,'sha256'),'hex');
  v_terms_digest:=encode(extensions.digest(v_terms::text,'sha256'),'hex');

  select * into v_existing from public.agent_skill_installations i
   where i.agent_id=p_agent_id and i.idempotency_key=p_idempotency_key;
  if found then
    if v_existing.source_agent_id<>p_source_agent_id or v_existing.source_skill_id<>p_source_skill_id
       or v_existing.source_version<>p_source_version then
      raise exception 'SKILL_INSTALL_IDEMPOTENCY_CONFLICT' using errcode='23505';
    end if;
    return jsonb_build_object('installation',to_jsonb(v_existing),'installed_skill_id',v_existing.installed_skill_id,'idempotent_replay',true);
  end if;
  if exists(select 1 from public.agent_skill_installations i
     where i.agent_id=p_agent_id and i.source_skill_id=p_source_skill_id and i.source_version=p_source_version and i.status='active') then
    raise exception 'SKILL_VERSION_ALREADY_INSTALLED' using errcode='23505';
  end if;

  v_slug:=left(coalesce(v_snapshot->>'slug','skill'),35)||'-i-'||substr(replace(v_installed_skill_id::text,'-',''),1,12);
  insert into public.agent_skills(
    id,agent_id,created_by,slug,name,description,category,inputs_schema,outputs_schema,
    instructions,constraints,tool_dependencies,required_permission_scopes,model_requirements,
    budget_limits,tests,evaluation_rubric,provenance,version,changelog,publication_terms,status
  ) values(
    v_installed_skill_id,p_agent_id,v_actor,v_slug,
    coalesce(v_snapshot->>'name','Installed Skill'),
    coalesce(v_snapshot->>'description',''),
    coalesce(v_snapshot->>'category','general'),
    coalesce(v_snapshot->'inputs_schema','{"type":"object"}'::jsonb),
    coalesce(v_snapshot->'outputs_schema','{"type":"object"}'::jsonb),
    coalesce(v_snapshot->>'instructions',''),
    coalesce(v_snapshot->'constraints','{}'::jsonb),
    array(select jsonb_array_elements_text(coalesce(v_snapshot->'tool_dependencies','[]'::jsonb))),
    array(select jsonb_array_elements_text(coalesce(v_snapshot->'required_permission_scopes','[]'::jsonb))),
    coalesce(v_snapshot->'model_requirements','{}'::jsonb),
    coalesce(v_snapshot->'budget_limits','{}'::jsonb),
    coalesce(v_snapshot->'tests','[]'::jsonb),
    coalesce(v_snapshot->'evaluation_rubric','{}'::jsonb),
    coalesce(v_snapshot->'provenance','{}'::jsonb)||jsonb_build_object(
      'installed_from_agent_id',p_source_agent_id,
      'installed_from_skill_id',p_source_skill_id,
      'installed_from_version',p_source_version,
      'source_snapshot_digest',v_snapshot_digest,
      'license_terms_digest',v_terms_digest,
      'license_key',v_license
    ),
    1,'Installed from public Agent Skill; owner review required before publication.',
    v_terms,'draft'
  );

  insert into public.agent_skill_installations(
    agent_id,source_agent_id,source_skill_id,source_version,source_snapshot_digest,
    installed_skill_id,installed_by,installer_subject_ref,license_terms_snapshot,
    license_terms_digest,license_expires_at,idempotency_key
  ) values(
    p_agent_id,p_source_agent_id,p_source_skill_id,p_source_version,v_snapshot_digest,
    v_installed_skill_id,v_actor,encode(extensions.digest(v_actor::text,'sha256'),'hex'),
    v_terms,v_terms_digest,v_license_expiry,p_idempotency_key
  ) returning * into v_installation;

  insert into public.agent_skill_installation_events(
    installation_id,agent_id,source_agent_id,source_skill_id,event_type,actor_user_id,
    actor_subject_ref,source_version,source_snapshot_digest,license_terms_digest,details
  ) values(
    v_installation.id,p_agent_id,p_source_agent_id,p_source_skill_id,'installed',v_actor,
    encode(extensions.digest(v_actor::text,'sha256'),'hex'),p_source_version,
    v_snapshot_digest,v_terms_digest,jsonb_build_object('license_key',v_license,'installed_skill_id',v_installed_skill_id)
  );
  return jsonb_build_object('installation',to_jsonb(v_installation),'installed_skill_id',v_installed_skill_id,'idempotent_replay',false);
end;
$function$;

create or replace function public.revoke_agent_skill_installation(
  p_agent_id uuid,p_installation_id uuid,p_reason text
) returns jsonb
language plpgsql security definer set search_path=''
as $function$
declare v_actor uuid:=auth.uid(); v_installation public.agent_skill_installations%rowtype;
begin
  if v_actor is null or coalesce(auth.role(),'')<>'authenticated' then
    raise exception 'AUTHENTICATED_AGENT_OWNER_REQUIRED' using errcode='42501';
  end if;
  if not private.has_agent_ownership(p_agent_id,v_actor,'owner') then
    raise exception 'TARGET_AGENT_OWNER_REQUIRED' using errcode='42501';
  end if;
  if p_reason is null or char_length(btrim(p_reason))<8 or char_length(p_reason)>500 then
    raise exception 'SKILL_INSTALL_REVOCATION_REASON_REQUIRED' using errcode='22023';
  end if;
  update public.agent_skill_installations i
     set status='revoked',revoked_by=v_actor,revoked_at=clock_timestamp(),
         revocation_reason=btrim(p_reason),updated_at=clock_timestamp()
   where i.id=p_installation_id and i.agent_id=p_agent_id and i.status='active'
   returning * into v_installation;
  if not found then raise exception 'ACTIVE_SKILL_INSTALLATION_NOT_FOUND' using errcode='40400'; end if;
  insert into public.agent_skill_installation_events(
    installation_id,agent_id,source_agent_id,source_skill_id,event_type,actor_user_id,
    actor_subject_ref,source_version,source_snapshot_digest,license_terms_digest,details
  ) values(
    v_installation.id,v_installation.agent_id,v_installation.source_agent_id,v_installation.source_skill_id,
    'revoked',v_actor,encode(extensions.digest(v_actor::text,'sha256'),'hex'),
    v_installation.source_version,v_installation.source_snapshot_digest,v_installation.license_terms_digest,
    jsonb_build_object('reason',v_installation.revocation_reason,'installed_skill_id',v_installation.installed_skill_id)
  );
  return jsonb_build_object('installation',to_jsonb(v_installation),'runtime_authorized',false);
end;
$function$;

create or replace view public.agent_skill_publications as
select distinct on (v.skill_id)
  v.skill_id as id,v.agent_id,
  v.snapshot->>'slug' as slug,v.snapshot->>'name' as name,
  v.snapshot->>'description' as description,v.snapshot->>'category' as category,
  (v.snapshot->>'version')::integer as version,v.snapshot->>'status' as status,
  v.snapshot->'publication_terms' as publication_terms,
  nullif(v.snapshot->>'created_at','')::timestamptz as created_at,
  nullif(v.snapshot->>'updated_at','')::timestamptz as updated_at
from public.agent_skill_versions v
join public.agent_skills s on s.id=v.skill_id and s.agent_id=v.agent_id
join public.ai_agents a on a.id=v.agent_id
where v.snapshot->>'status'='published'
  and s.status<>'archived'
  and a.visibility='public' and a.status='active'
  and not exists (
    select 1 from public.agent_skill_installations i
     where i.installed_skill_id=v.skill_id
       and (i.status<>'active' or (i.license_expires_at is not null and i.license_expires_at<=clock_timestamp()))
  )
order by v.skill_id,(v.snapshot->>'version')::integer desc,v.created_at desc;

revoke all on function public.install_agent_skill(uuid,uuid,uuid,integer,boolean,text) from public,anon;
revoke all on function public.revoke_agent_skill_installation(uuid,uuid,text) from public,anon;
grant execute on function public.install_agent_skill(uuid,uuid,uuid,integer,boolean,text) to authenticated;
grant execute on function public.revoke_agent_skill_installation(uuid,uuid,text) to authenticated;

-- Account export/deletion preserve installed-license evidence and pseudonymize installer identity.
insert into private.account_export_sources(source_key,table_name,filter_kind,owner_columns,sort_order,enabled)
values
 ('agent_skill_installations','agent_skill_installations','owned_agents',array['agent_id'],74,true),
 ('agent_skill_installation_events','agent_skill_installation_events','owned_agents',array['agent_id'],75,true)
on conflict(source_key) do update set table_name=excluded.table_name,filter_kind=excluded.filter_kind,
 owner_columns=excluded.owner_columns,sort_order=excluded.sort_order,enabled=true;

insert into public.account_deletion_source_policies(
 source_key,data_class,deletion_action,dependency_order,policy_version,reason,approved_by,approved_at,active,
 table_name,filter_kind,owner_columns,decision_source,decision_reference
)
select v.source_key,'agent_operational','preserve',v.dependency_order,p.policy_version,v.reason,
 p.approved_by,p.approved_at,true,v.table_name,'owned_agents',array['agent_id'],
 p.decision_source,p.decision_reference
from (values
 ('agent_skill_installations','agent_skill_installations',74,
  'Installed Skill license acceptance and source-version binding are retained as Agent operational audit; installer identity is detached by SET NULL and represented by a subject hash.'),
 ('agent_skill_installation_events','agent_skill_installation_events',75,
  'Immutable Skill installation and revocation evidence is retained as pseudonymous Agent operational audit.')
) v(source_key,table_name,dependency_order,reason)
cross join lateral (select * from public.account_deletion_source_policies where source_key='agent_ownerships' limit 1) p
on conflict(source_key) do update set data_class=excluded.data_class,deletion_action=excluded.deletion_action,
 dependency_order=excluded.dependency_order,policy_version=excluded.policy_version,reason=excluded.reason,
 active=true,table_name=excluded.table_name,filter_kind=excluded.filter_kind,owner_columns=excluded.owner_columns,
 decision_source=excluded.decision_source,decision_reference=excluded.decision_reference,updated_at=clock_timestamp();

insert into public.account_deletion_dependency_rules(child_schema,child_table,constraint_name,fk_column,delete_rule,resolution_action,reason,active)
select 'public',t.relname,c.conname,a.attname,
 case c.confdeltype when 'c' then 'CASCADE' when 'n' then 'SET NULL' when 'r' then 'RESTRICT' else 'NO ACTION' end,
 case c.confdeltype when 'c' then 'database_cascade' when 'n' then 'database_set_null' else 'preserve_tombstone' end,
 'ENG-P06 Skill installation/license audit FK; preserve the source-version entitlement evidence and detach deleted installer identifiers.',
 true
from pg_constraint c
join pg_class t on t.oid=c.conrelid
join pg_namespace n on n.oid=t.relnamespace
join unnest(c.conkey) with ordinality k(attnum,ord) on true
join pg_attribute a on a.attrelid=t.oid and a.attnum=k.attnum
where n.nspname='public' and c.contype='f'
  and t.relname in ('agent_skill_installations','agent_skill_installation_events')
  and not exists(select 1 from public.account_deletion_dependency_rules r
    where r.child_schema='public' and r.child_table=t.relname and r.constraint_name=c.conname)
on conflict(child_schema,child_table,constraint_name) do update
set fk_column=excluded.fk_column,delete_rule=excluded.delete_rule,resolution_action=excluded.resolution_action,
 reason=excluded.reason,active=true;


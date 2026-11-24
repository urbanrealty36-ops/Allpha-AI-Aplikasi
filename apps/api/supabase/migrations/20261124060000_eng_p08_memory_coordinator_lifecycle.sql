-- ENG-P08: canonical owner-private Memory Coordinator persistence, governance and retrieval.
create table if not exists public.agent_memory_policies (
 id uuid primary key default gen_random_uuid(),
 owner_user_id uuid not null references auth.users(id) on delete cascade,
 agent_id uuid references public.ai_agents(id) on delete cascade,
 memory_type text not null check (memory_type in ('working','episodic','semantic','procedural','long_term')),
 enabled boolean not null default false,
 consent_version text,
 allowed_purposes text[] not null default '{}',
 allowed_sensitivities text[] not null default '{}',
 retention_days integer not null default 30 check (retention_days between 1 and 3650),
 policy_version integer not null default 1 check (policy_version > 0),
 consent_revoked_at timestamptz,
 created_at timestamptz not null default now(),
 updated_at timestamptz not null default now(),
 check (memory_type <> 'working' or retention_days = 1),
 check (not enabled or (consent_version = 'allpha.memory.v1' and cardinality(allowed_purposes) > 0 and cardinality(allowed_sensitivities) > 0))
);
create unique index if not exists agent_memory_policies_owner_agent_type_uq
 on public.agent_memory_policies(owner_user_id,agent_id,memory_type) where agent_id is not null;
create unique index if not exists agent_memory_policies_owner_personal_type_uq
 on public.agent_memory_policies(owner_user_id,memory_type) where agent_id is null;
create index if not exists agent_memory_policies_owner_agent_idx
 on public.agent_memory_policies(owner_user_id,agent_id);

create table if not exists public.agent_memory_items (
 id uuid primary key default gen_random_uuid(),
 owner_user_id uuid not null references auth.users(id) on delete cascade,
 agent_id uuid references public.ai_agents(id) on delete cascade,
 policy_id uuid references public.agent_memory_policies(id) on delete set null,
 memory_type text not null check (memory_type in ('working','episodic','semantic','procedural','long_term')),
 visibility_scope text not null check (visibility_scope in ('owner_private','agent_private')),
 purpose text not null check (purpose in ('agent_generation_context','agent_runtime_context','workflow_context','personalization_context')),
 classification text not null check (classification in ('public','internal','confidential','restricted')),
 content text not null check (char_length(content) <= 8000),
 content_sha256 text not null check (content_sha256 ~ '^[0-9a-f]{64}$'),
 source_ref jsonb not null default '{}',
 provenance jsonb not null default '{}',
 confidence numeric(5,4) check (confidence between 0 and 1),
 version integer not null default 1 check (version > 0),
 policy_version integer not null check (policy_version > 0),
 status text not null default 'pending' check (status in ('pending','active','rejected','expired')),
 retention_expires_at timestamptz not null,
 approved_at timestamptz,
 created_at timestamptz not null default now(),
 updated_at timestamptz not null default now()
);
create index if not exists agent_memory_items_owner_agent_status_idx
 on public.agent_memory_items(owner_user_id,agent_id,status,retention_expires_at);
create index if not exists agent_memory_items_policy_version_idx
 on public.agent_memory_items(policy_id,policy_version,status);
create index if not exists agent_memory_items_search_gin
 on public.agent_memory_items using gin(to_tsvector('simple',content));
create unique index if not exists agent_memory_items_generation_source_uq
 on public.agent_memory_items(owner_user_id,coalesce(agent_id,'00000000-0000-0000-0000-000000000000'::uuid),(source_ref->>'generation_job_id'))
 where source_ref ? 'generation_job_id';

create table if not exists public.agent_memory_events (
 id uuid primary key default gen_random_uuid(),
 owner_user_id uuid references auth.users(id) on delete set null,
 owner_subject_hash text not null,
 agent_id uuid references public.ai_agents(id) on delete set null,
 policy_id uuid references public.agent_memory_policies(id) on delete set null,
 item_id uuid references public.agent_memory_items(id) on delete set null,
 actor_user_id uuid references auth.users(id) on delete set null,
 event_type text not null check (event_type in ('policy_enabled','policy_disabled','proposal_created','proposal_approved','proposal_rejected','item_corrected','item_deleted','item_expired')),
 details jsonb not null default '{}',
 created_at timestamptz not null default now()
);
create index if not exists agent_memory_events_owner_created_idx
 on public.agent_memory_events(owner_user_id,created_at desc);
create index if not exists agent_memory_events_agent_created_idx
 on public.agent_memory_events(agent_id,created_at desc);

alter table public.agent_memory_policies enable row level security;
alter table public.agent_memory_items enable row level security;
alter table public.agent_memory_events enable row level security;
revoke all on public.agent_memory_policies,public.agent_memory_items,public.agent_memory_events from public,anon,authenticated;
grant select on public.agent_memory_policies,public.agent_memory_items,public.agent_memory_events to service_role;

create or replace function public.agent_memory_transition(
 p_action text,p_owner_user_id uuid,p_agent_id uuid,p_item_id uuid,p_payload jsonb
) returns jsonb
language plpgsql security definer set search_path=''
as $function$
declare
 v_policy public.agent_memory_policies%rowtype;
 v_item public.agent_memory_items%rowtype;
 v_memory_type text;
 v_enabled boolean;
 v_retention_days integer;
 v_purposes text[];
 v_sensitivities text[];
 v_decision text;
 v_content text;
 v_digest text;
 v_expired integer:=0;
 v_result jsonb;
 v_source_job text;
begin
 if p_action not in ('set_policy','expire','expire_all','create_proposal','decide','correct','delete') then
  raise exception 'MEMORY_ACTION_INVALID' using errcode='22023';
 end if;
 if p_action='expire_all' then
  with expired as (
   update public.agent_memory_items i set status='expired',content='',
    content_sha256=encode(extensions.digest('','sha256'),'hex'),
    source_ref='{}'::jsonb,provenance='{"retention":"expired"}'::jsonb,
    confidence=null,updated_at=clock_timestamp()
   where i.status in ('pending','active') and i.retention_expires_at<=clock_timestamp()
   returning i.id,i.owner_user_id,i.agent_id,i.policy_id,i.memory_type,i.purpose,i.classification,i.version
  ), events as (
   insert into public.agent_memory_events(owner_user_id,owner_subject_hash,agent_id,policy_id,item_id,actor_user_id,event_type,details)
   select e.owner_user_id,encode(extensions.digest(e.owner_user_id::text,'sha256'),'hex'),e.agent_id,e.policy_id,e.id,null,
    'item_expired',jsonb_build_object('memory_type',e.memory_type,'purpose',e.purpose,'classification',e.classification,'version',e.version)
   from expired e returning id
  )
  select count(*) into v_expired from expired;
  return jsonb_build_object('expired_count',v_expired);
 end if;
 if p_owner_user_id is null then
  raise exception 'MEMORY_OWNER_REQUIRED' using errcode='42501';
 end if;

 if p_action in ('decide','correct','delete') then
  if p_item_id is null then raise exception 'MEMORY_ITEM_REQUIRED' using errcode='22023'; end if;
  select * into v_item from public.agent_memory_items i
   where i.id=p_item_id and i.owner_user_id=p_owner_user_id for update;
  if not found then return null; end if;
  if v_item.agent_id is not null and not exists(
   select 1 from public.agent_ownerships o where o.agent_id=v_item.agent_id
    and o.owner_user_id=p_owner_user_id and o.ownership_role='owner' and o.status='active'
  ) then raise exception 'AGENT_OWNER_REQUIRED' using errcode='42501'; end if;
  p_agent_id:=v_item.agent_id;
 end if;

 if p_agent_id is not null and not exists(
  select 1 from public.agent_ownerships o where o.agent_id=p_agent_id
   and o.owner_user_id=p_owner_user_id and o.ownership_role='owner' and o.status='active'
 ) then raise exception 'AGENT_OWNER_REQUIRED' using errcode='42501'; end if;

 if p_action='set_policy' then
  v_memory_type:=p_payload->>'memory_type';
  v_enabled:=coalesce((p_payload->>'enabled')::boolean,false);
  v_retention_days:=coalesce((p_payload->>'retention_days')::integer,30);
  if v_memory_type not in ('working','episodic','semantic','procedural','long_term')
     or v_retention_days not between 1 and 3650
     or (v_memory_type='working' and v_retention_days<>1) then
   raise exception 'MEMORY_POLICY_INVALID' using errcode='23514';
  end if;
  if jsonb_typeof(coalesce(p_payload->'allowed_purposes','[]'::jsonb))<>'array'
     or jsonb_typeof(coalesce(p_payload->'allowed_sensitivities','[]'::jsonb))<>'array' then
   raise exception 'MEMORY_POLICY_ARRAY_INVALID' using errcode='22023';
  end if;
  select coalesce(array_agg(distinct value order by value),'{}'::text[]) into v_purposes
   from jsonb_array_elements_text(coalesce(p_payload->'allowed_purposes','[]'::jsonb)) t(value);
  select coalesce(array_agg(distinct value order by value),'{}'::text[]) into v_sensitivities
   from jsonb_array_elements_text(coalesce(p_payload->'allowed_sensitivities','[]'::jsonb)) t(value);
  if v_enabled and (
   coalesce(p_payload->>'consent_version','')<>'allpha.memory.v1'
   or cardinality(v_purposes)=0 or cardinality(v_sensitivities)=0
   or exists(select 1 from unnest(v_purposes) x where x not in ('agent_generation_context','agent_runtime_context','workflow_context','personalization_context'))
   or exists(select 1 from unnest(v_sensitivities) x where x not in ('public','internal','confidential','restricted'))
  ) then raise exception 'MEMORY_CONSENT_OR_SCOPE_INVALID' using errcode='42501'; end if;
  perform pg_advisory_xact_lock(hashtextextended(
   p_owner_user_id::text||':'||coalesce(p_agent_id::text,'personal')||':'||v_memory_type,0));
  select * into v_policy from public.agent_memory_policies p
   where p.owner_user_id=p_owner_user_id and p.agent_id is not distinct from p_agent_id
    and p.memory_type=v_memory_type for update;
  if not found then
   insert into public.agent_memory_policies(owner_user_id,agent_id,memory_type,enabled,consent_version,allowed_purposes,allowed_sensitivities,retention_days,policy_version,consent_revoked_at)
   values(p_owner_user_id,p_agent_id,v_memory_type,v_enabled,
    case when v_enabled then 'allpha.memory.v1' else null end,
    case when v_enabled then v_purposes else '{}'::text[] end,
    case when v_enabled then v_sensitivities else '{}'::text[] end,
    v_retention_days,1,case when v_enabled then null else clock_timestamp() end)
   returning * into v_policy;
  elsif v_policy.enabled is distinct from v_enabled
     or v_policy.allowed_purposes is distinct from case when v_enabled then v_purposes else '{}'::text[] end
     or v_policy.allowed_sensitivities is distinct from case when v_enabled then v_sensitivities else '{}'::text[] end
     or v_policy.retention_days is distinct from v_retention_days
     or v_policy.consent_version is distinct from case when v_enabled then 'allpha.memory.v1' else null end
     or (v_enabled and v_policy.consent_revoked_at is not null)
     or (not v_enabled and v_policy.consent_revoked_at is null) then
   update public.agent_memory_policies set enabled=v_enabled,
    consent_version=case when v_enabled then 'allpha.memory.v1' else null end,
    allowed_purposes=case when v_enabled then v_purposes else '{}'::text[] end,
    allowed_sensitivities=case when v_enabled then v_sensitivities else '{}'::text[] end,
    retention_days=v_retention_days,policy_version=policy_version+1,
    consent_revoked_at=case when v_enabled then null else clock_timestamp() end,
    updated_at=clock_timestamp()
   where id=v_policy.id returning * into v_policy;
  end if;
  insert into public.agent_memory_events(owner_user_id,owner_subject_hash,agent_id,policy_id,actor_user_id,event_type,details)
  values(p_owner_user_id,encode(extensions.digest(p_owner_user_id::text,'sha256'),'hex'),p_agent_id,v_policy.id,p_owner_user_id,
   case when v_enabled then 'policy_enabled' else 'policy_disabled' end,
   jsonb_build_object('memory_type',v_memory_type,'policy_version',v_policy.policy_version,'retention_days',v_retention_days));
  return to_jsonb(v_policy);
 end if;

 if p_action='expire' then
  with expired as (
   update public.agent_memory_items i set status='expired',content='',
    content_sha256=encode(extensions.digest('','sha256'),'hex'),
    source_ref='{}'::jsonb,provenance='{"retention":"expired"}'::jsonb,
    confidence=null,updated_at=clock_timestamp()
   where i.owner_user_id=p_owner_user_id and i.agent_id is not distinct from p_agent_id
    and i.status in ('pending','active') and i.retention_expires_at<=clock_timestamp()
   returning i.id,i.owner_user_id,i.agent_id,i.policy_id,i.memory_type,i.purpose,i.classification,i.version
  ), events as (
   insert into public.agent_memory_events(owner_user_id,owner_subject_hash,agent_id,policy_id,item_id,actor_user_id,event_type,details)
   select e.owner_user_id,encode(extensions.digest(e.owner_user_id::text,'sha256'),'hex'),e.agent_id,e.policy_id,e.id,p_owner_user_id,
    'item_expired',jsonb_build_object('memory_type',e.memory_type,'purpose',e.purpose,'classification',e.classification,'version',e.version)
   from expired e returning id
  )
  select count(*) into v_expired from expired;
  return jsonb_build_object('expired_count',v_expired);
 end if;

 if p_action='create_proposal' then
  v_memory_type:=p_payload->>'memory_type';
  select * into v_policy from public.agent_memory_policies p
   where p.owner_user_id=p_owner_user_id and p.agent_id is not distinct from p_agent_id
    and p.memory_type=v_memory_type for update;
  if not found or not v_policy.enabled or v_policy.consent_version<>'allpha.memory.v1'
     or v_policy.consent_revoked_at is not null
     or not (p_payload->>'purpose'=any(v_policy.allowed_purposes))
     or not (p_payload->>'classification'=any(v_policy.allowed_sensitivities))
     or v_policy.policy_version<=0 then
   raise exception 'MEMORY_POLICY_DENIED' using errcode='42501';
  end if;
  v_content:=p_payload->>'content';
  v_digest:=encode(extensions.digest(v_content,'sha256'),'hex');
  if v_content is null or char_length(v_content)=0 or char_length(v_content)>8000
     or p_payload->>'content_sha256'<>v_digest then
   raise exception 'MEMORY_CONTENT_INVALID' using errcode='22023';
  end if;
  if (p_payload->>'retention_expires_at')::timestamptz<=clock_timestamp()
     or (p_payload->>'retention_expires_at')::timestamptz>clock_timestamp()+make_interval(days=>v_policy.retention_days) then
   raise exception 'MEMORY_RETENTION_INVALID' using errcode='22023';
  end if;
  insert into public.agent_memory_items(owner_user_id,agent_id,policy_id,memory_type,visibility_scope,purpose,classification,content,content_sha256,source_ref,provenance,confidence,policy_version,retention_expires_at)
  values(p_owner_user_id,p_agent_id,v_policy.id,v_memory_type,
   case when p_agent_id is null then 'owner_private' else 'agent_private' end,
   p_payload->>'purpose',p_payload->>'classification',v_content,v_digest,
   coalesce(p_payload->'source_ref','{}'::jsonb),coalesce(p_payload->'provenance','{}'::jsonb),
   nullif(p_payload->>'confidence','')::numeric,v_policy.policy_version,(p_payload->>'retention_expires_at')::timestamptz)
  on conflict do nothing returning * into v_item;
  if v_item.id is null then
   v_source_job:=p_payload->'source_ref'->>'generation_job_id';
   if v_source_job is null then raise exception 'MEMORY_PROPOSAL_CONFLICT' using errcode='23505'; end if;
   select * into v_item from public.agent_memory_items i where i.owner_user_id=p_owner_user_id
    and i.agent_id is not distinct from p_agent_id and i.source_ref->>'generation_job_id'=v_source_job limit 1;
  end if;
  insert into public.agent_memory_events(owner_user_id,owner_subject_hash,agent_id,policy_id,item_id,actor_user_id,event_type,details)
  values(p_owner_user_id,encode(extensions.digest(p_owner_user_id::text,'sha256'),'hex'),p_agent_id,v_policy.id,v_item.id,p_owner_user_id,
   'proposal_created',jsonb_build_object('memory_type',v_memory_type,'purpose',p_payload->>'purpose','classification',p_payload->>'classification','content_sha256',v_digest));
  return to_jsonb(v_item);
 end if;

 if p_action='decide' then
  v_decision:=p_payload->>'decision';
  if v_decision is null or v_decision not in ('approve','reject') then raise exception 'MEMORY_DECISION_INVALID' using errcode='22023'; end if;
  select * into v_policy from public.agent_memory_policies p where p.id=v_item.policy_id for update;
  if v_decision='approve' and (
   not found or not v_policy.enabled or v_policy.consent_version<>'allpha.memory.v1'
   or v_policy.consent_revoked_at is not null or v_item.policy_version<>v_policy.policy_version
   or v_item.retention_expires_at<=clock_timestamp()
  ) then raise exception 'MEMORY_POLICY_DENIED' using errcode='42501'; end if;
  if v_item.status<>'pending' then return null; end if;
  update public.agent_memory_items set status=case when v_decision='approve' then 'active' else 'rejected' end,
   approved_at=case when v_decision='approve' then clock_timestamp() else null end,updated_at=clock_timestamp()
  where id=v_item.id returning * into v_item;
  insert into public.agent_memory_events(owner_user_id,owner_subject_hash,agent_id,policy_id,item_id,actor_user_id,event_type,details)
  values(p_owner_user_id,encode(extensions.digest(p_owner_user_id::text,'sha256'),'hex'),v_item.agent_id,v_item.policy_id,v_item.id,p_owner_user_id,
   case when v_decision='approve' then 'proposal_approved' else 'proposal_rejected' end,
   jsonb_build_object('memory_type',v_item.memory_type,'policy_version',v_item.policy_version));
  return jsonb_build_object('id',v_item.id,'status',v_item.status);
 end if;

 if p_action='correct' then
  select * into v_policy from public.agent_memory_policies p where p.id=v_item.policy_id for update;
  if not found or not v_policy.enabled or v_policy.consent_revoked_at is not null
     or v_item.policy_version<>v_policy.policy_version or v_item.status<>'active'
     or v_item.retention_expires_at<=clock_timestamp() then
   raise exception 'MEMORY_POLICY_DENIED' using errcode='42501';
  end if;
  v_content:=p_payload->>'content';
  if v_content is null or char_length(v_content)=0 or char_length(v_content)>8000 then
   raise exception 'MEMORY_CONTENT_INVALID' using errcode='22023';
  end if;
  v_digest:=encode(extensions.digest(v_content,'sha256'),'hex');
  update public.agent_memory_items set content=v_content,content_sha256=v_digest,version=version+1,updated_at=clock_timestamp()
  where id=v_item.id returning * into v_item;
  insert into public.agent_memory_events(owner_user_id,owner_subject_hash,agent_id,policy_id,item_id,actor_user_id,event_type,details)
  values(p_owner_user_id,encode(extensions.digest(p_owner_user_id::text,'sha256'),'hex'),v_item.agent_id,v_item.policy_id,v_item.id,p_owner_user_id,
   'item_corrected',jsonb_build_object('memory_type',v_item.memory_type,'version',v_item.version,'content_sha256',v_digest));
  return jsonb_build_object('id',v_item.id,'status','corrected');
 end if;

 if p_action='delete' then
  insert into public.agent_memory_events(owner_user_id,owner_subject_hash,agent_id,policy_id,item_id,actor_user_id,event_type,details)
  values(p_owner_user_id,encode(extensions.digest(p_owner_user_id::text,'sha256'),'hex'),v_item.agent_id,v_item.policy_id,v_item.id,p_owner_user_id,
   'item_deleted',jsonb_build_object('memory_type',v_item.memory_type,'purpose',v_item.purpose,'classification',v_item.classification,'version',v_item.version));
  delete from public.agent_memory_items where id=v_item.id;
  return jsonb_build_object('id',v_item.id,'status','deleted');
 end if;

 raise exception 'MEMORY_ACTION_UNHANDLED' using errcode='22023';
end;
$function$;

create or replace function public.agent_memory_search(
 p_owner_user_id uuid,p_agent_id uuid,p_policy_ids uuid[],p_purpose text,
 p_allowed_sensitivities text[],p_query text,p_max_sensitivity text,p_limit integer
) returns table(
 id uuid,policy_id uuid,memory_type text,purpose text,classification text,
 content text,content_sha256 text,source_ref jsonb,provenance jsonb,
 confidence numeric,version integer,policy_version integer,
 retention_expires_at timestamptz,created_at timestamptz,retrieval_score real
)
language plpgsql stable security definer set search_path=''
as $function$
declare v_query tsquery;
begin
 if p_owner_user_id is null or p_agent_id is null then return; end if;
 if not exists(select 1 from public.agent_ownerships o where o.agent_id=p_agent_id
  and o.owner_user_id=p_owner_user_id and o.ownership_role='owner' and o.status='active') then
  raise exception 'AGENT_OWNER_REQUIRED' using errcode='42501';
 end if;
 if p_purpose not in ('agent_generation_context','agent_runtime_context','workflow_context','personalization_context')
    or coalesce(array_length(p_policy_ids,1),0)=0
    or coalesce(array_length(p_allowed_sensitivities,1),0)=0
    or p_limit not between 1 and 30 then
  raise exception 'MEMORY_SEARCH_ARGUMENTS_INVALID' using errcode='22023';
 end if;
 if p_query is not null and btrim(p_query)<>'' then
  v_query:=plainto_tsquery('simple',left(btrim(p_query),300));
 end if;
 return query
 select i.id,i.policy_id,i.memory_type,i.purpose,i.classification,i.content,i.content_sha256,
  i.source_ref,i.provenance,i.confidence,i.version,i.policy_version,i.retention_expires_at,i.created_at,
  case when v_query is null then 0::real else ts_rank(to_tsvector('simple',i.content),v_query) end::real
 from public.agent_memory_items i
 join public.agent_memory_policies p on p.id=i.policy_id
 where i.owner_user_id=p_owner_user_id and i.agent_id=p_agent_id
  and i.policy_id=any(p_policy_ids) and i.purpose=p_purpose
  and i.classification=any(p_allowed_sensitivities)
  and (p_max_sensitivity is null or
   case i.classification when 'public' then 1 when 'internal' then 2 when 'confidential' then 3 when 'restricted' then 4 else 99 end
   <= case p_max_sensitivity when 'public' then 1 when 'internal' then 2 when 'confidential' then 3 when 'restricted' then 4 else 0 end)
  and i.status='active' and i.retention_expires_at>clock_timestamp()
  and p.enabled and p.consent_version='allpha.memory.v1' and p.consent_revoked_at is null
  and i.policy_version=p.policy_version and p.allowed_purposes @> array[p_purpose]::text[]
  and p.allowed_sensitivities @> array[i.classification]::text[]
  and (v_query is null or to_tsvector('simple',i.content) @@ v_query)
 order by
  case when v_query is null then 0 else ts_rank(to_tsvector('simple',i.content),v_query) end desc,
  i.created_at desc
 limit p_limit;
end;
$function$;

revoke all on function public.agent_memory_transition(text,uuid,uuid,uuid,jsonb) from public,anon,authenticated;
revoke all on function public.agent_memory_search(uuid,uuid,uuid[],text,text[],text,text,integer) from public,anon,authenticated;
grant execute on function public.agent_memory_transition(text,uuid,uuid,uuid,jsonb) to service_role;
grant execute on function public.agent_memory_search(uuid,uuid,uuid[],text,text[],text,text,integer) to service_role;

insert into private.account_export_sources(source_key,table_name,filter_kind,owner_columns,sort_order,enabled)
values
 ('agent_memory_policies','agent_memory_policies','owner_columns',array['owner_user_id'],203,true),
 ('agent_memory_items','agent_memory_items','owner_columns',array['owner_user_id'],204,true),
 ('agent_memory_events','agent_memory_events','owner_columns',array['owner_user_id'],205,true)
on conflict(source_key) do update set table_name=excluded.table_name,filter_kind=excluded.filter_kind,
 owner_columns=excluded.owner_columns,sort_order=excluded.sort_order,enabled=true;

insert into public.account_deletion_source_policies(
 source_key,data_class,deletion_action,dependency_order,policy_version,reason,active,
 table_name,filter_kind,owner_columns,decision_source,decision_reference
) values
 ('agent_memory_policies','owner_private','delete_rows',78,'owner-directive-2026-11-24-v1',
  'Owner Memory policies and consent are removed with the account; immutable policy transition evidence remains in the event stream.',
  true,'agent_memory_policies','owner_columns',array['owner_user_id'],'product_owner_directive',
  'Allpha Master PRD v3.1.0 §§27-30, 74; owner-directed private data deletion'),
 ('agent_memory_items','owner_private','delete_rows',79,'owner-directive-2026-11-24-v1',
  'Owner-private Memory content and derived context are removed with the account; item events retain only pseudonymous non-content evidence.',
  true,'agent_memory_items','owner_columns',array['owner_user_id'],'product_owner_directive',
  'Allpha Master PRD v3.1.0 §§27-30, 74; owner-directed private data deletion'),
 ('agent_memory_events','agent_operational','preserve',90,'owner-directive-2026-11-24-v1',
  'Memory governance events are retained as non-content operational evidence; owner and actor foreign keys are detached and owner_subject_hash remains.',
  true,'agent_memory_events','owner_columns',array['owner_user_id'],'product_owner_directive',
  'Allpha Master PRD v3.1.0 §§27-30, 74; pseudonymous operational audit retention')
on conflict(source_key) do update set data_class=excluded.data_class,deletion_action=excluded.deletion_action,
 dependency_order=excluded.dependency_order,policy_version=excluded.policy_version,reason=excluded.reason,
 active=true,table_name=excluded.table_name,filter_kind=excluded.filter_kind,owner_columns=excluded.owner_columns,
 decision_source=excluded.decision_source,decision_reference=excluded.decision_reference,updated_at=clock_timestamp();

notify pgrst,'reload schema';

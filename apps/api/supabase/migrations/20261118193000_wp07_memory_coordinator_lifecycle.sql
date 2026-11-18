-- WP-07 Memory Coordinator lifecycle and retrieval persistence.
-- Source-only migration. Apply only through the approved ENG-P37 migration campaign;
-- do not run against the canonical production database as a test.
begin;

create table if not exists public.agent_memory_policies (
  id uuid primary key default gen_random_uuid(),
  owner_user_id uuid not null references auth.users(id) on delete cascade,
  agent_id uuid references public.ai_agents(id) on delete cascade,
  memory_type text not null check (memory_type in ('working','episodic','semantic','procedural','long_term')),
  enabled boolean not null default false,
  consent_version text,
  consent_revoked_at timestamptz,
  allowed_purposes text[] not null default '{}',
  allowed_sensitivities text[] not null default '{}',
  retention_days integer not null default 30 check (retention_days between 1 and 3650),
  policy_version integer not null default 1 check (policy_version > 0),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique nulls not distinct (owner_user_id, agent_id, memory_type),
  check (memory_type <> 'working' or retention_days = 1),
  check (not enabled or (consent_version = 'allpha.memory.v1'
    and cardinality(allowed_purposes) > 0 and cardinality(allowed_sensitivities) > 0))
);
create index if not exists agent_memory_policies_owner_agent_idx
  on public.agent_memory_policies(owner_user_id, agent_id, memory_type);

create table if not exists public.agent_memory_items (
  id uuid primary key default gen_random_uuid(),
  owner_user_id uuid not null references auth.users(id) on delete cascade,
  agent_id uuid references public.ai_agents(id) on delete cascade,
  policy_id uuid not null references public.agent_memory_policies(id) on delete restrict,
  memory_type text not null check (memory_type in ('working','episodic','semantic','procedural','long_term')),
  visibility_scope text not null check (visibility_scope in ('owner','agent')),
  purpose text not null check (purpose in ('agent_generation_context','agent_runtime_context','workflow_context','personalization_context')),
  classification text not null check (classification in ('public','internal','confidential','restricted')),
  content text not null,
  content_sha256 text not null check (content_sha256 ~ '^[0-9a-f]{64}$'),
  source_ref jsonb not null default '{}'::jsonb check (jsonb_typeof(source_ref)='object'),
  provenance jsonb not null default '{}'::jsonb check (jsonb_typeof(provenance)='object'),
  confidence double precision check (confidence is null or (confidence >= 0 and confidence <= 1)),
  version integer not null default 1 check (version > 0),
  policy_version integer not null check (policy_version > 0),
  status text not null default 'proposed' check (status in ('proposed','active','rejected','expired','deleted')),
  retention_expires_at timestamptz not null,
  approved_at timestamptz,
  deleted_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check ((agent_id is null and visibility_scope='owner') or (agent_id is not null and visibility_scope='agent')),
  check (status <> 'active' or approved_at is not null)
);
create index if not exists agent_memory_items_owner_scope_idx
  on public.agent_memory_items(owner_user_id, agent_id, status, created_at desc);
create index if not exists agent_memory_items_expiry_idx
  on public.agent_memory_items(retention_expires_at)
  where status in ('proposed','active');
create index if not exists agent_memory_items_search_idx
  on public.agent_memory_items using gin(to_tsvector('simple'::regconfig, content));
create unique index if not exists agent_memory_items_generation_source_unique
  on public.agent_memory_items(owner_user_id, agent_id, (source_ref->>'generation_job_id'))
  where source_ref ? 'generation_job_id';

create table if not exists public.agent_memory_events (
  id uuid primary key default gen_random_uuid(),
  owner_user_id uuid not null references auth.users(id) on delete cascade,
  agent_id uuid references public.ai_agents(id) on delete cascade,
  policy_id uuid references public.agent_memory_policies(id) on delete set null,
  item_id uuid references public.agent_memory_items(id) on delete set null,
  actor_user_id uuid references auth.users(id) on delete set null,
  event_type text not null check (event_type in (
    'policy_enabled','policy_disabled','proposal_created','proposal_approved',
    'proposal_rejected','item_corrected','item_deleted','item_expired'
  )),
  details jsonb not null default '{}'::jsonb check (jsonb_typeof(details)='object'),
  created_at timestamptz not null default now()
);
create index if not exists agent_memory_events_owner_created_idx
  on public.agent_memory_events(owner_user_id, created_at desc);

alter table public.agent_memory_policies enable row level security;
alter table public.agent_memory_items enable row level security;
alter table public.agent_memory_events enable row level security;
revoke all on public.agent_memory_policies, public.agent_memory_items, public.agent_memory_events from public, anon, authenticated;
grant select, insert, update, delete on public.agent_memory_policies, public.agent_memory_items, public.agent_memory_events to service_role;

create or replace function public.agent_memory_transition(
  p_action text,
  p_owner_user_id uuid,
  p_agent_id uuid default null,
  p_item_id uuid default null,
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  policy_row public.agent_memory_policies%rowtype;
  item_row public.agent_memory_items%rowtype;
  result_row public.agent_memory_items%rowtype;
  v_memory_type text;
  v_enabled boolean;
  v_consent text;
  v_purposes text[];
  v_sensitivities text[];
  v_retention integer;
  v_now timestamptz := now();
  v_count integer := 0;
begin
  if p_action not in ('set_policy','create_proposal','decide','correct','delete','expire','expire_all') then
    raise exception 'unsupported memory transition' using errcode='22023';
  end if;
  if p_action <> 'expire_all' and p_owner_user_id is null then
    raise exception 'owner is required' using errcode='22023';
  end if;
  if p_action in ('set_policy','create_proposal') and p_agent_id is not null
     and not exists (
       select 1 from public.agent_ownerships o
       where o.agent_id=p_agent_id and o.owner_user_id=p_owner_user_id
         and o.status='active' and o.ownership_role='owner'
     ) then
    raise exception 'active agent ownership required' using errcode='42501';
  end if;

  if p_action='set_policy' then
    v_memory_type := p_payload->>'memory_type';
    v_enabled := coalesce((p_payload->>'enabled')::boolean,false);
    v_consent := nullif(p_payload->>'consent_version','');
    v_purposes := coalesce(array(select jsonb_array_elements_text(coalesce(p_payload->'allowed_purposes','[]'::jsonb))), '{}');
    v_sensitivities := coalesce(array(select jsonb_array_elements_text(coalesce(p_payload->'allowed_sensitivities','[]'::jsonb))), '{}');
    v_retention := coalesce((p_payload->>'retention_days')::integer,30);
    if v_memory_type not in ('working','episodic','semantic','procedural','long_term')
       or v_retention not between 1 and 3650
       or (v_memory_type='working' and v_retention<>1) then
      raise exception 'invalid memory policy' using errcode='22023';
    end if;
    if v_enabled and (v_consent<>'allpha.memory.v1'
       or cardinality(v_purposes)=0
       or not (v_purposes <@ array['agent_generation_context','agent_runtime_context','workflow_context','personalization_context'])
       or cardinality(v_sensitivities)=0
       or not (v_sensitivities <@ array['public','internal','confidential','restricted'])) then
      raise exception 'explicit current consent and valid scopes are required' using errcode='42501';
    end if;
    insert into public.agent_memory_policies(
      owner_user_id,agent_id,memory_type,enabled,consent_version,consent_revoked_at,
      allowed_purposes,allowed_sensitivities,retention_days
    ) values (
      p_owner_user_id,p_agent_id,v_memory_type,v_enabled,
      case when v_enabled then v_consent else null end,
      case when v_enabled then null else v_now end,
      case when v_enabled then v_purposes else '{}' end,
      case when v_enabled then v_sensitivities else '{}' end,
      v_retention
    )
    on conflict (owner_user_id,agent_id,memory_type) do update set
      enabled=excluded.enabled, consent_version=excluded.consent_version,
      consent_revoked_at=excluded.consent_revoked_at,
      allowed_purposes=excluded.allowed_purposes,
      allowed_sensitivities=excluded.allowed_sensitivities,
      retention_days=excluded.retention_days,
      policy_version=public.agent_memory_policies.policy_version+1,
      updated_at=v_now
    returning * into policy_row;
    insert into public.agent_memory_events(owner_user_id,agent_id,policy_id,actor_user_id,event_type,details)
    values(p_owner_user_id,p_agent_id,policy_row.id,p_owner_user_id,
      case when v_enabled then 'policy_enabled' else 'policy_disabled' end,
      jsonb_build_object('memory_type',v_memory_type,'policy_version',policy_row.policy_version));
    return to_jsonb(policy_row);
  end if;

  if p_action='create_proposal' then
    select * into policy_row from public.agent_memory_policies
    where id=(p_payload->>'policy_id')::uuid
      and owner_user_id=p_owner_user_id
      and agent_id is not distinct from p_agent_id
    for update;
    if not found or not policy_row.enabled or policy_row.consent_version<>'allpha.memory.v1'
       or policy_row.consent_revoked_at is not null then
      raise exception 'memory consent is not active' using errcode='42501';
    end if;
    v_memory_type := p_payload->>'memory_type';
    if v_memory_type<>policy_row.memory_type
       or not ((p_payload->>'purpose')=any(policy_row.allowed_purposes))
       or not ((p_payload->>'classification')=any(policy_row.allowed_sensitivities))
       or length(coalesce(p_payload->>'content','')) not between 1 and 8000 then
      raise exception 'proposal is outside the approved memory policy' using errcode='42501';
    end if;
    insert into public.agent_memory_items(
      owner_user_id,agent_id,policy_id,memory_type,visibility_scope,purpose,classification,
      content,content_sha256,source_ref,provenance,confidence,policy_version,retention_expires_at
    ) values (
      p_owner_user_id,p_agent_id,policy_row.id,v_memory_type,
      case when p_agent_id is null then 'owner' else 'agent' end,
      p_payload->>'purpose',p_payload->>'classification',p_payload->>'content',
      p_payload->>'content_sha256',coalesce(p_payload->'source_ref','{}'::jsonb),
      coalesce(p_payload->'provenance','{}'::jsonb),
      nullif(p_payload->>'confidence','')::double precision,policy_row.policy_version,
      least(coalesce(nullif(p_payload->>'retention_expires_at','')::timestamptz,
                    v_now+make_interval(days=>policy_row.retention_days)),
            v_now+make_interval(days=>policy_row.retention_days))
    ) returning * into result_row;
    insert into public.agent_memory_events(owner_user_id,agent_id,policy_id,item_id,actor_user_id,event_type,details)
    values(p_owner_user_id,p_agent_id,policy_row.id,result_row.id,p_owner_user_id,'proposal_created',
      jsonb_build_object('memory_type',v_memory_type,'purpose',result_row.purpose,'classification',result_row.classification));
    return to_jsonb(result_row);
  end if;

  if p_action in ('decide','correct','delete') then
    select * into item_row from public.agent_memory_items
    where id=p_item_id and owner_user_id=p_owner_user_id
    for update;
    if not found then return null; end if;
    select * into policy_row from public.agent_memory_policies
    where id=item_row.policy_id and owner_user_id=p_owner_user_id
    for update;
  end if;

  if p_action='decide' then
    if item_row.status<>'proposed' or item_row.retention_expires_at<=v_now then return null; end if;
    if p_payload->>'decision'='approve' then
      if not found or not policy_row.enabled or policy_row.consent_revoked_at is not null
         or policy_row.consent_version<>'allpha.memory.v1'
         or policy_row.policy_version<>item_row.policy_version
         or not (item_row.purpose=any(policy_row.allowed_purposes))
         or not (item_row.classification=any(policy_row.allowed_sensitivities)) then
        raise exception 'current owner memory policy no longer permits this proposal' using errcode='42501';
      end if;
      update public.agent_memory_items set status='active',approved_at=v_now,updated_at=v_now
      where id=p_item_id returning * into result_row;
      insert into public.agent_memory_events(owner_user_id,agent_id,policy_id,item_id,actor_user_id,event_type,details)
      values(p_owner_user_id,item_row.agent_id,item_row.policy_id,p_item_id,p_owner_user_id,'proposal_approved',
        jsonb_build_object('version',result_row.version));
    elsif p_payload->>'decision'='reject' then
      update public.agent_memory_items set status='rejected',updated_at=v_now
      where id=p_item_id returning * into result_row;
      insert into public.agent_memory_events(owner_user_id,agent_id,policy_id,item_id,actor_user_id,event_type,details)
      values(p_owner_user_id,item_row.agent_id,item_row.policy_id,p_item_id,p_owner_user_id,'proposal_rejected','{}'::jsonb);
    else
      raise exception 'invalid memory decision' using errcode='22023';
    end if;
    return to_jsonb(result_row);
  end if;

  if p_action='correct' then
    if item_row.status<>'active' or not found or not policy_row.enabled
       or policy_row.consent_revoked_at is not null
       or policy_row.policy_version<>item_row.policy_version
       or length(coalesce(p_payload->>'content','')) not between 1 and 8000 then
      return null;
    end if;
    update public.agent_memory_items set content=p_payload->>'content',
      content_sha256=p_payload->>'content_sha256',version=version+1,updated_at=v_now
    where id=p_item_id returning * into result_row;
    insert into public.agent_memory_events(owner_user_id,agent_id,policy_id,item_id,actor_user_id,event_type,details)
    values(p_owner_user_id,item_row.agent_id,item_row.policy_id,p_item_id,p_owner_user_id,'item_corrected',
      jsonb_build_object('version',result_row.version));
    return to_jsonb(result_row);
  end if;

  if p_action='delete' then
    if item_row.status='deleted' then return to_jsonb(item_row); end if;
    update public.agent_memory_items set status='deleted',content='',content_sha256='e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
      source_ref='{}'::jsonb,provenance='{}'::jsonb,deleted_at=v_now,updated_at=v_now
    where id=p_item_id returning * into result_row;
    insert into public.agent_memory_events(owner_user_id,agent_id,policy_id,item_id,actor_user_id,event_type,details)
    values(p_owner_user_id,item_row.agent_id,item_row.policy_id,p_item_id,p_owner_user_id,'item_deleted',
      jsonb_build_object('previous_version',item_row.version));
    return to_jsonb(result_row);
  end if;

  if p_action='expire' then
    with expired as (
      update public.agent_memory_items set status='expired',updated_at=v_now
      where owner_user_id=p_owner_user_id and agent_id is not distinct from p_agent_id
        and status in ('proposed','active') and retention_expires_at<=v_now
      returning id,owner_user_id,agent_id,policy_id
    )
    insert into public.agent_memory_events(owner_user_id,agent_id,policy_id,item_id,event_type,details)
    select owner_user_id,agent_id,policy_id,id,'item_expired','{}'::jsonb from expired;
    get diagnostics v_count = row_count;
    return jsonb_build_object('expired_count',v_count);
  end if;

  if p_action='expire_all' then
    with expired as (
      update public.agent_memory_items set status='expired',updated_at=v_now
      where status in ('proposed','active') and retention_expires_at<=v_now
      returning id,owner_user_id,agent_id,policy_id
    )
    insert into public.agent_memory_events(owner_user_id,agent_id,policy_id,item_id,event_type,details)
    select owner_user_id,agent_id,policy_id,id,'item_expired','{}'::jsonb from expired;
    get diagnostics v_count = row_count;
    return jsonb_build_object('expired_count',v_count);
  end if;

  return null;
end;
$$;

create or replace function public.agent_memory_search(
  p_owner_user_id uuid,
  p_agent_id uuid,
  p_policy_ids uuid[],
  p_purpose text,
  p_allowed_sensitivities text[],
  p_query text default null,
  p_max_sensitivity text default null,
  p_limit integer default 12
)
returns table (
  id uuid, policy_id uuid, agent_id uuid, memory_type text, visibility_scope text,
  purpose text, classification text, content text, content_sha256 text,
  source_ref jsonb, provenance jsonb, confidence double precision, version integer,
  policy_version integer, status text, retention_expires_at timestamptz,
  approved_at timestamptz, created_at timestamptz, updated_at timestamptz,
  retrieval_score real
)
language sql
security definer
set search_path = ''
as $$
  select i.id,i.policy_id,i.agent_id,i.memory_type,i.visibility_scope,i.purpose,i.classification,
    i.content,i.content_sha256,i.source_ref,i.provenance,i.confidence,i.version,i.policy_version,
    i.status,i.retention_expires_at,i.approved_at,i.created_at,i.updated_at,
    case when nullif(trim(p_query),'') is null then 0::real
      else ts_rank(to_tsvector('simple'::regconfig,i.content),
                   plainto_tsquery('simple'::regconfig,left(p_query,300))) end as retrieval_score
  from public.agent_memory_items i
  join public.agent_memory_policies p on p.id=i.policy_id
  where i.owner_user_id=p_owner_user_id
    and i.agent_id is not distinct from p_agent_id
    and i.policy_id=any(coalesce(p_policy_ids,'{}'::uuid[]))
    and i.status='active' and i.retention_expires_at>now()
    and p.enabled and p.consent_revoked_at is null
    and p.consent_version='allpha.memory.v1'
    and p.policy_version=i.policy_version
    and i.purpose=p_purpose and i.purpose=any(p.allowed_purposes)
    and i.classification=any(p.allowed_sensitivities)
    and i.classification=any(coalesce(p_allowed_sensitivities,'{}'::text[]))
    and (p_max_sensitivity is null or
      array_position(array['public','internal','confidential','restricted']::text[],i.classification)
      <= array_position(array['public','internal','confidential','restricted']::text[],p_max_sensitivity))
    and (nullif(trim(p_query),'') is null or
      to_tsvector('simple'::regconfig,i.content) @@ plainto_tsquery('simple'::regconfig,left(p_query,300)))
  order by
    case when nullif(trim(p_query),'') is null then 0
      else ts_rank(to_tsvector('simple'::regconfig,i.content),
                   plainto_tsquery('simple'::regconfig,left(p_query,300))) end desc,
    i.created_at desc
  limit greatest(1,least(coalesce(p_limit,12),30));
$$;

revoke all on function public.agent_memory_transition(text,uuid,uuid,uuid,jsonb) from public,anon,authenticated;
revoke all on function public.agent_memory_search(uuid,uuid,uuid[],text,text[],text,text,integer) from public,anon,authenticated;
grant execute on function public.agent_memory_transition(text,uuid,uuid,uuid,jsonb) to service_role;
grant execute on function public.agent_memory_search(uuid,uuid,uuid[],text,text[],text,text,integer) to service_role;

comment on table public.agent_memory_items is
  'Owner-consented, versioned, provenance-bearing private Agent Memory; retrieval only through Memory Coordinator.';
comment on table public.agent_memory_events is
  'Append-only lifecycle audit for consent, proposals, corrections, deletion and expiry.';
comment on function public.agent_memory_search(uuid,uuid,uuid[],text,text[],text,text,integer) is
  'Owner/Agent scoped full-text retrieval that rechecks current consent, policy version, classification and retention.';

commit;

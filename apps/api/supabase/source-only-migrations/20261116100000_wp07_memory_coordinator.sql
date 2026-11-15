-- WP-07 / ENG-P06 Memory Coordinator. SOURCE ONLY; do not apply to production before Privacy/Security + Data Platform review.
create table if not exists public.agent_memory_policies (
 id uuid primary key default gen_random_uuid(),
 owner_user_id uuid not null references auth.users(id) on delete cascade,
 agent_id uuid references public.ai_agents(id) on delete cascade,
 memory_type text not null check(memory_type in ('working','episodic','semantic','procedural','long_term')),
 enabled boolean not null default false, consent_version text, consent_granted_at timestamptz, consent_revoked_at timestamptz,
 allowed_purposes text[] not null default '{}', allowed_sensitivities text[] not null default '{}',
 retention_days integer not null default 30 check(retention_days between 1 and 3650),
 write_mode text not null default 'manual_only' check(write_mode='manual_only'),
 policy_version integer not null default 1 check(policy_version>0),
 created_at timestamptz not null default now(), updated_at timestamptz not null default now(),
 check(not enabled or (consent_version is not null and consent_granted_at is not null and consent_revoked_at is null and cardinality(allowed_purposes)>0 and cardinality(allowed_sensitivities)>0))
);
create unique index if not exists agent_memory_policy_personal_uq on public.agent_memory_policies(owner_user_id,memory_type) where agent_id is null;
create unique index if not exists agent_memory_policy_agent_uq on public.agent_memory_policies(owner_user_id,agent_id,memory_type) where agent_id is not null;
create table if not exists public.agent_memory_items (
 id uuid primary key default gen_random_uuid(), policy_id uuid not null references public.agent_memory_policies(id) on delete restrict,
 owner_user_id uuid not null references auth.users(id) on delete cascade, agent_id uuid references public.ai_agents(id) on delete cascade,
 memory_type text not null check(memory_type in ('working','episodic','semantic','procedural','long_term')),
 visibility_scope text not null check(visibility_scope in ('owner_private','agent_private')),
 purpose text not null, classification text not null check(classification in ('public','internal','confidential','restricted')),
 content text not null check(char_length(content) between 1 and 8000), content_sha256 text not null check(content_sha256 ~ '^[0-9a-f]{64}$'),
 source_ref jsonb not null default '{}'::jsonb check(jsonb_typeof(source_ref)='object'),
 provenance jsonb not null default '{}'::jsonb check(jsonb_typeof(provenance)='object'),
 confidence numeric(5,4) check(confidence is null or confidence between 0 and 1),
 version integer not null default 1, policy_version integer not null,
 status text not null default 'proposed' check(status in ('proposed','active','rejected','deleted','expired')),
 retention_expires_at timestamptz not null, search_vector tsvector generated always as (to_tsvector('simple'::regconfig,content)) stored,
 created_by uuid not null references auth.users(id), approved_by uuid references auth.users(id), approved_at timestamptz,
 deleted_at timestamptz, created_at timestamptz not null default now(), updated_at timestamptz not null default now(),
 check((agent_id is null and visibility_scope='owner_private') or (agent_id is not null and visibility_scope='agent_private')),
 check((status='active' and approved_by is not null and approved_at is not null) or status<>'active')
);
create index if not exists agent_memory_items_scope_idx on public.agent_memory_items(owner_user_id,agent_id,memory_type,status,created_at desc);
create index if not exists agent_memory_items_policy_idx on public.agent_memory_items(policy_id,policy_version,status,retention_expires_at);
create index if not exists agent_memory_items_search_idx on public.agent_memory_items using gin(search_vector);
create unique index if not exists agent_memory_items_digest_uq on public.agent_memory_items(owner_user_id,coalesce(agent_id,'00000000-0000-0000-0000-000000000000'::uuid),memory_type,policy_version,content_sha256) where status in ('proposed','active');
create table if not exists public.agent_memory_events (
 id uuid primary key default gen_random_uuid(), owner_user_id uuid not null references auth.users(id) on delete cascade,
 agent_id uuid references public.ai_agents(id) on delete cascade, policy_id uuid references public.agent_memory_policies(id) on delete set null,
 item_id uuid references public.agent_memory_items(id) on delete set null, actor_user_id uuid references auth.users(id) on delete set null,
 event_type text not null check(event_type in ('policy_enabled','policy_disabled','memory_proposed','memory_approved','memory_rejected','memory_corrected','memory_deleted','memory_expired')),
 details jsonb not null default '{}'::jsonb check(jsonb_typeof(details)='object'), created_at timestamptz not null default now()
);
create index if not exists agent_memory_events_owner_idx on public.agent_memory_events(owner_user_id,created_at desc);
alter table public.agent_memory_policies enable row level security;
alter table public.agent_memory_items enable row level security;
alter table public.agent_memory_events enable row level security;
create policy agent_memory_policies_owner_select on public.agent_memory_policies for select to authenticated using(owner_user_id=(select auth.uid()));
create policy agent_memory_items_owner_select on public.agent_memory_items for select to authenticated using(owner_user_id=(select auth.uid()));
create policy agent_memory_events_owner_select on public.agent_memory_events for select to authenticated using(owner_user_id=(select auth.uid()));
revoke all on public.agent_memory_policies,public.agent_memory_items,public.agent_memory_events from public,anon,authenticated;
grant select on public.agent_memory_policies,public.agent_memory_items,public.agent_memory_events to authenticated;
grant all on public.agent_memory_policies,public.agent_memory_items,public.agent_memory_events to service_role;
comment on table public.agent_memory_policies is 'Owner-controlled per-Agent/per-class consent and retention policy; disabled by default.';
comment on table public.agent_memory_items is 'Private Agent Memory; Knowledge corpus and Conversation messages remain separate.';
comment on table public.agent_memory_events is 'Content-minimized Memory lifecycle audit events.';


-- Atomic lifecycle transitions keep the Memory item and its audit event in one transaction.
create or replace function public.agent_memory_transition(
 p_action text,p_owner_user_id uuid,p_agent_id uuid default null,p_item_id uuid default null,p_payload jsonb default '{}'::jsonb
) returns jsonb language plpgsql security invoker set search_path=public,pg_temp as $$
declare
 v_policy public.agent_memory_policies%rowtype;
 v_item public.agent_memory_items%rowtype;
 v_type text; v_purpose text; v_class text; v_content text; v_digest text;
 v_expiry timestamptz; v_decision text; v_count integer; v_result jsonb;
begin
 if current_user<>'service_role' then raise exception 'MEMORY_SERVICE_ROLE_REQUIRED' using errcode='42501'; end if;
 if p_action='create_proposal' then
  v_type:=p_payload->>'memory_type'; v_purpose:=p_payload->>'purpose'; v_class:=p_payload->>'classification';
  v_content:=p_payload->>'content'; v_digest:=p_payload->>'content_sha256'; v_expiry:=(p_payload->>'retention_expires_at')::timestamptz;
  select * into v_policy from public.agent_memory_policies p where p.id=(p_payload->>'policy_id')::uuid
   and p.owner_user_id=p_owner_user_id and p.agent_id is not distinct from p_agent_id and p.memory_type=v_type for share;
  if not found or not v_policy.enabled or v_policy.consent_version is null or v_policy.consent_revoked_at is not null
   or not(v_purpose=any(v_policy.allowed_purposes)) or not(v_class=any(v_policy.allowed_sensitivities))
   or v_expiry<=now() or v_expiry>now()+make_interval(days=>v_policy.retention_days)
   or (v_type='working' and v_expiry>now()+interval '24 hours')
   or char_length(coalesce(v_content,'')) not between 1 and 8000 or v_digest !~ '^[0-9a-f]{64}$'
  then raise exception 'MEMORY_POLICY_DENIED' using errcode='42501'; end if;
  if p_agent_id is not null and not exists(select 1 from public.agent_ownerships o where o.agent_id=p_agent_id and o.owner_user_id=p_owner_user_id and o.status='active')
  then raise exception 'MEMORY_AGENT_OWNERSHIP_REQUIRED' using errcode='42501'; end if;
  insert into public.agent_memory_items(policy_id,owner_user_id,agent_id,memory_type,visibility_scope,purpose,classification,content,content_sha256,source_ref,provenance,confidence,policy_version,status,retention_expires_at,created_by)
  values(v_policy.id,p_owner_user_id,p_agent_id,v_type,case when p_agent_id is null then 'owner_private' else 'agent_private' end,v_purpose,v_class,v_content,v_digest,
   coalesce(p_payload->'source_ref','{}'::jsonb),coalesce(p_payload->'provenance','{}'::jsonb),nullif(p_payload->>'confidence','')::numeric,
   v_policy.policy_version,'proposed',v_expiry,p_owner_user_id) returning * into v_item;
  insert into public.agent_memory_events(owner_user_id,agent_id,policy_id,item_id,actor_user_id,event_type,details)
  values(p_owner_user_id,p_agent_id,v_policy.id,v_item.id,p_owner_user_id,'memory_proposed',jsonb_build_object('memory_type',v_type,'purpose',v_purpose,'classification',v_class,'content_sha256',v_digest,'policy_version',v_policy.policy_version));
  return to_jsonb(v_item);
 elsif p_action='decide' then
  select * into v_item from public.agent_memory_items where id=p_item_id and owner_user_id=p_owner_user_id for update;
  if not found or v_item.status<>'proposed' or v_item.retention_expires_at<=now() then return null; end if;
  v_decision:=p_payload->>'decision';
  if v_decision='approve' then
   select * into v_policy from public.agent_memory_policies where id=v_item.policy_id for share;
   if not found or not v_policy.enabled or v_policy.policy_version<>v_item.policy_version or v_policy.consent_revoked_at is not null
   then raise exception 'MEMORY_POLICY_CHANGED_RECONSENT_REQUIRED' using errcode='42501'; end if;
   update public.agent_memory_items set status='active',approved_by=p_owner_user_id,approved_at=now(),updated_at=now() where id=p_item_id returning * into v_item;
   insert into public.agent_memory_events(owner_user_id,agent_id,policy_id,item_id,actor_user_id,event_type,details)
   values(p_owner_user_id,v_item.agent_id,v_item.policy_id,p_item_id,p_owner_user_id,'memory_approved',jsonb_build_object('policy_version',v_item.policy_version));
  elsif v_decision='reject' then
   update public.agent_memory_items set status='rejected',updated_at=now() where id=p_item_id returning * into v_item;
   insert into public.agent_memory_events(owner_user_id,agent_id,policy_id,item_id,actor_user_id,event_type,details)
   values(p_owner_user_id,v_item.agent_id,v_item.policy_id,p_item_id,p_owner_user_id,'memory_rejected','{}'::jsonb);
  else raise exception 'MEMORY_DECISION_INVALID' using errcode='22023'; end if;
  return jsonb_build_object('id',v_item.id,'status',v_item.status);
 elsif p_action='correct' then
  select * into v_item from public.agent_memory_items where id=p_item_id and owner_user_id=p_owner_user_id for update;
  v_content:=p_payload->>'content'; v_digest:=p_payload->>'content_sha256';
  if not found or v_item.status<>'active' then return null; end if;
  if char_length(coalesce(v_content,'')) not between 1 and 8000 or v_digest !~ '^[0-9a-f]{64}$' then raise exception 'MEMORY_CORRECTION_INVALID' using errcode='22023'; end if;
  select * into v_policy from public.agent_memory_policies where id=v_item.policy_id for share;
  if not found or not v_policy.enabled or v_policy.policy_version<>v_item.policy_version then raise exception 'MEMORY_POLICY_CHANGED_RECONSENT_REQUIRED' using errcode='42501'; end if;
  update public.agent_memory_items set content=v_content,content_sha256=v_digest,version=version+1,updated_at=now() where id=p_item_id returning * into v_item;
  insert into public.agent_memory_events(owner_user_id,agent_id,policy_id,item_id,actor_user_id,event_type,details)
  values(p_owner_user_id,v_item.agent_id,v_item.policy_id,p_item_id,p_owner_user_id,'memory_corrected',jsonb_build_object('version',v_item.version,'content_sha256',v_digest));
  return jsonb_build_object('id',v_item.id,'version',v_item.version);
 elsif p_action='delete' then
  select * into v_item from public.agent_memory_items where id=p_item_id and owner_user_id=p_owner_user_id for update;
  if not found then return null; end if;
  if v_item.status<>'deleted' then
   update public.agent_memory_items set status='deleted',deleted_at=now(),updated_at=now() where id=p_item_id returning * into v_item;
   insert into public.agent_memory_events(owner_user_id,agent_id,policy_id,item_id,actor_user_id,event_type,details)
   values(p_owner_user_id,v_item.agent_id,v_item.policy_id,p_item_id,p_owner_user_id,'memory_deleted',jsonb_build_object('content_sha256',v_item.content_sha256,'derived_memory_index_exists',false));
  end if;
  return jsonb_build_object('id',v_item.id,'status','deleted');
 elsif p_action='expire' then
  with expired as (update public.agent_memory_items i set status='expired',updated_at=now()
   where i.owner_user_id=p_owner_user_id and i.agent_id is not distinct from p_agent_id
    and i.status in ('proposed','active') and i.retention_expires_at<=now()
   returning i.id,i.agent_id,i.policy_id,i.memory_type,i.content_sha256)
  insert into public.agent_memory_events(owner_user_id,agent_id,policy_id,item_id,event_type,details)
  select p_owner_user_id,e.agent_id,e.policy_id,e.id,'memory_expired',jsonb_build_object('memory_type',e.memory_type,'content_sha256',e.content_sha256) from expired e;
  get diagnostics v_count=row_count;
  return jsonb_build_object('expired_count',v_count);
 elsif p_action='policy_event' then
  insert into public.agent_memory_events(owner_user_id,agent_id,policy_id,actor_user_id,event_type,details)
  values(p_owner_user_id,p_agent_id,(p_payload->>'policy_id')::uuid,p_owner_user_id,
   case when (p_payload->>'enabled')::boolean then 'policy_enabled' else 'policy_disabled' end,
   jsonb_build_object('memory_type',p_payload->>'memory_type','policy_version',p_payload->>'policy_version','retention_days',p_payload->>'retention_days'));
  return jsonb_build_object('recorded',true);
 end if;
 raise exception 'MEMORY_ACTION_INVALID' using errcode='22023';
end; $$;
revoke all on function public.agent_memory_transition(text,uuid,uuid,uuid,jsonb) from public,anon,authenticated;
grant execute on function public.agent_memory_transition(text,uuid,uuid,uuid,jsonb) to service_role;

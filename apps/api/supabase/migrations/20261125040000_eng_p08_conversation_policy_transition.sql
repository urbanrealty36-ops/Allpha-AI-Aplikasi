-- ENG-P08: extend the existing canonical transition RPC for Conversation consent.
-- Conversation content remains in Messaging and cannot be written to agent_memory_items.
begin;

CREATE OR REPLACE FUNCTION public.agent_memory_transition(p_action text, p_owner_user_id uuid, p_agent_id uuid, p_item_id uuid, p_payload jsonb)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
declare
 v_policy public.agent_memory_policies%rowtype;
 v_item public.agent_memory_items%rowtype;
 v_memory_type text;
 v_enabled boolean;
 v_retention_days integer;
 v_purposes text[];
 v_sensitivities text[];
 v_consent_version text;
 v_decision text;
 v_content text;
 v_digest text;
 v_expired integer:=0;
 v_result jsonb;
 v_source_job text;
begin
 if p_action not in ('set_policy','expire','expire_all','create_proposal','decide','correct','delete','pin','expire_item') then
  raise exception 'MEMORY_ACTION_INVALID' using errcode='22023';
 end if;
 if p_action='expire_all' then
  with expired as (
   update public.agent_memory_items i set status='expired',content='',pinned_at=null,
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

 if p_action in ('decide','correct','delete','pin','expire_item') then
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
  if v_memory_type not in ('conversation','working','episodic','semantic','procedural','long_term')
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
  v_consent_version:=case when v_enabled then 'allpha.memory.v1' else null end;
  if not v_enabled then v_purposes:='{}'::text[]; v_sensitivities:='{}'::text[]; end if;
  perform pg_advisory_xact_lock(hashtextextended(
   p_owner_user_id::text||':'||coalesce(p_agent_id::text,'personal')||':'||v_memory_type,0));
  select * into v_policy from public.agent_memory_policies p
   where p.owner_user_id=p_owner_user_id and p.agent_id is not distinct from p_agent_id
    and p.memory_type=v_memory_type for update;
  if not found then
   insert into public.agent_memory_policies(owner_user_id,agent_id,memory_type,enabled,consent_version,allowed_purposes,allowed_sensitivities,retention_days,policy_version,consent_revoked_at)
   values(p_owner_user_id,p_agent_id,v_memory_type,v_enabled,
    v_consent_version,v_purposes,v_sensitivities,
    v_retention_days,1,case when v_enabled then null else clock_timestamp() end)
   returning * into v_policy;
  elsif v_policy.enabled is distinct from v_enabled
     or v_policy.allowed_purposes is distinct from v_purposes
     or v_policy.allowed_sensitivities is distinct from v_sensitivities
     or v_policy.retention_days is distinct from v_retention_days
     or v_policy.consent_version is distinct from v_consent_version
     or (v_enabled and v_policy.consent_revoked_at is not null)
     or (not v_enabled and v_policy.consent_revoked_at is null) then
   update public.agent_memory_policies set enabled=v_enabled,
    consent_version=v_consent_version,
    allowed_purposes=v_purposes,
    allowed_sensitivities=v_sensitivities,
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
   update public.agent_memory_items i set status='expired',content='',pinned_at=null,
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
  if v_memory_type='conversation' then
   raise exception 'MEMORY_CONVERSATION_STORED_IN_MESSAGING' using errcode='42501';
  end if;
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

 if p_action='pin' then
  if v_item.status<>'active' or v_item.retention_expires_at<=clock_timestamp() then
   raise exception 'MEMORY_ITEM_NOT_ACTIVE' using errcode='23514';
  end if;
  select * into v_policy from public.agent_memory_policies p where p.id=v_item.policy_id for update;
  if not found or not v_policy.enabled or v_policy.consent_version<>'allpha.memory.v1'
     or v_policy.consent_revoked_at is not null or v_item.policy_version<>v_policy.policy_version then
   raise exception 'MEMORY_POLICY_DENIED' using errcode='42501';
  end if;
  v_enabled:=coalesce((p_payload->>'pinned')::boolean,false);
  if (v_item.pinned_at is not null)=v_enabled then
   return jsonb_build_object('id',v_item.id,'status',v_item.status,'pinned_at',v_item.pinned_at);
  end if;
  update public.agent_memory_items set pinned_at=case when v_enabled then clock_timestamp() else null end,
   updated_at=clock_timestamp() where id=v_item.id returning * into v_item;
  insert into public.agent_memory_events(owner_user_id,owner_subject_hash,agent_id,policy_id,item_id,actor_user_id,event_type,details)
  values(p_owner_user_id,encode(extensions.digest(p_owner_user_id::text,'sha256'),'hex'),v_item.agent_id,v_item.policy_id,v_item.id,p_owner_user_id,
   case when v_enabled then 'item_pinned' else 'item_unpinned' end,
   jsonb_build_object('memory_type',v_item.memory_type,'version',v_item.version,'policy_version',v_item.policy_version));
  return jsonb_build_object('id',v_item.id,'status',v_item.status,'pinned_at',v_item.pinned_at);
 end if;

 if p_action='expire_item' then
  if v_item.status not in ('pending','active') then return null; end if;
  update public.agent_memory_items set status='expired',content='',pinned_at=null,
   content_sha256=encode(extensions.digest('','sha256'),'hex'),
   source_ref='{}'::jsonb,provenance='{"retention":"owner_expired"}'::jsonb,
   confidence=null,updated_at=clock_timestamp()
  where id=v_item.id returning * into v_item;
  insert into public.agent_memory_events(owner_user_id,owner_subject_hash,agent_id,policy_id,item_id,actor_user_id,event_type,details)
  values(p_owner_user_id,encode(extensions.digest(p_owner_user_id::text,'sha256'),'hex'),v_item.agent_id,v_item.policy_id,v_item.id,p_owner_user_id,
   'item_expired',jsonb_build_object('memory_type',v_item.memory_type,'purpose',v_item.purpose,
    'classification',v_item.classification,'version',v_item.version,'owner_requested',true));
  return jsonb_build_object('id',v_item.id,'status','expired');
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
$function$

revoke all on function public.agent_memory_transition(text,uuid,uuid,uuid,jsonb) from public,anon,authenticated;
grant execute on function public.agent_memory_transition(text,uuid,uuid,uuid,jsonb) to service_role;

comment on function public.agent_memory_transition(text,uuid,uuid,uuid,jsonb) is
 'Canonical owner-scoped Agent Memory transition engine. Conversation consent grants bounded reads from Messaging only; conversation content is never copied into persistent memory items.';

commit;

-- WP-06 DM reply approval/effect adapter.
-- Extends the existing Social approval and Agent Runtime receipt lifecycle.
-- Source-only: apply only through the canonical migration release process.
begin;

do $$
begin
  if to_regclass('public.agent_social_action_approvals') is null
     or to_regclass('public.agent_social_automation_grants') is null
     or to_regclass('public.agent_runtime_effect_receipts') is null
     or to_regclass('public.agent_runtime_tasks') is null
     or not exists(select 1 from information_schema.columns where table_schema='public'
       and table_name='agent_social_action_approvals' and column_name='dispatch_task_id')
     or to_regclass('public.messages') is null
     or to_regclass('public.conversation_participants') is null
     or to_regclass('public.conversations') is null then
    raise exception 'WP06_DM_APPROVAL_SCHEMA_PREREQUISITE_MISSING';
  end if;
end $$;

alter table public.agent_social_action_approvals
  add column if not exists target_conversation_id uuid references public.conversations(id) on delete restrict,
  add column if not exists target_message_id uuid references public.messages(id) on delete restrict;

alter table public.messages
  add column if not exists agent_social_approval_id uuid references public.agent_social_action_approvals(id) on delete restrict,
  add column if not exists agent_disclosure_snapshot text;

do $$
begin
  if not exists (select 1 from pg_constraint where conname='messages_agent_social_attribution_complete') then
    alter table public.messages add constraint messages_agent_social_attribution_complete
      check (
        (agent_social_approval_id is null and agent_disclosure_snapshot is null)
        or (sender_agent_id is not null and agent_social_approval_id is not null
            and length(btrim(coalesce(agent_disclosure_snapshot,''))) between 8 and 180)
      ) not valid;
  end if;
end $$;

create unique index if not exists messages_agent_client_message_id_unique
  on public.messages(conversation_id,sender_agent_id,client_message_id)
  where agent_social_approval_id is not null;

create or replace function public.request_agent_social_message_draft(
  p_owner_user_id uuid,
  p_agent_id uuid,
  p_runtime_task_id uuid,
  p_target_conversation_id uuid,
  p_target_message_id uuid,
  p_body text,
  p_idempotency_key text
) returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_task public.agent_runtime_tasks%rowtype;
  v_policy public.agent_social_presence_policies%rowtype;
  v_conversation public.conversations%rowtype;
  v_source public.messages%rowtype;
  v_item public.content_items%rowtype;
  v_approval public.agent_social_action_approvals%rowtype;
  v_prior public.agent_social_action_approvals%rowtype;
  v_actor uuid;
  v_participant_count integer;
begin
  if (select auth.role()) <> 'service_role' then
    raise exception 'service_role_required' using errcode='42501';
  end if;
  if p_owner_user_id is null or p_agent_id is null or p_runtime_task_id is null
     or p_target_conversation_id is null or p_target_message_id is null
     or length(btrim(coalesce(p_body,''))) not between 1 and 10000
     or length(coalesce(p_idempotency_key,'')) not between 12 and 160 then
    raise exception 'AGENT_SOCIAL_DM_DRAFT_INPUT_INVALID' using errcode='22023';
  end if;

  perform pg_advisory_xact_lock(hashtextextended(p_owner_user_id::text||':'||p_idempotency_key,0));
  select * into v_prior from public.agent_social_action_approvals
  where owner_user_id=p_owner_user_id and idempotency_key=p_idempotency_key;
  if found then
    if v_prior.agent_id<>p_agent_id or v_prior.runtime_task_id<>p_runtime_task_id
       or v_prior.action_type<>'draft_reply'
       or v_prior.target_conversation_id is distinct from p_target_conversation_id
       or v_prior.target_message_id is distinct from p_target_message_id then
      raise exception 'AGENT_SOCIAL_DM_IDEMPOTENCY_CONFLICT' using errcode='23505';
    end if;
    select * into v_item from public.content_items where id=v_prior.content_id;
    return jsonb_build_object('outcome','replayed','item',to_jsonb(v_item),'approval',to_jsonb(v_prior));
  end if;

  if not exists (
    select 1 from public.ai_agents a
    join public.agent_ownerships o on o.agent_id=a.id
    where a.id=p_agent_id and a.status='active'
      and o.owner_user_id=p_owner_user_id and o.ownership_role='owner' and o.status='active'
  ) then
    raise exception 'AGENT_SOCIAL_OWNERSHIP_REQUIRED' using errcode='42501';
  end if;

  select * into v_task from public.agent_runtime_tasks
  where id=p_runtime_task_id and owner_user_id=p_owner_user_id
    and agent_id=p_agent_id and state='succeeded' and completed_at is not null
  for share;
  if not found or jsonb_typeof(v_task.output_payload)<>'object' then
    raise exception 'AGENT_SOCIAL_RUNTIME_TASK_REQUIRED' using errcode='P0002';
  end if;
  if coalesce(nullif(btrim(v_task.output_payload->>'content'),''),nullif(btrim(v_task.output_payload->>'text'),'')) is distinct from btrim(p_body) then
    raise exception 'AGENT_SOCIAL_RUNTIME_OUTPUT_MISMATCH' using errcode='22023';
  end if;

  select * into v_policy from public.agent_social_presence_policies
  where owner_user_id=p_owner_user_id and agent_id=p_agent_id
  for share;
  if not found or not v_policy.is_enabled or v_policy.revoked_at is not null
     or not v_policy.auto_reply_enabled or v_policy.takeover_active
     or not ('dm'=any(v_policy.auto_reply_channels))
     or not ('draft_reply'=any(v_policy.allowed_actions))
     or v_policy.owner_approval_required is not true
     or v_policy.output_moderation_required is not true then
    raise exception 'AGENT_SOCIAL_DM_POLICY_NOT_AUTHORIZED' using errcode='42501';
  end if;
  if not exists (
    select 1 from public.agent_social_automation_grants g
    where g.owner_user_id=p_owner_user_id and g.agent_id=p_agent_id
      and g.status='active' and g.policy_version=v_policy.version
      and 'dm'=any(g.granted_scopes) and (g.expires_at is null or g.expires_at>now())
  ) then
    raise exception 'AGENT_SOCIAL_DM_GRANT_NOT_ACTIVE' using errcode='42501';
  end if;

  select * into v_conversation from public.conversations
  where id=p_target_conversation_id and kind='agent' for share;
  if not found then
    raise exception 'AGENT_SOCIAL_DM_CONVERSATION_NOT_FOUND' using errcode='P0002';
  end if;
  select count(*) into v_participant_count from public.conversation_participants
  where conversation_id=p_target_conversation_id;
  if v_participant_count<>2
     or not exists(select 1 from public.conversation_participants
       where conversation_id=p_target_conversation_id and participant_type='agent' and agent_id=p_agent_id)
     or not exists(select 1 from public.conversation_participants
       where conversation_id=p_target_conversation_id and participant_type='human' and user_id is not null) then
    raise exception 'AGENT_SOCIAL_DM_PARTICIPANT_ACL_FAILED' using errcode='42501';
  end if;
  select user_id into v_actor from public.conversation_participants
  where conversation_id=p_target_conversation_id and participant_type='human';
  select * into v_source from public.messages
  where id=p_target_message_id and conversation_id=p_target_conversation_id
    and sender_type='human' and sender_user_id=v_actor
  for share;
  if not found or v_actor is null then
    raise exception 'AGENT_SOCIAL_DM_SOURCE_MESSAGE_INVALID' using errcode='42501';
  end if;
  if exists (
    select 1 from public.messages newer
    where newer.conversation_id=p_target_conversation_id
      and newer.sender_type='human' and newer.id<>v_source.id and newer.created_at>=v_source.created_at
  ) then
    raise exception 'AGENT_SOCIAL_DM_SOURCE_MESSAGE_STALE' using errcode='40001';
  end if;
  if exists (
    select 1 from public.social_edges e
    where e.edge_type='block' and e.status='active'
      and ((e.actor_user_id=p_owner_user_id and e.target_user_id=v_actor)
        or (e.actor_user_id=v_actor and e.target_user_id=p_owner_user_id))
  ) then
    raise exception 'AGENT_SOCIAL_DM_BLOCKED' using errcode='42501';
  end if;

  insert into public.content_items
    (owner_id,ai_agent_id,content_type,body,visibility,status,moderation_status,version,provenance)
  values
    (p_owner_user_id,p_agent_id,'text',btrim(p_body),'private','draft','not_submitted',1,
     jsonb_build_object('coauthored',true,'human_owner_id',p_owner_user_id,'agent_id',p_agent_id,
       'runtime_task_id',p_runtime_task_id,'dm_conversation_id',p_target_conversation_id,
       'dm_target_message_id',p_target_message_id,
       'runtime_output_sha256',encode(extensions.digest(convert_to(btrim(p_body),'UTF8'),'sha256'),'hex'),
       'disclosure',v_policy.disclosure_text,'agent_policy_version',v_policy.version))
  returning * into v_item;

  insert into public.agent_social_action_approvals
    (owner_user_id,agent_id,content_id,runtime_task_id,target_content_id,target_comment_id,target_user_id,
     target_conversation_id,target_message_id,action_type,content_version,status,disclosure_snapshot,idempotency_key)
  values
    (p_owner_user_id,p_agent_id,v_item.id,p_runtime_task_id,null,null,v_actor,
     p_target_conversation_id,p_target_message_id,'draft_reply',v_item.version,'pending',
     v_policy.disclosure_text,p_idempotency_key)
  returning * into v_approval;

  insert into public.agent_social_audit_events
    (owner_user_id,agent_id,approval_id,actor_user_id,event_type,outcome,metadata)
  values
    (p_owner_user_id,p_agent_id,v_approval.id,p_owner_user_id,'draft_requested','allowed',
     jsonb_build_object('action_type','draft_reply','channel','dm','runtime_task_id',p_runtime_task_id,
       'target_conversation_id',p_target_conversation_id,'target_message_id',p_target_message_id));

  insert into public.notifications(user_id,category,event_key,title,body,payload,delivery_state)
  values(p_owner_user_id,'social_activity','agent-social-request:'||v_approval.id::text,
    'Persetujuan balasan DM AI Agent menunggu keputusan',
    'Draft balasan DM AI Agent menunggu persetujuan Anda.',
    jsonb_build_object('type','agent_social_approval_request','approval_id',v_approval.id,
      'content_id',v_item.id,'action_type','draft_reply','channel','dm'),'queued')
  on conflict(user_id,event_key) do nothing;

  return jsonb_build_object('outcome','created','item',to_jsonb(v_item),
    'approval',to_jsonb(v_approval),'disclosure',v_policy.disclosure_text);
end;
$$;

revoke all on function public.request_agent_social_message_draft(uuid,uuid,uuid,uuid,uuid,text,text)
  from public,anon,authenticated;
grant execute on function public.request_agent_social_message_draft(uuid,uuid,uuid,uuid,uuid,text,text)
  to service_role;

create or replace function public.execute_agent_social_message_approval_effect(
  p_task_id uuid,p_owner_user_id uuid,p_lease_token uuid,p_task_version integer,
  p_step_key text,p_idempotency_key text,p_input_fingerprint text,
  p_actor_user_id uuid,p_agent_id uuid,p_action_key text,p_target_reference text,
  p_approval_id uuid,p_correlation_id text,p_policy_id uuid,p_policy_version text,
  p_policy_digest text,p_reason text default null
) returns jsonb
language plpgsql security definer set search_path=''
as $$
declare
  v_task public.agent_runtime_tasks%rowtype;
  v_policy public.agent_runtime_policies%rowtype;
  v_social_policy public.agent_social_presence_policies%rowtype;
  v_approval public.agent_social_action_approvals%rowtype;
  v_draft public.content_items%rowtype;
  v_conversation public.conversations%rowtype;
  v_source public.messages%rowtype;
  v_message public.messages%rowtype;
  v_receipt public.agent_runtime_effect_receipts%rowtype;
  v_inserted_id uuid;
  v_actor uuid;
  v_result jsonb;
  v_conversation_id uuid;
begin
  if (select auth.role())<>'service_role' then
    raise exception 'service_role_required' using errcode='42501';
  end if;
  if p_owner_user_id is null or p_actor_user_id is distinct from p_owner_user_id
     or p_agent_id is null or p_approval_id is null or p_step_key is null or p_step_key=''
     or p_idempotency_key is distinct from p_approval_id::text
     or p_correlation_id is null or p_correlation_id=''
     or p_action_key is distinct from 'social.reply'
     or p_target_reference is null
     or p_target_reference !~ '^conversation:[0-9a-fA-F-]{36}
     or p_policy_id is null or coalesce(p_policy_version,'')=''
     or p_policy_digest !~ '^[a-f0-9]{64}$'
     or p_input_fingerprint !~ '^[a-f0-9]{64}$' then
    raise exception 'AGENT_SOCIAL_DM_EFFECT_COMMAND_INVALID' using errcode='22023';
  end if;
  v_conversation_id := substring(p_target_reference from 14)::uuid;

  select * into v_social_policy from public.agent_social_presence_policies
  where owner_user_id=p_owner_user_id and agent_id=p_agent_id for share;
  if not found or not v_social_policy.is_enabled or v_social_policy.revoked_at is not null
     or v_social_policy.takeover_active or not ('draft_reply'=any(v_social_policy.allowed_actions)) then
    raise exception 'AGENT_SOCIAL_POLICY_REVOKED' using errcode='42501';
  end if;
  if not exists (
    select 1 from public.agent_social_automation_grants g
    where g.owner_user_id=p_owner_user_id and g.agent_id=p_agent_id
      and g.status='active' and g.policy_version=v_social_policy.version
      and 'dm'=any(g.granted_scopes) and (g.expires_at is null or g.expires_at>now())
  ) then
    raise exception 'AGENT_SOCIAL_DM_GRANT_REVOKED' using errcode='42501';
  end if;

  select * into v_approval from public.agent_social_action_approvals
  where id=p_approval_id and owner_user_id=p_owner_user_id and agent_id=p_agent_id
  for update;
  if not found or v_approval.status<>'approved'
     or v_approval.action_type<>'draft_reply'
     or v_approval.dispatch_task_id is distinct from p_task_id
     or v_approval.target_conversation_id is distinct from v_conversation_id
     or v_approval.target_message_id is null then
    raise exception 'AGENT_SOCIAL_DM_APPROVAL_NOT_AUTHORIZED' using errcode='42501';
  end if;

  select * into v_task from public.agent_runtime_tasks
  where id=p_task_id and owner_user_id=p_owner_user_id for update;
  if not found or v_task.state<>'executing'
     or v_task.execution_lease_token is distinct from p_lease_token
     or v_task.lease_expires_at is null or v_task.lease_expires_at<=now()
     or v_task.task_version<>p_task_version or v_task.agent_id<>p_agent_id then
    raise exception 'AGENT_RUNTIME_STALE_LEASE' using errcode='40001';
  end if;
  select * into v_policy from public.agent_runtime_policies
  where id=p_policy_id and agent_id=p_agent_id and policy_version=p_policy_version
    and policy_digest=p_policy_digest and status='approved'
    and p_action_key=any(approved_tool_keys) for share;
  if not found then
    raise exception 'AGENT_RUNTIME_EFFECT_POLICY_NOT_APPROVED' using errcode='42501';
  end if;
  if not exists (
    select 1 from public.ai_agents a join public.agent_ownerships o on o.agent_id=a.id
    where a.id=p_agent_id and a.status='active' and o.owner_user_id=p_owner_user_id
      and o.ownership_role='owner' and o.status='active'
  ) then raise exception 'AGENT_SOCIAL_OWNERSHIP_REQUIRED' using errcode='42501'; end if;

  select * into v_draft from public.content_items
  where id=v_approval.content_id and owner_id=p_owner_user_id and ai_agent_id=p_agent_id
    and status='draft' and version=v_approval.content_version and deleted_at is null
  for update;
  if not found then raise exception 'AGENT_SOCIAL_DRAFT_CHANGED' using errcode='40001'; end if;
  select * into v_conversation from public.conversations
  where id=v_conversation_id and kind='agent' for share;
  if not found then raise exception 'AGENT_SOCIAL_DM_CONVERSATION_NOT_FOUND' using errcode='P0002'; end if;
  if (select count(*) from public.conversation_participants where conversation_id=v_conversation_id)<>2
     or not exists(select 1 from public.conversation_participants
       where conversation_id=v_conversation_id and participant_type='agent' and agent_id=p_agent_id) then
    raise exception 'AGENT_SOCIAL_DM_PARTICIPANT_ACL_FAILED' using errcode='42501';
  end if;
  select user_id into v_actor from public.conversation_participants
  where conversation_id=v_conversation_id and participant_type='human';
  select * into v_source from public.messages
  where id=v_approval.target_message_id and conversation_id=v_conversation_id
    and sender_type='human' and sender_user_id=v_actor for share;
  if not found or v_actor is null or v_approval.target_user_id is distinct from v_actor
     or exists(select 1 from public.messages newer where newer.conversation_id=v_conversation_id
       and newer.sender_type='human' and newer.id<>v_source.id and newer.created_at>=v_source.created_at) then
    raise exception 'AGENT_SOCIAL_DM_SOURCE_MESSAGE_STALE' using errcode='40001';
  end if;
  if exists(select 1 from public.social_edges e where e.edge_type='block' and e.status='active'
    and ((e.actor_user_id=p_owner_user_id and e.target_user_id=v_actor)
      or (e.actor_user_id=v_actor and e.target_user_id=p_owner_user_id))) then
    raise exception 'AGENT_SOCIAL_DM_BLOCKED' using errcode='42501';
  end if;
  if length(btrim(coalesce(v_approval.disclosure_snapshot,''))) not between 8 and 180 then
    raise exception 'AGENT_SOCIAL_DISCLOSURE_REQUIRED' using errcode='42501';
  end if;

  insert into public.agent_runtime_effect_receipts(
    task_id,task_version,step_key,idempotency_key,input_fingerprint,status,
    actor_user_id,owner_user_id,agent_id,target_reference,action_key,approval_id,
    correlation_id,provider_key,policy_id,policy_version,policy_digest,metadata
  ) values (
    p_task_id,p_task_version,p_step_key,p_idempotency_key,p_input_fingerprint,'started',
    p_actor_user_id,p_owner_user_id,p_agent_id,p_target_reference,p_action_key,p_approval_id,
    p_correlation_id,'allpha.social',p_policy_id,p_policy_version,p_policy_digest,
    jsonb_build_object('approval_id',p_approval_id,'channel','dm')
  ) on conflict(task_id,step_key,idempotency_key) do nothing returning id into v_inserted_id;

  if v_inserted_id is null then
    select * into v_receipt from public.agent_runtime_effect_receipts
    where task_id=p_task_id and step_key=p_step_key and idempotency_key=p_idempotency_key for update;
    if v_receipt.input_fingerprint is distinct from p_input_fingerprint
       or v_receipt.actor_user_id is distinct from p_actor_user_id
       or v_receipt.owner_user_id is distinct from p_owner_user_id
       or v_receipt.agent_id is distinct from p_agent_id
       or v_receipt.target_reference is distinct from p_target_reference
       or v_receipt.action_key is distinct from p_action_key
       or v_receipt.approval_id is distinct from p_approval_id
       or v_receipt.correlation_id is distinct from p_correlation_id
       or v_receipt.policy_id is distinct from p_policy_id
       or v_receipt.policy_version is distinct from p_policy_version
       or v_receipt.policy_digest is distinct from p_policy_digest then
      raise exception 'AGENT_RUNTIME_EFFECT_IDEMPOTENCY_CONFLICT' using errcode='23505';
    end if;
    if v_receipt.status='completed' then
      return jsonb_build_object('outcome','replayed','receipt',to_jsonb(v_receipt),'execution',v_receipt.result_payload);
    end if;
    raise exception 'AGENT_RUNTIME_EFFECT_OUTCOME_UNKNOWN_NO_REPLAY' using errcode='40001';
  end if;

  update public.agent_runtime_tasks set effect_outcome='started',current_step_key=p_step_key,updated_at=now()
  where id=p_task_id and owner_user_id=p_owner_user_id;

  insert into public.messages(
    conversation_id,sender_type,sender_agent_id,body,client_message_id,delivery_status,
    agent_social_approval_id,agent_disclosure_snapshot
  ) values (
    v_conversation_id,'agent',p_agent_id,btrim(v_draft.body),p_approval_id,'sent',
    p_approval_id,v_approval.disclosure_snapshot
  ) on conflict(conversation_id,sender_agent_id,client_message_id) where agent_social_approval_id is not null
  do nothing returning * into v_message;

  if v_message.id is null then
    select * into v_message from public.messages
    where conversation_id=v_conversation_id and sender_agent_id=p_agent_id
      and client_message_id=p_approval_id;
    if not found or v_message.agent_social_approval_id is distinct from p_approval_id
       or v_message.body is distinct from btrim(v_draft.body) then
      raise exception 'AGENT_SOCIAL_DM_MESSAGE_IDEMPOTENCY_CONFLICT' using errcode='23505';
    end if;
  end if;

  update public.conversations set updated_at=now(),last_message_at=now()
  where id=v_conversation_id;
  v_result := jsonb_build_object('kind','direct_message','message_id',v_message.id,
    'conversation_id',v_conversation_id,'recipient_user_id',v_actor,'agent_id',p_agent_id,
    'disclosure',v_approval.disclosure_snapshot);
  update public.agent_social_action_approvals set execution_result=v_result
  where id=p_approval_id and owner_user_id=p_owner_user_id;

  insert into public.notifications(user_id,category,event_key,title,body,payload,delivery_state)
  values(v_actor,'social_activity','agent-social-dm:'||p_approval_id::text,
    'Pesan baru dari AI Agent','AI Agent mengirim balasan DM yang telah disetujui pemilik.',
    jsonb_build_object('type','agent_dm_reply','approval_id',p_approval_id,
      'conversation_id',v_conversation_id,'message_id',v_message.id,'agent_id',p_agent_id),
    public.agent_social_notification_state(v_actor))
  on conflict(user_id,event_key) do nothing;

  select * into v_task from public.agent_runtime_tasks
  where id=p_task_id and owner_user_id=p_owner_user_id for update;
  if not found or v_task.state<>'executing'
     or v_task.execution_lease_token is distinct from p_lease_token
     or v_task.lease_expires_at is null or v_task.lease_expires_at<=now()
     or v_task.task_version<>p_task_version then
    raise exception 'AGENT_RUNTIME_STALE_LEASE_AT_COMMIT' using errcode='40001';
  end if;

  update public.agent_runtime_effect_receipts set status='completed',
    result_payload=v_result,external_reference=v_message.id::text,
    evidence_reference='message:'||v_message.id::text,completed_at=now(),updated_at=now()
  where id=v_inserted_id returning * into v_receipt;
  update public.agent_runtime_tasks set effect_outcome='completed',updated_at=now()
  where id=p_task_id and owner_user_id=p_owner_user_id;

  return jsonb_build_object('outcome','completed','receipt',to_jsonb(v_receipt),'execution',v_result);
end;
$$;

revoke all on function public.execute_agent_social_message_approval_effect(uuid,uuid,uuid,integer,text,text,text,uuid,uuid,text,text,uuid,text,uuid,text,text,text)
  from public,anon,authenticated;
grant execute on function public.execute_agent_social_message_approval_effect(uuid,uuid,uuid,integer,text,text,text,uuid,uuid,text,text,uuid,text,uuid,text,text,text)
  to service_role;

commit;

     or p_policy_id is null or coalesce(p_policy_version,'')=''
     or p_policy_digest !~ '^[a-f0-9]{64}$'
     or p_input_fingerprint !~ '^[a-f0-9]{64}$' then
    raise exception 'AGENT_SOCIAL_DM_EFFECT_COMMAND_INVALID' using errcode='22023';
  end if;
  v_conversation_id := substring(p_target_reference from 13)::uuid;

  select * into v_social_policy from public.agent_social_presence_policies
  where owner_user_id=p_owner_user_id and agent_id=p_agent_id for share;
  if not found or not v_social_policy.is_enabled or v_social_policy.revoked_at is not null
     or v_social_policy.takeover_active or not ('draft_reply'=any(v_social_policy.allowed_actions)) then
    raise exception 'AGENT_SOCIAL_POLICY_REVOKED' using errcode='42501';
  end if;
  if not exists (
    select 1 from public.agent_social_automation_grants g
    where g.owner_user_id=p_owner_user_id and g.agent_id=p_agent_id
      and g.status='active' and g.policy_version=v_social_policy.version
      and 'dm'=any(g.granted_scopes) and (g.expires_at is null or g.expires_at>now())
  ) then
    raise exception 'AGENT_SOCIAL_DM_GRANT_REVOKED' using errcode='42501';
  end if;

  select * into v_approval from public.agent_social_action_approvals
  where id=p_approval_id and owner_user_id=p_owner_user_id and agent_id=p_agent_id
  for update;
  if not found or v_approval.status<>'approved'
     or v_approval.action_type<>'draft_reply'
     or v_approval.dispatch_task_id is distinct from p_task_id
     or v_approval.target_conversation_id is distinct from v_conversation_id
     or v_approval.target_message_id is null then
    raise exception 'AGENT_SOCIAL_DM_APPROVAL_NOT_AUTHORIZED' using errcode='42501';
  end if;

  select * into v_task from public.agent_runtime_tasks
  where id=p_task_id and owner_user_id=p_owner_user_id for update;
  if not found or v_task.state<>'executing'
     or v_task.execution_lease_token is distinct from p_lease_token
     or v_task.lease_expires_at is null or v_task.lease_expires_at<=now()
     or v_task.task_version<>p_task_version or v_task.agent_id<>p_agent_id then
    raise exception 'AGENT_RUNTIME_STALE_LEASE' using errcode='40001';
  end if;
  select * into v_policy from public.agent_runtime_policies
  where id=p_policy_id and agent_id=p_agent_id and policy_version=p_policy_version
    and policy_digest=p_policy_digest and status='approved'
    and p_action_key=any(approved_tool_keys) for share;
  if not found then
    raise exception 'AGENT_RUNTIME_EFFECT_POLICY_NOT_APPROVED' using errcode='42501';
  end if;
  if not exists (
    select 1 from public.ai_agents a join public.agent_ownerships o on o.agent_id=a.id
    where a.id=p_agent_id and a.status='active' and o.owner_user_id=p_owner_user_id
      and o.ownership_role='owner' and o.status='active'
  ) then raise exception 'AGENT_SOCIAL_OWNERSHIP_REQUIRED' using errcode='42501'; end if;

  select * into v_draft from public.content_items
  where id=v_approval.content_id and owner_id=p_owner_user_id and ai_agent_id=p_agent_id
    and status='draft' and version=v_approval.content_version and deleted_at is null
  for update;
  if not found then raise exception 'AGENT_SOCIAL_DRAFT_CHANGED' using errcode='40001'; end if;
  select * into v_conversation from public.conversations
  where id=v_conversation_id and kind='agent' for share;
  if not found then raise exception 'AGENT_SOCIAL_DM_CONVERSATION_NOT_FOUND' using errcode='P0002'; end if;
  if (select count(*) from public.conversation_participants where conversation_id=v_conversation_id)<>2
     or not exists(select 1 from public.conversation_participants
       where conversation_id=v_conversation_id and participant_type='agent' and agent_id=p_agent_id) then
    raise exception 'AGENT_SOCIAL_DM_PARTICIPANT_ACL_FAILED' using errcode='42501';
  end if;
  select user_id into v_actor from public.conversation_participants
  where conversation_id=v_conversation_id and participant_type='human';
  select * into v_source from public.messages
  where id=v_approval.target_message_id and conversation_id=v_conversation_id
    and sender_type='human' and sender_user_id=v_actor for share;
  if not found or v_actor is null
     or exists(select 1 from public.messages newer where newer.conversation_id=v_conversation_id
       and newer.sender_type='human' and newer.created_at>v_source.created_at) then
    raise exception 'AGENT_SOCIAL_DM_SOURCE_MESSAGE_STALE' using errcode='40001';
  end if;
  if exists(select 1 from public.social_edges e where e.edge_type='block' and e.status='active'
    and ((e.actor_user_id=p_owner_user_id and e.target_user_id=v_actor)
      or (e.actor_user_id=v_actor and e.target_user_id=p_owner_user_id))) then
    raise exception 'AGENT_SOCIAL_DM_BLOCKED' using errcode='42501';
  end if;
  if length(btrim(coalesce(v_approval.disclosure_snapshot,''))) not between 8 and 180 then
    raise exception 'AGENT_SOCIAL_DISCLOSURE_REQUIRED' using errcode='42501';
  end if;

  insert into public.agent_runtime_effect_receipts(
    task_id,task_version,step_key,idempotency_key,input_fingerprint,status,
    actor_user_id,owner_user_id,agent_id,target_reference,action_key,approval_id,
    correlation_id,provider_key,policy_id,policy_version,policy_digest,metadata
  ) values (
    p_task_id,p_task_version,p_step_key,p_idempotency_key,p_input_fingerprint,'started',
    p_actor_user_id,p_owner_user_id,p_agent_id,p_target_reference,p_action_key,p_approval_id,
    p_correlation_id,'allpha.social',p_policy_id,p_policy_version,p_policy_digest,
    jsonb_build_object('approval_id',p_approval_id,'channel','dm')
  ) on conflict(task_id,step_key,idempotency_key) do nothing returning id into v_inserted_id;

  if v_inserted_id is null then
    select * into v_receipt from public.agent_runtime_effect_receipts
    where task_id=p_task_id and step_key=p_step_key and idempotency_key=p_idempotency_key for update;
    if v_receipt.input_fingerprint is distinct from p_input_fingerprint
       or v_receipt.actor_user_id is distinct from p_actor_user_id
       or v_receipt.owner_user_id is distinct from p_owner_user_id
       or v_receipt.agent_id is distinct from p_agent_id
       or v_receipt.target_reference is distinct from p_target_reference
       or v_receipt.action_key is distinct from p_action_key
       or v_receipt.approval_id is distinct from p_approval_id
       or v_receipt.correlation_id is distinct from p_correlation_id
       or v_receipt.policy_id is distinct from p_policy_id
       or v_receipt.policy_version is distinct from p_policy_version
       or v_receipt.policy_digest is distinct from p_policy_digest then
      raise exception 'AGENT_RUNTIME_EFFECT_IDEMPOTENCY_CONFLICT' using errcode='23505';
    end if;
    if v_receipt.status='completed' then
      return jsonb_build_object('outcome','replayed','receipt',to_jsonb(v_receipt),'execution',v_receipt.result_payload);
    end if;
    raise exception 'AGENT_RUNTIME_EFFECT_OUTCOME_UNKNOWN_NO_REPLAY' using errcode='40001';
  end if;

  update public.agent_runtime_tasks set effect_outcome='started',current_step_key=p_step_key,updated_at=now()
  where id=p_task_id and owner_user_id=p_owner_user_id;

  insert into public.messages(
    conversation_id,sender_type,sender_agent_id,body,client_message_id,delivery_status,
    agent_social_approval_id,agent_disclosure_snapshot
  ) values (
    v_conversation_id,'agent',p_agent_id,btrim(v_draft.body),p_approval_id,'sent',
    p_approval_id,v_approval.disclosure_snapshot
  ) on conflict(conversation_id,sender_agent_id,client_message_id) where sender_agent_id is not null
  do nothing returning * into v_message;

  if v_message.id is null then
    select * into v_message from public.messages
    where conversation_id=v_conversation_id and sender_agent_id=p_agent_id
      and client_message_id=p_approval_id;
    if not found or v_message.agent_social_approval_id is distinct from p_approval_id
       or v_message.body is distinct from btrim(v_draft.body) then
      raise exception 'AGENT_SOCIAL_DM_MESSAGE_IDEMPOTENCY_CONFLICT' using errcode='23505';
    end if;
  end if;

  update public.conversations set updated_at=now(),last_message_at=now()
  where id=v_conversation_id;
  v_result := jsonb_build_object('kind','direct_message','message_id',v_message.id,
    'conversation_id',v_conversation_id,'recipient_user_id',v_actor,'agent_id',p_agent_id,
    'disclosure',v_approval.disclosure_snapshot);
  update public.agent_social_action_approvals set execution_result=v_result
  where id=p_approval_id and owner_user_id=p_owner_user_id;

  insert into public.notifications(user_id,category,event_key,title,body,payload,delivery_state)
  values(v_actor,'social_activity','agent-social-dm:'||p_approval_id::text,
    'Pesan baru dari AI Agent','AI Agent mengirim balasan DM yang telah disetujui pemilik.',
    jsonb_build_object('type','agent_dm_reply','approval_id',p_approval_id,
      'conversation_id',v_conversation_id,'message_id',v_message.id,'agent_id',p_agent_id),
    public.agent_social_notification_state(v_actor))
  on conflict(user_id,event_key) do nothing;

  select * into v_task from public.agent_runtime_tasks
  where id=p_task_id and owner_user_id=p_owner_user_id for update;
  if not found or v_task.state<>'executing'
     or v_task.execution_lease_token is distinct from p_lease_token
     or v_task.lease_expires_at is null or v_task.lease_expires_at<=now()
     or v_task.task_version<>p_task_version then
    raise exception 'AGENT_RUNTIME_STALE_LEASE_AT_COMMIT' using errcode='40001';
  end if;

  update public.agent_runtime_effect_receipts set status='completed',
    result_payload=v_result,external_reference=v_message.id::text,
    evidence_reference='message:'||v_message.id::text,completed_at=now(),updated_at=now()
  where id=v_inserted_id returning * into v_receipt;
  update public.agent_runtime_tasks set effect_outcome='completed',updated_at=now()
  where id=p_task_id and owner_user_id=p_owner_user_id;

  return jsonb_build_object('outcome','completed','receipt',to_jsonb(v_receipt),'execution',v_result);
end;
$$;

revoke all on function public.execute_agent_social_message_approval_effect(uuid,uuid,uuid,integer,text,text,text,uuid,uuid,text,text,uuid,text,uuid,text,text,text)
  from public,anon,authenticated;
grant execute on function public.execute_agent_social_message_approval_effect(uuid,uuid,uuid,integer,text,text,text,uuid,uuid,text,text,uuid,text,uuid,text,text,text)
  to service_role;

commit;

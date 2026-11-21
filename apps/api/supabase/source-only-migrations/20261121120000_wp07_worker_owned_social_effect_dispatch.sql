-- WP-07/WP-06: dispatch owner-approved Social effects through the canonical durable Agent Runtime.
-- Source-only: no database changes are applied by this migration file.
begin;

alter table public.agent_social_action_approvals
  add column if not exists dispatch_task_id uuid
    references public.agent_runtime_tasks(id) on delete restrict;

create unique index if not exists agent_social_action_approvals_dispatch_task_uidx
  on public.agent_social_action_approvals(dispatch_task_id)
  where dispatch_task_id is not null;

alter table public.agent_social_audit_events
  drop constraint if exists agent_social_audit_events_event_type_check;
alter table public.agent_social_audit_events
  add constraint agent_social_audit_events_event_type_check
  check (event_type in (
    'policy_created','policy_updated','policy_disabled','draft_requested',
    'approval_approved','approval_rejected','approval_revoked','effect_completed'
  )) not valid;

create or replace function public.enqueue_agent_social_runtime_dispatch()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_source public.agent_runtime_tasks%rowtype;
  v_tool_key text;
  v_dispatch_id uuid;
  v_plan jsonb;
  v_fingerprint text;
  v_trace_id text;
begin
  v_tool_key := case new.action_type
    when 'draft_comment' then 'social.comment'
    when 'draft_reply' then 'social.reply'
    when 'draft_story' then 'social.story_reply'
    else null
  end;
  if v_tool_key is null then
    return new;
  end if;

  select * into v_source
  from public.agent_runtime_tasks
  where id = new.runtime_task_id
    and owner_user_id = new.owner_user_id
    and agent_id = new.agent_id
    and state = 'succeeded'
  for share;

  if not found then
    raise exception 'AGENT_SOCIAL_SOURCE_RUNTIME_TASK_INVALID' using errcode = '23514';
  end if;

  if not exists (
    select 1 from public.agent_skills s
    where s.id = v_source.skill_id and s.agent_id = new.agent_id
      and s.status = 'published' and v_tool_key = any(s.tool_dependencies)
  ) then
    raise exception 'AGENT_SOCIAL_SKILL_SCOPE_REQUIRED' using errcode = '42501';
  end if;

  if not exists (
    select 1 from public.agent_capabilities c
    where c.agent_id = new.agent_id and c.capability_key = v_tool_key
      and c.status = 'approved' and c.runtime_policy_id is not null
  ) then
    raise exception 'AGENT_SOCIAL_CAPABILITY_NOT_APPROVED' using errcode = '42501';
  end if;

  v_trace_id := 'agent-social:' || new.id::text;
  v_plan := jsonb_build_object(
    '_runtime_plan_version', 1,
    'steps', jsonb_build_array(jsonb_build_object(
      'step_id', 'approved_social_effect',
      'tool_key', v_tool_key,
      'inputs', jsonb_build_object(
        'approval_id', new.id::text,
        'reason', 'owner_approved_dispatch'
      ),
      'bindings', '{}'::jsonb
    ))
  );
  v_fingerprint := encode(
    extensions.digest(
      convert_to(jsonb_build_object(
        'approval_id', new.id,
        'source_task_id', v_source.id,
        'tool_key', v_tool_key,
        'target_content_id', new.target_content_id,
        'target_comment_id', new.target_comment_id,
        'content_version', new.content_version
      )::text, 'UTF8'),
      'sha256'
    ),
    'hex'
  );

  insert into public.agent_runtime_tasks (
    owner_user_id, session_id, agent_id, skill_id,
    agent_version, skill_version, state,
    idempotency_key, request_fingerprint, tool_key, input_payload,
    event_log, trace_id, policy_version
  ) values (
    new.owner_user_id, v_source.session_id, new.agent_id, v_source.skill_id,
    v_source.agent_version, v_source.skill_version, 'waiting_for_approval',
    'agent-social-dispatch:' || new.id::text, v_fingerprint, v_tool_key, v_plan,
    jsonb_build_array(jsonb_build_object(
      'event','agent_social_dispatch_waiting_for_approval',
      'approval_id',new.id,'trace_id',v_trace_id,'at',now()
    )),
    v_trace_id, v_source.policy_version
  )
  on conflict (owner_user_id, idempotency_key) do nothing
  returning id into v_dispatch_id;

  if v_dispatch_id is null then
    select id into v_dispatch_id
    from public.agent_runtime_tasks
    where owner_user_id = new.owner_user_id
      and idempotency_key = 'agent-social-dispatch:' || new.id::text;
  end if;

  if v_dispatch_id is null then
    raise exception 'AGENT_SOCIAL_DISPATCH_TASK_UNCONFIRMED' using errcode = '40001';
  end if;

  update public.agent_social_action_approvals
  set dispatch_task_id = v_dispatch_id
  where id = new.id;

  return new;
end;
$$;

revoke all on function public.enqueue_agent_social_runtime_dispatch()
  from public, anon, authenticated;

drop trigger if exists agent_social_runtime_dispatch_after_insert
  on public.agent_social_action_approvals;
create trigger agent_social_runtime_dispatch_after_insert
after insert on public.agent_social_action_approvals
for each row execute function public.enqueue_agent_social_runtime_dispatch();

create or replace function public.cancel_agent_social_runtime_dispatch()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  if old.status in ('pending','approved')
     and new.status in ('rejected','revoked','superseded')
     and new.dispatch_task_id is not null then
    update public.agent_runtime_tasks t
    set state = case
          when t.state in ('waiting_for_approval','created','queued','retrying') then 'cancelled'
          else t.state
        end,
        cancel_requested = case when t.state = 'executing' then true else t.cancel_requested end,
        error_code = case
          when t.state in ('waiting_for_approval','created','queued','retrying') then 'owner_approval_' || new.status
          else t.error_code
        end,
        completed_at = case
          when t.state in ('waiting_for_approval','created','queued','retrying') then now()
          else t.completed_at
        end,
        execution_lease_token = case
          when t.state in ('waiting_for_approval','created','queued','retrying') then null
          else t.execution_lease_token
        end,
        lease_expires_at = case
          when t.state in ('waiting_for_approval','created','queued','retrying') then null
          else t.lease_expires_at
        end,
        task_version = t.task_version + 1,
        event_log = t.event_log || jsonb_build_array(jsonb_build_object(
          'event','agent_social_dispatch_cancelled',
          'approval_id',new.id,'reason',new.status,'at',now()
        )),
        updated_at = now()
    where t.id = new.dispatch_task_id
      and t.state not in ('succeeded','failed','cancelled','timed_out','budget_exhausted');
  end if;
  return new;
end;
$$;

revoke all on function public.cancel_agent_social_runtime_dispatch()
  from public, anon, authenticated;

drop trigger if exists agent_social_runtime_dispatch_cancel_after_decision
  on public.agent_social_action_approvals;
create trigger agent_social_runtime_dispatch_cancel_after_decision
after update of status on public.agent_social_action_approvals
for each row execute function public.cancel_agent_social_runtime_dispatch();

create or replace function public.approve_agent_social_action_for_runtime(
  p_approval_id uuid,
  p_owner_user_id uuid,
  p_decision text,
  p_reason text default null
) returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_approval public.agent_social_action_approvals%rowtype;
  v_policy public.agent_social_presence_policies%rowtype;
  v_draft public.content_items%rowtype;
  v_dispatch public.agent_runtime_tasks%rowtype;
begin
  if (select auth.role()) <> 'service_role' then
    raise exception 'service_role_required' using errcode = '42501';
  end if;
  if p_decision not in ('approve','reject') then
    raise exception 'AGENT_SOCIAL_DECISION_INVALID' using errcode = '22023';
  end if;

  select * into v_approval
  from public.agent_social_action_approvals
  where id = p_approval_id and owner_user_id = p_owner_user_id
    and action_type in ('draft_comment','draft_reply','draft_story')
  for update;
  if not found then
    raise exception 'AGENT_SOCIAL_APPROVAL_NOT_FOUND' using errcode = 'P0002';
  end if;

  if v_approval.status <> 'pending' then
    if v_approval.status = 'approved' and p_decision = 'approve' then
      select * into v_dispatch from public.agent_runtime_tasks
      where id = v_approval.dispatch_task_id and owner_user_id = p_owner_user_id;
      return jsonb_build_object(
        'outcome','replayed','approval',to_jsonb(v_approval),
        'execution',v_approval.execution_result,
        'dispatch_task',to_jsonb(v_dispatch)
      );
    end if;
    if v_approval.status = 'rejected' and p_decision = 'reject' then
      return jsonb_build_object('outcome','replayed','approval',to_jsonb(v_approval),
                                'execution',v_approval.execution_result);
    end if;
    raise exception 'AGENT_SOCIAL_APPROVAL_ALREADY_DECIDED' using errcode = 'P0001';
  end if;

  select * into v_policy
  from public.agent_social_presence_policies
  where owner_user_id = p_owner_user_id and agent_id = v_approval.agent_id
  for share;
  if not found or not v_policy.is_enabled or v_policy.revoked_at is not null
     or not (v_approval.action_type = any(v_policy.allowed_actions)) then
    raise exception 'AGENT_SOCIAL_POLICY_REVOKED' using errcode = '42501';
  end if;

  if not exists (
    select 1 from public.ai_agents a
    join public.agent_ownerships o on o.agent_id = a.id
    where a.id = v_approval.agent_id and a.status = 'active'
      and o.owner_user_id = p_owner_user_id
      and o.ownership_role = 'owner' and o.status = 'active'
  ) then
    raise exception 'AGENT_SOCIAL_OWNERSHIP_REQUIRED' using errcode = '42501';
  end if;

  select * into v_draft
  from public.content_items
  where id = v_approval.content_id and owner_id = p_owner_user_id
    and ai_agent_id = v_approval.agent_id
  for update;
  if not found or v_draft.status <> 'draft'
     or v_draft.version <> v_approval.content_version
     or v_draft.deleted_at is not null then
    raise exception 'AGENT_SOCIAL_DRAFT_CHANGED' using errcode = '40001';
  end if;

  if p_decision = 'reject' then
    update public.agent_social_action_approvals
    set status = 'rejected', decided_at = now(), decided_by = p_owner_user_id,
        decision_reason = left(coalesce(p_reason,''),500),
        execution_result = jsonb_build_object('kind','none','outcome','rejected')
    where id = p_approval_id
    returning * into v_approval;

    insert into public.agent_social_audit_events
      (owner_user_id,agent_id,approval_id,actor_user_id,event_type,outcome,metadata)
    values (p_owner_user_id,v_approval.agent_id,p_approval_id,p_owner_user_id,
      'approval_rejected','allowed',
      jsonb_build_object('decision_reason',left(coalesce(p_reason,''),500),
                         'dispatch_task_id',v_approval.dispatch_task_id));

    insert into public.notifications
      (user_id,category,event_key,title,body,payload,delivery_state)
    values (p_owner_user_id,'social_activity',
      'agent-social-approval:'||p_approval_id::text||':rejected',
      'Persetujuan kolaborasi Agent diperbarui',
      'Draft kolaborasi Agent ditolak.',
      jsonb_build_object('type','agent_social_approval','approval_id',p_approval_id,
                         'content_id',v_approval.content_id,'status','rejected'),
      public.agent_social_notification_state(p_owner_user_id))
    on conflict (user_id,event_key) do nothing;

    return jsonb_build_object('outcome','rejected','approval',to_jsonb(v_approval),
                              'execution',v_approval.execution_result);
  end if;

  select * into v_dispatch
  from public.agent_runtime_tasks
  where id = v_approval.dispatch_task_id
    and owner_user_id = p_owner_user_id
    and agent_id = v_approval.agent_id
    and state = 'waiting_for_approval'
  for update;
  if not found then
    raise exception 'AGENT_SOCIAL_DISPATCH_TASK_NOT_WAITING' using errcode = '40001';
  end if;

  update public.agent_social_action_approvals
  set status = 'approved', decided_at = now(), decided_by = p_owner_user_id,
      decision_reason = left(coalesce(p_reason,''),500),
      execution_result = jsonb_build_object(
        'kind','pending_agent_runtime','status','queued',
        'dispatch_task_id',v_dispatch.id,'next_action','agent_runtime_worker'
      )
  where id = p_approval_id
  returning * into v_approval;

  update public.agent_runtime_tasks
  set state = 'queued',
      task_version = task_version + 1,
      event_log = event_log || jsonb_build_array(jsonb_build_object(
        'event','agent_social_approval_authorized',
        'approval_id',p_approval_id,'trace_id',trace_id,'at',now()
      )),
      updated_at = now()
  where id = v_dispatch.id and owner_user_id = p_owner_user_id
  returning * into v_dispatch;
  if not found then
    raise exception 'AGENT_SOCIAL_DISPATCH_ENQUEUE_UNCONFIRMED' using errcode = '40001';
  end if;

  insert into public.agent_social_audit_events
    (owner_user_id,agent_id,approval_id,actor_user_id,event_type,outcome,metadata)
  values (p_owner_user_id,v_approval.agent_id,p_approval_id,p_owner_user_id,
    'approval_approved','allowed',
    jsonb_build_object('decision_reason',left(coalesce(p_reason,''),500),
                       'dispatch_task_id',v_dispatch.id,'execution_state','queued'));

  insert into public.notifications
    (user_id,category,event_key,title,body,payload,delivery_state)
  values (p_owner_user_id,'social_activity',
    'agent-social-approval:'||p_approval_id::text||':approved',
    'Persetujuan kolaborasi Agent diperbarui',
    'Draft disetujui dan dikirim ke Agent Runtime.',
    jsonb_build_object('type','agent_social_approval','approval_id',p_approval_id,
                       'content_id',v_approval.content_id,'status','approved',
                       'dispatch_task_id',v_dispatch.id,'execution_state','queued'),
    public.agent_social_notification_state(p_owner_user_id))
  on conflict (user_id,event_key) do nothing;

  return jsonb_build_object(
    'outcome','approved','approval',to_jsonb(v_approval),
    'execution',v_approval.execution_result,'dispatch_task',to_jsonb(v_dispatch)
  );
end;
$$;

revoke all on function public.approve_agent_social_action_for_runtime(uuid,uuid,text,text)
  from public, anon, authenticated;
grant execute on function public.approve_agent_social_action_for_runtime(uuid,uuid,text,text)
  to service_role;

create or replace function public.execute_agent_social_approval_effect(
  p_task_id uuid,
  p_owner_user_id uuid,
  p_lease_token uuid,
  p_task_version integer,
  p_step_key text,
  p_idempotency_key text,
  p_input_fingerprint text,
  p_actor_user_id uuid,
  p_agent_id uuid,
  p_action_key text,
  p_target_reference text,
  p_approval_id uuid,
  p_correlation_id text,
  p_policy_id uuid,
  p_policy_version text,
  p_policy_digest text,
  p_reason text default null
) returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_task public.agent_runtime_tasks%rowtype;
  v_policy public.agent_runtime_policies%rowtype;
  v_social_policy public.agent_social_presence_policies%rowtype;
  v_approval public.agent_social_action_approvals%rowtype;
  v_receipt public.agent_runtime_effect_receipts%rowtype;
  v_draft public.content_items%rowtype;
  v_target public.content_items%rowtype;
  v_parent_comment public.content_comments%rowtype;
  v_comment public.content_comments%rowtype;
  v_story_owner uuid;
  v_recipient uuid;
  v_conversation_id uuid;
  v_message_id uuid;
  v_inserted_id uuid;
  v_target_id uuid;
  v_action_key text;
  v_body text;
  v_execution jsonb;
begin
  if (select auth.role()) <> 'service_role' then
    raise exception 'service_role_required' using errcode = '42501';
  end if;
  if p_owner_user_id is null or p_actor_user_id is distinct from p_owner_user_id
     or p_agent_id is null or p_approval_id is null
     or p_step_key is null or p_step_key = ''
     or p_idempotency_key is distinct from p_approval_id::text
     or p_correlation_id is null or p_correlation_id = ''
     or p_action_key not in ('social.comment','social.reply','social.story_reply')
     or p_target_reference is null or p_policy_version is null
     or p_policy_digest !~ '^[a-f0-9]{64}$'
     or p_input_fingerprint !~ '^[a-f0-9]{64}$' then
    raise exception 'AGENT_SOCIAL_EFFECT_COMMAND_INVALID' using errcode = '22023';
  end if;

  -- Lock approval first, matching owner decision/revocation lock order.
  select * into v_approval
  from public.agent_social_action_approvals
  where id = p_approval_id and owner_user_id = p_owner_user_id
    and agent_id = p_agent_id
  for update;
  if not found or v_approval.status <> 'approved'
     or v_approval.dispatch_task_id is distinct from p_task_id then
    raise exception 'AGENT_SOCIAL_APPROVAL_NOT_AUTHORIZED' using errcode = '42501';
  end if;

  select * into v_task
  from public.agent_runtime_tasks
  where id = p_task_id and owner_user_id = p_owner_user_id
  for update;
  if not found or v_task.state <> 'executing'
     or v_task.execution_lease_token is distinct from p_lease_token
     or v_task.lease_expires_at is null or v_task.lease_expires_at <= now()
     or v_task.task_version <> p_task_version
     or v_task.agent_id <> p_agent_id then
    raise exception 'AGENT_RUNTIME_STALE_LEASE' using errcode = '40001';
  end if;

  select * into v_policy
  from public.agent_runtime_policies
  where id = p_policy_id and agent_id = p_agent_id
    and policy_version = p_policy_version and policy_digest = p_policy_digest
    and status = 'approved'
    and p_action_key = any(approved_tool_keys)
  for share;
  if not found then
    raise exception 'AGENT_RUNTIME_EFFECT_POLICY_NOT_APPROVED' using errcode = '42501';
  end if;

  select * into v_social_policy
  from public.agent_social_presence_policies
  where owner_user_id = p_owner_user_id and agent_id = p_agent_id
  for share;
  if not found or not v_social_policy.is_enabled
     or v_social_policy.revoked_at is not null
     or not (v_approval.action_type = any(v_social_policy.allowed_actions)) then
    raise exception 'AGENT_SOCIAL_POLICY_REVOKED' using errcode = '42501';
  end if;

  if not exists (
    select 1 from public.ai_agents a
    join public.agent_ownerships o on o.agent_id = a.id
    where a.id = p_agent_id and a.status = 'active'
      and o.owner_user_id = p_owner_user_id
      and o.ownership_role = 'owner' and o.status = 'active'
  ) then
    raise exception 'AGENT_SOCIAL_OWNERSHIP_REQUIRED' using errcode = '42501';
  end if;

  v_action_key := case v_approval.action_type
    when 'draft_comment' then 'social.comment'
    when 'draft_reply' then 'social.reply'
    when 'draft_story' then 'social.story_reply'
    else null
  end;
  v_target_id := coalesce(v_approval.target_content_id,v_approval.content_id);
  if v_action_key is distinct from p_action_key
     or p_target_reference <> 'content:' || v_target_id::text then
    raise exception 'AGENT_SOCIAL_EFFECT_TARGET_OR_ACTION_MISMATCH' using errcode = '42501';
  end if;

  select * into v_receipt
  from public.agent_runtime_effect_receipts
  where task_id = p_task_id and step_key = p_step_key
    and idempotency_key = p_idempotency_key
  for update;
  if found then
    if v_receipt.input_fingerprint <> p_input_fingerprint
       or v_receipt.approval_id is distinct from p_approval_id
       or v_receipt.owner_user_id is distinct from p_owner_user_id
       or v_receipt.actor_user_id is distinct from p_actor_user_id
       or v_receipt.agent_id is distinct from p_agent_id
       or v_receipt.target_reference is distinct from p_target_reference
       or v_receipt.action_key is distinct from p_action_key
       or v_receipt.correlation_id is distinct from p_correlation_id
       or v_receipt.policy_id is distinct from p_policy_id
       or v_receipt.policy_version is distinct from p_policy_version
       or v_receipt.policy_digest is distinct from p_policy_digest then
      raise exception 'AGENT_RUNTIME_EFFECT_IDEMPOTENCY_CONFLICT' using errcode = '23505';
    end if;
    if v_receipt.status = 'completed' then
      return jsonb_build_object('outcome','replayed','receipt',to_jsonb(v_receipt),
                                'execution',v_receipt.result_payload);
    end if;
    raise exception 'AGENT_RUNTIME_EFFECT_OUTCOME_UNKNOWN_NO_REPLAY' using errcode = '40001';
  end if;

  if v_approval.execution_result->>'kind' <> 'pending_agent_runtime' then
    raise exception 'AGENT_SOCIAL_APPROVAL_EXECUTION_ALREADY_CONSUMED' using errcode = '40001';
  end if;

  select * into v_draft
  from public.content_items
  where id = v_approval.content_id and owner_id = p_owner_user_id
    and ai_agent_id = p_agent_id
  for update;
  if not found or v_draft.status <> 'draft'
     or v_draft.version <> v_approval.content_version
     or v_draft.deleted_at is not null then
    raise exception 'AGENT_SOCIAL_DRAFT_CHANGED' using errcode = '40001';
  end if;
  v_body := btrim(v_draft.body);

  insert into public.agent_runtime_effect_receipts (
    task_id,task_version,step_key,idempotency_key,input_fingerprint,status,
    actor_user_id,owner_user_id,agent_id,target_reference,action_key,
    approval_id,correlation_id,provider_key,policy_id,policy_version,
    policy_digest,metadata
  ) values (
    p_task_id,p_task_version,p_step_key,p_idempotency_key,p_input_fingerprint,'started',
    p_actor_user_id,p_owner_user_id,p_agent_id,p_target_reference,p_action_key,
    p_approval_id,p_correlation_id,'allpha.social',p_policy_id,p_policy_version,
    p_policy_digest,jsonb_build_object('approval_id',p_approval_id,'action_key',p_action_key)
  ) returning id into v_inserted_id;

  update public.agent_runtime_tasks
  set effect_outcome = 'started', current_step_key = p_step_key, updated_at = now()
  where id = p_task_id and owner_user_id = p_owner_user_id;

  if p_action_key in ('social.comment','social.reply') then
    if v_approval.target_content_id is null then
      raise exception 'AGENT_SOCIAL_COMMENT_TARGET_REQUIRED' using errcode = '22023';
    end if;
    select * into v_target from public.content_items
    where id = v_approval.target_content_id and content_type <> 'story'
      and status = 'published' and moderation_status = 'approved' and deleted_at is null
    for share;
    if not found or v_target.visibility not in ('public','followers') then
      raise exception 'AGENT_SOCIAL_TARGET_NOT_AVAILABLE' using errcode = 'P0002';
    end if;
    if exists (
      select 1 from public.social_edges e
      where e.status = 'active' and e.edge_type = 'block'
        and ((e.actor_user_id = p_owner_user_id and e.target_user_id = v_target.owner_id)
          or (e.actor_user_id = v_target.owner_id and e.target_user_id = p_owner_user_id))
    ) then
      raise exception 'AGENT_SOCIAL_TARGET_BLOCKED' using errcode = '42501';
    end if;
    if v_target.visibility = 'followers' and not exists (
      select 1 from public.social_edges e
      where e.actor_user_id = p_owner_user_id and e.target_user_id = v_target.owner_id
        and e.edge_type = 'follow' and e.status = 'active'
    ) then
      raise exception 'AGENT_SOCIAL_TARGET_NOT_VISIBLE' using errcode = '42501';
    end if;

    if p_action_key = 'social.reply' then
      if v_approval.target_comment_id is null then
        raise exception 'AGENT_SOCIAL_PARENT_COMMENT_REQUIRED' using errcode = '22023';
      end if;
      select * into v_parent_comment from public.content_comments
      where id = v_approval.target_comment_id
        and content_id = v_approval.target_content_id and status = 'visible'
      for share;
      if not found then
        raise exception 'AGENT_SOCIAL_PARENT_COMMENT_NOT_AVAILABLE' using errcode = 'P0002';
      end if;
      if exists (
        select 1 from public.social_edges e
        where e.status = 'active' and e.edge_type = 'block'
          and ((e.actor_user_id = p_owner_user_id and e.target_user_id = v_parent_comment.actor_user_id)
            or (e.actor_user_id = v_parent_comment.actor_user_id and e.target_user_id = p_owner_user_id))
      ) then
        raise exception 'AGENT_SOCIAL_REPLY_BLOCKED' using errcode = '42501';
      end if;
      v_recipient := v_parent_comment.actor_user_id;
    else
      if v_approval.target_comment_id is not null then
        raise exception 'AGENT_SOCIAL_ROOT_COMMENT_HAS_PARENT' using errcode = '22023';
      end if;
      v_recipient := v_target.owner_id;
    end if;

    insert into public.content_comments(
      content_id,actor_user_id,body,status,parent_comment_id,
      actor_agent_id,agent_social_approval_id,agent_disclosure_snapshot
    ) values (
      v_approval.target_content_id,p_owner_user_id,v_body,'visible',
      case when p_action_key = 'social.reply' then v_approval.target_comment_id else null end,
      p_agent_id,p_approval_id,v_approval.disclosure_snapshot
    ) returning * into v_comment;

    v_execution := jsonb_build_object(
      'kind','comment','comment_id',v_comment.id,
      'content_id',v_approval.target_content_id,
      'parent_comment_id',v_comment.parent_comment_id,
      'agent_id',p_agent_id,'disclosure',v_approval.disclosure_snapshot
    );
  else
    if v_approval.target_content_id is null then
      raise exception 'AGENT_SOCIAL_STORY_TARGET_REQUIRED' using errcode = '22023';
    end if;
    select * into v_target from public.content_items
    where id = v_approval.target_content_id and content_type = 'story'
      and status = 'published' and moderation_status = 'approved'
      and expires_at > now() and deleted_at is null
    for share;
    if not found then
      raise exception 'AGENT_SOCIAL_STORY_NOT_AVAILABLE' using errcode = 'P0002';
    end if;
    v_story_owner := v_target.owner_id;
    if v_story_owner = p_owner_user_id then
      raise exception 'AGENT_SOCIAL_STORY_SELF_REPLY_NOT_ALLOWED' using errcode = '22023';
    end if;
    if exists (
      select 1 from public.social_edges e
      where e.status = 'active' and e.edge_type = 'block'
        and ((e.actor_user_id = p_owner_user_id and e.target_user_id = v_story_owner)
          or (e.actor_user_id = v_story_owner and e.target_user_id = p_owner_user_id))
    ) then
      raise exception 'AGENT_SOCIAL_STORY_REPLY_BLOCKED' using errcode = '42501';
    end if;
    if v_target.visibility = 'followers' and not exists (
      select 1 from public.social_edges e
      where e.actor_user_id = p_owner_user_id and e.target_user_id = v_story_owner
        and e.edge_type = 'follow' and e.status = 'active'
    ) then
      raise exception 'AGENT_SOCIAL_STORY_NOT_VISIBLE' using errcode = '42501';
    end if;
    if v_target.visibility not in ('public','followers') then
      raise exception 'AGENT_SOCIAL_STORY_NOT_VISIBLE' using errcode = '42501';
    end if;

    insert into public.conversations(kind,title,created_by)
    values('agent','Balasan Story',p_owner_user_id)
    returning id into v_conversation_id;
    insert into public.conversation_participants(conversation_id,user_id,participant_type)
    values(v_conversation_id,v_story_owner,'human');
    insert into public.conversation_participants(conversation_id,agent_id,participant_type)
    values(v_conversation_id,p_agent_id,'agent');
    insert into public.messages(
      conversation_id,sender_type,sender_agent_id,body,client_message_id,
      delivery_status,story_id
    ) values (
      v_conversation_id,'agent',p_agent_id,v_body,p_approval_id,'sent',
      v_approval.target_content_id
    ) returning id into v_message_id;
    update public.conversations
    set updated_at = now(), last_message_at = now()
    where id = v_conversation_id;
    v_recipient := v_story_owner;
    v_execution := jsonb_build_object(
      'kind','story_dm','message_id',v_message_id,
      'conversation_id',v_conversation_id,'story_id',v_approval.target_content_id,
      'recipient_user_id',v_story_owner,'agent_id',p_agent_id,
      'disclosure',v_approval.disclosure_snapshot
    );
  end if;

  update public.agent_social_action_approvals
  set execution_result = v_execution
  where id = p_approval_id;

  update public.agent_runtime_effect_receipts
  set status = 'completed', result_payload = v_execution,
      external_reference = coalesce(v_execution->>'comment_id',v_execution->>'message_id'),
      evidence_reference = 'agent_social_action_approvals:' || p_approval_id::text,
      completed_at = now(), updated_at = now()
  where id = v_inserted_id
  returning * into v_receipt;

  update public.agent_runtime_tasks
  set effect_outcome = 'completed', updated_at = now()
  where id = p_task_id and owner_user_id = p_owner_user_id
    and execution_lease_token = p_lease_token
    and task_version = p_task_version;
  if not found then
    raise exception 'AGENT_RUNTIME_LEASE_EXPIRED_BEFORE_COMMIT' using errcode = '40001';
  end if;

  insert into public.agent_social_audit_events
    (owner_user_id,agent_id,approval_id,actor_user_id,event_type,outcome,metadata)
  values (
    p_owner_user_id,p_agent_id,p_approval_id,p_actor_user_id,
    'effect_completed','allowed',
    jsonb_build_object('task_id',p_task_id,'receipt_id',v_receipt.id,
                       'action_key',p_action_key,'target_reference',p_target_reference,
                       'correlation_id',p_correlation_id,'result',v_execution)
  );

  if v_recipient is not null and v_recipient <> p_owner_user_id then
    insert into public.notifications
      (user_id,category,event_key,title,body,payload,delivery_state)
    values (
      v_recipient,'social_activity','agent-social-action:'||p_approval_id::text,
      case when p_action_key = 'social.story_reply' then 'Balasan Story baru' else 'Balasan komentar baru' end,
      case when p_action_key = 'social.story_reply' then 'AI Agent membalas Story Anda melalui pesan.' else 'AI Agent membalas komentar Anda.' end,
      jsonb_build_object('type',case when p_action_key = 'social.story_reply' then 'story_dm' else 'comment_reply' end,
                         'approval_id',p_approval_id,'agent_id',p_agent_id,
                         'execution',v_execution,'receipt_id',v_receipt.id),
      public.agent_social_notification_state(v_recipient)
    )
    on conflict (user_id,event_key) do nothing;
  end if;

  return jsonb_build_object('outcome','completed','receipt',to_jsonb(v_receipt),
                            'execution',v_execution);
end;
$$;

revoke all on function public.execute_agent_social_approval_effect(
  uuid,uuid,uuid,integer,text,text,text,uuid,uuid,text,text,uuid,text,uuid,text,text,text
) from public, anon, authenticated;
grant execute on function public.execute_agent_social_approval_effect(
  uuid,uuid,uuid,integer,text,text,text,uuid,uuid,text,text,uuid,text,uuid,text,text,text
) to service_role;

commit;

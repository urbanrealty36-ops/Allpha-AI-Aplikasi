-- WP-07/WP-06: atomic Allpha Social side-effect execution with a durable runtime receipt.
-- Source-only. The function is deliberately not activated until its dependency migrations
-- and the approved isolated verification gate are satisfied.
begin;

alter table public.agent_runtime_effect_receipts
  add column if not exists actor_user_id uuid references auth.users(id) on delete restrict,
  add column if not exists owner_user_id uuid references auth.users(id) on delete restrict,
  add column if not exists agent_id uuid references public.ai_agents(id) on delete restrict,
  add column if not exists target_reference text,
  add column if not exists action_key text,
  add column if not exists approval_id uuid,
  add column if not exists correlation_id text,
  add column if not exists provider_key text,
  add column if not exists external_reference text,
  add column if not exists evidence_reference text,
  add column if not exists policy_id uuid,
  add column if not exists policy_version text,
  add column if not exists policy_digest text,
  add column if not exists metadata jsonb not null default '{}'::jsonb;

update public.agent_runtime_effect_receipts r
set owner_user_id = t.owner_user_id,
    agent_id = t.agent_id
from public.agent_runtime_tasks t
where t.id = r.task_id
  and (r.owner_user_id is null or r.agent_id is null);

alter table public.agent_runtime_effect_receipts
  add constraint agent_runtime_effect_receipts_metadata_object
  check (jsonb_typeof(metadata) = 'object') not valid;

create index if not exists agent_runtime_effect_receipts_owner_created_idx
  on public.agent_runtime_effect_receipts(owner_user_id, updated_at desc)
  where owner_user_id is not null;
create index if not exists agent_runtime_effect_receipts_approval_idx
  on public.agent_runtime_effect_receipts(approval_id)
  where approval_id is not null;
create index if not exists agent_runtime_effect_receipts_correlation_idx
  on public.agent_runtime_effect_receipts(correlation_id)
  where correlation_id is not null;

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
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_task public.agent_runtime_tasks%rowtype;
  v_policy public.agent_runtime_policies%rowtype;
  v_approval public.agent_social_action_approvals%rowtype;
  v_receipt public.agent_runtime_effect_receipts%rowtype;
  v_inserted_id uuid;
  v_decision jsonb;
  v_execution jsonb;
  v_target_id uuid;
  v_action_key text;
begin
  if p_owner_user_id is null or p_actor_user_id is null
     or p_actor_user_id <> p_owner_user_id
     or p_agent_id is null or p_approval_id is null
     or coalesce(p_step_key,'') = ''
     or coalesce(p_idempotency_key,'') = ''
     or coalesce(p_correlation_id,'') = ''
     or coalesce(p_action_key,'') not in ('social.comment','social.reply','social.story_reply')
     or coalesce(p_target_reference,'') = ''
     or coalesce(p_policy_version,'') = ''
     or coalesce(p_policy_digest,'') !~ '^[a-f0-9]{64}$'
     or coalesce(p_input_fingerprint,'') !~ '^[a-f0-9]{64}$' then
    raise exception 'AGENT_SOCIAL_EFFECT_COMMAND_INVALID' using errcode = '22023';
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

  select * into v_approval
  from public.agent_social_action_approvals
  where id = p_approval_id and owner_user_id = p_owner_user_id
    and agent_id = p_agent_id
  for update;

  if not found then
    raise exception 'AGENT_SOCIAL_APPROVAL_NOT_FOUND' using errcode = 'P0002';
  end if;

  v_action_key := case v_approval.action_type
    when 'draft_comment' then 'social.comment'
    when 'draft_reply' then 'social.reply'
    when 'draft_story' then 'social.story_reply'
    else null
  end;
  v_target_id := coalesce(v_approval.target_content_id, v_approval.content_id);

  if v_action_key is distinct from p_action_key
     or p_target_reference <> 'content:' || v_target_id::text then
    raise exception 'AGENT_SOCIAL_EFFECT_TARGET_OR_ACTION_MISMATCH' using errcode = '42501';
  end if;

  insert into public.agent_runtime_effect_receipts (
    task_id, task_version, step_key, idempotency_key, input_fingerprint, status,
    actor_user_id, owner_user_id, agent_id, target_reference, action_key,
    approval_id, correlation_id, provider_key, policy_id, policy_version,
    policy_digest, metadata
  ) values (
    p_task_id, p_task_version, p_step_key, p_idempotency_key, p_input_fingerprint, 'started',
    p_actor_user_id, p_owner_user_id, p_agent_id, p_target_reference, p_action_key,
    p_approval_id, p_correlation_id, 'allpha.social', p_policy_id, p_policy_version,
    p_policy_digest, jsonb_build_object('approval_id',p_approval_id,'action_key',p_action_key)
  )
  on conflict (task_id, step_key, idempotency_key) do nothing
  returning id into v_inserted_id;

  if v_inserted_id is null then
    select * into v_receipt
    from public.agent_runtime_effect_receipts
    where task_id = p_task_id and step_key = p_step_key
      and idempotency_key = p_idempotency_key
    for update;

    if v_receipt.input_fingerprint <> p_input_fingerprint then
      raise exception 'AGENT_RUNTIME_EFFECT_IDEMPOTENCY_CONFLICT' using errcode = '23505';
    end if;
    if v_receipt.status = 'completed' then
      return jsonb_build_object('outcome','replayed','receipt',to_jsonb(v_receipt),
                                'execution',v_receipt.result_payload);
    end if;
    raise exception 'AGENT_RUNTIME_EFFECT_OUTCOME_UNKNOWN_NO_REPLAY' using errcode = '40001';
  end if;

  update public.agent_runtime_tasks
  set effect_outcome = 'started', current_step_key = p_step_key, updated_at = now()
  where id = p_task_id;

  v_decision := public.decide_agent_social_approval(
    p_approval_id, p_owner_user_id, 'approve', left(coalesce(p_reason,''),500)
  );

  if jsonb_typeof(v_decision) <> 'object'
     or v_decision->>'outcome' not in ('approved','replayed')
     or coalesce(v_decision->'approval'->>'status','') <> 'approved'
     or jsonb_typeof(v_decision->'execution') <> 'object' then
    raise exception 'AGENT_SOCIAL_EFFECT_NOT_CONFIRMED' using errcode = '40001';
  end if;

  v_execution := v_decision->'execution';

  -- Recheck the lease at commit time. The task row lock prevents a competing
  -- worker from taking over while this transaction executes. If the lease expired
  -- during the operation, raising rolls back the social mutation and the receipt.
  select * into v_task
  from public.agent_runtime_tasks
  where id = p_task_id and owner_user_id = p_owner_user_id
  for update;

  if not found or v_task.state <> 'executing'
     or v_task.execution_lease_token is distinct from p_lease_token
     or v_task.lease_expires_at is null or v_task.lease_expires_at <= now()
     or v_task.task_version <> p_task_version then
    raise exception 'AGENT_RUNTIME_LEASE_EXPIRED_BEFORE_COMMIT' using errcode = '40001';
  end if;

  update public.agent_runtime_effect_receipts
  set status = 'completed',
      result_payload = v_execution,
      external_reference = coalesce(v_execution->>'comment_id',v_execution->>'message_id',v_execution->>'content_id'),
      evidence_reference = 'agent_social_action_approvals:' || p_approval_id::text,
      completed_at = now(),
      updated_at = now()
  where id = v_inserted_id
  returning * into v_receipt;

  update public.agent_runtime_tasks
  set effect_outcome = 'completed', updated_at = now()
  where id = p_task_id and owner_user_id = p_owner_user_id;

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

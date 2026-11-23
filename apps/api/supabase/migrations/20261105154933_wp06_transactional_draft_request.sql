-- WP-06: draft + approval request + audit + ENG-P20 notification are one transaction.
create or replace function public.request_agent_social_draft(
  p_owner_user_id uuid,
  p_agent_id uuid,
  p_runtime_task_id uuid,
  p_action_type text,
  p_content_type text,
  p_visibility text,
  p_body text,
  p_target_content_id uuid,
  p_target_comment_id uuid,
  p_idempotency_key text
) returns jsonb
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  v_task public.agent_runtime_tasks%rowtype;
  v_policy public.agent_social_presence_policies%rowtype;
  v_item public.content_items%rowtype;
  v_approval public.agent_social_action_approvals%rowtype;
  v_prior public.agent_social_action_approvals%rowtype;
  v_generated text;
begin
  if p_action_type not in ('draft_post','draft_comment','draft_reply','suggest_repost','draft_story')
     or p_content_type not in ('text','image','video','story')
     or p_visibility not in ('public','followers','private')
     or length(btrim(coalesce(p_body,''))) not between 1 and 10000
     or length(p_idempotency_key) not between 12 and 160 then
    raise exception 'AGENT_SOCIAL_DRAFT_INPUT_INVALID' using errcode = '22023';
  end if;
  if p_action_type in ('draft_comment','draft_reply') and p_target_content_id is null then
    raise exception 'AGENT_SOCIAL_COMMENT_TARGET_REQUIRED' using errcode = '22023';
  end if;
  if p_action_type = 'draft_reply' and p_target_comment_id is null then
    raise exception 'AGENT_SOCIAL_PARENT_COMMENT_REQUIRED' using errcode = '22023';
  end if;
  if p_action_type = 'draft_story' and (p_target_content_id is null or p_content_type <> 'story') then
    raise exception 'AGENT_SOCIAL_STORY_TARGET_REQUIRED' using errcode = '22023';
  end if;

  perform pg_advisory_xact_lock(hashtextextended(p_owner_user_id::text||':'||p_idempotency_key,0));
  select * into v_prior from public.agent_social_action_approvals
  where owner_user_id = p_owner_user_id and idempotency_key = p_idempotency_key;
  if found then
    if v_prior.agent_id <> p_agent_id or v_prior.runtime_task_id <> p_runtime_task_id
       or v_prior.action_type <> p_action_type or v_prior.target_content_id is distinct from p_target_content_id
       or v_prior.target_comment_id is distinct from p_target_comment_id then
      raise exception 'AGENT_SOCIAL_IDEMPOTENCY_KEY_REUSED' using errcode = '23505';
    end if;
    select * into v_item from public.content_items where id = v_prior.content_id;
    return jsonb_build_object('outcome','replayed','item',to_jsonb(v_item),'approval',to_jsonb(v_prior));
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

  select * into v_task from public.agent_runtime_tasks
  where id = p_runtime_task_id and owner_user_id = p_owner_user_id
    and agent_id = p_agent_id and state = 'succeeded' and completed_at is not null
  for share;
  if not found or jsonb_typeof(v_task.output_payload) <> 'object' then
    raise exception 'AGENT_SOCIAL_RUNTIME_TASK_REQUIRED' using errcode = 'P0002';
  end if;
  v_generated := coalesce(
    nullif(btrim(v_task.output_payload->>'content'),''),
    nullif(btrim(v_task.output_payload->>'text'),''),
    nullif(btrim(v_task.output_payload->>'body'),''),
    nullif(btrim(v_task.output_payload->>'generated_text'),'')
  );
  if v_generated is null or length(v_generated) > 10000 or v_generated <> btrim(p_body) then
    raise exception 'AGENT_SOCIAL_RUNTIME_OUTPUT_MISMATCH' using errcode = '22023';
  end if;

  select * into v_policy from public.agent_social_presence_policies
  where owner_user_id = p_owner_user_id and agent_id = p_agent_id
  for share;
  if not found or not v_policy.is_enabled or v_policy.revoked_at is not null
     or not (p_action_type = any(v_policy.allowed_actions))
     or v_policy.approval_mode = 'disabled' then
    raise exception 'AGENT_SOCIAL_ACTION_NOT_AUTHORIZED' using errcode = '42501';
  end if;

  insert into public.content_items
    (owner_id,ai_agent_id,content_type,body,visibility,status,moderation_status,version,provenance)
  values
    (p_owner_user_id,p_agent_id,p_content_type,btrim(p_body),p_visibility,'draft','not_submitted',1,
     jsonb_build_object('coauthored',true,'human_owner_id',p_owner_user_id,'agent_id',p_agent_id,
                        'runtime_task_id',p_runtime_task_id,
                        'runtime_output_sha256',encode(digest(btrim(p_body),'sha256'),'hex'),
                        'disclosure',v_policy.disclosure_text,'agent_policy_version',v_policy.version))
  returning * into v_item;

  insert into public.agent_social_action_approvals
    (owner_user_id,agent_id,content_id,runtime_task_id,target_content_id,target_comment_id,
     action_type,content_version,status,disclosure_snapshot,idempotency_key)
  values
    (p_owner_user_id,p_agent_id,v_item.id,p_runtime_task_id,p_target_content_id,p_target_comment_id,
     p_action_type,v_item.version,'pending',v_policy.disclosure_text,p_idempotency_key)
  returning * into v_approval;

  insert into public.agent_social_audit_events
    (owner_user_id,agent_id,approval_id,actor_user_id,event_type,outcome,metadata)
  values
    (p_owner_user_id,p_agent_id,v_approval.id,p_owner_user_id,'draft_requested','allowed',
     jsonb_build_object('action_type',p_action_type,'runtime_task_id',p_runtime_task_id,
                        'target_content_id',p_target_content_id,'target_comment_id',p_target_comment_id));

  insert into public.notifications
    (user_id,category,event_key,title,body,payload,delivery_state)
  values
    (p_owner_user_id,'social_activity','agent-social-request:'||v_approval.id::text,
     'Persetujuan AI Agent menunggu keputusan',
     'Draft kolaborasi AI Agent menunggu persetujuan Anda.',
     jsonb_build_object('type','agent_social_approval_request','approval_id',v_approval.id,
                        'content_id',v_item.id,'action_type',p_action_type),
     'queued')
  on conflict (user_id,event_key) do nothing;

  return jsonb_build_object('outcome','created','item',to_jsonb(v_item),
                            'approval',to_jsonb(v_approval),
                            'disclosure',v_policy.disclosure_text);
end;
$$;

revoke all on function public.request_agent_social_draft(uuid,uuid,uuid,text,text,text,text,uuid,uuid,text) from public, anon, authenticated;
grant execute on function public.request_agent_social_draft(uuid,uuid,uuid,text,text,text,text,uuid,uuid,text) to service_role;

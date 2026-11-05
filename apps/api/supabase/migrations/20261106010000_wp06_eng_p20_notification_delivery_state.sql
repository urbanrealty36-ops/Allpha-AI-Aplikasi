create or replace function public.agent_social_notification_state(p_user_id uuid)
returns text
language sql
stable
security definer
set search_path = public, pg_temp
as $$
  select case
    when coalesce(
      (select case when us.notification_preferences->>'social_activity' in ('true','false')
                   then (us.notification_preferences->>'social_activity')::boolean
                   else true end
       from public.user_settings us where us.user_id=p_user_id),
      true
    ) then 'delivered'
    else 'suppressed'
  end;
$$;
revoke all on function public.agent_social_notification_state(uuid) from public, anon, authenticated;
grant execute on function public.agent_social_notification_state(uuid) to service_role;

-- WP-06 transactional approval execution.
-- All approval decisions, social side effects, audit events and ENG-P20 inbox rows commit atomically.
alter table public.agent_social_action_approvals
  add column if not exists target_comment_id uuid references public.content_comments(id) on delete set null,
  add column if not exists execution_result jsonb not null default '{}'::jsonb;

alter table public.messages
  add column if not exists story_id uuid references public.content_items(id) on delete set null;

create index if not exists messages_story_id_idx
  on public.messages(story_id, created_at desc) where story_id is not null;

create or replace function public.decide_agent_social_approval(
  p_approval_id uuid,
  p_owner_user_id uuid,
  p_decision text,
  p_reason text default null
) returns jsonb
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  v_approval public.agent_social_action_approvals%rowtype;
  v_policy public.agent_social_presence_policies%rowtype;
  v_draft public.content_items%rowtype;
  v_target public.content_items%rowtype;
  v_comment public.content_comments%rowtype;
  v_story_owner uuid;
  v_recipient uuid;
  v_conversation_id uuid;
  v_message_id uuid;
  v_result jsonb := '{}'::jsonb;
  v_status text;
  v_event text;
  v_body text;
begin
  if p_decision not in ('approve','reject') then
    raise exception 'AGENT_SOCIAL_DECISION_INVALID' using errcode = '22023';
  end if;

  select * into v_approval
  from public.agent_social_action_approvals
  where id = p_approval_id and owner_user_id = p_owner_user_id
  for update;

  if not found then
    raise exception 'AGENT_SOCIAL_APPROVAL_NOT_FOUND' using errcode = 'P0002';
  end if;

  if v_approval.status <> 'pending' then
    if v_approval.status = 'approved' and p_decision = 'approve'
       and v_approval.execution_result <> '{}'::jsonb then
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
    values
      (p_owner_user_id,v_approval.agent_id,p_approval_id,p_owner_user_id,
       'approval_rejected','allowed',
       jsonb_build_object('decision_reason',left(coalesce(p_reason,''),500),'content_id',v_approval.content_id));

    insert into public.notifications
      (user_id,category,event_key,title,body,payload,delivery_state)
    values
      (p_owner_user_id,'social_activity',
       'agent-social-approval:'||p_approval_id::text||':rejected',
       'Persetujuan kolaborasi Agent diperbarui',
       'Draft kolaborasi Agent ditolak.',
       jsonb_build_object('type','agent_social_approval','approval_id',p_approval_id,
                          'content_id',v_approval.content_id,'status','rejected'),
       'queued')
    on conflict (user_id,event_key) do nothing;

    return jsonb_build_object('outcome','rejected','approval',to_jsonb(v_approval),
                              'execution',v_approval.execution_result);
  end if;

  v_status := 'approved';
  v_event := 'approval_approved';
  v_body := btrim(v_draft.body);

  if v_approval.action_type in ('draft_comment','draft_reply') then
    if v_approval.target_content_id is null then
      raise exception 'AGENT_SOCIAL_COMMENT_TARGET_REQUIRED' using errcode = '22023';
    end if;
    select * into v_target from public.content_items
    where id = v_approval.target_content_id and status = 'published'
      and moderation_status = 'approved' and deleted_at is null
    for share;
    if not found then
      raise exception 'AGENT_SOCIAL_TARGET_NOT_AVAILABLE' using errcode = 'P0002';
    end if;
    if v_approval.action_type = 'draft_reply' then
      if v_approval.target_comment_id is null then
        raise exception 'AGENT_SOCIAL_PARENT_COMMENT_REQUIRED' using errcode = '22023';
      end if;
      select * into v_comment from public.content_comments
      where id = v_approval.target_comment_id
        and content_id = v_approval.target_content_id and status = 'visible'
      for share;
      if not found then
        raise exception 'AGENT_SOCIAL_PARENT_COMMENT_NOT_AVAILABLE' using errcode = 'P0002';
      end if;
      v_recipient := v_comment.actor_user_id;
    else
      if v_approval.target_comment_id is not null then
        raise exception 'AGENT_SOCIAL_ROOT_COMMENT_HAS_PARENT' using errcode = '22023';
      end if;
      v_recipient := v_target.owner_id;
    end if;

    insert into public.content_comments(content_id,actor_user_id,body,status,parent_comment_id)
    values(v_approval.target_content_id,p_owner_user_id,v_body,'visible',
           case when v_approval.action_type = 'draft_reply' then v_approval.target_comment_id else null end)
    returning * into v_comment;

    v_result := jsonb_build_object('kind','comment','comment_id',v_comment.id,
                                   'content_id',v_approval.target_content_id,
                                   'parent_comment_id',v_comment.parent_comment_id);
  elsif v_approval.action_type = 'draft_story' then
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
    values('human','Balasan Story',p_owner_user_id)
    returning id into v_conversation_id;

    insert into public.conversation_participants(conversation_id,user_id,participant_type)
    values(v_conversation_id,v_story_owner,'human');
    insert into public.conversation_participants(conversation_id,agent_id,participant_type)
    values(v_conversation_id,v_approval.agent_id,'agent');

    insert into public.messages(conversation_id,sender_type,sender_agent_id,body,client_message_id,delivery_status,story_id)
    values(v_conversation_id,'agent',v_approval.agent_id,v_body,p_approval_id,'sent',v_approval.target_content_id)
    returning id into v_message_id;

    update public.conversations
    set updated_at = now(), last_message_at = now()
    where id = v_conversation_id;

    v_recipient := v_story_owner;
    v_result := jsonb_build_object('kind','story_dm','message_id',v_message_id,
                                   'conversation_id',v_conversation_id,
                                   'story_id',v_approval.target_content_id,
                                   'recipient_user_id',v_story_owner);
  else
    -- Post/repost suggestions remain in their canonical moderation/share workflows.
    v_result := jsonb_build_object('kind','draft_approved','content_id',v_approval.content_id,
                                   'next_action','canonical_content_or_share_lifecycle');
  end if;

  update public.agent_social_action_approvals
  set status = v_status, decided_at = now(), decided_by = p_owner_user_id,
      decision_reason = left(coalesce(p_reason,''),500),
      execution_result = v_result
  where id = p_approval_id
  returning * into v_approval;

  insert into public.agent_social_audit_events
    (owner_user_id,agent_id,approval_id,actor_user_id,event_type,outcome,metadata)
  values
    (p_owner_user_id,v_approval.agent_id,p_approval_id,p_owner_user_id,
     v_event,'allowed',
     jsonb_build_object('decision_reason',left(coalesce(p_reason,''),500),
                        'action_type',v_approval.action_type,'content_id',v_approval.content_id,
                        'execution',v_result));

  insert into public.notifications
    (user_id,category,event_key,title,body,payload,delivery_state)
  values
    (p_owner_user_id,'social_activity',
     'agent-social-approval:'||p_approval_id::text||':approved',
     'Persetujuan kolaborasi Agent diperbarui',
     'Draft kolaborasi Agent disetujui.',
     jsonb_build_object('type','agent_social_approval','approval_id',p_approval_id,
                        'content_id',v_approval.content_id,'status','approved','execution',v_result),
     public.agent_social_notification_state(p_owner_user_id))
  on conflict (user_id,event_key) do nothing;

  if v_recipient is not null and v_recipient <> p_owner_user_id then
    insert into public.notifications
      (user_id,category,event_key,title,body,payload,delivery_state)
    values
      (v_recipient,'social_activity',
       'agent-social-action:'||p_approval_id::text,
       case when v_approval.action_type = 'draft_story' then 'Balasan Story baru' else 'Balasan komentar baru' end,
       case when v_approval.action_type = 'draft_story' then 'AI Agent membalas Story Anda melalui pesan.' else 'AI Agent membalas komentar Anda.' end,
       jsonb_build_object('type',case when v_approval.action_type = 'draft_story' then 'story_dm' else 'comment_reply' end,
                          'approval_id',p_approval_id,'agent_id',v_approval.agent_id,
                          'execution',v_result),
       public.agent_social_notification_state(v_recipient))
    on conflict (user_id,event_key) do nothing;
  end if;

  return jsonb_build_object('outcome','approved','approval',to_jsonb(v_approval),
                            'execution',v_result);
end;
$$;

revoke all on function public.decide_agent_social_approval(uuid,uuid,text,text) from public, anon, authenticated;
grant execute on function public.decide_agent_social_approval(uuid,uuid,text,text) to service_role;

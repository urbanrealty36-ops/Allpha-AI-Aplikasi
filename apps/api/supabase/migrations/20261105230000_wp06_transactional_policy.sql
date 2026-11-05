-- WP-06: policy changes and automatic approval revocation are atomic with audit and ENG-P20 inbox events.
create or replace function public.save_agent_social_policy(
  p_owner_user_id uuid,
  p_agent_id uuid,
  p_allowed_actions text[],
  p_approval_mode text,
  p_disclosure_text text,
  p_is_enabled boolean,
  p_expected_version integer default null
) returns jsonb
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  v_policy public.agent_social_presence_policies%rowtype;
  v_existing public.agent_social_presence_policies%rowtype;
  v_approval public.agent_social_action_approvals%rowtype;
  v_event text;
  v_revoked_count integer := 0;
begin
  if p_approval_mode not in ('every_post','high_risk_only','disabled')
     or cardinality(coalesce(p_allowed_actions,'{}'::text[])) > 5
     or not (coalesce(p_allowed_actions,'{}'::text[]) <@ array['draft_post','draft_comment','draft_reply','suggest_repost','draft_story']::text[])
     or length(btrim(coalesce(p_disclosure_text,''))) not between 8 and 180 then
    raise exception 'AGENT_SOCIAL_POLICY_INPUT_INVALID' using errcode = '22023';
  end if;
  if not exists (
    select 1 from public.ai_agents a join public.agent_ownerships o on o.agent_id=a.id
    where a.id=p_agent_id and a.status='active' and o.owner_user_id=p_owner_user_id
      and o.ownership_role='owner' and o.status='active'
  ) then
    raise exception 'AGENT_SOCIAL_OWNERSHIP_REQUIRED' using errcode = '42501';
  end if;

  select * into v_existing from public.agent_social_presence_policies
  where owner_user_id=p_owner_user_id and agent_id=p_agent_id
  for update;

  if found then
    if p_expected_version is null or p_expected_version <> v_existing.version then
      raise exception 'AGENT_SOCIAL_POLICY_CONFLICT' using errcode = '40001';
    end if;
    update public.agent_social_presence_policies
    set allowed_actions=coalesce(p_allowed_actions,'{}'::text[]),
        approval_mode=p_approval_mode,disclosure_text=p_disclosure_text,
        is_enabled=p_is_enabled,version=v_existing.version+1,
        updated_at=now(),revoked_at=case when p_is_enabled then null else now() end
    where id=v_existing.id returning * into v_policy;
    v_event := case when p_is_enabled then 'policy_updated' else 'policy_disabled' end;
  else
    if p_expected_version is not null then
      raise exception 'AGENT_SOCIAL_POLICY_CONFLICT' using errcode = '40001';
    end if;
    insert into public.agent_social_presence_policies
      (owner_user_id,agent_id,allowed_actions,approval_mode,disclosure_text,is_enabled)
    values
      (p_owner_user_id,p_agent_id,coalesce(p_allowed_actions,'{}'::text[]),
       p_approval_mode,p_disclosure_text,p_is_enabled)
    returning * into v_policy;
    v_event := case when p_is_enabled then 'policy_created' else 'policy_disabled' end;
  end if;

  if not p_is_enabled then
    for v_approval in
      update public.agent_social_action_approvals
      set status='revoked',decided_at=now(),decided_by=p_owner_user_id,
          decision_reason='owner_policy_disabled'
      where owner_user_id=p_owner_user_id and agent_id=p_agent_id
        and status in ('pending','approved')
      returning *
    loop
      insert into public.agent_social_audit_events
        (owner_user_id,agent_id,approval_id,actor_user_id,event_type,outcome,metadata)
      values
        (p_owner_user_id,p_agent_id,v_approval.id,p_owner_user_id,
         'approval_revoked','allowed',
         jsonb_build_object('content_id',v_approval.content_id,'reason','owner_policy_disabled'));
      insert into public.notifications
        (user_id,category,event_key,title,body,payload,delivery_state)
      values
        (p_owner_user_id,'social_activity',
         'agent-social-approval:'||v_approval.id::text||':policy-revoked',
         'Persetujuan kolaborasi Agent dicabut',
         'Persetujuan dicabut karena kebijakan Agent dinonaktifkan.',
         jsonb_build_object('type','agent_social_approval','approval_id',v_approval.id,
                            'content_id',v_approval.content_id,'status','revoked'),
         'queued')
      on conflict (user_id,event_key) do nothing;
      v_revoked_count := v_revoked_count + 1;
    end loop;
  end if;

  insert into public.agent_social_audit_events
    (owner_user_id,agent_id,actor_user_id,event_type,outcome,metadata)
  values
    (p_owner_user_id,p_agent_id,p_owner_user_id,v_event,'allowed',
     jsonb_build_object('version',v_policy.version,'approval_mode',p_approval_mode,
                        'allowed_actions',coalesce(p_allowed_actions,'{}'::text[]),
                        'is_enabled',p_is_enabled,'revoked_approvals',v_revoked_count));

  return jsonb_build_object('outcome','saved','policy',to_jsonb(v_policy),
                            'revoked_approvals',v_revoked_count);
end;
$$;

revoke all on function public.save_agent_social_policy(uuid,uuid,text[],text,text,boolean,integer) from public, anon, authenticated;
grant execute on function public.save_agent_social_policy(uuid,uuid,text[],text,text,boolean,integer) to service_role;

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

-- WP-06: approval revocation must also commit with audit and ENG-P20 inbox notification.
create or replace function public.revoke_agent_social_approval(
  p_approval_id uuid,
  p_owner_user_id uuid,
  p_reason text default 'owner_revoked'
) returns jsonb
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  v_approval public.agent_social_action_approvals%rowtype;
begin
  select * into v_approval
  from public.agent_social_action_approvals
  where id = p_approval_id and owner_user_id = p_owner_user_id
  for update;
  if not found then
    raise exception 'AGENT_SOCIAL_APPROVAL_NOT_FOUND' using errcode = 'P0002';
  end if;
  if v_approval.status = 'revoked' then
    return jsonb_build_object('outcome','replayed','approval',to_jsonb(v_approval),
                              'execution',v_approval.execution_result);
  end if;
  if v_approval.status <> 'approved' then
    raise exception 'AGENT_SOCIAL_APPROVAL_NOT_REVOCABLE' using errcode = 'P0001';
  end if;

  update public.agent_social_action_approvals
  set status = 'revoked', decided_at = now(), decided_by = p_owner_user_id,
      decision_reason = left(coalesce(p_reason,'owner_revoked'),500)
  where id = p_approval_id
  returning * into v_approval;

  insert into public.agent_social_audit_events
    (owner_user_id,agent_id,approval_id,actor_user_id,event_type,outcome,metadata)
  values
    (p_owner_user_id,v_approval.agent_id,p_approval_id,p_owner_user_id,
     'approval_revoked','allowed',
     jsonb_build_object('content_id',v_approval.content_id,
                        'decision_reason',left(coalesce(p_reason,'owner_revoked'),500)));

  insert into public.notifications
    (user_id,category,event_key,title,body,payload,delivery_state)
  values
    (p_owner_user_id,'social_activity',
     'agent-social-approval:'||p_approval_id::text||':revoked',
     'Persetujuan kolaborasi Agent dicabut',
     'Persetujuan tindakan sosial Agent telah dicabut.',
     jsonb_build_object('type','agent_social_approval','approval_id',p_approval_id,
                        'content_id',v_approval.content_id,'status','revoked'),
     public.agent_social_notification_state(p_owner_user_id))
  on conflict (user_id,event_key) do nothing;

  return jsonb_build_object('outcome','revoked','approval',to_jsonb(v_approval),
                            'execution',v_approval.execution_result);
end;
$$;

revoke all on function public.revoke_agent_social_approval(uuid,uuid,text) from public, anon, authenticated;
grant execute on function public.revoke_agent_social_approval(uuid,uuid,text) to service_role;

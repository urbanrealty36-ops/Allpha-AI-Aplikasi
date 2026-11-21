-- WP-06: atomic per-Agent daily budget guard on the canonical AI Credit Ledger.
-- Source-only: do not apply until the canonical WP-06/WP-07 prerequisites are approved.
begin;

do $$
begin
  if to_regclass('public.agent_social_automation_events') is null
     or to_regclass('public.agent_social_automation_runs') is null
     or to_regclass('public.agent_social_presence_policies') is null
     or to_regclass('public.credit_reservations') is null
     or to_regprocedure('public.credit_ledger_reserve(jsonb)') is null then
    raise exception 'WP06_SOCIAL_CREDIT_GUARD_PREREQUISITES_MISSING';
  end if;
end $$;

create or replace function public.block_agent_social_automation_event(
  p_event_id uuid,p_claim_token uuid,p_reason_code text
) returns setof public.agent_social_automation_events
language plpgsql security definer set search_path=''
as $$
declare v_event public.agent_social_automation_events%rowtype;
begin
  if p_event_id is null or p_claim_token is null
     or coalesce(length(btrim(p_reason_code)),0) not between 1 and 120 then
    raise exception 'AGENT_SOCIAL_EVENT_BLOCK_INVALID' using errcode='22023';
  end if;
  update public.agent_social_automation_events e
  set status='blocked',claim_token=null,lease_expires_at=null,
      reason_code=left(p_reason_code,120),updated_at=now()
  where e.id=p_event_id and e.status='claimed'
    and e.claim_token=p_claim_token and e.lease_expires_at>now()
  returning e.* into v_event;
  if not found then return; end if;
  if p_reason_code in ('SOCIAL_ESCALATION_REQUIRED','SOCIAL_BLOCKED_TOPIC_MATCH') then
    insert into public.notifications(user_id,category,event_key,title,body,payload,delivery_state)
    values(
      v_event.owner_user_id,'social_activity','agent-social-escalation:'||v_event.id::text,
      'Auto Reply memerlukan peninjauan manusia',
      'Event Social ditahan oleh policy escalation/moderation dan tidak dikirim otomatis.',
      jsonb_build_object('type','agent_social_escalation','event_id',v_event.id,
        'agent_id',v_event.agent_id,'channel',v_event.channel,'reason_code',p_reason_code),
      'queued'
    ) on conflict(user_id,event_key) do nothing;
  end if;
  return next v_event;
end $$;

create or replace function public.credit_ledger_reserve_agent_social_auto_reply(
  p_command jsonb
) returns jsonb
language plpgsql security definer set search_path=''
as $$
declare
  v_owner uuid := nullif(p_command->>'owner_user_id','')::uuid;
  v_agent uuid := nullif(p_command->>'agent_id','')::uuid;
  v_daily_budget bigint := nullif(p_command->>'daily_credit_budget','')::bigint;
  v_requested bigint := nullif(p_command->>'credits_to_reserve','')::bigint;
  v_key text := p_command->>'idempotency_key';
  v_policy public.agent_social_presence_policies%rowtype;
  v_used bigint := 0;
begin
  if v_owner is null or v_agent is null or coalesce(v_key,'')=''
     or v_daily_budget is null or v_daily_budget<=0
     or v_requested is null or v_requested<=0 then
    raise exception 'SOCIAL_CREDIT_RESERVATION_INPUT_INVALID' using errcode='22023';
  end if;

  -- An idempotent retry must reach the canonical ledger even when the daily
  -- budget has since been exhausted by this very reservation.
  if exists (
    select 1 from public.credit_reservations r
    where r.owner_user_id=v_owner and r.idempotency_key=v_key
  ) then
    return public.credit_ledger_reserve(p_command-'agent_id'-'daily_credit_budget');
  end if;

  select * into v_policy
  from public.agent_social_presence_policies p
  where p.owner_user_id=v_owner and p.agent_id=v_agent
  for update;
  if not found or not v_policy.is_enabled or v_policy.revoked_at is not null
     or not v_policy.auto_reply_enabled or v_policy.takeover_active
     or v_policy.daily_credit_budget<>v_daily_budget then
    raise exception 'SOCIAL_CREDIT_OWNER_POLICY_CHANGED' using errcode='42501';
  end if;

  select coalesce(sum(
    case when r.state='settled' then r.settled_credits else r.reserved_credits end
  ),0) into v_used
  from public.credit_reservations r
  join public.agent_social_automation_runs ar
    on ar.runtime_task_id::text=r.task_id
  where ar.owner_user_id=v_owner and ar.agent_id=v_agent
    and (case when r.state='settled' then r.updated_at else r.created_at end)
      >= (date_trunc('day',now() at time zone 'utc') at time zone 'utc')
    and r.state in ('reserved','pending_reconciliation','settled');

  if v_used+v_requested>v_daily_budget then
    raise exception 'SOCIAL_DAILY_CREDIT_BUDGET_EXCEEDED' using errcode='42501';
  end if;

  return public.credit_ledger_reserve(p_command-'agent_id'-'daily_credit_budget');
end $$;

revoke all on function public.block_agent_social_automation_event(uuid,uuid,text)
  from public,anon,authenticated;
revoke all on function public.credit_ledger_reserve_agent_social_auto_reply(jsonb)
  from public,anon,authenticated;
grant execute on function public.block_agent_social_automation_event(uuid,uuid,text)
  to service_role;
grant execute on function public.credit_ledger_reserve_agent_social_auto_reply(jsonb)
  to service_role;

commit;

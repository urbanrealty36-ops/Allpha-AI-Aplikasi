-- SOURCE ONLY — WP-06 Human-controlled Auto Reply configuration and emergency Takeover.
-- Auto Reply execution remains disabled until the canonical event consumer is wired and approved.
begin;

alter table public.agent_social_presence_policies
  add column if not exists auto_reply_enabled boolean not null default false,
  add column if not exists auto_reply_channels text[] not null default '{}'::text[],
  add column if not exists blocked_topics text[] not null default '{}'::text[],
  add column if not exists reply_tone text not null default 'friendly_concise',
  add column if not exists allowed_tool_scopes text[] not null default '{}'::text[],
  add column if not exists max_replies_per_minute integer not null default 1,
  add column if not exists daily_credit_budget bigint not null default 0,
  add column if not exists quiet_hours jsonb not null default '{}'::jsonb,
  add column if not exists escalation_rules jsonb not null default '{}'::jsonb,
  add column if not exists owner_approval_required boolean not null default true,
  add column if not exists output_moderation_required boolean not null default true,
  add column if not exists takeover_active boolean not null default true,
  add column if not exists takeover_started_at timestamptz,
  add column if not exists takeover_started_by uuid references auth.users(id) on delete set null,
  add column if not exists automation_version integer not null default 1;

do $$
begin
  if not exists (select 1 from pg_constraint where conname='agent_social_reply_channels_check') then
    alter table public.agent_social_presence_policies add constraint agent_social_reply_channels_check
      check (auto_reply_channels <@ array['comments','mentions','dm','live_chat']::text[]);
  end if;
  if not exists (select 1 from pg_constraint where conname='agent_social_reply_tone_check') then
    alter table public.agent_social_presence_policies add constraint agent_social_reply_tone_check
      check (reply_tone in ('friendly_concise','professional','warm','formal'));
  end if;
  if not exists (select 1 from pg_constraint where conname='agent_social_reply_rate_check') then
    alter table public.agent_social_presence_policies add constraint agent_social_reply_rate_check
      check (max_replies_per_minute between 1 and 20);
  end if;
  if not exists (select 1 from pg_constraint where conname='agent_social_reply_budget_check') then
    alter table public.agent_social_presence_policies add constraint agent_social_reply_budget_check
      check (daily_credit_budget >= 0);
  end if;
  if not exists (select 1 from pg_constraint where conname='agent_social_automation_version_check') then
    alter table public.agent_social_presence_policies add constraint agent_social_automation_version_check
      check (automation_version > 0);
  end if;
  if not exists (select 1 from pg_constraint where conname='agent_social_reply_moderation_check') then
    alter table public.agent_social_presence_policies add constraint agent_social_reply_moderation_check
      check (output_moderation_required and owner_approval_required);
  end if;
end
$$;

create table if not exists public.agent_social_control_events (
  id uuid primary key default gen_random_uuid(),
  owner_user_id uuid not null references auth.users(id) on delete cascade,
  agent_id uuid not null references public.ai_agents(id) on delete cascade,
  policy_id uuid references public.agent_social_presence_policies(id) on delete set null,
  event_type text not null check (event_type in ('automation_policy_saved','takeover_activated','takeover_released')),
  actor_user_id uuid not null references auth.users(id) on delete restrict,
  metadata jsonb not null default '{}'::jsonb check (jsonb_typeof(metadata)='object'),
  created_at timestamptz not null default now()
);
create index if not exists agent_social_control_events_owner_created_idx
  on public.agent_social_control_events(owner_user_id,created_at desc);
create index if not exists agent_social_control_events_agent_created_idx
  on public.agent_social_control_events(agent_id,created_at desc);
alter table public.agent_social_control_events enable row level security;
revoke all on public.agent_social_control_events from public,anon,authenticated;
grant select,insert on public.agent_social_control_events to service_role;

create or replace function public.save_agent_social_automation_policy(
  p_owner_user_id uuid,p_agent_id uuid,p_auto_reply_channels text[],
  p_blocked_topics text[],p_reply_tone text,p_allowed_tool_scopes text[],
  p_max_replies_per_minute integer,p_daily_credit_budget bigint,
  p_quiet_hours jsonb,p_escalation_rules jsonb,p_expected_version integer
) returns jsonb
language plpgsql security definer set search_path=public,pg_temp
as $$
declare v_policy public.agent_social_presence_policies%rowtype;
begin
  if not exists (
    select 1 from public.ai_agents a join public.agent_ownerships o on o.agent_id=a.id
    where a.id=p_agent_id and a.status='active' and o.owner_user_id=p_owner_user_id
      and o.ownership_role='owner' and o.status='active'
  ) then raise exception 'AGENT_SOCIAL_OWNERSHIP_REQUIRED' using errcode='42501'; end if;
  if coalesce(p_auto_reply_channels,'{}'::text[]) - array['comments','mentions','dm','live_chat']::text[] <> '{}'::text[]
     or cardinality(coalesce(p_auto_reply_channels,'{}'::text[]))>4
     or cardinality(coalesce(p_blocked_topics,'{}'::text[]))>100
     or cardinality(coalesce(p_allowed_tool_scopes,'{}'::text[]))>20
     or p_reply_tone not in ('friendly_concise','professional','warm','formal')
     or p_max_replies_per_minute not between 1 and 20
     or p_daily_credit_budget<0
     or jsonb_typeof(coalesce(p_quiet_hours,'{}'::jsonb))<>'object'
     or jsonb_typeof(coalesce(p_escalation_rules,'{}'::jsonb))<>'object' then
    raise exception 'AGENT_SOCIAL_AUTOMATION_INPUT_INVALID' using errcode='22023';
  end if;
  select * into v_policy from public.agent_social_presence_policies
  where owner_user_id=p_owner_user_id and agent_id=p_agent_id for update;
  if not found then raise exception 'AGENT_SOCIAL_POLICY_REQUIRED' using errcode='P0002'; end if;
  if p_expected_version is null or p_expected_version<>v_policy.version then
    raise exception 'AGENT_SOCIAL_POLICY_CONFLICT' using errcode='40001';
  end if;
  update public.agent_social_presence_policies set
    auto_reply_enabled=false,
    auto_reply_channels=coalesce(p_auto_reply_channels,'{}'::text[]),
    blocked_topics=coalesce(p_blocked_topics,'{}'::text[]),
    reply_tone=p_reply_tone,
    allowed_tool_scopes=coalesce(p_allowed_tool_scopes,'{}'::text[]),
    max_replies_per_minute=p_max_replies_per_minute,
    daily_credit_budget=p_daily_credit_budget,
    quiet_hours=coalesce(p_quiet_hours,'{}'::jsonb),
    escalation_rules=coalesce(p_escalation_rules,'{}'::jsonb),
    owner_approval_required=true,output_moderation_required=true,
    automation_version=automation_version+1,version=version+1,updated_at=now()
  where id=v_policy.id returning * into v_policy;
  insert into public.agent_social_control_events(owner_user_id,agent_id,policy_id,event_type,actor_user_id,metadata)
  values(p_owner_user_id,p_agent_id,v_policy.id,'automation_policy_saved',p_owner_user_id,
    jsonb_build_object('automation_version',v_policy.automation_version,'channels',v_policy.auto_reply_channels,
      'auto_reply_enabled',false,'reason','runtime_consumer_not_yet_wired'));
  return jsonb_build_object('outcome','saved','policy',to_jsonb(v_policy),
    'auto_reply_runtime_enabled',false,'reason','AUTO_REPLY_RUNTIME_NOT_CONNECTED');
end;
$$;

create or replace function public.set_agent_social_takeover(
  p_owner_user_id uuid,p_agent_id uuid,p_takeover_active boolean,p_reason text default null
) returns jsonb
language plpgsql security definer set search_path=public,pg_temp
as $$
declare v_policy public.agent_social_presence_policies%rowtype; v_count integer:=0;
begin
  if not exists (
    select 1 from public.ai_agents a join public.agent_ownerships o on o.agent_id=a.id
    where a.id=p_agent_id and a.status='active' and o.owner_user_id=p_owner_user_id
      and o.ownership_role='owner' and o.status='active'
  ) then raise exception 'AGENT_SOCIAL_OWNERSHIP_REQUIRED' using errcode='42501'; end if;
  select * into v_policy from public.agent_social_presence_policies
  where owner_user_id=p_owner_user_id and agent_id=p_agent_id for update;
  if not found then raise exception 'AGENT_SOCIAL_POLICY_REQUIRED' using errcode='P0002'; end if;

  update public.agent_social_presence_policies set
    takeover_active=p_takeover_active,
    takeover_started_at=case when p_takeover_active then now() else null end,
    takeover_started_by=case when p_takeover_active then p_owner_user_id else null end,
    auto_reply_enabled=false,version=version+1,updated_at=now()
  where id=v_policy.id returning * into v_policy;

  if p_takeover_active then
    update public.agent_social_action_approvals
      set status='revoked',decided_at=now(),decided_by=p_owner_user_id,
          decision_reason=left(coalesce(p_reason,'owner_takeover'),500)
    where owner_user_id=p_owner_user_id and agent_id=p_agent_id and status='pending';
    get diagnostics v_count=row_count;
  end if;
  insert into public.agent_social_control_events(owner_user_id,agent_id,policy_id,event_type,actor_user_id,metadata)
  values(p_owner_user_id,p_agent_id,v_policy.id,
    case when p_takeover_active then 'takeover_activated' else 'takeover_released' end,
    p_owner_user_id,jsonb_build_object('revoked_pending_approvals',v_count,'reason',left(coalesce(p_reason,''),500)));
  return jsonb_build_object('outcome','saved','policy',to_jsonb(v_policy),
    'revoked_pending_approvals',v_count,'auto_reply_enabled',false);
end;
$$;

revoke all on function public.save_agent_social_automation_policy(uuid,uuid,text[],text[],text,text[],integer,bigint,jsonb,jsonb,integer) from public,anon,authenticated;
revoke all on function public.set_agent_social_takeover(uuid,uuid,boolean,text) from public,anon,authenticated;
grant execute on function public.save_agent_social_automation_policy(uuid,uuid,text[],text[],text,text[],integer,bigint,jsonb,jsonb,integer) to service_role;
grant execute on function public.set_agent_social_takeover(uuid,uuid,boolean,text) to service_role;

commit;

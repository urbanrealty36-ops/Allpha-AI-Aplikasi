-- WP-06: durable Social event intake and claim lifecycle.
-- Source-only by instruction. This adds an intake ledger, not a second task queue:
-- execution remains exclusively in agent_runtime_tasks / AgentRuntimeStore.
begin;

do $
begin
  if to_regclass('public.agent_social_automation_grants') is null
     or to_regclass('public.agent_social_automation_runs') is null
     or to_regclass('public.agent_social_control_events') is null then
    raise exception 'WP06_AUTOMATION_TAKEOVER_MIGRATION_REQUIRED';
  end if;
  if to_regclass('public.content_comments') is null
     or to_regclass('public.content_mentions') is null
     or to_regclass('public.messages') is null
     or to_regclass('public.agent_runtime_tasks') is null then
    raise exception 'WP06_SOCIAL_RUNTIME_DOMAIN_PREREQUISITE_MISSING';
  end if;
end $;

alter table public.agent_social_presence_policies
  add column if not exists auto_reply_skill_id uuid;

do $$
begin
  if not exists (
    select 1 from pg_constraint
    where conname='agent_social_policy_auto_reply_skill_agent_fk'
      and conrelid='public.agent_social_presence_policies'::regclass
  ) then
    alter table public.agent_social_presence_policies
      add constraint agent_social_policy_auto_reply_skill_agent_fk
      foreign key (auto_reply_skill_id, agent_id)
      references public.agent_skills(id, agent_id) on delete restrict;
  end if;
end $$;

create table if not exists public.agent_social_automation_events (
  id uuid primary key default gen_random_uuid(),
  owner_user_id uuid not null references auth.users(id) on delete cascade,
  agent_id uuid not null references public.ai_agents(id) on delete cascade,
  channel text not null check (channel in ('comments','mentions','dm','live_chat')),
  source_table text not null check (source_table in ('content_comments','content_mentions','messages')),
  source_record_id uuid not null,
  source_actor_user_id uuid references auth.users(id) on delete set null,
  content_id uuid references public.content_items(id) on delete set null,
  conversation_id uuid references public.conversations(id) on delete set null,
  status text not null default 'received' check (status in (
    'received','claimed','retry_wait','dispatched','ignored','blocked','cancelled','dead_letter'
  )),
  attempt_count integer not null default 0 check (attempt_count >= 0),
  max_attempts integer not null default 8 check (max_attempts between 1 and 20),
  available_at timestamptz not null default now(),
  claim_token uuid,
  lease_expires_at timestamptz,
  runtime_task_id uuid references public.agent_runtime_tasks(id) on delete restrict,
  reason_code text,
  event_fingerprint text not null check (event_fingerprint ~ '^[a-f0-9]{64}$'),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(owner_user_id, agent_id, channel, source_table, source_record_id),
  check ((status='claimed') = (claim_token is not null and lease_expires_at is not null)),
  check ((status='dispatched') = (runtime_task_id is not null))
);
create index if not exists agent_social_automation_events_claim_idx
  on public.agent_social_automation_events(status, available_at, created_at)
  where status in ('received','retry_wait','claimed');
create index if not exists agent_social_automation_events_owner_idx
  on public.agent_social_automation_events(owner_user_id,agent_id,status,created_at desc);
create unique index if not exists agent_social_automation_events_runtime_task_uidx
  on public.agent_social_automation_events(runtime_task_id) where runtime_task_id is not null;

alter table public.agent_social_automation_events enable row level security;
revoke all on public.agent_social_automation_events from public, anon, authenticated;
grant select,insert,update,delete on public.agent_social_automation_events to service_role;

create or replace function public.save_agent_social_automation_policy_v2(
  p_owner_user_id uuid,p_agent_id uuid,p_auto_reply_channels text[],
  p_blocked_topics text[],p_reply_tone text,p_allowed_tool_scopes text[],
  p_max_replies_per_minute integer,p_daily_credit_budget bigint,
  p_quiet_hours jsonb,p_escalation_rules jsonb,p_expected_version integer,
  p_auto_reply_skill_id uuid
) returns jsonb
language plpgsql security definer set search_path=''
as $$
declare v_policy public.agent_social_presence_policies%rowtype;
  v_skill public.agent_skills%rowtype; v_grants_revoked integer:=0;
begin
  if not exists (
    select 1 from public.ai_agents a join public.agent_ownerships o on o.agent_id=a.id
    where a.id=p_agent_id and a.status='active' and o.owner_user_id=p_owner_user_id
      and o.ownership_role='owner' and o.status='active'
  ) then raise exception 'AGENT_SOCIAL_OWNERSHIP_REQUIRED' using errcode='42501'; end if;
  if not (coalesce(p_auto_reply_channels,'{}'::text[]) <@ array['comments','mentions','dm','live_chat']::text[])
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
  if cardinality(coalesce(p_auto_reply_channels,'{}'::text[]))>0 then
    select * into v_skill from public.agent_skills
      where id=p_auto_reply_skill_id and agent_id=p_agent_id and status='published';
    if not found then raise exception 'AGENT_SOCIAL_AUTO_REPLY_SKILL_REQUIRED' using errcode='42501'; end if;
  elsif p_auto_reply_skill_id is not null then
    raise exception 'AGENT_SOCIAL_AUTO_REPLY_SKILL_NOT_NEEDED' using errcode='22023';
  end if;
  select * into v_policy from public.agent_social_presence_policies
    where owner_user_id=p_owner_user_id and agent_id=p_agent_id for update;
  if not found then raise exception 'AGENT_SOCIAL_POLICY_REQUIRED' using errcode='P0002'; end if;
  if p_expected_version is null or p_expected_version<>v_policy.version then
    raise exception 'AGENT_SOCIAL_POLICY_CONFLICT' using errcode='40001';
  end if;
  update public.agent_social_presence_policies set
    auto_reply_enabled=(cardinality(coalesce(p_auto_reply_channels,'{}'::text[]))>0),
    auto_reply_skill_id=p_auto_reply_skill_id,
    auto_reply_channels=coalesce(p_auto_reply_channels,'{}'::text[]),
    blocked_topics=coalesce(p_blocked_topics,'{}'::text[]),
    reply_tone=p_reply_tone,allowed_tool_scopes=coalesce(p_allowed_tool_scopes,'{}'::text[]),
    max_replies_per_minute=p_max_replies_per_minute,daily_credit_budget=p_daily_credit_budget,
    quiet_hours=coalesce(p_quiet_hours,'{}'::jsonb),
    escalation_rules=coalesce(p_escalation_rules,'{}'::jsonb),
    owner_approval_required=true,output_moderation_required=true,
    automation_version=automation_version+1,version=version+1,updated_at=now()
  where id=v_policy.id returning * into v_policy;
  update public.agent_social_automation_grants
    set status='revoked',revoked_by=p_owner_user_id,revoked_at=now(),
        revoke_reason='automation_policy_updated'
    where owner_user_id=p_owner_user_id and agent_id=p_agent_id and status='active'
      and policy_version<>v_policy.version;
  get diagnostics v_grants_revoked=row_count;
  insert into public.agent_social_control_events(owner_user_id,agent_id,policy_id,event_type,actor_user_id,metadata)
  values(p_owner_user_id,p_agent_id,v_policy.id,'automation_policy_saved',p_owner_user_id,
    jsonb_build_object('automation_version',v_policy.automation_version,
      'channels',v_policy.auto_reply_channels,'auto_reply_enabled',v_policy.auto_reply_enabled,
      'automation_skill_id',v_policy.auto_reply_skill_id,
      'automation_grants_revoked',v_grants_revoked,'reason','event_intake_source_ready_worker_disabled'));
  insert into public.agent_social_audit_events(owner_user_id,agent_id,actor_user_id,event_type,outcome,metadata)
  values(p_owner_user_id,p_agent_id,p_owner_user_id,'automation_policy_saved','allowed',
    jsonb_build_object('automation_version',v_policy.automation_version,
      'channels',v_policy.auto_reply_channels,'daily_credit_budget',v_policy.daily_credit_budget,
      'automation_grants_revoked',v_grants_revoked,'auto_reply_enabled',v_policy.auto_reply_enabled));
  return jsonb_build_object('outcome','saved','policy',to_jsonb(v_policy),
    'automation_grants_revoked',v_grants_revoked,'event_intake_enabled',v_policy.auto_reply_enabled,
    'auto_reply_runtime_enabled',false,'reason','RUNTIME_DISPATCH_REQUIRES_CREDIT_AND_APPROVAL_GATES');
end;
$$;

create or replace function public.enqueue_agent_social_automation_event(
  p_owner_user_id uuid,p_agent_id uuid,p_channel text,p_source_table text,
  p_source_record_id uuid,p_source_actor_user_id uuid,p_content_id uuid default null,
  p_conversation_id uuid default null
) returns uuid
language plpgsql security definer set search_path=''
as $$
declare v_policy public.agent_social_presence_policies%rowtype;
  v_grant public.agent_social_automation_grants%rowtype;
  v_id uuid; v_delay integer:=0; v_fingerprint text;
begin
  if p_channel not in ('comments','mentions','dm','live_chat')
     or p_source_table not in ('content_comments','content_mentions','messages')
     or p_source_record_id is null or p_owner_user_id is null or p_agent_id is null then
    raise exception 'AGENT_SOCIAL_EVENT_INVALID' using errcode='22023';
  end if;
  if not exists (
    select 1 from public.ai_agents a join public.agent_ownerships o on o.agent_id=a.id
    where a.id=p_agent_id and a.status='active' and o.owner_user_id=p_owner_user_id
      and o.ownership_role='owner' and o.status='active'
  ) then return null; end if;
  select * into v_policy from public.agent_social_presence_policies
    where owner_user_id=p_owner_user_id and agent_id=p_agent_id
      and is_enabled and revoked_at is null and auto_reply_enabled
      and not takeover_active and p_channel=any(auto_reply_channels)
    for share;
  if not found then return null; end if;
  select * into v_grant from public.agent_social_automation_grants
    where owner_user_id=p_owner_user_id and agent_id=p_agent_id
      and status='active' and (expires_at is null or expires_at>now())
      and p_channel=any(granted_scopes) and policy_version=v_policy.version
    order by granted_at desc limit 1;
  if not found then return null; end if;
  if p_source_actor_user_id is not null and exists (
    select 1 from public.social_edges e where e.edge_type='block' and e.status='active'
      and ((e.actor_user_id=p_owner_user_id and e.target_user_id=p_source_actor_user_id)
        or (e.actor_user_id=p_source_actor_user_id and e.target_user_id=p_owner_user_id))
  ) then return null; end if;
  select greatest(0,count(*)::integer-v_policy.max_replies_per_minute+1) into v_delay
    from public.agent_social_automation_events e
    where e.owner_user_id=p_owner_user_id and e.agent_id=p_agent_id and e.channel=p_channel
      and e.created_at>now()-interval '1 minute'
      and e.status not in ('ignored','blocked','cancelled','dead_letter');
  v_fingerprint := encode(public.digest(
    p_owner_user_id::text||':'||p_agent_id::text||':'||p_channel||':'||p_source_table||':'||p_source_record_id::text,
    'sha256'),'hex');
  insert into public.agent_social_automation_events(
    owner_user_id,agent_id,channel,source_table,source_record_id,source_actor_user_id,
    content_id,conversation_id,status,available_at,event_fingerprint
  ) values (
    p_owner_user_id,p_agent_id,p_channel,p_source_table,p_source_record_id,p_source_actor_user_id,
    p_content_id,p_conversation_id,case when v_delay>0 then 'retry_wait' else 'received' end,
    now()+make_interval(secs=>least(v_delay*60,3600)),v_fingerprint
  ) on conflict(owner_user_id,agent_id,channel,source_table,source_record_id) do nothing
  returning id into v_id;
  return v_id;
end;
$$;

create or replace function public.capture_agent_social_comment_event()
returns trigger language plpgsql security definer set search_path=''
as $$
declare v_owner uuid; v_agent record; v_visibility text;
begin
  if new.status<>'visible' then return new; end if;
  select c.owner_id,c.visibility into v_owner,v_visibility
    from public.content_items c where c.id=new.content_id
      and c.deleted_at is null and c.status='published';
  if v_owner is null or v_owner=new.actor_user_id or v_visibility='private' then return new; end if;
  for v_agent in
    select a.id from public.ai_agents a join public.agent_ownerships o on o.agent_id=a.id
    where o.owner_user_id=v_owner and o.ownership_role='owner' and o.status='active' and a.status='active'
  loop
    perform public.enqueue_agent_social_automation_event(
      v_owner,v_agent.id,'comments','content_comments',new.id,new.actor_user_id,new.content_id,null
    );
  end loop;
  return new;
end $$;

create or replace function public.capture_agent_social_mention_event()
returns trigger language plpgsql security definer set search_path=''
as $$
declare v_agent record;
begin
  for v_agent in
    select a.id from public.ai_agents a join public.agent_ownerships o on o.agent_id=a.id
    where o.owner_user_id=new.mentioned_user_id and o.ownership_role='owner'
      and o.status='active' and a.status='active'
  loop
    perform public.enqueue_agent_social_automation_event(
      new.mentioned_user_id,v_agent.id,'mentions','content_mentions',new.id,
      new.mentioner_user_id,new.content_id,null
    );
  end loop;
  return new;
end $$;

create or replace function public.capture_agent_social_message_event()
returns trigger language plpgsql security definer set search_path=''
as $$
declare v_participant record; v_channel text; v_live boolean;
begin
  if new.sender_type<>'human' or new.sender_user_id is null then return new; end if;
  if not exists(select 1 from public.conversation_participants cp
    where cp.conversation_id=new.conversation_id and cp.user_id=new.sender_user_id
      and cp.participant_type='human') then return new; end if;
  v_live := false;
  if to_regclass('public.live_sessions') is not null
     and to_regclass('public.live_participants') is not null then
    execute 'select exists(select 1 from public.live_sessions s where s.conversation_id=$1 and s.status=''live'')'
      into v_live using new.conversation_id;
  end if;
  if v_live then
    if not exists(select 1 from public.conversation_participants cp
      where cp.conversation_id=new.conversation_id and cp.user_id=new.sender_user_id
        and cp.participant_type='human') then return new; end if;
    if to_regclass('public.live_participants') is not null then
      execute 'select exists(select 1 from public.live_participants p join public.live_sessions s on s.id=p.session_id where s.conversation_id=$1 and s.status=''live'' and p.user_id=$2 and p.status=''joined'')'
        into v_live using new.conversation_id,new.sender_user_id;
      if not v_live then return new; end if;
    end if;
    v_channel := 'live_chat';
  else
    if not exists(select 1 from public.conversations c
      where c.id=new.conversation_id and c.kind='agent') then return new; end if;
    v_channel := 'dm';
  end if;
  for v_participant in
    select cp.agent_id,o.owner_user_id
    from public.conversation_participants cp
    join public.agent_ownerships o on o.agent_id=cp.agent_id
    join public.ai_agents a on a.id=cp.agent_id and a.status='active'
    where cp.conversation_id=new.conversation_id and cp.participant_type='agent'
      and o.ownership_role='owner' and o.status='active'
      and o.owner_user_id<>new.sender_user_id
  loop
    perform public.enqueue_agent_social_automation_event(
      v_participant.owner_user_id,v_participant.agent_id,v_channel,'messages',new.id,
      new.sender_user_id,null,new.conversation_id
    );
  end loop;
  return new;
end $$;

revoke all on function public.enqueue_agent_social_automation_event(uuid,uuid,text,text,uuid,uuid,uuid,uuid) from public,anon,authenticated;
revoke all on function public.capture_agent_social_comment_event() from public,anon,authenticated;
revoke all on function public.capture_agent_social_mention_event() from public,anon,authenticated;
revoke all on function public.capture_agent_social_message_event() from public,anon,authenticated;
grant execute on function public.enqueue_agent_social_automation_event(uuid,uuid,text,text,uuid,uuid,uuid,uuid) to service_role;

drop trigger if exists content_comments_agent_automation_event on public.content_comments;
create trigger content_comments_agent_automation_event after insert on public.content_comments
for each row execute function public.capture_agent_social_comment_event();
drop trigger if exists content_mentions_agent_automation_event on public.content_mentions;
create trigger content_mentions_agent_automation_event after insert on public.content_mentions
for each row execute function public.capture_agent_social_mention_event();
drop trigger if exists messages_agent_automation_event on public.messages;
create trigger messages_agent_automation_event after insert on public.messages
for each row execute function public.capture_agent_social_message_event();

create or replace function public.claim_agent_social_automation_events(
  p_claim_token uuid,p_limit integer default 10,p_lease_seconds integer default 60
) returns setof public.agent_social_automation_events
language plpgsql security definer set search_path=''
as $$
begin
  if p_claim_token is null or p_limit not between 1 and 50
     or p_lease_seconds not between 10 and 300 then
    raise exception 'AGENT_SOCIAL_EVENT_CLAIM_INVALID' using errcode='22023';
  end if;
  update public.agent_social_automation_events e set status='dead_letter',
    claim_token=null,lease_expires_at=null,reason_code='retry_exhausted',updated_at=now()
  where e.attempt_count>=e.max_attempts and (
    e.status in ('received','retry_wait')
    or (e.status='claimed' and e.lease_expires_at<=now())
  );
  return query
  with picked as (
    select e.id from public.agent_social_automation_events e
    where (e.status in ('received','retry_wait') and e.available_at<=now())
       or (e.status='claimed' and e.lease_expires_at<=now())
    order by e.available_at,e.created_at
    for update skip locked limit p_limit
  )
  update public.agent_social_automation_events e set
    status='claimed',claim_token=p_claim_token,
    lease_expires_at=now()+make_interval(secs=>p_lease_seconds),
    attempt_count=e.attempt_count+1,updated_at=now()
  from picked where e.id=picked.id and e.attempt_count<e.max_attempts
  returning e.*;
end $$;

create or replace function public.heartbeat_agent_social_automation_event(
  p_event_id uuid,p_claim_token uuid,p_lease_seconds integer default 60
) returns setof public.agent_social_automation_events
language plpgsql security definer set search_path=''
as $$
begin
  if p_lease_seconds not between 10 and 300 then
    raise exception 'AGENT_SOCIAL_EVENT_LEASE_INVALID' using errcode='22023';
  end if;
  return query update public.agent_social_automation_events e
    set lease_expires_at=now()+make_interval(secs=>p_lease_seconds),updated_at=now()
    where e.id=p_event_id and e.status='claimed' and e.claim_token=p_claim_token
      and e.lease_expires_at>now()
    returning e.*;
end $$;

create or replace function public.complete_agent_social_automation_event(
  p_event_id uuid,p_claim_token uuid,p_runtime_task_id uuid
) returns setof public.agent_social_automation_events
language plpgsql security definer set search_path=''
as $$
declare v_event public.agent_social_automation_events%rowtype;
begin
  if p_runtime_task_id is null then raise exception 'AGENT_SOCIAL_RUNTIME_TASK_REQUIRED' using errcode='22023'; end if;
  select * into v_event from public.agent_social_automation_events
    where id=p_event_id and status='claimed' and claim_token=p_claim_token
      and lease_expires_at>now() for update;
  if not found then return; end if;
  update public.agent_social_automation_events set status='dispatched',
    runtime_task_id=p_runtime_task_id,claim_token=null,lease_expires_at=null,
    reason_code=null,updated_at=now() where id=p_event_id returning * into v_event;
  insert into public.agent_social_automation_runs(
    owner_user_id,agent_id,runtime_task_id,source_event_id,channel,status
  ) values(v_event.owner_user_id,v_event.agent_id,p_runtime_task_id,v_event.id::text,v_event.channel,'queued')
  on conflict(owner_user_id,source_event_id) do nothing;
  return next v_event;
end $$;

create or replace function public.fail_agent_social_automation_event(
  p_event_id uuid,p_claim_token uuid,p_reason_code text,p_retry_after_seconds integer default 60
) returns setof public.agent_social_automation_events
language plpgsql security definer set search_path=''
as $$
begin
  if p_retry_after_seconds not between 5 and 86400 then
    raise exception 'AGENT_SOCIAL_EVENT_RETRY_INVALID' using errcode='22023';
  end if;
  return query update public.agent_social_automation_events e set
    status=case when e.attempt_count>=e.max_attempts then 'dead_letter'
                else 'retry_wait' end,
    available_at=now()+make_interval(secs=>p_retry_after_seconds),
    claim_token=null,lease_expires_at=null,
    reason_code=left(coalesce(p_reason_code,'event_processing_failed'),120),
    updated_at=now()
  where e.id=p_event_id and e.status='claimed' and e.claim_token=p_claim_token
  returning e.*;
end $$;

create or replace function public.cancel_agent_social_automation_events(
  p_owner_user_id uuid,p_agent_id uuid,p_reason_code text default 'owner_takeover'
) returns integer
language plpgsql security definer set search_path=''
as $$
declare v_count integer;
begin
  update public.agent_social_automation_events set status='cancelled',
    claim_token=null,lease_expires_at=null,reason_code=left(coalesce(p_reason_code,'owner_takeover'),120),
    updated_at=now()
  where owner_user_id=p_owner_user_id and agent_id=p_agent_id
    and status in ('received','retry_wait','claimed');
  get diagnostics v_count=row_count;
  return v_count;
end $$;

revoke all on function public.claim_agent_social_automation_events(uuid,integer,integer) from public,anon,authenticated;
revoke all on function public.heartbeat_agent_social_automation_event(uuid,uuid,integer) from public,anon,authenticated;
revoke all on function public.complete_agent_social_automation_event(uuid,uuid,uuid) from public,anon,authenticated;
revoke all on function public.fail_agent_social_automation_event(uuid,uuid,text,integer) from public,anon,authenticated;
revoke all on function public.cancel_agent_social_automation_events(uuid,uuid,text) from public,anon,authenticated;
grant execute on function public.claim_agent_social_automation_events(uuid,integer,integer) to service_role;
grant execute on function public.heartbeat_agent_social_automation_event(uuid,uuid,integer) to service_role;
grant execute on function public.complete_agent_social_automation_event(uuid,uuid,uuid) to service_role;
grant execute on function public.fail_agent_social_automation_event(uuid,uuid,text,integer) to service_role;
grant execute on function public.cancel_agent_social_automation_events(uuid,uuid,text) to service_role;


create or replace function public.cancel_agent_social_events_on_policy_change()
returns trigger language plpgsql security definer set search_path=''
as $
begin
  if new.takeover_active or not new.is_enabled or new.revoked_at is not null
     or not new.auto_reply_enabled or new.version is distinct from old.version then
    perform public.cancel_agent_social_automation_events(
      new.owner_user_id,new.agent_id,
      case when new.takeover_active then 'owner_takeover'
           when not new.is_enabled or new.revoked_at is not null then 'policy_revoked'
           else 'automation_policy_changed' end
    );
  end if;
  return new;
end $;

create or replace function public.cancel_agent_social_events_on_grant_revoke()
returns trigger language plpgsql security definer set search_path=''
as $
begin
  if old.status='active' and new.status<>'active' then
    perform public.cancel_agent_social_automation_events(
      new.owner_user_id,new.agent_id,'automation_grant_revoked'
    );
  end if;
  return new;
end $;

revoke all on function public.cancel_agent_social_events_on_policy_change() from public,anon,authenticated;
revoke all on function public.cancel_agent_social_events_on_grant_revoke() from public,anon,authenticated;
drop trigger if exists agent_social_cancel_events_policy_change on public.agent_social_presence_policies;
create trigger agent_social_cancel_events_policy_change
after update on public.agent_social_presence_policies
for each row execute function public.cancel_agent_social_events_on_policy_change();
drop trigger if exists agent_social_cancel_events_grant_revoke on public.agent_social_automation_grants;
create trigger agent_social_cancel_events_grant_revoke
after update of status on public.agent_social_automation_grants
for each row execute function public.cancel_agent_social_events_on_grant_revoke();


commit;

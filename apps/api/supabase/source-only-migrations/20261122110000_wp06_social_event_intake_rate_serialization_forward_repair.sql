-- WP-06: forward repair for Social event intake pacing per owner/Agent/channel.
-- Supersedes source-only 20261122100000_wp06_social_event_intake_rate_serialization.sql
-- for application selection: that historical file calls public.digest(text,text),
-- but pgcrypto is installed in the extensions schema. Keep the historical file
-- unchanged for provenance and do not apply it; this version uses the verified
-- extensions.digest(bytea,text) signature. This migration remains source-only.
-- Extends the existing event inbox; Agent Runtime remains the sole execution queue.
begin;

do $
begin
  if to_regclass('public.agent_social_automation_events') is null
     or to_regclass('public.agent_social_presence_policies') is null
     or to_regclass('public.agent_social_automation_grants') is null
     or to_regclass('public.agent_social_automation_runs') is null
     or to_regclass('public.agent_social_control_events') is null
     or to_regclass('public.agent_ownerships') is null
     or to_regclass('public.social_edges') is null then
    raise exception 'WP06_SOCIAL_EVENT_INTAKE_SCHEMA_PREREQUISITE_MISSING';
  end if;
  if to_regprocedure('extensions.digest(bytea,text)') is null then
    raise exception 'WP06_SOCIAL_EVENT_INTAKE_DIGEST_DEPENDENCY_MISSING';
  end if;
end $;

create or replace function public.enqueue_agent_social_automation_event(
  p_owner_user_id uuid,p_agent_id uuid,p_channel text,p_source_table text,
  p_source_record_id uuid,p_source_actor_user_id uuid,p_content_id uuid default null,
  p_conversation_id uuid default null
) returns uuid
language plpgsql security definer set search_path=''
as $$
declare
  v_policy public.agent_social_presence_policies%rowtype;
  v_grant public.agent_social_automation_grants%rowtype;
  v_id uuid;
  v_delay integer:=0;
  v_fingerprint text;
begin
  if p_channel not in ('comments','mentions','dm','live_chat')
     or p_source_table not in ('content_comments','content_mentions','messages')
     or p_source_record_id is null or p_owner_user_id is null or p_agent_id is null
     or (p_channel='comments' and p_source_table<>'content_comments')
     or (p_channel='mentions' and p_source_table<>'content_mentions')
     or (p_channel in ('dm','live_chat') and p_source_table<>'messages') then
    raise exception 'AGENT_SOCIAL_EVENT_INVALID' using errcode='22023';
  end if;

  if not exists (
    select 1 from public.ai_agents a
    join public.agent_ownerships o on o.agent_id=a.id
    where a.id=p_agent_id and a.status='active'
      and o.owner_user_id=p_owner_user_id
      and o.ownership_role='owner' and o.status='active'
  ) then
    return null;
  end if;

  -- Serialize the count + insert critical section. A plain count followed by an
  -- INSERT allows concurrent triggers to exceed the owner's per-minute limit.
  perform pg_advisory_xact_lock(hashtextextended(
    p_owner_user_id::text||':'||p_agent_id::text||':'||p_channel,0
  ));

  select * into v_policy
  from public.agent_social_presence_policies
  where owner_user_id=p_owner_user_id and agent_id=p_agent_id
    and is_enabled and revoked_at is null and auto_reply_enabled
    and not takeover_active and p_channel=any(auto_reply_channels)
  for share;
  if not found then return null; end if;

  select * into v_grant
  from public.agent_social_automation_grants
  where owner_user_id=p_owner_user_id and agent_id=p_agent_id
    and status='active' and (expires_at is null or expires_at>now())
    and p_channel=any(granted_scopes) and policy_version=v_policy.version
  order by granted_at desc limit 1;
  if not found then return null; end if;

  if p_source_actor_user_id is not null and exists (
    select 1 from public.social_edges e
    where e.edge_type='block' and e.status='active'
      and ((e.actor_user_id=p_owner_user_id and e.target_user_id=p_source_actor_user_id)
        or (e.actor_user_id=p_source_actor_user_id and e.target_user_id=p_owner_user_id))
  ) then
    return null;
  end if;

  select greatest(0,count(*)::integer-v_policy.max_replies_per_minute+1)
    into v_delay
  from public.agent_social_automation_events e
  where e.owner_user_id=p_owner_user_id and e.agent_id=p_agent_id
    and e.channel=p_channel
    and e.created_at>now()-interval '1 minute'
    and e.status not in ('ignored','blocked','cancelled','dead_letter');

  v_fingerprint := encode(extensions.digest(convert_to(
    p_owner_user_id::text||':'||p_agent_id::text||':'||p_channel||':'||
    p_source_table||':'||p_source_record_id::text,'UTF8'
  ),'sha256'),'hex');

  insert into public.agent_social_automation_events(
    owner_user_id,agent_id,channel,source_table,source_record_id,
    source_actor_user_id,content_id,conversation_id,status,available_at,event_fingerprint
  ) values (
    p_owner_user_id,p_agent_id,p_channel,p_source_table,p_source_record_id,
    p_source_actor_user_id,p_content_id,p_conversation_id,
    case when v_delay>0 then 'retry_wait' else 'received' end,
    now()+make_interval(secs=>least(v_delay*60,3600)),v_fingerprint
  )
  on conflict(owner_user_id,agent_id,channel,source_table,source_record_id) do nothing
  returning id into v_id;

  return v_id;
end;
$$;

revoke all on function public.enqueue_agent_social_automation_event(
  uuid,uuid,text,text,uuid,uuid,uuid,uuid
) from public,anon,authenticated;
grant execute on function public.enqueue_agent_social_automation_event(
  uuid,uuid,text,text,uuid,uuid,uuid,uuid
) to service_role;

commit;

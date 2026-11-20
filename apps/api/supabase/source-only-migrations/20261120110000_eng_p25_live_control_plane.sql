-- SOURCE ONLY — ENG-P25 Live session control plane.
-- No media provider, WebRTC/SFU, TURN, publish/subscribe token or recording provider is activated.
-- Keep this migration in source-only until ADR-WP10-001 and the canonical DB verification window are approved.
begin;

create table if not exists public.live_sessions (
  id uuid primary key default gen_random_uuid(),
  host_user_id uuid not null references auth.users(id) on delete restrict,
  conversation_id uuid not null references public.conversations(id) on delete restrict,
  title text not null check (char_length(btrim(title)) between 1 and 160),
  description text not null default '' check (char_length(description) <= 4000),
  visibility text not null default 'public' check (visibility in ('public','followers','private')),
  status text not null default 'planned' check (
    status in ('planned','preparing','live','paused','reconnecting','ended','cancelled','failed','moderation_stopped')
  ),
  provider_key text,
  provider_session_ref text,
  recording_state text not null default 'not_requested' check (
    recording_state in ('not_requested','consent_pending','consent_granted','processing','ready','failed','deleted')
  ),
  scheduled_at timestamptz,
  started_at timestamptz,
  ended_at timestamptz,
  version integer not null default 1 check (version > 0),
  idempotency_key text not null check (char_length(idempotency_key) between 8 and 160),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(host_user_id,idempotency_key),
  check ((status in ('live','paused','reconnecting') and started_at is not null) or status not in ('live','paused','reconnecting')),
  check (ended_at is null or status in ('ended','cancelled','failed','moderation_stopped'))
);
create index if not exists live_sessions_public_status_idx
  on public.live_sessions(status,scheduled_at desc,created_at desc) where visibility='public';
create index if not exists live_sessions_host_status_idx
  on public.live_sessions(host_user_id,status,created_at desc);

create table if not exists public.live_participants (
  id uuid primary key default gen_random_uuid(),
  session_id uuid not null references public.live_sessions(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete restrict,
  participant_role text not null check (participant_role in ('host','cohost','speaker','viewer')),
  status text not null default 'invited' check (status in ('invited','joined','left','removed')),
  invited_by uuid references auth.users(id) on delete set null,
  recording_consent boolean not null default false,
  recording_consent_at timestamptz,
  joined_at timestamptz,
  left_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(session_id,user_id),
  check ((recording_consent and recording_consent_at is not null) or not recording_consent)
);
create index if not exists live_participants_user_status_idx
  on public.live_participants(user_id,status,updated_at desc);
create index if not exists live_participants_session_role_idx
  on public.live_participants(session_id,participant_role,status);

create table if not exists public.live_stage_events (
  id uuid primary key default gen_random_uuid(),
  event_seq bigint generated always as identity,
  session_id uuid not null references public.live_sessions(id) on delete cascade,
  actor_user_id uuid references auth.users(id) on delete set null,
  event_type text not null check (event_type in (
    'session_created','participant_invited','participant_joined','participant_left','participant_removed',
    'session_preparing','session_live','session_paused','session_reconnecting',
    'session_ended','session_cancelled','session_failed','moderation_stopped',
    'recording_consent_updated','stage_slide_changed','stage_annotation_added',
    'stage_poll_created','stage_qa_submitted'
  )),
  payload jsonb not null default '{}'::jsonb check (jsonb_typeof(payload)='object'),
  idempotency_key text not null check (char_length(idempotency_key) between 8 and 160),
  created_at timestamptz not null default now(),
  unique(session_id,idempotency_key),
  unique(session_id,event_seq)
);
create index if not exists live_stage_events_session_seq_idx
  on public.live_stage_events(session_id,event_seq);

create or replace function public.is_live_session_member(p_session_id uuid,p_user_id uuid)
returns boolean
language sql stable security definer set search_path=public,pg_temp
as $$
  select exists (
    select 1 from public.live_sessions s
    where s.id=p_session_id and (
      s.host_user_id=p_user_id or exists (
        select 1 from public.live_participants p
        where p.session_id=s.id and p.user_id=p_user_id and p.status in ('invited','joined')
      )
    )
  );
$$;
revoke all on function public.is_live_session_member(uuid,uuid) from public,anon;
grant execute on function public.is_live_session_member(uuid,uuid) to authenticated,service_role;

alter table public.live_sessions enable row level security;
alter table public.live_participants enable row level security;
alter table public.live_stage_events enable row level security;

revoke all on public.live_sessions,public.live_participants,public.live_stage_events from public,anon,authenticated,service_role;
grant select on public.live_sessions,public.live_participants,public.live_stage_events to authenticated;
grant select,insert,update,delete on public.live_sessions,public.live_participants,public.live_stage_events to service_role;

drop policy if exists live_sessions_participant_read on public.live_sessions;
create policy live_sessions_participant_read on public.live_sessions for select to authenticated
using (public.is_live_session_member(id,auth.uid()));
drop policy if exists live_participants_session_read on public.live_participants;
create policy live_participants_session_read on public.live_participants for select to authenticated
using (public.is_live_session_member(session_id,auth.uid()));
drop policy if exists live_stage_events_participant_read on public.live_stage_events;
create policy live_stage_events_participant_read on public.live_stage_events for select to authenticated
using (public.is_live_session_member(session_id,auth.uid()));

create or replace function public.create_live_session(
  p_host_user_id uuid,p_title text,p_description text,p_visibility text,
  p_scheduled_at timestamptz,p_idempotency_key text
) returns jsonb
language plpgsql security definer set search_path=public,pg_temp
as $$
declare v_session public.live_sessions%rowtype; v_conversation_id uuid;
begin
  if p_idempotency_key is null or char_length(p_idempotency_key) not between 8 and 160
     or p_visibility not in ('public','followers','private')
     or char_length(btrim(coalesce(p_title,''))) not between 1 and 160
     or char_length(coalesce(p_description,''))>4000 then
    raise exception 'LIVE_SESSION_INPUT_INVALID' using errcode='22023';
  end if;
  select * into v_session from public.live_sessions
    where host_user_id=p_host_user_id and idempotency_key=p_idempotency_key for update;
  if found then
    if v_session.title<>btrim(p_title) or v_session.visibility<>p_visibility
       or v_session.scheduled_at is distinct from p_scheduled_at then
      raise exception 'LIVE_SESSION_IDEMPOTENCY_CONFLICT' using errcode='23505';
    end if;
    return jsonb_build_object('outcome','replayed','session',to_jsonb(v_session));
  end if;
  insert into public.conversations(kind,title,created_by)
    values('human','Live: '||btrim(p_title),p_host_user_id) returning id into v_conversation_id;
  insert into public.conversation_participants(conversation_id,user_id,participant_type)
    values(v_conversation_id,p_host_user_id,'human');
  insert into public.live_sessions(
    host_user_id,conversation_id,title,description,visibility,scheduled_at,idempotency_key
  ) values(
    p_host_user_id,v_conversation_id,btrim(p_title),coalesce(p_description,''),p_visibility,p_scheduled_at,p_idempotency_key
  ) returning * into v_session;
  insert into public.live_participants(session_id,user_id,participant_role,status,invited_by,joined_at)
    values(v_session.id,p_host_user_id,'host','joined',p_host_user_id,now());
  insert into public.live_stage_events(session_id,actor_user_id,event_type,payload,idempotency_key)
    values(v_session.id,p_host_user_id,'session_created',
      jsonb_build_object('status',v_session.status,'visibility',v_session.visibility),
      p_idempotency_key);
  return jsonb_build_object('outcome','created','session',to_jsonb(v_session));
end;
$$;

create or replace function public.invite_live_participant(
  p_session_id uuid,p_host_user_id uuid,p_user_id uuid,p_role text,p_idempotency_key text
) returns jsonb
language plpgsql security definer set search_path=public,pg_temp
as $$
declare v_session public.live_sessions%rowtype; v_participant public.live_participants%rowtype;
begin
  if p_idempotency_key is null or char_length(p_idempotency_key) not between 8 and 160 then
    raise exception 'LIVE_IDEMPOTENCY_KEY_INVALID' using errcode='22023';
  end if;
  select * into v_session from public.live_sessions
    where id=p_session_id and host_user_id=p_host_user_id for update;
  if not found then raise exception 'LIVE_SESSION_HOST_REQUIRED' using errcode='42501'; end if;
  if v_session.status not in ('planned','preparing') or p_user_id=p_host_user_id
     or p_role not in ('cohost','speaker','viewer')
     or p_idempotency_key is null or char_length(p_idempotency_key) not between 8 and 160 then
    raise exception 'LIVE_INVITATION_INVALID' using errcode='22023';
  end if;
  select * into v_participant from public.live_participants
    where session_id=p_session_id and user_id=p_user_id for update;
  if found then
    if v_participant.participant_role<>p_role then
      raise exception 'LIVE_PARTICIPANT_ROLE_CONFLICT' using errcode='23505';
    end if;
    return jsonb_build_object('outcome','replayed','participant',to_jsonb(v_participant));
  end if;
  insert into public.live_participants(session_id,user_id,participant_role,status,invited_by)
    values(p_session_id,p_user_id,p_role,'invited',p_host_user_id) returning * into v_participant;
  insert into public.conversation_participants(conversation_id,user_id,participant_type)
    values(v_session.conversation_id,p_user_id,'human') on conflict do nothing;
  insert into public.live_stage_events(session_id,actor_user_id,event_type,payload,idempotency_key)
    values(p_session_id,p_host_user_id,'participant_invited',
      jsonb_build_object('participant_id',v_participant.id,'user_id',p_user_id,'role',p_role),
      p_idempotency_key);
  return jsonb_build_object('outcome','invited','participant',to_jsonb(v_participant));
end;
$$;

create or replace function public.join_live_session(
  p_session_id uuid,p_user_id uuid,p_idempotency_key text
) returns jsonb
language plpgsql security definer set search_path=public,pg_temp
as $$
declare v_session public.live_sessions%rowtype; v_participant public.live_participants%rowtype;
begin
  if p_idempotency_key is null or char_length(p_idempotency_key) not between 8 and 160 then
    raise exception 'LIVE_IDEMPOTENCY_KEY_INVALID' using errcode='22023';
  end if;
  select * into v_session from public.live_sessions where id=p_session_id for share;
  if not found or v_session.status not in ('planned','preparing','live','paused','reconnecting') then
    raise exception 'LIVE_SESSION_NOT_JOINABLE' using errcode='P0002';
  end if;
  select * into v_participant from public.live_participants
    where session_id=p_session_id and user_id=p_user_id for update;
  if found then
    if v_participant.status='removed' then raise exception 'LIVE_PARTICIPANT_REMOVED' using errcode='42501'; end if;
    if v_participant.status='joined' then
      return jsonb_build_object('outcome','replayed','participant',to_jsonb(v_participant));
    end if;
    update public.live_participants set status='joined',joined_at=coalesce(joined_at,now()),
      left_at=null,updated_at=now() where id=v_participant.id returning * into v_participant;
  else
    if v_session.visibility='private' then
      raise exception 'LIVE_SESSION_INVITE_REQUIRED' using errcode='42501';
    elsif v_session.visibility='followers' and not exists (
      select 1 from public.social_edges e
      where e.actor_user_id=p_user_id and e.target_user_id=v_session.host_user_id
        and e.edge_type='follow' and e.status='active'
    ) then
      raise exception 'LIVE_SESSION_FOLLOW_REQUIRED' using errcode='42501';
    end if;
    insert into public.live_participants(session_id,user_id,participant_role,status,joined_at)
      values(p_session_id,p_user_id,'viewer','joined',now()) returning * into v_participant;
    insert into public.conversation_participants(conversation_id,user_id,participant_type)
      values(v_session.conversation_id,p_user_id,'human') on conflict do nothing;
  end if;
  insert into public.live_stage_events(session_id,actor_user_id,event_type,payload,idempotency_key)
    values(p_session_id,p_user_id,'participant_joined',
      jsonb_build_object('participant_id',v_participant.id,'role',v_participant.participant_role),
      p_idempotency_key);
  return jsonb_build_object('outcome','joined','participant',to_jsonb(v_participant));
end;
$$;

create or replace function public.leave_live_session(
  p_session_id uuid,p_user_id uuid,p_idempotency_key text
) returns jsonb
language plpgsql security definer set search_path=public,pg_temp
as $$
declare v_participant public.live_participants%rowtype;
begin
  if p_idempotency_key is null or char_length(p_idempotency_key) not between 8 and 160 then
    raise exception 'LIVE_IDEMPOTENCY_KEY_INVALID' using errcode='22023';
  end if;
  select * into v_participant from public.live_participants
    where session_id=p_session_id and user_id=p_user_id for update;
  if not found then raise exception 'LIVE_PARTICIPANT_NOT_FOUND' using errcode='P0002'; end if;
  if v_participant.participant_role='host' then
    raise exception 'LIVE_HOST_MUST_END_SESSION' using errcode='42501';
  end if;
  if v_participant.status<>'left' then
    update public.live_participants set status='left',left_at=now(),updated_at=now()
      where id=v_participant.id returning * into v_participant;
    insert into public.live_stage_events(session_id,actor_user_id,event_type,payload,idempotency_key)
      values(p_session_id,p_user_id,'participant_left',
        jsonb_build_object('participant_id',v_participant.id,'role',v_participant.participant_role),
        p_idempotency_key);
  end if;
  return jsonb_build_object('outcome','left','participant',to_jsonb(v_participant));
end;
$$;

create or replace function public.transition_live_session(
  p_session_id uuid,p_host_user_id uuid,p_expected_version integer,
  p_next_status text,p_reason text default null
) returns jsonb
language plpgsql security definer set search_path=public,pg_temp
as $$
declare v_session public.live_sessions%rowtype; v_event text;
begin
  select * into v_session from public.live_sessions
    where id=p_session_id and host_user_id=p_host_user_id for update;
  if not found then raise exception 'LIVE_SESSION_HOST_REQUIRED' using errcode='42501'; end if;
  if v_session.version<>p_expected_version then
    raise exception 'LIVE_SESSION_VERSION_CONFLICT' using errcode='40001';
  end if;
  if p_next_status='live' and (v_session.provider_key is null or v_session.provider_session_ref is null) then
    raise exception 'LIVE_MEDIA_PROVIDER_NOT_APPROVED' using errcode='42501';
  end if;
  if not (
    (v_session.status='planned' and p_next_status in ('preparing','cancelled'))
    or (v_session.status='preparing' and p_next_status in ('cancelled','failed'))
    or (v_session.status='live' and p_next_status in ('paused','reconnecting','ended','moderation_stopped'))
    or (v_session.status='paused' and p_next_status in ('reconnecting','ended','moderation_stopped'))
    or (v_session.status='reconnecting' and p_next_status in ('paused','ended','failed','moderation_stopped'))
  ) then raise exception 'LIVE_SESSION_TRANSITION_INVALID' using errcode='22023'; end if;
  v_event := case p_next_status
    when 'preparing' then 'session_preparing' when 'live' then 'session_live'
    when 'paused' then 'session_paused' when 'reconnecting' then 'session_reconnecting'
    when 'ended' then 'session_ended' when 'cancelled' then 'session_cancelled'
    when 'failed' then 'session_failed' else 'moderation_stopped' end;
  update public.live_sessions set status=p_next_status,version=version+1,
    started_at=case when p_next_status='live' then coalesce(started_at,now()) else started_at end,
    ended_at=case when p_next_status in ('ended','cancelled','failed','moderation_stopped') then now() else ended_at end,
    updated_at=now()
    where id=p_session_id returning * into v_session;
  insert into public.live_stage_events(session_id,actor_user_id,event_type,payload,idempotency_key)
    values(p_session_id,p_host_user_id,v_event,
      jsonb_build_object('status',p_next_status,'version',v_session.version,'reason',left(coalesce(p_reason,''),500)),
      'transition:'||v_session.version::text);
  return jsonb_build_object('outcome','transitioned','session',to_jsonb(v_session));
end;
$$;

create or replace function public.remove_live_participant(
  p_session_id uuid,p_host_user_id uuid,p_user_id uuid,p_reason text,p_idempotency_key text
) returns jsonb
language plpgsql security definer set search_path=public,pg_temp
as $$
declare v_session public.live_sessions%rowtype; v_participant public.live_participants%rowtype;
begin
  if p_idempotency_key is null or char_length(p_idempotency_key) not between 8 and 160 then
    raise exception 'LIVE_IDEMPOTENCY_KEY_INVALID' using errcode='22023';
  end if;
  select * into v_session from public.live_sessions
    where id=p_session_id and host_user_id=p_host_user_id for update;
  if not found then raise exception 'LIVE_SESSION_HOST_REQUIRED' using errcode='42501'; end if;
  select * into v_participant from public.live_participants
    where session_id=p_session_id and user_id=p_user_id for update;
  if not found then raise exception 'LIVE_PARTICIPANT_NOT_FOUND' using errcode='P0002'; end if;
  if v_participant.participant_role='host' then raise exception 'LIVE_HOST_CANNOT_BE_REMOVED' using errcode='42501'; end if;
  if v_participant.status<>'removed' then
    update public.live_participants set status='removed',left_at=now(),updated_at=now()
      where id=v_participant.id returning * into v_participant;
    delete from public.conversation_participants
      where conversation_id=v_session.conversation_id and user_id=p_user_id;
    insert into public.live_stage_events(session_id,actor_user_id,event_type,payload,idempotency_key)
      values(p_session_id,p_host_user_id,'participant_removed',
        jsonb_build_object('participant_id',v_participant.id,'user_id',p_user_id,
                           'reason',left(coalesce(p_reason,''),500)),p_idempotency_key);
  end if;
  return jsonb_build_object('outcome','removed','participant',to_jsonb(v_participant));
end;
$$;

create or replace function public.set_live_recording_consent(
  p_session_id uuid,p_user_id uuid,p_consent boolean,p_idempotency_key text
) returns jsonb
language plpgsql security definer set search_path=public,pg_temp
as $$
declare v_participant public.live_participants%rowtype; v_session public.live_sessions%rowtype;
  v_existing public.live_stage_events%rowtype;
begin
  if p_idempotency_key is null or char_length(p_idempotency_key) not between 8 and 160 then
    raise exception 'LIVE_IDEMPOTENCY_KEY_INVALID' using errcode='22023';
  end if;
  select * into v_session from public.live_sessions
    where id=p_session_id and status in ('preparing','live','paused','reconnecting') for share;
  if not found then raise exception 'LIVE_RECORDING_CONSENT_WINDOW_CLOSED' using errcode='40900'; end if;
  select * into v_participant from public.live_participants
    where session_id=p_session_id and user_id=p_user_id and status in ('invited','joined') for update;
  if not found then raise exception 'LIVE_PARTICIPANT_NOT_FOUND' using errcode='P0002'; end if;
  select * into v_existing from public.live_stage_events
    where session_id=p_session_id and idempotency_key=p_idempotency_key for update;
  if found then
    if v_existing.event_type<>'recording_consent_updated'
       or v_existing.payload->>'consent'<>p_consent::text
       or v_existing.payload->>'participant_id'<>v_participant.id::text then
      raise exception 'LIVE_IDEMPOTENCY_CONFLICT' using errcode='23505';
    end if;
    return jsonb_build_object('outcome','replayed','participant',to_jsonb(v_participant),
      'recording_provider_enabled',false);
  end if;
  update public.live_participants set recording_consent=p_consent,
    recording_consent_at=case when p_consent then now() else null end,updated_at=now()
    where id=v_participant.id returning * into v_participant;
  insert into public.live_stage_events(session_id,actor_user_id,event_type,payload,idempotency_key)
    values(p_session_id,p_user_id,'recording_consent_updated',
      jsonb_build_object('participant_id',v_participant.id,'consent',p_consent),
      p_idempotency_key);
  return jsonb_build_object('outcome','saved','participant',to_jsonb(v_participant),
    'recording_provider_enabled',false);
end;
$$;

create or replace function public.append_live_stage_event(
  p_session_id uuid,p_actor_user_id uuid,p_event_type text,p_payload jsonb,p_idempotency_key text
) returns jsonb
language plpgsql security definer set search_path=public,pg_temp
as $$
declare v_event public.live_stage_events%rowtype;
begin
  if p_event_type not in ('stage_slide_changed','stage_annotation_added','stage_poll_created','stage_qa_submitted')
     or jsonb_typeof(coalesce(p_payload,'{}'::jsonb))<>'object'
     or octet_length(coalesce(p_payload,'{}'::jsonb)::text)>16384
     or p_idempotency_key is null or char_length(p_idempotency_key) not between 8 and 160 then
    raise exception 'LIVE_STAGE_EVENT_INVALID' using errcode='22023';
  end if;
  if not exists (
    select 1 from public.live_sessions s join public.live_participants p on p.session_id=s.id
    where s.id=p_session_id and s.status in ('preparing','live','paused','reconnecting')
      and p.user_id=p_actor_user_id and p.status='joined'
  ) then raise exception 'LIVE_STAGE_PARTICIPANT_REQUIRED' using errcode='42501'; end if;
  select * into v_event from public.live_stage_events
    where session_id=p_session_id and idempotency_key=p_idempotency_key for update;
  if found then
    if v_event.event_type<>p_event_type or v_event.payload<>p_payload then
      raise exception 'LIVE_IDEMPOTENCY_CONFLICT' using errcode='23505';
    end if;
    return jsonb_build_object('outcome','replayed','event',to_jsonb(v_event));
  end if;
  insert into public.live_stage_events(session_id,actor_user_id,event_type,payload,idempotency_key)
    values(p_session_id,p_actor_user_id,p_event_type,p_payload,p_idempotency_key)
    returning * into v_event;
  return jsonb_build_object('outcome','recorded','event',to_jsonb(v_event));
end;
$$;

revoke all on function public.create_live_session(uuid,text,text,text,timestamptz,text) from public,anon,authenticated;
revoke all on function public.invite_live_participant(uuid,uuid,uuid,text,text) from public,anon,authenticated;
revoke all on function public.join_live_session(uuid,uuid,text) from public,anon,authenticated;
revoke all on function public.leave_live_session(uuid,uuid,text) from public,anon,authenticated;
revoke all on function public.transition_live_session(uuid,uuid,integer,text,text) from public,anon,authenticated;
revoke all on function public.remove_live_participant(uuid,uuid,uuid,text,text) from public,anon,authenticated;
revoke all on function public.set_live_recording_consent(uuid,uuid,boolean,text) from public,anon,authenticated;
revoke all on function public.append_live_stage_event(uuid,uuid,text,jsonb,text) from public,anon,authenticated;
grant execute on function public.create_live_session(uuid,text,text,text,timestamptz,text) to service_role;
grant execute on function public.invite_live_participant(uuid,uuid,uuid,text,text) to service_role;
grant execute on function public.join_live_session(uuid,uuid,text) to service_role;
grant execute on function public.leave_live_session(uuid,uuid,text) to service_role;
grant execute on function public.transition_live_session(uuid,uuid,integer,text,text) to service_role;
grant execute on function public.remove_live_participant(uuid,uuid,uuid,text,text) to service_role;
grant execute on function public.set_live_recording_consent(uuid,uuid,boolean,text) to service_role;
grant execute on function public.append_live_stage_event(uuid,uuid,text,jsonb,text) to service_role;

do $$
begin
  if exists (select 1 from pg_publication where pubname='supabase_realtime') then
    if not exists (select 1 from pg_publication_tables where pubname='supabase_realtime' and schemaname='public' and tablename='live_stage_events') then
      alter publication supabase_realtime add table public.live_stage_events;
    end if;
  end if;
end
$$;

commit;

-- ENG-P13: durable owner-scoped playback sessions, idempotent playback events and watchlist.
-- Source-only until the production migration/recovery gate is satisfied.
begin;
create table if not exists public.cinema_playback_sessions (
 id uuid primary key default gen_random_uuid(),
 owner_user_id uuid not null references auth.users(id) on delete cascade,
 title_id uuid not null references public.cinema_titles(id) on delete cascade,
 episode_id uuid not null references public.cinema_episodes(id) on delete cascade,
 media_id uuid not null references public.content_media(id) on delete restrict,
 entitlement_id uuid references public.playback_entitlements(id) on delete set null,
 access_policy_version text not null,
 session_token_hash text not null check (session_token_hash ~ '^[0-9a-f]{64}$'),
 status text not null default 'active' check (status in ('active','completed','expired','revoked')),
 duration_seconds integer check (duration_seconds is null or duration_seconds > 0),
 last_position_seconds integer not null default 0 check (last_position_seconds >= 0),
 max_position_seconds integer not null default 0 check (max_position_seconds >= 0),
 idempotency_key text not null check (length(idempotency_key) between 8 and 160),
 started_at timestamptz not null default now(),
 last_heartbeat_at timestamptz,
 expires_at timestamptz not null,
 finished_at timestamptz,
 created_at timestamptz not null default now(),
 updated_at timestamptz not null default now(),
 constraint cinema_playback_session_owner_idempotency_uq unique (owner_user_id,idempotency_key),
 constraint cinema_playback_session_position_bound check (duration_seconds is null or (
  last_position_seconds <= duration_seconds + 5 and max_position_seconds <= duration_seconds + 5
 ))
);
create table if not exists public.cinema_playback_session_events (
 id uuid primary key default gen_random_uuid(),
 session_id uuid not null references public.cinema_playback_sessions(id) on delete cascade,
 owner_user_id uuid not null references auth.users(id) on delete cascade,
 event_id uuid not null unique,
 event_type text not null check (event_type in ('heartbeat','finish')),
 position_seconds integer not null check (position_seconds >= 0),
 created_at timestamptz not null default now(),
 constraint cinema_playback_event_session_event_uq unique (session_id,event_id)
);
create table if not exists public.cinema_watchlist_items (
 id uuid primary key default gen_random_uuid(),
 owner_user_id uuid not null references auth.users(id) on delete cascade,
 title_id uuid not null references public.cinema_titles(id) on delete cascade,
 created_at timestamptz not null default now(),
 constraint cinema_watchlist_owner_title_uq unique (owner_user_id,title_id)
);
create index if not exists cinema_playback_sessions_owner_updated_idx on public.cinema_playback_sessions(owner_user_id,updated_at desc);
create index if not exists cinema_playback_sessions_owner_active_idx on public.cinema_playback_sessions(owner_user_id,expires_at) where status='active';
create index if not exists cinema_playback_sessions_episode_progress_idx on public.cinema_playback_sessions(owner_user_id,episode_id,updated_at desc);
create index if not exists cinema_playback_session_events_session_created_idx on public.cinema_playback_session_events(session_id,created_at desc);
create index if not exists cinema_watchlist_items_owner_created_idx on public.cinema_watchlist_items(owner_user_id,created_at desc);

alter table public.cinema_playback_sessions enable row level security;
alter table public.cinema_playback_session_events enable row level security;
alter table public.cinema_watchlist_items enable row level security;
revoke all on public.cinema_playback_sessions,public.cinema_playback_session_events,public.cinema_watchlist_items from public,anon,authenticated,service_role;
grant all on public.cinema_playback_sessions,public.cinema_playback_session_events,public.cinema_watchlist_items to service_role;
-- No client policies or grants are created: every read/write is mediated by authenticated FastAPI.
-- RLS therefore denies direct anon/authenticated table access; service_role is used only server-side.

create or replace function public.cinema_record_playback_heartbeat(
 p_session_id uuid,p_owner_user_id uuid,p_session_token_hash text,p_event_id uuid,p_position_seconds integer
) returns jsonb language plpgsql security definer set search_path=public,pg_temp as $function$
declare v_session public.cinema_playback_sessions%rowtype; v_event public.cinema_playback_session_events%rowtype; v_inserted integer;
begin
 if p_event_id is null or p_position_seconds is null or p_position_seconds<0 or p_position_seconds>86400
    or p_session_token_hash is null or p_session_token_hash !~ '^[0-9a-f]{64}$' then
  raise exception 'invalid playback heartbeat' using errcode='22023';
 end if;
 select * into v_session from public.cinema_playback_sessions where id=p_session_id and owner_user_id=p_owner_user_id for update;
 if not found or v_session.session_token_hash<>p_session_token_hash then
  raise exception 'playback session not found' using errcode='42501';
 end if;
 select * into v_event from public.cinema_playback_session_events where event_id=p_event_id;
 if found then
  if v_event.session_id<>p_session_id or v_event.owner_user_id<>p_owner_user_id or v_event.event_type<>'heartbeat' or v_event.position_seconds<>p_position_seconds then
   raise exception 'playback event idempotency conflict' using errcode='23505';
  end if;
  return jsonb_build_object('session_id',p_session_id,'duplicate',true,'last_position_seconds',v_session.last_position_seconds,'max_position_seconds',v_session.max_position_seconds);
 end if;
 if v_session.status<>'active' or v_session.expires_at<=clock_timestamp() then
  raise exception 'playback session is not active' using errcode='55000';
 end if;
 if v_session.duration_seconds is not null and p_position_seconds>v_session.duration_seconds+5 then
  raise exception 'playback position exceeds duration' using errcode='22023';
 end if;
 insert into public.cinema_playback_session_events(session_id,owner_user_id,event_id,event_type,position_seconds)
 values(p_session_id,p_owner_user_id,p_event_id,'heartbeat',p_position_seconds) on conflict(event_id) do nothing;
 get diagnostics v_inserted=row_count;
 if v_inserted=0 then
  select * into v_event from public.cinema_playback_session_events where event_id=p_event_id;
  if not found or v_event.session_id<>p_session_id or v_event.owner_user_id<>p_owner_user_id or v_event.event_type<>'heartbeat' or v_event.position_seconds<>p_position_seconds then
   raise exception 'playback event idempotency conflict' using errcode='23505';
  end if;
  return jsonb_build_object('session_id',p_session_id,'duplicate',true,'last_position_seconds',v_session.last_position_seconds,'max_position_seconds',v_session.max_position_seconds);
 end if;
 update public.cinema_playback_sessions set last_position_seconds=p_position_seconds,max_position_seconds=greatest(max_position_seconds,p_position_seconds),
  last_heartbeat_at=clock_timestamp(),updated_at=clock_timestamp() where id=p_session_id returning * into v_session;
 return jsonb_build_object('session_id',p_session_id,'duplicate',false,'last_position_seconds',v_session.last_position_seconds,
  'max_position_seconds',v_session.max_position_seconds,'last_heartbeat_at',v_session.last_heartbeat_at);
end;$function$;

create or replace function public.cinema_finish_playback_session(
 p_session_id uuid,p_owner_user_id uuid,p_session_token_hash text,p_event_id uuid,p_position_seconds integer
) returns jsonb language plpgsql security definer set search_path=public,pg_temp as $function$
declare v_session public.cinema_playback_sessions%rowtype; v_event public.cinema_playback_session_events%rowtype; v_inserted integer;
begin
 if p_event_id is null or p_position_seconds is null or p_position_seconds<0 or p_position_seconds>86400
    or p_session_token_hash is null or p_session_token_hash !~ '^[0-9a-f]{64}$' then
  raise exception 'invalid playback finish' using errcode='22023';
 end if;
 select * into v_session from public.cinema_playback_sessions where id=p_session_id and owner_user_id=p_owner_user_id for update;
 if not found or v_session.session_token_hash<>p_session_token_hash then
  raise exception 'playback session not found' using errcode='42501';
 end if;
 select * into v_event from public.cinema_playback_session_events where event_id=p_event_id;
 if found then
  if v_event.session_id<>p_session_id or v_event.owner_user_id<>p_owner_user_id or v_event.event_type<>'finish' or v_event.position_seconds<>p_position_seconds then
   raise exception 'playback event idempotency conflict' using errcode='23505';
  end if;
  return jsonb_build_object('session_id',p_session_id,'duplicate',true,'status',v_session.status,'last_position_seconds',v_session.last_position_seconds);
 end if;
 if v_session.status<>'active' or v_session.expires_at<=clock_timestamp() then
  raise exception 'playback session is not active' using errcode='55000';
 end if;
 if v_session.duration_seconds is not null and p_position_seconds>v_session.duration_seconds+5 then
  raise exception 'playback position exceeds duration' using errcode='22023';
 end if;
 insert into public.cinema_playback_session_events(session_id,owner_user_id,event_id,event_type,position_seconds)
 values(p_session_id,p_owner_user_id,p_event_id,'finish',p_position_seconds) on conflict(event_id) do nothing;
 get diagnostics v_inserted=row_count;
 if v_inserted=0 then
  select * into v_event from public.cinema_playback_session_events where event_id=p_event_id;
  if not found or v_event.session_id<>p_session_id or v_event.owner_user_id<>p_owner_user_id or v_event.event_type<>'finish' or v_event.position_seconds<>p_position_seconds then
   raise exception 'playback event idempotency conflict' using errcode='23505';
  end if;
  return jsonb_build_object('session_id',p_session_id,'duplicate',true,'status',v_session.status,'last_position_seconds',v_session.last_position_seconds);
 end if;
 update public.cinema_playback_sessions set status='completed',last_position_seconds=p_position_seconds,
  max_position_seconds=greatest(max_position_seconds,p_position_seconds),last_heartbeat_at=clock_timestamp(),
  finished_at=clock_timestamp(),updated_at=clock_timestamp() where id=p_session_id returning * into v_session;
 return jsonb_build_object('session_id',p_session_id,'duplicate',false,'status',v_session.status,
  'last_position_seconds',v_session.last_position_seconds,'max_position_seconds',v_session.max_position_seconds,'finished_at',v_session.finished_at);
end;$function$;

revoke all on function public.cinema_record_playback_heartbeat(uuid,uuid,text,uuid,integer) from public,anon,authenticated;
revoke all on function public.cinema_finish_playback_session(uuid,uuid,text,uuid,integer) from public,anon,authenticated;
grant execute on function public.cinema_record_playback_heartbeat(uuid,uuid,text,uuid,integer) to service_role;
grant execute on function public.cinema_finish_playback_session(uuid,uuid,text,uuid,integer) to service_role;
comment on table public.cinema_playback_sessions is 'Server-authorized playback sessions; only SHA-256 token hashes are persisted.';
comment on table public.cinema_playback_session_events is 'Idempotent owner-scoped playback heartbeat and finish receipts.';
comment on table public.cinema_watchlist_items is 'Owner-private AI Cinema watchlist; mutations are FastAPI-only.';
commit;

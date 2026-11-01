-- WP-03: durable, private social-graph change outbox.
-- Additive only: reuses the canonical social_edges and user_interests tables.
-- Events contain relationship identifiers and owner-private interest signals only.
create table if not exists public.social_graph_events (
  id uuid primary key default gen_random_uuid(),
  event_type text not null check (event_type in (
    'social.follow.requested',
    'social.follow.created',
    'social.follow.accepted',
    'social.follow.removed',
    'social.block.created',
    'social.block.removed',
    'social.mute.created',
    'social.mute.removed',
    'interest.preference.created',
    'interest.preference.updated',
    'interest.preference.removed'
  )),
  actor_user_id uuid,
  target_user_id uuid,
  entity_key text,
  payload jsonb not null default '{}'::jsonb check (jsonb_typeof(payload) = 'object'),
  delivery_state text not null default 'pending' check (delivery_state in ('pending','processing','processed','dead')),
  attempts integer not null default 0 check (attempts >= 0),
  next_attempt_at timestamptz not null default now(),
  lease_token uuid,
  lease_expires_at timestamptz,
  processed_at timestamptz,
  last_error_code text check (last_error_code is null or char_length(last_error_code) <= 80),
  created_at timestamptz not null default now(),
  constraint social_graph_events_lease_state check (
    (delivery_state = 'processing' and lease_token is not null and lease_expires_at is not null)
    or (delivery_state <> 'processing' and lease_token is null and lease_expires_at is null)
  ),
  constraint social_graph_events_processed_state check (
    (delivery_state = 'processed' and processed_at is not null)
    or (delivery_state <> 'processed' and processed_at is null)
  )
);

create index if not exists social_graph_events_pending_idx
  on public.social_graph_events(next_attempt_at, created_at)
  where delivery_state in ('pending','processing');
create index if not exists social_graph_events_actor_created_idx
  on public.social_graph_events(actor_user_id, created_at desc);
create index if not exists social_graph_events_target_created_idx
  on public.social_graph_events(target_user_id, created_at desc);

comment on table public.social_graph_events is
  'Private transactional outbox for canonical Social Graph and Interest preference changes. Service/worker only; never a client-readable feed.';

alter table public.social_graph_events enable row level security;
revoke all on public.social_graph_events from public, anon, authenticated;
grant select, update on public.social_graph_events to service_role;

create or replace function public.capture_social_graph_event()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_event_type text;
  v_actor uuid;
  v_target uuid;
  v_entity_key text;
  v_payload jsonb;
begin
  if tg_table_name = 'social_edges' then
    if tg_op = 'DELETE' then
      v_actor := old.actor_user_id;
      v_target := old.target_user_id;
      v_entity_key := old.edge_type;
      v_event_type := case old.edge_type
        when 'follow' then 'social.follow.removed'
        when 'block' then 'social.block.removed'
        when 'mute' then 'social.mute.removed'
        else null
      end;
      v_payload := jsonb_build_object('edge_type', old.edge_type, 'previous_status', old.status);
    elsif tg_op = 'INSERT' then
      v_actor := new.actor_user_id;
      v_target := new.target_user_id;
      v_entity_key := new.edge_type;
      v_event_type := case
        when new.edge_type = 'follow' and new.status = 'requested' then 'social.follow.requested'
        when new.edge_type = 'follow' then 'social.follow.created'
        when new.edge_type = 'block' then 'social.block.created'
        when new.edge_type = 'mute' then 'social.mute.created'
        else null
      end;
      v_payload := jsonb_build_object('edge_type', new.edge_type, 'status', new.status);
    elsif tg_op = 'UPDATE' and old.status is distinct from new.status
      and new.edge_type = 'follow' and old.status = 'requested' and new.status = 'active' then
      v_actor := new.actor_user_id;
      v_target := new.target_user_id;
      v_entity_key := new.edge_type;
      v_event_type := 'social.follow.accepted';
      v_payload := jsonb_build_object('edge_type', new.edge_type, 'previous_status', old.status, 'status', new.status);
    else
      return new;
    end if;

    if v_event_type is not null then
      insert into public.social_graph_events(event_type, actor_user_id, target_user_id, entity_key, payload)
      values (v_event_type, v_actor, v_target, v_entity_key, coalesce(v_payload, '{}'::jsonb));
    end if;
    if tg_op = 'DELETE' then return old; end if;
    return new;
  end if;

  if tg_table_name = 'user_interests' then
    if tg_op = 'DELETE' then
      v_actor := old.user_id;
      v_entity_key := old.interest_key;
      v_event_type := 'interest.preference.removed';
      v_payload := jsonb_build_object('interest_key', old.interest_key, 'preference', old.preference, 'data_scope', 'owner_private');
    elsif tg_op = 'INSERT' then
      v_actor := new.user_id;
      v_entity_key := new.interest_key;
      v_event_type := 'interest.preference.created';
      v_payload := jsonb_build_object('interest_key', new.interest_key, 'preference', new.preference, 'data_scope', 'owner_private');
    elsif tg_op = 'UPDATE' and old.preference is distinct from new.preference then
      v_actor := new.user_id;
      v_entity_key := new.interest_key;
      v_event_type := 'interest.preference.updated';
      v_payload := jsonb_build_object('interest_key', new.interest_key, 'previous_preference', old.preference, 'preference', new.preference, 'data_scope', 'owner_private');
    else
      return new;
    end if;

    insert into public.social_graph_events(event_type, actor_user_id, entity_key, payload)
    values (v_event_type, v_actor, v_entity_key, coalesce(v_payload, '{}'::jsonb));
    if tg_op = 'DELETE' then return old; end if;
    return new;
  end if;

  return null;
end;
$$;

revoke all on function public.capture_social_graph_event() from public, anon, authenticated;

drop trigger if exists social_edges_capture_graph_event on public.social_edges;
create trigger social_edges_capture_graph_event
after insert or update or delete on public.social_edges
for each row execute function public.capture_social_graph_event();

drop trigger if exists user_interests_capture_graph_event on public.user_interests;
create trigger user_interests_capture_graph_event
after insert or update or delete on public.user_interests
for each row execute function public.capture_social_graph_event();

-- A user may inspect their own active incoming follower edges. Other users' graph
-- edges remain private; this policy does not make follower lists globally public.
drop policy if exists social_edges_select_incoming_active_follow on public.social_edges;
create policy social_edges_select_incoming_active_follow on public.social_edges
for select to authenticated
using (
  target_user_id = (select auth.uid())
  and edge_type = 'follow'
  and status = 'active'
);

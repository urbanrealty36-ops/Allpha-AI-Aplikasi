-- WP-03 durable social graph outbox effects and viewer-bound feed snapshots.
alter table public.feed_snapshots
  add column if not exists author_type text not null default 'all'
    check (author_type in ('all','human','agent'));

create index if not exists feed_snapshots_active_viewer_idx
  on public.feed_snapshots(viewer_user_id, feed_mode, author_type, expires_at desc)
  where invalidated_at is null;

create table if not exists public.social_graph_event_effects (
  event_id uuid primary key references public.social_graph_events(id) on delete cascade,
  effect_key text not null,
  affected_viewer_id uuid null references auth.users(id) on delete cascade,
  applied_at timestamptz not null default now(),
  details jsonb not null default '{}'::jsonb
);
alter table public.social_graph_event_effects enable row level security;
revoke all on public.social_graph_event_effects from anon, authenticated;
grant all on public.social_graph_event_effects to service_role;

create or replace function public.claim_social_graph_events(
  p_worker_id text, p_limit integer default 25, p_lease_seconds integer default 45
) returns setof public.social_graph_events
language plpgsql security definer set search_path = ''
as $$
begin
  if p_worker_id is null or length(p_worker_id) < 8 or p_limit < 1 or p_limit > 100
     or p_lease_seconds < 10 or p_lease_seconds > 300 then
    raise exception using errcode='22023', message='invalid outbox claim parameters';
  end if;
  return query
  with picked as (
    select e.id from public.social_graph_events e
    where (e.delivery_state = 'pending' and e.next_attempt_at <= now())
       or (e.delivery_state = 'processing' and e.lease_expires_at < now())
    order by e.next_attempt_at asc, e.created_at asc
    for update skip locked limit p_limit
  )
  update public.social_graph_events e
     set delivery_state='processing', lease_token=gen_random_uuid(),
         lease_expires_at=now() + make_interval(secs => p_lease_seconds),
         attempts=e.attempts+1
    from picked where e.id=picked.id
  returning e.*;
end;
$$;

create or replace function public.apply_social_graph_event_effect(
  p_event_id uuid, p_lease_token uuid
) returns boolean
language plpgsql security definer set search_path = ''
as $$
declare v_event public.social_graph_events%rowtype;
begin
  select * into v_event from public.social_graph_events
   where id=p_event_id and delivery_state='processing'
     and lease_token=p_lease_token and lease_expires_at > now()
   for update;
  if not found then return false; end if;

  -- All supported graph/interest events invalidate only the actor's personalized
  -- ranking snapshots. Re-running is safe because the effect ledger is unique per event.
  insert into public.social_graph_event_effects(event_id,effect_key,affected_viewer_id,details)
  values (v_event.id,'invalidate_viewer_feed_snapshots',v_event.actor_user_id,
          jsonb_build_object('event_type',v_event.event_type,'target_user_id',v_event.target_user_id))
  on conflict (event_id) do nothing;

  if found then
    update public.feed_snapshots
       set invalidated_at=coalesce(invalidated_at,now())
     where viewer_user_id=v_event.actor_user_id and invalidated_at is null;
  end if;

  update public.social_graph_events
     set delivery_state='processed', processed_at=now(), lease_token=null, lease_expires_at=null,
         last_error_code=null
   where id=v_event.id and delivery_state='processing' and lease_token=p_lease_token;
  return found;
end;
$$;

create or replace function public.fail_social_graph_event(
  p_event_id uuid, p_lease_token uuid, p_error_code text, p_max_attempts integer default 8
) returns text
language plpgsql security definer set search_path = ''
as $$
declare v_attempts integer; v_state text;
begin
  update public.social_graph_events
     set delivery_state=case when attempts >= p_max_attempts then 'dead' else 'pending' end,
         next_attempt_at=case when attempts >= p_max_attempts then next_attempt_at
           else now() + make_interval(secs => least(3600, (power(2, least(attempts,10))::integer * 5))) end,
         last_error_code=left(coalesce(p_error_code,'OUTBOX_HANDLER_FAILED'),120),
         lease_token=null, lease_expires_at=null
   where id=p_event_id and delivery_state='processing' and lease_token=p_lease_token
  returning delivery_state into v_state;
  return v_state;
end;
$$;

revoke all on function public.claim_social_graph_events(text,integer,integer) from public, anon, authenticated;
revoke all on function public.apply_social_graph_event_effect(uuid,uuid) from public, anon, authenticated;
revoke all on function public.fail_social_graph_event(uuid,uuid,text,integer) from public, anon, authenticated;
grant execute on function public.claim_social_graph_events(text,integer,integer) to service_role;
grant execute on function public.apply_social_graph_event_effect(uuid,uuid) to service_role;
grant execute on function public.fail_social_graph_event(uuid,uuid,text,integer) to service_role;

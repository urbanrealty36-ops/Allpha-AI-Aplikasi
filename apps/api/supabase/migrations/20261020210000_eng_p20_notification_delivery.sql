-- ENG-P20: transactional message notification producer, preference-aware inbox,
-- per-device Expo push queue, bounded leases/retries, and provider receipt recovery.

create table if not exists public.notification_devices (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  expo_push_token text not null unique check (char_length(expo_push_token) between 20 and 220),
  platform text not null check (platform in ('android','ios')),
  device_id text check (device_id is null or char_length(device_id) between 1 and 160),
  enabled boolean not null default true,
  last_seen_at timestamptz not null default now(),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists notification_devices_user_enabled_idx
  on public.notification_devices(user_id, enabled, last_seen_at desc);

create table if not exists public.notification_push_deliveries (
  id uuid primary key default gen_random_uuid(),
  notification_id uuid not null references public.notifications(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  device_id uuid not null references public.notification_devices(id) on delete cascade,
  state text not null default 'pending'
    check (state in ('pending','sending','sent','delivered','failed','suppressed')),
  attempt_count integer not null default 0 check (attempt_count >= 0),
  max_attempts integer not null default 5 check (max_attempts between 1 and 10),
  next_attempt_at timestamptz default now(),
  lease_token uuid,
  lease_expires_at timestamptz,
  provider_ticket_id text,
  last_error_code text,
  sent_at timestamptz,
  receipt_checked_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (notification_id, device_id)
);
create index if not exists notification_push_due_idx
  on public.notification_push_deliveries(state, next_attempt_at, created_at)
  where state in ('pending','failed');
create index if not exists notification_push_receipts_idx
  on public.notification_push_deliveries(sent_at, created_at)
  where state = 'sent' and provider_ticket_id is not null and receipt_checked_at is null;

alter table public.notification_devices enable row level security;
alter table public.notification_push_deliveries enable row level security;
revoke all on public.notification_devices from anon, authenticated;
revoke all on public.notification_push_deliveries from anon, authenticated;
grant select, insert, update, delete on public.notification_devices to service_role;
grant select, insert, update, delete on public.notification_push_deliveries to service_role;

create or replace function public.enqueue_message_notification()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  recipient record;
  sender_label text;
  pref_text text;
  allowed boolean;
begin
  -- Only human-authored messages create user-facing social notifications.
  if new.sender_type is distinct from 'human' or new.sender_user_id is null then
    return new;
  end if;

  select coalesce(nullif(pg_catalog.btrim(p.display_name), ''),
                  nullif(pg_catalog.btrim(p.username), ''),
                  'Pengguna Allpha')
    into sender_label
  from public.profiles p
  where p.id = new.sender_user_id;

  sender_label := coalesce(sender_label, 'Pengguna Allpha');

  for recipient in
    select cp.user_id
    from public.conversation_participants cp
    where cp.conversation_id = new.conversation_id
      and cp.user_id is not null
      and cp.user_id <> new.sender_user_id
  loop
    select us.notification_preferences ->> 'social_activity'
      into pref_text
    from public.user_settings us
    where us.user_id = recipient.user_id;

    allowed := case
      when pref_text in ('true','false') then pref_text = 'true'
      else true
    end;

    insert into public.notifications (
      user_id, category, event_key, title, body, payload,
      delivery_state, created_at, updated_at
    ) values (
      recipient.user_id,
      'social_activity',
      'message:' || new.id::text,
      pg_catalog.left('Pesan baru dari ' || sender_label, 160),
      'Anda menerima pesan baru.',
      pg_catalog.jsonb_build_object(
        'type', 'message',
        'message_id', new.id,
        'conversation_id', new.conversation_id
      ),
      case when allowed then 'delivered' else 'suppressed' end,
      coalesce(new.created_at, pg_catalog.now()),
      pg_catalog.now()
    )
    on conflict (user_id, event_key) do nothing;
  end loop;

  return new;
end;
$$;

drop trigger if exists messages_enqueue_notification on public.messages;
create trigger messages_enqueue_notification
after insert on public.messages
for each row execute function public.enqueue_message_notification();

create or replace function public.enqueue_notification_push_deliveries(p_limit integer default 200)
returns integer
language plpgsql
security definer
set search_path = ''
as $$
declare inserted_count integer;
begin
  if p_limit < 1 or p_limit > 1000 then
    raise exception 'invalid_limit';
  end if;

  insert into public.notification_push_deliveries (
    notification_id, user_id, device_id, state, next_attempt_at
  )
  select n.id, n.user_id, d.id, 'pending', pg_catalog.now()
  from public.notifications n
  join public.notification_devices d
    on d.user_id = n.user_id and d.enabled = true
  left join public.user_settings us on us.user_id = n.user_id
  where n.delivery_state = 'delivered'
    and n.created_at >= pg_catalog.now() - interval '24 hours'
    and coalesce(
      case
        when us.notification_preferences ->> 'push_enabled' in ('true','false')
          then (us.notification_preferences ->> 'push_enabled')::boolean
        else true
      end, true
    )
    and coalesce(
      case
        when us.notification_preferences ->> n.category in ('true','false')
          then (us.notification_preferences ->> n.category)::boolean
        else true
      end, true
    )
  and not exists (
    select 1 from public.notification_push_deliveries existing
    where existing.notification_id = n.id and existing.device_id = d.id
  )
  order by n.created_at, d.created_at
  limit p_limit
  on conflict (notification_id, device_id) do nothing;

  get diagnostics inserted_count = row_count;
  return inserted_count;
end;
$$;

create or replace function public.claim_notification_push_deliveries(
  p_limit integer default 25,
  p_lease_seconds integer default 90
)
returns setof public.notification_push_deliveries
language plpgsql
security definer
set search_path = ''
as $$
begin
  if p_limit < 1 or p_limit > 100 or p_lease_seconds < 30 or p_lease_seconds > 300 then
    raise exception 'invalid_claim_bounds';
  end if;

  return query
  with candidates as (
    select q.id
    from public.notification_push_deliveries q
    where (
      q.state in ('pending','failed')
      and q.next_attempt_at <= pg_catalog.now()
      and q.attempt_count < q.max_attempts
    ) or (
      q.state = 'sending'
      and q.lease_expires_at <= pg_catalog.now()
      and q.attempt_count < q.max_attempts
    )
    order by q.next_attempt_at, q.created_at
    limit p_limit
    for update skip locked
  )
  update public.notification_push_deliveries q
  set state = 'sending',
      attempt_count = q.attempt_count + 1,
      lease_token = gen_random_uuid(),
      lease_expires_at = pg_catalog.now() + pg_catalog.make_interval(secs => p_lease_seconds),
      updated_at = pg_catalog.now()
  from candidates c
  where q.id = c.id
  returning q.*;
end;
$$;

create or replace function public.claim_notification_push_receipts(
  p_limit integer default 100,
  p_lease_seconds integer default 90
)
returns setof public.notification_push_deliveries
language plpgsql
security definer
set search_path = ''
as $$
begin
  if p_limit < 1 or p_limit > 200 or p_lease_seconds < 30 or p_lease_seconds > 300 then
    raise exception 'invalid_receipt_claim_bounds';
  end if;

  return query
  with candidates as (
    select q.id
    from public.notification_push_deliveries q
    where q.state = 'sent'
      and q.provider_ticket_id is not null
      and q.receipt_checked_at is null
      and q.sent_at <= pg_catalog.now() - interval '10 minutes'
      and (q.lease_token is null or q.lease_expires_at <= pg_catalog.now())
    order by q.sent_at, q.created_at
    limit p_limit
    for update skip locked
  )
  update public.notification_push_deliveries q
  set lease_token = gen_random_uuid(),
      lease_expires_at = pg_catalog.now() + pg_catalog.make_interval(secs => p_lease_seconds),
      updated_at = pg_catalog.now()
  from candidates c
  where q.id = c.id
  returning q.*;
end;
$$;

revoke all on function public.enqueue_message_notification() from public, anon, authenticated;
revoke all on function public.enqueue_notification_push_deliveries(integer) from public, anon, authenticated;
revoke all on function public.claim_notification_push_deliveries(integer, integer) from public, anon, authenticated;
revoke all on function public.claim_notification_push_receipts(integer, integer) from public, anon, authenticated;
grant execute on function public.enqueue_notification_push_deliveries(integer) to service_role;
grant execute on function public.claim_notification_push_deliveries(integer, integer) to service_role;
grant execute on function public.claim_notification_push_receipts(integer, integer) to service_role;

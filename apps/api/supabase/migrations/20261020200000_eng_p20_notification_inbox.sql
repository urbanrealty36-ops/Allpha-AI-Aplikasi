-- ENG-P20: durable user notification inbox and idempotent delivery state.
create table if not exists public.notifications (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  category text not null check (category in ('social_activity','product_updates','security_alerts','community','workspace','system')),
  event_key text not null check (char_length(event_key) between 1 and 160),
  title text not null check (char_length(title) between 1 and 160),
  body text not null default '' check (char_length(body) <= 2000),
  payload jsonb not null default '{}'::jsonb check (jsonb_typeof(payload) = 'object'),
  delivery_state text not null default 'queued' check (delivery_state in ('queued','delivered','failed','suppressed')),
  attempt_count integer not null default 0 check (attempt_count >= 0),
  next_attempt_at timestamptz,
  last_error_code text,
  read_at timestamptz,
  delivered_at timestamptz,
  expires_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (user_id, event_key)
);
create index if not exists notifications_user_inbox_idx
  on public.notifications(user_id, created_at desc, id desc);
create index if not exists notifications_delivery_queue_idx
  on public.notifications(delivery_state, next_attempt_at, created_at)
  where delivery_state in ('queued','failed');
alter table public.notifications enable row level security;
revoke all on public.notifications from anon, authenticated;
grant select, insert, update, delete on public.notifications to service_role;

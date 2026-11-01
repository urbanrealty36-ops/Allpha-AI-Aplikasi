-- WP-03 follow-up: feed delivery/view telemetry and explicit negative feedback.
-- These records are owner-private and written only through the canonical FastAPI service role.
create table if not exists public.feed_impressions (
  id uuid primary key default gen_random_uuid(),
  viewer_user_id uuid not null references auth.users(id) on delete cascade,
  content_id uuid not null references public.content_items(id) on delete cascade,
  impression_key text not null check (impression_key ~ '^[A-Za-z0-9._:-]{12,128}$'),
  event_type text not null check (event_type in ('impression','view')),
  feed_mode text not null check (feed_mode in ('for_you','following','recent','reels')),
  position integer not null check (position >= 0 and position < 1000),
  ranking_version text not null check (char_length(ranking_version) between 1 and 80),
  created_at timestamptz not null default now(),
  constraint feed_impressions_idempotent unique (viewer_user_id, content_id, impression_key)
);
create index if not exists feed_impressions_viewer_created_idx
  on public.feed_impressions(viewer_user_id, created_at desc);
create index if not exists feed_impressions_content_created_idx
  on public.feed_impressions(content_id, created_at desc);

create table if not exists public.feed_feedback (
  id uuid primary key default gen_random_uuid(),
  viewer_user_id uuid not null references auth.users(id) on delete cascade,
  content_id uuid not null references public.content_items(id) on delete cascade,
  target_owner_id uuid not null references auth.users(id) on delete cascade,
  feedback_type text not null check (feedback_type in ('not_interested','hide_creator')),
  status text not null default 'active' check (status in ('active','retracted')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint feed_feedback_unique unique (viewer_user_id, content_id, feedback_type)
);
create index if not exists feed_feedback_viewer_active_idx
  on public.feed_feedback(viewer_user_id, feedback_type, created_at desc)
  where status = 'active';
create index if not exists feed_feedback_target_active_idx
  on public.feed_feedback(viewer_user_id, target_owner_id)
  where status = 'active' and feedback_type = 'hide_creator';

alter table public.feed_impressions enable row level security;
alter table public.feed_feedback enable row level security;
revoke all on public.feed_impressions, public.feed_feedback from public, anon, authenticated;
grant select, insert, update, delete on public.feed_impressions, public.feed_feedback to service_role;

create or replace function public.feed_feedback_touch_updated_at()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;
revoke all on function public.feed_feedback_touch_updated_at() from public, anon, authenticated;
drop trigger if exists feed_feedback_touch_updated_at on public.feed_feedback;
create trigger feed_feedback_touch_updated_at
before update on public.feed_feedback
for each row execute function public.feed_feedback_touch_updated_at();

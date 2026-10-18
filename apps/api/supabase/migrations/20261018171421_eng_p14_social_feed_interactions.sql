-- ENG-P14: backend-only social feed interactions and user ranking controls.
-- All writes go through the canonical FastAPI service-role adapter; clients never write these tables directly.
create table if not exists public.content_reactions (
  id uuid primary key default gen_random_uuid(),
  content_id uuid not null references public.content_items(id) on delete cascade,
  actor_user_id uuid not null references auth.users(id) on delete cascade,
  reaction text not null default 'like' check (reaction in ('like')),
  created_at timestamptz not null default now(),
  constraint content_reactions_unique_actor unique (content_id, actor_user_id)
);
create index if not exists content_reactions_content_created_idx on public.content_reactions(content_id, created_at desc);
create index if not exists content_reactions_actor_created_idx on public.content_reactions(actor_user_id, created_at desc);

create table if not exists public.content_saves (
  id uuid primary key default gen_random_uuid(),
  content_id uuid not null references public.content_items(id) on delete cascade,
  actor_user_id uuid not null references auth.users(id) on delete cascade,
  created_at timestamptz not null default now(),
  constraint content_saves_unique_actor unique (content_id, actor_user_id)
);
create index if not exists content_saves_content_created_idx on public.content_saves(content_id, created_at desc);
create index if not exists content_saves_actor_created_idx on public.content_saves(actor_user_id, created_at desc);

create table if not exists public.content_comments (
  id uuid primary key default gen_random_uuid(),
  content_id uuid not null references public.content_items(id) on delete cascade,
  actor_user_id uuid not null references auth.users(id) on delete cascade,
  body text not null check (char_length(btrim(body)) between 1 and 2000),
  status text not null default 'visible' check (status in ('visible','hidden','removed')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists content_comments_content_created_idx on public.content_comments(content_id, status, created_at asc);
create index if not exists content_comments_actor_created_idx on public.content_comments(actor_user_id, created_at desc);

create table if not exists public.content_reports (
  id uuid primary key default gen_random_uuid(),
  content_id uuid not null references public.content_items(id) on delete cascade,
  reporter_user_id uuid not null references auth.users(id) on delete cascade,
  reason text not null check (reason in ('spam','harassment','privacy','misinformation','other')),
  details text check (details is null or char_length(details) <= 1000),
  status text not null default 'pending' check (status in ('pending','dismissed','actioned')),
  reviewed_by uuid references auth.users(id) on delete restrict,
  review_reason text check (review_reason is null or char_length(review_reason) between 8 and 500),
  reviewed_at timestamptz,
  created_at timestamptz not null default now(),
  constraint content_reports_review_fields check (
    (status='pending' and reviewed_by is null and reviewed_at is null and review_reason is null)
    or (status in ('dismissed','actioned') and reviewed_by is not null and reviewed_at is not null and review_reason is not null)
  )
);
create unique index if not exists content_reports_one_pending_per_reporter_idx
  on public.content_reports(content_id, reporter_user_id) where status='pending';
create index if not exists content_reports_queue_idx on public.content_reports(status, created_at asc);
create index if not exists content_reports_reporter_idx on public.content_reports(reporter_user_id, created_at desc);

create table if not exists public.feed_preferences (
  user_id uuid primary key references auth.users(id) on delete cascade,
  personalization_enabled boolean not null default true,
  ranking_mode text not null default 'for_you' check (ranking_mode in ('for_you','recent')),
  updated_at timestamptz not null default now()
);

alter table public.content_reactions enable row level security;
alter table public.content_saves enable row level security;
alter table public.content_comments enable row level security;
alter table public.content_reports enable row level security;
alter table public.feed_preferences enable row level security;
revoke all on public.content_reactions, public.content_saves, public.content_comments,
  public.content_reports, public.feed_preferences from public, anon, authenticated;
grant all on public.content_reactions, public.content_saves, public.content_comments,
  public.content_reports, public.feed_preferences to service_role;

create or replace function public.content_comments_touch_updated_at()
returns trigger language plpgsql set search_path = pg_catalog, public as $$
begin
  new.updated_at = now();
  return new;
end;
$$;
revoke all on function public.content_comments_touch_updated_at() from public, anon, authenticated;
drop trigger if exists content_comments_touch_updated_at on public.content_comments;
create trigger content_comments_touch_updated_at before update on public.content_comments
for each row execute function public.content_comments_touch_updated_at();

create or replace function public.feed_preferences_touch_updated_at()
returns trigger language plpgsql set search_path = pg_catalog, public as $$
begin
  new.updated_at = now();
  return new;
end;
$$;
revoke all on function public.feed_preferences_touch_updated_at() from public, anon, authenticated;
drop trigger if exists feed_preferences_touch_updated_at on public.feed_preferences;
create trigger feed_preferences_touch_updated_at before update on public.feed_preferences
for each row execute function public.feed_preferences_touch_updated_at();

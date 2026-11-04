-- WP-03 Agent attribution and stable feed snapshot foundations.
-- Agent identity is attribution metadata; the authenticated human remains content owner.
alter table public.content_items
  add column if not exists ai_agent_id uuid null
  references public.ai_agents(id) on delete set null;

create index if not exists content_items_ai_agent_published_idx
  on public.content_items (ai_agent_id, published_at desc, id desc)
  where ai_agent_id is not null and status = 'published' and moderation_status = 'approved';

create table if not exists public.feed_snapshots (
  id uuid primary key default gen_random_uuid(),
  viewer_user_id uuid null references auth.users(id) on delete cascade,
  feed_mode text not null check (feed_mode in ('for_you','recent','following','agents')),
  ranking_version text not null,
  created_at timestamptz not null default now(),
  expires_at timestamptz not null,
  invalidated_at timestamptz null,
  item_count integer not null default 0 check (item_count >= 0),
  constraint feed_snapshots_expiry_check check (expires_at > created_at)
);

create table if not exists public.feed_snapshot_items (
  snapshot_id uuid not null references public.feed_snapshots(id) on delete cascade,
  ordinal integer not null check (ordinal >= 0),
  content_id uuid not null references public.content_items(id) on delete cascade,
  owner_id uuid not null references auth.users(id) on delete cascade,
  rank_signals jsonb not null default '[]'::jsonb check (jsonb_typeof(rank_signals) = 'array'),
  primary key (snapshot_id, ordinal),
  unique (snapshot_id, content_id)
);

create index if not exists feed_snapshots_viewer_expiry_idx
  on public.feed_snapshots(viewer_user_id, expires_at desc);
create index if not exists feed_snapshot_items_content_idx
  on public.feed_snapshot_items(content_id);

alter table public.feed_snapshots enable row level security;
alter table public.feed_snapshot_items enable row level security;
revoke all on public.feed_snapshots, public.feed_snapshot_items from anon, authenticated;
grant all on public.feed_snapshots, public.feed_snapshot_items to service_role;

comment on column public.content_items.ai_agent_id is
  'Optional active AI Agent attribution. owner_id remains the authenticated human publisher.';
comment on table public.feed_snapshots is
  'Server-only, viewer-scoped immutable ranking snapshot; API must re-check visibility on read.';

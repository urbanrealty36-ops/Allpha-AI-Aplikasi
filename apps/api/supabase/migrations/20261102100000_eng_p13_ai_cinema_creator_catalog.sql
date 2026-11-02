-- ENG-P13: canonical AI Cinema creator catalogue metadata.
create table if not exists public.cinema_titles (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references auth.users(id) on delete cascade,
  title text not null check (char_length(btrim(title)) between 1 and 160),
  original_title text,
  synopsis text not null default '' check (char_length(synopsis) <= 5000),
  genre text not null check (genre in ('c_drama','k_drama','scifi','romance','thriller','animation_3d','documentary','other')),
  language_code text not null default 'id',
  maturity_rating text not null default 'unrated' check (maturity_rating in ('unrated','all_ages','13_plus','17_plus','21_plus')),
  ai_disclosure text not null default 'AI-assisted content',
  credits jsonb not null default '[]'::jsonb check (jsonb_typeof(credits) = 'array'),
  status text not null default 'draft' check (status in ('draft','processing','pending_review','published','rejected','archived','blocked')),
  moderation_status text not null default 'not_submitted' check (moderation_status in ('not_submitted','pending','approved','rejected','needs_changes')),
  rights_status text not null default 'unverified' check (rights_status in ('unverified','pending','cleared','rejected')),
  cover_media_id uuid references public.content_media(id) on delete set null,
  trailer_media_id uuid references public.content_media(id) on delete set null,
  version integer not null default 1 check (version > 0),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  published_at timestamptz,
  constraint cinema_publication_gate check (status <> 'published' or (moderation_status = 'approved' and rights_status = 'cleared'))
);
create table if not exists public.cinema_episodes (
  id uuid primary key default gen_random_uuid(),
  title_id uuid not null references public.cinema_titles(id) on delete cascade,
  owner_id uuid not null references auth.users(id) on delete cascade,
  episode_number integer not null check (episode_number > 0),
  title text not null check (char_length(btrim(title)) between 1 and 160),
  synopsis text not null default '' check (char_length(synopsis) <= 3000),
  media_id uuid references public.content_media(id) on delete set null,
  duration_seconds integer check (duration_seconds is null or duration_seconds between 1 and 86400),
  is_free_preview boolean not null default false,
  status text not null default 'draft' check (status in ('draft','processing','pending_review','ready','rejected','blocked')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(title_id, episode_number)
);
create index if not exists cinema_titles_public_catalog_idx on public.cinema_titles (published_at desc, genre, maturity_rating) where status = 'published' and moderation_status = 'approved' and rights_status = 'cleared';
create index if not exists cinema_titles_owner_updated_idx on public.cinema_titles(owner_id, updated_at desc);
create index if not exists cinema_episodes_title_order_idx on public.cinema_episodes(title_id, episode_number);
alter table public.cinema_titles enable row level security;
alter table public.cinema_episodes enable row level security;
create policy cinema_titles_owner_select on public.cinema_titles for select to authenticated using ((select auth.uid()) = owner_id);
create policy cinema_titles_owner_insert on public.cinema_titles for insert to authenticated with check ((select auth.uid()) = owner_id and status = 'draft');
create policy cinema_titles_owner_update on public.cinema_titles for update to authenticated using ((select auth.uid()) = owner_id) with check ((select auth.uid()) = owner_id and status in ('draft','rejected','archived'));
create policy cinema_titles_public_catalog_read on public.cinema_titles for select to anon, authenticated using (status = 'published' and moderation_status = 'approved' and rights_status = 'cleared');
create policy cinema_episodes_owner_select on public.cinema_episodes for select to authenticated using ((select auth.uid()) = owner_id);
create policy cinema_episodes_owner_insert on public.cinema_episodes for insert to authenticated with check ((select auth.uid()) = owner_id and exists (select 1 from public.cinema_titles t where t.id = title_id and t.owner_id = (select auth.uid()) and t.status in ('draft','rejected')));
create policy cinema_episodes_owner_update on public.cinema_episodes for update to authenticated using ((select auth.uid()) = owner_id) with check ((select auth.uid()) = owner_id);
create policy cinema_episodes_public_read on public.cinema_episodes for select to anon, authenticated using (status = 'ready' and exists (select 1 from public.cinema_titles t where t.id = title_id and t.status = 'published' and t.moderation_status = 'approved' and t.rights_status = 'cleared'));

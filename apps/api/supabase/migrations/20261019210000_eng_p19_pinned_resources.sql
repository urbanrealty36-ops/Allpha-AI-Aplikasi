-- ENG-P19 community lifecycle completion: canonical pinned resources and post moderation state.
alter table public.community_posts
  add column if not exists is_pinned boolean not null default false,
  add column if not exists pinned_by uuid references auth.users(id) on delete set null,
  add column if not exists pinned_at timestamptz;
create index if not exists community_posts_pinned_timeline_idx
  on public.community_posts(community_id,is_pinned desc,pinned_at desc,created_at desc)
  where status='published';

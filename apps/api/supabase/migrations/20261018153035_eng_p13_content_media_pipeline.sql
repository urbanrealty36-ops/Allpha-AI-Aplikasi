-- ENG-P13 canonical user content and private media metadata. Apply through the approved migration path.
create table if not exists public.content_items (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references auth.users(id) on delete cascade,
  content_type text not null default 'text' check (content_type in ('text','image','video','story','capsule','document','event','spatial','listing')),
  body text not null default '' check (char_length(body) <= 10000),
  visibility text not null default 'public' check (visibility in ('public','followers','private')),
  status text not null default 'draft' check (status in ('draft','review','published','failed','archived','deleted')),
  moderation_status text not null default 'not_submitted' check (moderation_status in ('not_submitted','pending','approved','rejected','removed')),
  version integer not null default 1 check (version > 0),
  provenance jsonb not null default '{}'::jsonb check (jsonb_typeof(provenance) = 'object'),
  error_code text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  published_at timestamptz,
  constraint content_publish_requires_approval check (status <> 'published' or moderation_status = 'approved'),
  constraint content_items_id_owner_unique unique (id, owner_id)
);
create index if not exists content_items_owner_updated_idx on public.content_items(owner_id, updated_at desc);
create index if not exists content_items_public_feed_idx on public.content_items(published_at desc) where status='published' and moderation_status='approved' and visibility='public';
create table if not exists public.content_media (
  id uuid primary key default gen_random_uuid(),
  content_id uuid not null references public.content_items(id) on delete cascade,
  owner_id uuid not null references auth.users(id) on delete cascade,
  bucket_id text not null default 'content-media' check (bucket_id='content-media'),
  storage_path text not null unique,
  filename text not null check (char_length(filename) between 1 and 120),
  media_type text not null check (media_type in ('image/jpeg','image/png','image/webp','video/mp4','video/webm')),
  size_bytes bigint not null check (size_bytes > 0 and size_bytes <= 52428800),
  sha256 text not null check (sha256 ~ '^[0-9a-f]{64}$'),
  status text not null default 'uploaded' check (status in ('uploading','uploaded','processing','ready','failed','deleting')),
  created_at timestamptz not null default now(),
  constraint content_media_owner_consistency foreign key (content_id, owner_id) references public.content_items(id, owner_id) on delete cascade
);
create index if not exists content_media_owner_content_idx on public.content_media(owner_id, content_id, created_at);
alter table public.content_items enable row level security;
alter table public.content_media enable row level security;
revoke all on public.content_items, public.content_media from anon, public, authenticated;
grant select on public.content_items, public.content_media to authenticated;
drop policy if exists content_items_owner_select on public.content_items;
create policy content_items_owner_select on public.content_items for select to authenticated using (owner_id=(select auth.uid()));
drop policy if exists content_media_owner_select on public.content_media;
create policy content_media_owner_select on public.content_media for select to authenticated using (owner_id=(select auth.uid()));
drop policy if exists content_items_public_feed_select on public.content_items;
create policy content_items_public_feed_select on public.content_items for select to anon, authenticated using (status='published' and moderation_status='approved' and visibility='public');
insert into storage.buckets(id,name,public,file_size_limit,allowed_mime_types)
values ('content-media','content-media',false,52428800,array['image/jpeg','image/png','image/webp','video/mp4','video/webm'])
on conflict(id) do update set public=false,file_size_limit=52428800,allowed_mime_types=excluded.allowed_mime_types;
drop policy if exists content_media_storage_owner_select on storage.objects;
create policy content_media_storage_owner_select on storage.objects for select to authenticated using (
 bucket_id='content-media' and (storage.foldername(name))[1]=(select auth.uid())::text
 and exists(select 1 from public.content_media m where m.owner_id=(select auth.uid()) and m.storage_path=storage.objects.name)
);

create or replace function public.content_items_touch_updated_at()
returns trigger
language plpgsql
set search_path = pg_catalog, public
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;
revoke all on function public.content_items_touch_updated_at() from public, anon, authenticated;
drop trigger if exists content_items_touch_updated_at on public.content_items;
create trigger content_items_touch_updated_at before update on public.content_items
for each row execute function public.content_items_touch_updated_at();

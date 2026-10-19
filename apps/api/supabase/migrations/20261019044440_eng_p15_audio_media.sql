-- ENG-P15: extend the canonical ENG-P13 private media pipeline for audio.
-- Additive only: preserve existing media and keep the bucket private.
alter table public.content_items
  drop constraint if exists content_items_content_type_check;
alter table public.content_items
  add constraint content_items_content_type_check
  check (content_type in ('text','image','video','audio','story','capsule','document','event','spatial','listing'));

alter table public.content_media
  drop constraint if exists content_media_media_type_check;
alter table public.content_media
  add constraint content_media_media_type_check
  check (media_type in (
    'image/jpeg','image/png','image/webp',
    'video/mp4','video/webm',
    'audio/mpeg','audio/mp4','audio/aac','audio/ogg','audio/wav','audio/webm'
  ));

insert into storage.buckets(id,name,public,file_size_limit,allowed_mime_types)
values (
  'content-media','content-media',false,52428800,
  array['image/jpeg','image/png','image/webp','video/mp4','video/webm',
        'audio/mpeg','audio/mp4','audio/aac','audio/ogg','audio/wav','audio/webm']
)
on conflict(id) do update
set public=false,
    file_size_limit=greatest(storage.buckets.file_size_limit, excluded.file_size_limit),
    allowed_mime_types=(
      select array_agg(distinct mime_type order by mime_type)
      from unnest(coalesce(storage.buckets.allowed_mime_types, '{}'::text[]) || excluded.allowed_mime_types) as mime_type
    );

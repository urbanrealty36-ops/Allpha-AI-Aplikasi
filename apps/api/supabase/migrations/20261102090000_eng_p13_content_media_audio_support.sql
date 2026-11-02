-- ENG-P13: align the canonical media metadata and private Storage bucket with
-- the audio formats already accepted by the FastAPI upload contract.
-- Additive and repeatable: existing media records and objects are preserved.

alter table public.content_media
  drop constraint if exists content_media_media_type_check;

alter table public.content_media
  add constraint content_media_media_type_check
  check (media_type in (
    'image/jpeg','image/png','image/webp',
    'video/mp4','video/webm',
    'audio/mpeg','audio/mp4','audio/aac','audio/ogg','audio/wav','audio/webm'
  ));

-- Keep the existing bucket private. Extend only the MIME allow-list;
-- do not raise the existing 50 MiB object limit.
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values (
  'content-media',
  'content-media',
  false,
  52428800,
  array[
    'image/jpeg','image/png','image/webp',
    'video/mp4','video/webm',
    'audio/mpeg','audio/mp4','audio/aac','audio/ogg','audio/wav','audio/webm'
  ]
)
on conflict (id) do update
set public = false,
    file_size_limit = 52428800,
    allowed_mime_types = excluded.allowed_mime_types;

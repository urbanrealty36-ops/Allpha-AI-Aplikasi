alter table public.content_media
 add column if not exists provider_public_id text,
 add column if not exists provider_batch_id text;
create unique index if not exists content_media_provider_public_id_idx
 on public.content_media(provider_public_id) where provider_public_id is not null;

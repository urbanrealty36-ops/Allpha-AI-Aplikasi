-- SOURCE ONLY — WP-11 Creator Production Workspace.
-- Extends the canonical cinema_titles project and existing content_media registry.
-- Do not apply until the canonical database change window and migration gate are approved.
begin;

alter table public.cinema_titles
  add column if not exists production_document jsonb not null default
    '{"schema_version":1,"screenplay":{"logline":"","synopsis":"","draft":""},"storyboard":[],"scenes":[],"timeline":{"tracks":[]},"audio_tracks":[],"export_profile":{"container":"mp4","resolution":"1080p","frame_rate":24,"aspect_ratio":"16:9"}}'::jsonb;

do $$
begin
  if not exists (
    select 1 from pg_constraint
    where conname = 'cinema_titles_production_document_contract'
      and conrelid = 'public.cinema_titles'::regclass
  ) then
    alter table public.cinema_titles
      add constraint cinema_titles_production_document_contract
      check (
        jsonb_typeof(production_document) = 'object'
        and production_document ->> 'schema_version' = '1'
        and octet_length(production_document::text) <= 262144
      ) not valid;
  end if;
end
$$;

create table if not exists public.cinema_assets (
  id uuid primary key default gen_random_uuid(),
  title_id uuid not null,
  owner_id uuid not null references auth.users(id) on delete cascade,
  media_id uuid not null references public.content_media(id) on delete restrict,
  asset_role text not null check (
    asset_role in ('reference','storyboard','source_video','source_audio','music',
                   'subtitle','generated_image','generated_video','cover','trailer')
  ),
  display_name text not null check (char_length(btrim(display_name)) between 1 and 160),
  metadata jsonb not null default '{}'::jsonb check (jsonb_typeof(metadata) = 'object'),
  created_by uuid not null references auth.users(id) on delete restrict,
  created_at timestamptz not null default now(),
  foreign key (title_id, owner_id)
    references public.cinema_titles(id, owner_id) on delete cascade,
  unique (title_id, media_id)
);

create index if not exists cinema_assets_title_role_created_idx
  on public.cinema_assets(title_id, asset_role, created_at desc);
create index if not exists cinema_assets_owner_created_idx
  on public.cinema_assets(owner_id, created_at desc);

alter table public.cinema_assets enable row level security;
revoke all on public.cinema_assets from public, anon, authenticated, service_role;
grant select, insert, update, delete on public.cinema_assets to service_role;

commit;

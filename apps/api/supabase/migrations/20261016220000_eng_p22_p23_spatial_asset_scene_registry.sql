-- Canonical spatial catalog for ENG-P22/ENG-P23.
-- Source-only until a positively verified isolated non-production Supabase target is available.
-- This is the single asset registry; do not add a parallel theme/GLB registry.

create table if not exists public.spatial_asset_versions (
  asset_id uuid not null default gen_random_uuid(),
  version integer not null check (version > 0),
  asset_key text not null check (asset_key ~ '^[a-z0-9][a-z0-9._-]{2,120}$'),
  display_name text not null check (char_length(display_name) between 2 and 160),
  category text not null check (category = any (array[
    'universe','galaxy','world','orbit','capsule','district','booth',
    'content-feed','agent-character','live-stage','human-live',
    'sticker-social','animation','navigation-fx'
  ])),
  source_url text not null check (char_length(source_url) between 8 and 2048),
  provenance jsonb not null check (jsonb_typeof(provenance) = 'object'),
  license_evidence jsonb not null check (jsonb_typeof(license_evidence) = 'object'),
  sha256 text not null check (sha256 ~ '^[a-f0-9]{64}$'),
  byte_size bigint not null check (byte_size > 0 and byte_size <= 536870912),
  mime_type text not null default 'model/gltf-binary' check (mime_type = 'model/gltf-binary'),
  storage_bucket text not null check (char_length(storage_bucket) between 1 and 100),
  storage_path text not null check (char_length(storage_path) between 1 and 1024),
  dimensions jsonb not null default '{}'::jsonb check (jsonb_typeof(dimensions) = 'object'),
  material_metadata jsonb not null default '{}'::jsonb check (jsonb_typeof(material_metadata) = 'object'),
  capabilities jsonb not null default '{}'::jsonb check (jsonb_typeof(capabilities) = 'object'),
  compatibility jsonb not null default '{}'::jsonb check (jsonb_typeof(compatibility) = 'object'),
  moderation_status text not null default 'pending' check (moderation_status in ('pending','approved','rejected')),
  status text not null default 'draft' check (status in ('draft','uploaded','quarantined','validating','review','approved','published','deprecated','retired','rejected','failed','blocked','revoked')),
  created_at timestamptz not null default now(),
  published_at timestamptz,
  primary key (asset_id, version),
  unique (asset_key, version),
  check ((status = 'published') = (published_at is not null)),
  check (status <> 'published' or (moderation_status = 'approved' and license_evidence <> '{}'::jsonb))
);

create index if not exists spatial_asset_versions_public_lookup
  on public.spatial_asset_versions (asset_id, version)
  where status = 'published';

create table if not exists public.spatial_scene_versions (
  scene_id uuid not null default gen_random_uuid(),
  version integer not null check (version > 0),
  scene_key text not null check (scene_key ~ '^[a-z0-9][a-z0-9._-]{2,120}$'),
  world_id text not null check (char_length(world_id) between 1 and 128),
  coordinate_system text not null default 'right-handed-y-up' check (coordinate_system = 'right-handed-y-up'),
  units text not null default 'meters' check (units = 'meters'),
  fallback_mode text not null default '2d' check (fallback_mode in ('2d','low_detail')),
  objects jsonb not null check (jsonb_typeof(objects) = 'array' and jsonb_array_length(objects) between 1 and 500),
  status text not null default 'draft' check (status in ('draft','review','approved','published','rejected','deprecated','revoked')),
  created_at timestamptz not null default now(),
  published_at timestamptz,
  primary key (scene_id, version),
  unique (scene_key, version),
  check ((status = 'published') = (published_at is not null))
);

create index if not exists spatial_scene_versions_public_lookup
  on public.spatial_scene_versions (scene_key, version desc)
  where status = 'published';

alter table public.spatial_asset_versions enable row level security;
alter table public.spatial_scene_versions enable row level security;

revoke all on public.spatial_asset_versions from anon, authenticated;
revoke all on public.spatial_scene_versions from anon, authenticated;
grant select, insert, update, delete on public.spatial_asset_versions to service_role;
grant select, insert, update, delete on public.spatial_scene_versions to service_role;

comment on table public.spatial_asset_versions is 'Canonical versioned Allpha spatial asset registry; server-only writes; public access through authorized FastAPI manifests.';
comment on table public.spatial_scene_versions is 'Canonical declarative Allpha scene versions referencing immutable spatial_asset_versions; server-only writes.';

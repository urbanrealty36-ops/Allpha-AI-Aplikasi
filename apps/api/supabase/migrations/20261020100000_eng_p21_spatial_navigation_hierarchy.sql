-- ENG-P21: canonical spatial hierarchy and navigation landmarks.
-- Additive only. No fabricated hierarchy records are inserted.
create table if not exists public.spatial_navigation_nodes (
  id uuid primary key default gen_random_uuid(),
  node_key text not null unique check (node_key ~ '^[a-z0-9][a-z0-9._-]{2,127}$'),
  parent_id uuid references public.spatial_navigation_nodes(id) on delete restrict,
  level text not null check (level in ('universe','galaxy','world','district','zone','booth','poi','scene_object')),
  slug text not null check (slug ~ '^[a-z0-9][a-z0-9._-]{2,127}$'),
  display_name text not null check (char_length(display_name) between 1 and 160),
  coordinates jsonb check (coordinates is null or jsonb_typeof(coordinates)='object'),
  landmarks jsonb not null default '[]'::jsonb check (jsonb_typeof(landmarks)='array' and jsonb_array_length(landmarks)<=250),
  scene_key text check (scene_key is null or scene_key ~ '^[a-z0-9][a-z0-9._-]{2,120}$'),
  access_policy text not null default 'public' check (access_policy in ('public','authenticated','owner_only')),
  status text not null default 'draft' check (status in ('draft','review','approved','published','deprecated','rejected','revoked')),
  version integer not null default 1 check (version > 0),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  published_at timestamptz,
  check ((level='universe') = (parent_id is null)),
  check ((status in ('published','deprecated','revoked')) = (published_at is not null))
);
create index if not exists spatial_navigation_parent_public
  on public.spatial_navigation_nodes(parent_id, created_at, id)
  where status='published' and access_policy='public';
create index if not exists spatial_navigation_scene_key
  on public.spatial_navigation_nodes(scene_key) where scene_key is not null;
alter table public.spatial_navigation_nodes enable row level security;
revoke all on public.spatial_navigation_nodes from anon, authenticated;
grant select, insert, update, delete on public.spatial_navigation_nodes to service_role;
comment on table public.spatial_navigation_nodes is 'Canonical Universe/Galaxy/World/District/Zone/Booth/POI hierarchy; only published public nodes are exposed by FastAPI.';

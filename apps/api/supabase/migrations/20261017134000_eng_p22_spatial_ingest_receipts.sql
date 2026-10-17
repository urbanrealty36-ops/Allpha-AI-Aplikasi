-- ENG-P22: retain private ingest provenance even when category mapping is unresolved.
create table if not exists public.spatial_asset_ingest_receipts (
  receipt_id uuid primary key default gen_random_uuid(),
  asset_key text not null unique check (asset_key ~ '^[a-z0-9][a-z0-9._-]{2,120}$'),
  display_name text not null check (char_length(display_name) between 2 and 160),
  source_url text not null check (char_length(source_url) between 8 and 2048),
  source_repo text not null check (char_length(source_repo) between 1 and 256),
  source_path text not null check (char_length(source_path) between 1 and 1024),
  source_license_claim text not null default 'unknown',
  review_state text not null default 'unreviewed',
  category_candidate text check (category_candidate is null or category_candidate = any (array[
    'universe','galaxy','world','orbit','capsule','district','booth',
    'content-feed','agent-character','live-stage','human-live',
    'sticker-social','animation','navigation-fx'
  ])),
  category_mapping_status text not null check (category_mapping_status in ('mapped','unmapped')),
  sha256 text not null unique check (sha256 ~ '^[a-f0-9]{64}$'),
  byte_size bigint not null check (byte_size > 0 and byte_size <= 536870912),
  storage_bucket text not null check (char_length(storage_bucket) between 1 and 100),
  storage_path text not null check (char_length(storage_path) between 1 and 1024),
  lifecycle_status text not null default 'test_only' check (lifecycle_status in ('test_only','quarantined')),
  created_at timestamptz not null default now(),
  check ((category_mapping_status = 'mapped') = (category_candidate is not null))
);
create index if not exists spatial_asset_ingest_receipts_lifecycle
  on public.spatial_asset_ingest_receipts (lifecycle_status, category_mapping_status);
alter table public.spatial_asset_ingest_receipts enable row level security;
revoke all on public.spatial_asset_ingest_receipts from anon, authenticated;
grant select, insert, update on public.spatial_asset_ingest_receipts to service_role;
comment on table public.spatial_asset_ingest_receipts is 'Private intake/provenance receipts for ENG-P22; not a public asset catalog and never implies publication approval.';

-- ENG-P21 governance evidence and Agent-to-GLB mapping. Additive; no business rows seeded.
create table if not exists public.spatial_agent_asset_mappings (
  id uuid primary key default gen_random_uuid(),
  agent_id uuid not null,
  asset_key text not null,
  asset_version integer not null check (asset_version > 0),
  evidence_type text not null check (evidence_type in ('authoritative_agent_profile','owner_attestation','source_manifest','reviewed_visual_match')),
  evidence_uri text not null check (evidence_uri ~ '^https?://'),
  evidence_sha256 text check (evidence_sha256 is null or evidence_sha256 ~ '^[a-f0-9]{64}$'),
  rationale text not null check (char_length(rationale) between 12 and 1000),
  status text not null default 'pending' check (status in ('pending','approved','rejected','revoked')),
  created_by uuid not null,
  reviewed_by uuid,
  reviewed_at timestamptz,
  created_at timestamptz not null default now(),
  unique(agent_id, asset_key, asset_version),
  check ((status='approved') = (reviewed_by is not null and reviewed_at is not null))
);
create index if not exists spatial_agent_asset_mappings_review on public.spatial_agent_asset_mappings(status, created_at);
alter table public.spatial_agent_asset_mappings enable row level security;
revoke all on public.spatial_agent_asset_mappings from anon, authenticated;
grant select, insert, update, delete on public.spatial_agent_asset_mappings to service_role;
comment on table public.spatial_agent_asset_mappings is 'Evidence-backed Agent to GLB mapping with independent review and audit; not an Agent identity registry.';

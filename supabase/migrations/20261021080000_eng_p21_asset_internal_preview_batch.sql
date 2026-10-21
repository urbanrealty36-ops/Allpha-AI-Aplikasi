-- ENG-P21: distinguish internal developer preview from public catalog publication.
-- Preview activation does not imply license verification or public rights.
ALTER TABLE public.spatial_asset_versions
  ADD COLUMN IF NOT EXISTS internal_preview_enabled boolean NOT NULL DEFAULT false;

COMMENT ON COLUMN public.spatial_asset_versions.internal_preview_enabled IS
  'ENG-P21 internal developer preview eligibility; does not assert license verification or public publication rights.';

CREATE INDEX IF NOT EXISTS spatial_asset_versions_internal_preview_idx
  ON public.spatial_asset_versions (internal_preview_enabled, status, created_at);

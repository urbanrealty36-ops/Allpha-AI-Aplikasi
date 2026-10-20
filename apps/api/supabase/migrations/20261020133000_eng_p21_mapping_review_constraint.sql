-- ENG-P21: reviewed mapping decisions must be auditable for both approval and rejection.
-- Existing CHECK only permitted review metadata when status='approved', which made
-- the legitimate rejected transition fail at the database layer.
begin;
alter table public.spatial_agent_asset_mappings
  drop constraint if exists spatial_agent_asset_mappings_check;
alter table public.spatial_agent_asset_mappings
  add constraint spatial_agent_asset_mappings_review_metadata_check
  check (
    (status in ('approved', 'rejected', 'revoked')) =
    ((reviewed_by is not null) and (reviewed_at is not null))
  );
commit;

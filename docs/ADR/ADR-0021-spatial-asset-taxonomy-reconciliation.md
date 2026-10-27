# ADR-0021: Spatial Asset Taxonomy and Character Mapping Reconciliation

- **Status:** Proposed — Product Owner decision required before schema or production-data changes
- **Date:** 2026-10-27
- **Decision owner:** Product Owner
- **Scope:** Canonical mapping of the Master PRD's 14 spatial asset categories to the existing spatial registry, plus readiness constraints for mapping the 500 + 282 Official Allpha Agent roster to GLB character assets.

## Context

The Master PRD v3.1, §53, defines a proposed canonical taxonomy and explicitly requires it to be locked against the asset schema before implementation:

1. Universe & Galaxy
2. World & Environment
3. District & Landmark
4. Booth & Tenant
5. Live Experience Stage
6. AI Character & Animation
7. Human Avatar & Uniform
8. Portal & Navigation
9. Spatial FX & Visual Effects
10. Interior & Furniture
11. UI Props & Holograms
12. Interactive Objects
13. Collectibles & Rewards
14. Materials, Lighting & Theme FX

The current backend `spatial_governance_api.py` instead declares legacy keys:
`universe`, `galaxy`, `world`, `orbit`, `capsule`, `district`, `booth`, `content-feed`, `agent-character`, `live-stage`, `human-live`, `sticker-social`, `animation`, `navigation-fx`.
The production registry currently contains only a subset of these legacy keys. This is not a one-to-one mapping: several PRD categories have no equivalent legacy key, while keys such as `capsule`, `content-feed`, `sticker-social`, `orbit`, and `navigation-fx` are ambiguous without asset-level inspection.

Current Supabase evidence (2026-10-27):
- `spatial_asset_versions`: 921 records; 920 are `test_only`; 1 is published, approved and license-verified.
- `spatial_asset_ingest_receipts`: 927 records with file hashes, byte sizes and Storage references; 6 remain unmapped/quarantined.
- The 4 retained acquisition artifacts contain 927 unique GLBs (821,688,764 uncompressed bytes). All 927 container headers, declared lengths and JSON chunks validated, and all SHA-256 hashes matched the acquisition manifest. This is file-integrity evidence only, not visual/rig/animation/publication acceptance.
- The 500-entry Skill blueprint catalog and 282 Agency metadata records are represented by 782 `official_agent_bots` roster rows. All 782 remain `draft`; none has a runtime-policy binding, immutable Skill-version binding, character asset key or verified asset flag. `spatial_agent_asset_mappings` has zero rows.
- The acquisition manifest contains 241 GLBs with skins and 8 with animation clips. Most acquired GLBs are not character avatars; a large group consists of city/traffic-light assets. Therefore 927 total GLBs cannot be treated as 927 character assets.

## Decision options

### Option A — Replace legacy category keys in place

Migrate the existing `category` values and constraints to the PRD's 14 labels.

- Benefit: one field appears to represent the canonical taxonomy.
- Risk: breaks current API contracts, existing scene/theme manifests, stored asset references and renderer filters; legacy values cannot always be mapped without inspecting individual assets.
- Rollback: requires a coordinated database and API migration plus compatibility handling for previously published manifests.

### Option B — Add a versioned canonical category mapping layer (recommended)

Keep the existing category key stable for backwards compatibility. Introduce an explicit, versioned mapping from each asset version to one PRD primary category, with optional secondary tags, mapping method/confidence, review status and audit evidence. Public manifests expose the canonical category while retaining the legacy key only where compatibility requires it.

- Benefit: no destructive category rewrite; ambiguous assets can remain unmapped until reviewed; UI and renderers can migrate gradually.
- Cost: requires a schema migration, typed API/manifest changes, backfill, compatibility tests and explicit category governance.
- Rollback: disable the new projection and continue serving legacy category keys; do not delete the mapping evidence.

### Option C — Treat the existing 14 legacy keys as the canonical taxonomy

- Benefit: avoids immediate schema work.
- Risk: contradicts the semantics and names of §53 and leaves Interior & Furniture, UI Props & Holograms, Interactive Objects, Collectibles & Rewards, and Materials/Lighting/Theme FX without explicit category ownership.
- This option should not be selected without an explicit Product Owner amendment to the PRD.

## Proposed decision

Prefer **Option B**. Do not rename or bulk-map assets solely from legacy category strings. Generate asset-level candidate mappings from manifest metadata and actual GLB content, retain confidence/provenance, and require review for ambiguous assets. The final 14-category key names and stable identifiers must be approved before migration or publication.

For Agent-character binding, decide separately whether multiple Official Bots may share a canonical base GLB with distinct configuration/appearance variants, or whether every bot must have a unique character asset. The current roster constraint and available skinned-asset count do not support assuming 782 unique, verified avatar assets exist.

## Non-negotiable lifecycle gates

- Do not promote `test_only`, quarantined, rejected, or unmapped assets to public manifests.
- Do not bypass provenance, licensing/allowed-use evidence, security scanning, moderation, performance and compatibility checks. The PRD §53.2 requires these before publication.
- Do not activate an Official Bot until its canonical Agent identity, immutable Skill version, approved per-Agent runtime policy, registered tools, budget/readiness checks, audit trail and verified published character mapping are present.
- A successful GLB header/hash check does not prove renderer acceptance, rig compatibility, device performance or publication eligibility.
- No production DDL or mass status mutation is authorized by this proposed ADR. Schema migration and any publication batch remain blocked until the category mapping and character-reuse policy are approved and their owning phase acceptance evidence exists.

## Required follow-up

1. Product Owner approves the taxonomy mapping model and character-asset reuse policy.
2. ENG-P21/P22 owners produce a reviewed 927-file manifest with primary category, optional tags, provenance, rig/animation capability and lifecycle state.
3. ENG-P23 verifies candidate avatar assets through the actual Web/Android/iOS renderer using retained real GLB artifacts, without exposing `test_only` assets through the public production manifest.
4. ENG-P05/P06/P34 owners bind Official Bots to approved Skill/policy/tool/runtime contracts.
5. Run the controlled migration, reconciliation and acceptance sequence in the existing fixed phase plan. Do not create a parallel phase.

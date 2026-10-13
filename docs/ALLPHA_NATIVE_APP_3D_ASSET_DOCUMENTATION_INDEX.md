# Allpha Universe — Native Mobile & 3D Asset Documentation

Canonical product target: **native Android and iOS applications**. PWA is not the consumer product target.

## Documents in this delivery
- `ALLPHA_MASTER_PRD.md` — product baseline and domain requirements.
- `ALLPHA_MASTER_PHASE_ROADMAP_LATEST.md` — consolidated phase roadmap and 3D work packages.
- `ALLPHA_DISTRICT_3D_CITY_LAYOUT_UIUX_SPEC.md` — native spatial UX and District scene composition.
- `ALLPHA_25_THEME_GLB_DISTRICT_MAPPING.csv` — 25-theme / district mapping worksheet.
- `ALLPHA_25_THEME_GLB_QA_AND_DISTRICT_MAPPING.json` — asset QA summary.
- `ALLPHA_UNIVERSE_3D_ASSET_AUDIT_MAPPING_v1.0.md` — source audit and mapping.
- `ALLPHA_NATIVE_APP_ROADMAP_PRD_3D_ASSET_PACKAGE.zip` — source document package as supplied for this task.

## Important asset status
The supplied 25-GLB pack has a local QA summary reporting 25 GLB files, valid GLB headers, matching manifest SHA-256, 24 unique hashes, and 361,736 total bytes. This proves local integrity only. It does not prove license clearance, Supabase upload/registration, publication, signed URL access, or runtime rendering.

## Canonical execution constraints
- Inspect the actual repository and live schema before implementation or migrations.
- Use the correct canonical asset registry, lifecycle API, storage bucket, manifest and renderer; do not create duplicates.
- Do not bypass backend authorization, insert directly into `theme_assets`, use mock production data, or claim GREEN without evidence.
- Assets with unclear provenance/license remain quarantined.
- Complete one end-to-end District vertical slice before bulk promotion.

## Connector binding
GitHub target: `urbanrealty36-ops/Allpha-AI-Aplikasi`, branch `main`.
Supabase connector supplied for this task: `AllphaAiAplikasi-db` (project ref `dvdziauyvuhcnqhrrvww`). Its exposed public schema was reported empty; verify project identity before any write. Do not silently substitute a different Supabase project.

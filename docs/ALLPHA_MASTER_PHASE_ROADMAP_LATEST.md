# Allpha Universe — Master Phase Roadmap (Consolidated Baseline)

**Product target:** native Android and iOS applications. PWA is not the consumer app target.
**Repository target:** `urbanrealty36-ops/Allpha-AI-Aplikasi`, branch `main`.
**Status:** planning baseline only; phase completion must be evidenced by source, database, API, CI, E2E and runtime results.

## Execution rules
1. Read documents and inspect the canonical repository and live database before implementation.
2. Preserve canonical architecture. Do not create duplicate database, asset registry, renderer, runtime or phase.
3. Backend API is authoritative for domain writes and privileged reads.
4. No fake production data, client-side secrets, direct registry shortcuts or unsupported GREEN claims.
5. Each phase must deliver an end-to-end vertical slice before dependent phases are considered complete.
6. Reconcile phase numbers against actual phase contracts before creating formal phase IDs.

## Consolidated phase sequence
| Phase / area | Scope | Minimum exit evidence |
|---|---|---|
| 00–16 | Foundation and core platform | Build, migrations, API contracts, auth/security tests |
| 17 / 17.1 | AI Universe / Living Universe 3D | Persistent Universe relationships and validated scene manifest |
| 18 / 18.5–18.8 | Spatial runtime, E2E, activation, UI/3D realization, visual-functional QA | API-to-renderer evidence, logs and screenshots |
| 19 | District | Persisted, discoverable District rendered with permissions |
| 20 | Booth | API-backed Booth linked to District/scene |
| 21 | Theme / World | Versioned Theme, World Template, Scene Schema, asset/renderer contracts |
| 21.5 | 25 Theme 3D asset pipeline | 25 themes × 14 categories = 350 slots; each used asset passes rights, technical, storage, manifest and visual gates |
| 22 / 22I | Live experiences, streaming, AI Character voice/animation contract | Session, permissions, realtime/runtime and QA evidence |
| 23–25 | Marketplace, economy, credits, subscription and billing | Idempotent transactions, entitlements, webhook security and reconciliation |
| 26 | Security, Governance & Trust | RBAC/ABAC, IDOR, audit, policy, moderation and security evidence |
| 27B / 27C | Super Admin operations, governance, transaction explorer and master data | Authorized, auditable operations and verified live data |
| 28 | Cross-domain integration | Contracts and E2E pass; verify exact contract in repo |
| 30 | Full Feature Activation | Feature matrix, API, UX, observability and release gates |
| 31 | E2E / QA / Security | Cross-domain, mobile, accessibility and security evidence |
| 32 | CI/CD | Reproducible build/test/migration/release gates |
| 33 | Runtime readiness | Health, metrics, errors, realtime/spatial/AI runtime behavior |
| 34 | Production readiness | Deployment, secrets, backup/recovery, privacy, operations and rollback |
| 35 | Final production GREEN gate | All required evidence available; CI green alone is insufficient |

Phase ranges and status above are a consolidated summary, not authority to renumber or duplicate canonical phase contracts. Phase 23–25 and 28 must be checked against repository source documents.

## Phase 21.5 — 3D asset work packages
- **WP-A Source registry:** pinned source URL/commit/path, license, attribution, provenance, size, SHA-256, deduplication.
- **WP-B Validation/optimization:** parse, buffers, materials, textures, UV/normals, scale/pivot/bounds, rig/animation, dependencies, LOD and mobile budgets.
- **WP-C Theme mapping:** 25 × 14 matrix; slot states `unmapped`, `candidate`, `review`, `approved`, `published`, `blocked`.
- **WP-D District composition:** one vertical slice with District, landmark, Booth, ad placement, character and navigation path using validated Scene Schema/World DSL.
- **WP-E Lifecycle:** use the verified canonical bucket, asset registry, lifecycle API, manifest and signed URL. Never insert directly into `theme_assets` as a shortcut.
- **WP-F Navigation:** map-to-walk, camera, collision, waypoints, POIs, streaming, LOD, accessibility and fallback.
- **WP-G Native UX:** Universe → Galaxy/World → District Map → District exploration → Landmark/Booth → Agent/Live/Marketplace.
- **WP-H QA:** API → persistence → manifest → signed URL → GLB → renderer → native UI; capture device, performance, license, security and test evidence.

## Native application UX requirements
- Native Android/iOS first; Indonesian primary, English secondary.
- Keep utility screens clear and fast; allow cinematic 3D without hiding controls or essential information.
- Touch-first orbit/pan/zoom, guided walk, POI detail sheet, map/list fallback, reduced-motion and accessibility support.
- Load scenes incrementally and cancel stale loads. On GLB failure or GPU/memory pressure, preserve District map/list and retry.
- Camera/microphone permissions are requested only when a feature needs them, with a denial fallback.

## 3D category keys
`universe`, `galaxy`, `world`, `orbit`, `capsule`, `district`, `booth`, `content-feed`, `agent-character`, `live-stage`, `human-live`, `sticker-social`, `animation`, `navigation-fx`.

## Required publication gates
1. Provenance/license approval.
2. GLB integrity and geometry/material/dependency validation.
3. Duplicate review.
4. Official lifecycle registration and Storage size/hash verification.
5. Authorized manifest and signed URL verification.
6. Renderer load in intended District/World.
7. Native Android/iOS lifecycle, navigation and POI end-to-end tests.
8. Performance, memory, accessibility, permissions and fallback tests.
9. Evidence linked to commit/PR, API responses, CI/E2E logs and device captures.
10. Only then transition lifecycle to approved/published.

## Current execution caveats
- This file is a planning baseline, not evidence that phases are implemented.
- Supabase binding supplied for this task is `AllphaAiAplikasi-db` (ref `dvdziauyvuhcnqhrrvww`); public table listing was empty. Verify project identity/schema before any mutation.
- GLB candidate pack has local integrity evidence only. License/provenance, canonical upload, lifecycle registration, signed URL and renderer publication remain unverified.
- The repository connector's successful documentation-index commit does not imply application code or assets have been uploaded.

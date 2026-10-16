# ADR-0008 — Canonical Cross-Platform Spatial Renderer

- Status: Proposed implementation decision; renderer implementation may proceed behind this contract, but production activation remains gated on manifest API and platform QA.
- Date: 2026-10-16
- Owners: Product Owner / Spatial Engineering

## Context

Master PRD v3.0.0 sections 46–49, 53.1–53.3 and Phase 13/14 require a declarative World/Scene Schema, stable hierarchy IDs, version-pinned asset references, authorized manifests, chunk/lazy loading, cancellation/retry, device profiles, low-detail fallback and performance telemetry. The repository currently has no proven end-to-end asset manifest → renderer path, and Web/Native do not declare GLTF rendering dependencies.

## Decision proposal

1. Use Three.js as the rendering engine and React Three Fiber as the React integration for Web and React Native.
2. Web uses the WebGL canvas renderer. Native uses the React Native renderer backed by Expo GL. Platform-specific adapters are allowed; scene/manifest contracts and lifecycle semantics remain shared.
3. Load GLB only from an asset reference supplied by the canonical FastAPI manifest contract. Renderer code must not construct privileged storage URLs, query Supabase tables directly, infer approval from storage presence, or accept arbitrary executable scene content.
4. Renderer input must be a version-pinned, schema-validated, authorized scene manifest. Public display accepts only approved/published asset versions. Preview mode is explicitly developer-only and cannot be confused with public publication.
5. A failed asset must show a recoverable error state and non-3D fallback; cancellation/unmount must release renderer resources. Do not automatically retry permanent authorization/validation errors.
6. Do not add a second asset registry. apps/api and the canonical Supabase schema remain the source of truth. No schema/table is introduced by this ADR.

## Shared renderer input contract

SceneManifestV1 contains:
- schema_version: 1.0
- scene_id, scene_version, world_id
- coordinate_system and units
- objects[]: entity_id, asset_id, asset_version, category, asset_url (already authorized API-provided URL), sha256, byte_size, position[3], rotation[3], scale[3], publication_status
- optional fallback_mode: 2d or low_detail

The exact fourteen category keys remain the fixed keys in docs/PHASES/ALLPHA_FIXED_PHASE_PLAN.md §5.2. Unknown keys are rejected, not coerced. asset_url must be an authorized, time-bounded URL or same-origin API proxy result from the canonical API; clients must not mint signed URLs.

## Security and performance constraints

- Validate manifest shape and bounds before rendering. Do not execute scene-provided code.
- Reject private/unapproved/revoked assets and unsupported formats.
- Apply per-device limits for total bytes, object count, texture dimensions and concurrent loads. Initial values remain provisional until real device benchmarks; do not represent them as accepted budgets.
- Use bounded concurrency, lazy loads, cancellation, resource disposal, and a readable 2D/low-detail fallback.
- Never include private manifest URLs, user identifiers, or tokens in telemetry.
- Preserve explicit error taxonomy: unauthorized, not found, invalid manifest, unsupported asset, network/timeout, decode/render failure, resource budget exceeded.

## Consequences and open decisions

- Shared rendering semantics reduce drift while Web/Native platform adapters handle lifecycle and controls.
- Expo GL compatibility, Android/iOS GPU/device matrix, browser WebGL support, actual manifest endpoint/schema and performance budgets must be verified before the decision can be marked accepted.
- Until the canonical API/asset lifecycle is present and verified, renderer components are not a public production asset pipeline. No assets are approved or published by this ADR.

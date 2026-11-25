# ADR-P13-001 — Cloudinary as canonical media provider and delivery pipeline

- **Status:** ACCEPTED — explicit Product Owner direction in ALLPHA AI Master Execution Prompt dated 2026-11-26
- **Date:** 2026-11-26
- **Owners:** Product Owner (provider decision); Allpha engineering (implementation, migration and operations)
- **Scope:** ENG-P13 Media Foundation; Web, Native Client, FastAPI, media/transcode/callback/cleanup workers, canonical Supabase media metadata and Cloudinary delivery
- **Related:** Master PRD v3.1.0 (media API, social/content, security, storage/CDN open decision); `AGENTS.md`; `docs/PHASES/ALLPHA_FIXED_PHASE_PLAN.md`; ADR-0024 (production migration/recovery gate); Railway canonical runtime ADR

## 1. Context

The Master PRD requires a backend-authorized media lifecycle with quarantine/validation, processing, derivatives, private delivery, deletion propagation and durable workers. It explicitly leaves object-storage/CDN strategy open and requires an ADR before production implementation. The Product Owner has now directed Cloudinary as the media provider and required direct upload from Web and Native through FastAPI, authenticated delivery and Cloudinary transformations.

The canonical media metadata/lifecycle remains owned by the existing `content_media` registry and FastAPI. This ADR does not create a second media registry, queue, lifecycle engine or source of business truth.

## 2. Options considered

1. **Supabase Storage as binary origin with separate CDN/transform service.** Lowest migration from the current TUS flow, but retains a split derivative pipeline and does not satisfy the requested Cloudinary delivery/transform direction.
2. **Cloudinary as canonical provider for new media and derivatives.** Provides signed direct upload, authenticated assets, image/video/audio transformation and delivery, provider callbacks and server-side deletion. It requires a provider migration, webhook verification, scanner integration, operational configuration and careful legacy handling.
3. **Self-hosted object storage and media transformation.** Greater infrastructure control but requires additional operational ownership, transcoding capacity, CDN/egress design and security maintenance not currently approved.

## 3. Decision

Use **Cloudinary** as the canonical provider for new binary media uploads and generated derivatives. FastAPI remains the authorization, policy and lifecycle authority. Supabase Postgres remains the canonical metadata, ownership, status, idempotency, job and audit store.

### 3.1 Upload and authorization

- Web and Native request a short-lived upload intent from FastAPI under `/v1/media`.
- FastAPI authenticates the caller, derives the owner from the verified session, validates domain/resource/purpose, size, MIME, quota and idempotency, then reserves the canonical `content_media` row before issuing a signed Cloudinary upload intent.
- Uploads use Cloudinary authenticated delivery type. The client receives only the signed upload parameters and upload URL; never the Cloudinary API secret, service-role credential or webhook secret.
- The client reports completion through FastAPI. FastAPI verifies the provider asset through server-side Cloudinary credentials and checks the reserved media identity, resource type, delivery type, byte size and idempotency before advancing lifecycle state.
- Unsupported domain/resource bindings fail closed. Client-supplied owner, tenant, session, publication or moderation claims are not authority.

### 3.2 Callback, scan and derivative delivery

- Cloudinary eager/async transformations generate the configured thumbnail, preview and playback derivatives.
- Callback/webhook authenticity, timestamp/signature, provider identity, batch/asset identity, replay and idempotency are verified before a durable callback job is accepted.
- The original asset is downloaded through an authenticated, short-lived provider URL and scanned by the configured scanner. Its byte count and SHA-256 must match the reserved upload metadata.
- The callback worker persists verified Cloudinary derivative identity/metadata (resource type, authenticated delivery type, format, transformation, version, dimensions, duration and byte size). It does not copy derivative binaries back into Supabase Storage.
- FastAPI creates short-lived signed authenticated Cloudinary delivery URLs for authorized callers. Public manifests must never expose private originals or permanent unrestricted provider URLs.
- A media asset is not marked ready until required original scan, callback verification and derivative contract checks succeed.

### 3.3 Legacy media and deletion

- Existing Supabase/TUS uploads remain a supported ingress path during rollout. Once the approved schema and worker gates are satisfied, the canonical transcode dispatcher scans the original, verifies its hash, uploads it to Cloudinary, and waits for the verified provider callback before readiness promotion.
- New binary media lifecycle jobs route through the same Cloudinary transcode/callback pipeline; subtitle validation remains a separate supported job type.
- Cloudinary deletion is asynchronous, owner/resource-authorized, lease-fenced, idempotent and retryable. Legal holds and active resource references block deletion. Provider deletion is not reported as complete until the provider operation and canonical tombstone are confirmed.
- Supabase legacy originals are not purged merely because a Cloudinary upload was attempted. Cleanup requires verified provider completion, policy/retention clearance and the applicable recovery/deletion evidence.

## 4. Security and operational requirements

- Cloudinary API credentials and webhook secrets are server-side only and stored in Railway secret variables.
- Webhook signatures are verified using the configured secret; callbacks are replay-protected and idempotent.
- All provider requests use bounded timeouts, safe redirects/host validation, byte limits, retry/backoff, lease fencing and structured redacted logs.
- Original uploads remain private/quarantined until scan and processing gates pass.
- Scanner mode, scanner endpoint/version/signature, Cloudinary account identity, callback URL/secret, worker flags, queue/RPC readiness, resource limits and health/readiness checks must be verified before any worker is enabled.
- No direct client-to-Cloudinary operation may decide ownership, publication, moderation, readiness, quota or deletion.
- No provider credential or signed URL may be logged as a durable secret.

## 5. Rollout and migration strategy

1. Keep the existing TUS/Supabase upload path as the default while the Cloudinary database migration, recovery preflight, scanner and worker readiness gates are incomplete.
2. Implement the Cloudinary API/provider/worker/client code behind explicit Web and Native feature flags. Default flags remain disabled.
3. Add the forward-only canonical migration for the existing `content_media` registry and lifecycle RPCs. Preserve historical migration bytes and ledger; do not rewrite an applied migration or bulk-promote source-only SQL.
4. Before production DDL, satisfy ADR-0024 recovery preflight and its per-migration linked dry-run/catalog assertions. This ADR does not waive or bypass ADR-0024.
5. Verify schema/RPC/grants/RLS and provider callback contract, then configure scanner and worker dependencies. Only after these checks pass may the content transcode/callback/cleanup worker flags and Cloudinary client feature flags be enabled.
6. Roll out by a controlled feature flag, observe upload/callback/scan/derivative/delivery/deletion metrics, and preserve TUS ingress as the rollback path until Cloudinary lifecycle is proven.
7. Retire legacy Supabase binary objects only after each asset has a verified Cloudinary replacement and retention/deletion policy permits cleanup.

## 6. Rollback and failure behavior

- Set the Web/Native Cloudinary media flags to false to return new uploads to the existing TUS/Supabase ingress path. Do not delete or rewrite existing media metadata as part of rollback.
- If Cloudinary signing, callback, scanner or delivery is unavailable, fail closed or leave the durable job retryable; never report a fake successful upload or expose an unscanned asset.
- Keep legacy Supabase originals available until a verified provider handoff and retention-safe cleanup. Do not blindly retry an ambiguous provider upload; reconcile the provider asset identity first.
- If Cloudinary delivery is unavailable for already-promoted media, report a media delivery error and use only a separately verified authorized fallback; do not silently make authenticated media public.
- Production schema rollback is governed by ADR-0024 and the migration-specific forward-repair plan. This ADR does not authorize destructive rollback or PITR restore.

## 7. Consequences

- Cloudinary becomes the canonical provider for new binary media and derivatives; Supabase remains canonical for media metadata, lifecycle and authorization.
- Existing TUS/Supabase ingress remains available during migration and rollback; the transcode dispatcher moves eligible legacy originals to Cloudinary after worker activation.
- Media delivery is authenticated and transformation-based rather than derivative-copy-based.
- Production activation remains blocked until the Cloudinary registry/RPC migration, ADR-0024 recovery preflight, scanner, worker configuration and operational capacity are verified.
- Unsupported domain/resource types remain explicitly unavailable until their canonical ownership and reference contracts exist.

## 8. Acceptance evidence

P13 cannot be marked complete until evidence demonstrates:

1. Web and Native upload intent authorization, signed direct Cloudinary upload, completion and retry through FastAPI.
2. Verified callback signature, replay protection, idempotency and provider asset identity.
3. Original byte/hash verification and real scanner result.
4. Cloudinary thumbnail/preview/transcode derivatives and metadata persistence without Supabase derivative binary copies.
5. Authorized short-lived authenticated delivery and denial for unauthorized owners/resources.
6. Safe deletion with legal-hold/in-use protection, lease fencing, retry, provider confirmation and audit.
7. TUS legacy ingress promotion to Cloudinary and recovery from worker interruption.
8. Super Admin visibility/operations for media jobs, failure/retry and policy state where required by the fixed phase plan.
9. Web, Native, API, database, worker, security and real configured-provider evidence. Source tests/builds alone do not qualify as integration or production verification.

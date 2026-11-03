# ADR-WP04-001 — Media Processing, Retention and Scheduled Publication

- **Status:** ACCEPTED — Product Owner approval recorded 2026-11-03
- **Date:** 2026-11-03
- **Decision owners:** Product Owner, Platform Architecture
- **Implementation owner:** Media/Backend Engineering
- **Scope:** ENG-P13 / WP-04 Content & Media Lifecycle
- **Approval evidence:** Product Owner explicitly approved all three recommendations in the Allpha project conversation on 2026-11-03.
- **Implementation state:** Decision accepted; implementation and operational verification remain separate gates.

## Context

The Master PRD v3.1 requires quarantined media upload, server-side validation, media derivatives and moderation inputs, durable publication events, auditable lifecycle commands, scheduled publication, and retention/deletion propagation. Current source has private Storage upload metadata and owner-scoped content lifecycle APIs, but it does not yet provide a complete media-processing worker, approved physical retention executor, or scheduled-publication worker.

## Decisions

### A. Media processing — Hybrid

1. Uploaded originals enter a private quarantine area and remain inaccessible to public surfaces.
2. API validates authenticated ownership, declared MIME, byte signature, size, and supported format before accepting the upload.
3. A durable database-backed job/outbox is the source of truth for asynchronous processing; Realtime is only a notification mechanism.
4. An isolated worker performs safe image inspection/derivative generation and delegates video/audio transcoding to a managed provider selected through a separate provider configuration and security/cost review.
5. Worker transitions are idempotent and owner/content/media scoped. Every attempt records stage, retryability, error code, timestamps, and correlation/idempotency keys.
6. Media is not promoted to ready until all required processing, malware/content scanning, derivative persistence, and moderation-input generation are confirmed. Provider callbacks require authenticated signatures and replay protection.
7. Until a provider is configured and approved, video/audio remain private in uploaded or processing-unavailable state; no fake ready state or public playback is allowed.

### B. Retention — Soft-delete and recoverability

1. Owner-initiated content soft-delete has a 30-day recovery window.
2. Abandoned upload reservations and incomplete upload objects become eligible for review after 7 days.
3. Archived content is retained until explicit owner deletion or another approved lifecycle event.
4. Legal/safety holds suspend physical deletion; held records and evidence remain access-restricted.
5. Physical deletion is a durable, owner-scoped, auditable job. It removes originals, derivatives, thumbnails, indexes/embeddings, caches and references according to the data-class map.
6. Cleanup must support dry-run, bounded batches, idempotent retries, dead-letter/recovery, and a deletion receipt. Backups expire according to the separately approved backup policy; deletion from immutable backups is handled by documented expiry rather than claiming immediate erasure.
7. The 30-day/7-day periods are policy values approved here; they do not authorize enabling a destructive job until restore, legal hold, backup and storage-path behavior are implemented and reviewed.

### C. Scheduled publication — Durable scheduler

1. Scheduling uses a durable database-backed job/outbox contract owned by FastAPI and the Content domain.
2. Persist UTC execution time and the creator's IANA timezone for display/audit. Clients never schedule publication with browser timers.
3. Schedule, edit, cancel and reschedule commands are owner-scoped, version-aware and idempotent.
4. At execution, the worker rechecks ownership/status, moderation approval, media readiness, rights/disclosure, visibility and current publication policy.
5. Failed attempts use bounded retries and a dead-letter/operator-recovery state; missed schedules are not silently published.
6. Publication and outbox event creation must be atomic; delivery/fanout consumers are idempotent.
7. Notification delivery is a downstream integration contract; WP-04 may emit a publication event but does not implement WP-05 social notifications.

## Security and operational requirements

- Supabase Postgres is canonical transactional storage; private Supabase Storage buckets remain the media source of truth.
- RLS denies by default. Admin actions require explicit roles, reason codes and immutable audit.
- No service-role credential is exposed to clients.
- Worker leases, retry counts, job payload minimization, callback authentication, and secret redaction are mandatory.
- No destructive migration, provider provisioning, production credential change, or production data mutation is authorized by this ADR alone.

## Consequences and gates

- ADR decision gate: ACCEPTED.
- Source implementation gate: IN PROGRESS.
- Integration verification: NOT VERIFIED.
- Product acceptance: PENDING.
- Production verification: NOT PERFORMED.
- WP-04 remains active until media processing lifecycle, recoverable retention, durable scheduling, moderation/appeal workflow, client parity, and documented source-level closure criteria are implemented.
- WP-05 remains NOT STARTED until WP-04 is closed by explicit phase-plan update.
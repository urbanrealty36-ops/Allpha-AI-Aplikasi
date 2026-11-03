# ADR-WP04-001 — Media Processing, Retention and Scheduled Publication

- **Status:** PROPOSED — Product Owner / Platform Architecture decision required
- **Date:** 2026-11-03
- **Owners:** Product Owner, Platform Architecture, Media/Backend Engineering
- **Scope:** ENG-P13 / WP-04 Content & Media Lifecycle
- **Decision effect:** No provider, destructive retention policy, or scheduler is activated until this ADR is approved.

## Context

The Master PRD requires safe upload quarantine, media processing/transcoding, resumable lifecycle state, derivative cleanup, content scheduling, and deletion propagation. The current repository supports private Storage uploads and metadata states including `uploading`, `uploaded`, `processing`, `ready`, `failed`, and `deleting`. No configured media processor/transcoder, durable media worker contract, scheduler contract, or approved retention/deletion SLA was found in the inspected repository source.

The PRD explicitly leaves media processing/provider and retention decisions open. The implementation must not claim `ready` without actual processing and must not physically delete user media without an approved retention and recovery policy.

## Decision required

### A. Media processing

Choose one canonical processing architecture:

1. **Managed media processing provider** — less platform operations burden; recurring cost, vendor lock-in, data residency and callback security review required.
2. **Self-managed isolated worker** — full control; requires queue durability, sandboxing, capacity, patching, observability and media parser security.
3. **Hybrid** — supports image safety/metadata processing and delegated video/audio transcode; adds integration and lifecycle coordination.

Required decision fields: provider/worker, supported MIME and codecs, quarantine boundary, malware/content scanning, derivative formats, max duration/dimensions, retry/dead-letter policy, idempotency key, cancellation, callback authentication, data region, cost ceiling, observability and rollback.

Until approved and configured:
- uploaded media remains private and `uploaded`;
- no API or client may promote it to `ready`;
- public playback/preview of media requiring processing remains unavailable;
- media review must not imply a successful scan/transcode.

### B. Retention and deletion

Choose retention by data class and event: abandoned upload reservation, failed/incomplete upload, owner soft-delete, archived content, moderation rejection/removal, legal/safety hold, generated derivatives and caches, and account deletion/export obligations.

Required decision fields: retention duration, grace period, owner restore window, legal hold, audit retention, derivative/cache invalidation, Storage deletion mechanism, batch size/rate limits, retry/dead-letter, recovery/backup, and proof of deletion.

Until approved:
- soft-delete remains metadata-only;
- no destructive orphan sweeper or scheduled object deletion is enabled;
- proposed cleanup must be dry-run capable, owner-scoped, auditable and recoverable.

### C. Scheduled publication

Choose the canonical durable scheduler/worker owner and contract: schedule timestamp and timezone semantics; schedule edit/cancel/reschedule; due-job leasing and idempotency; moderation/rights/visibility revalidation at execution time; missed-run and retry behavior; event/notification delivery; observability and operator recovery.

Until approved and implemented:
- do not add a UI that claims a post is scheduled;
- do not publish based on client timers or browser background execution.

## Consequences

- WP-04 remains `in_progress` until a real processor lifecycle, safe retention workflow, and approved scheduling scope are implemented or explicitly removed from WP-04 by an approved phase-plan/PRD decision.
- This ADR is not approval to provision a vendor, create credentials, or change production resources.
- No processor-specific or schedule-execution schema migration is permitted until the chosen architecture and lifecycle contract are approved.

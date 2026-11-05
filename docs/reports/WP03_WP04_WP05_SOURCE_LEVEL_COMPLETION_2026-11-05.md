# WP-03 / WP-04 / WP-05 Source-Level Completion Checkpoint

**Date:** 2026-11-05  
**Repository:** `urbanrealty36-ops/Allpha-AI-Aplikasi`  
**Branch:** `main`  
**Execution mode:** source-only implementation and static source reconciliation  
**Explicit exclusions:** no staging, no isolated DB provisioning, no PostgreSQL execution, no migration application, no test/build/lint/typecheck/CI execution, no browser/account/device QA, no ClamAV or Cloudinary provider calls, no Expo push dispatch, no Supabase data mutation, and no deployment.

## Outcome

The current work package has been advanced at source level only. This checkpoint does **not** represent runtime integration acceptance. WP-03, WP-04 and WP-05 remain `in_progress` until their own phase gates and the Product Owner-authorized account/device QA gate are satisfied. WP-06 remains locked.

## Changes committed to main

| Commit | Scope | Change |
|---|---|---|
| `859a9404761f61795eafc49223467826aabeac36` | Native billing contract | Currency precision now uses a safe fallback; status announcements use React Native `accessibilityLiveRegion` rather than unsupported `accessibilityRole="status"`. |
| `c67adfa7b63039ca378d9a2f0970deec46e5db68` | Web billing type safety | `Intl.NumberFormat.resolvedOptions().maximumFractionDigits` has a safe fallback before exponentiation. |
| `82eff010e12c756d2ce3f6b7f72409480d50a2be` | WP-04 cron contract | Static contract now inspects the actual `getattr(worker, "batch")` / `process_batch` dispatch contract rather than expecting a direct AST attribute call; daemon `run` is excluded. |
| `f65db18438814662e1a787432669f161da30eeeb` | WP-03 Feed cursor/snapshot contract | Source contract fixture updated for v2 signed cursor scope (snapshot, viewer, mode, author type, expiry) and persisted Feed snapshot behavior. |
| `b05080ab305d93c8ecfc90d9e64997e7b73e6e62` | WP-03 fixture cleanup | Removed a duplicate fake-database branch from the Feed source contract fixture. |
| `45e4b3fe78d864cf44b8c84c9b3f02fab71f6d0c` | WP-04 PostgreSQL migration | Scheduled media readiness now uses null-safe `IS DISTINCT FROM` checks for both media status and scan status. Null scan metadata cannot pass the readiness guard through SQL three-valued logic. |
| `818c33a96315545419f0fce3332dec66fdaf04e4` | WP-04 migration contract | Static source contract aligned with the null-safe SQL predicates. |

## WP-03 — Outbox and Feed snapshots

### Source contract reconciled

- `social_graph_events` remains the durable outbox source.
- `claim_social_graph_events` leases work in bounded batches.
- `apply_social_graph_event_effect` applies effects under the active lease and uses the unique event-effect record for idempotency.
- `fail_social_graph_event` records retry/dead-letter outcomes with bounded attempts.
- Snapshot invalidation migration `20261102015102_wp03_invalidate_both_graph_participants.sql` covers both actor and target viewers and commits the outbox effect in the same database function.
- Feed cursors are signed and bound to snapshot ID, viewer identity (or guest), feed mode, author type and expiry.
- Feed snapshot reads check viewer/mode/author type and reject invalidated or expired snapshots.
- Feed projection re-evaluates current visibility, active profile state, relationship block/mute/follow rules and active Agent ownership before returning items.
- Public media projection remains gated by ready status, clean scan, processing timestamp and non-empty derivatives.

### Status

**Source implementation: present and reconciled.** Worker execution, database RPC behavior, authenticated relationship journeys and real snapshot invalidation are not asserted as passed in this source-only checkpoint.

## WP-04 — ClamAV, Cloudinary, lifecycle worker and scheduled publishing

### Source contract reconciled

- `wp04_vercel_cron.py` is a bounded orchestration layer and resolves each worker's `batch` or `process_batch` entry point. It does not start worker daemon loops from the Cron request.
- Scheduled publishing uses the existing durable schedule worker and database lease RPCs.
- Image processing requires `CLAMAV_HOST`; image bytes are scanned before derivative creation and promotion.
- Video/audio transcode and Cloudinary callback processing require the provider configuration and ClamAV configuration; callback processing verifies asset/batch identity and scans returned derivatives before the completion RPC.
- Provider cleanup uses the existing lifecycle cleanup worker.
- Retention candidate enqueueing is distinct from deletion. Purge remains locked unless purge enablement, backup/PITR, restore drill, legal hold and explicit approval flags are all present.
- Migration `20261105120000_wp04_schedule_media_readiness_guard.sql` now enforces the same null-safe media readiness predicate in both schedule creation and scheduled publication. It also rechecks moderation, rights/disclosure provenance, expected content version and the active schedule lease. Function execution is restricted to `service_role`.

### Status

**Source implementation: present and hardened.** No ClamAV/Cloudinary calls or worker execution occurred. No media was promoted, scheduled content published, or retention object purged. The migration was not applied to any database.

## WP-05 — Cross-ecosystem contract verification

### Source ownership map

| Surface | Canonical responsibility | Source-level state |
|---|---|---|
| FastAPI | Feed, comments, reactions, shares/repost/quote, notifications, moderation and lifecycle APIs | Canonical API routes remain authoritative. |
| Web PWA | Consume authenticated Feed and Notification APIs; render loading/empty/error/retry states | Uses canonical API contract; no new direct client-side business writes introduced in this checkpoint. |
| React Native / Expo | Consume the same canonical Feed/Notification/Billing APIs; incremental notification polling and native accessibility semantics | Existing API ownership preserved; Native billing type/accessibility defects corrected. |
| Super Admin | Operator-scoped moderation and lifecycle decisions | Existing `platform:content.moderate` scope and API-returned lifecycle status retained. |
| PostgreSQL / Supabase | Durable outbox, snapshots, lifecycle jobs, media status, inbox and push receipts | Canonical data authority; no schema/data mutation executed. |
| Notification worker | Sole Expo push sender; in-app inbox remains the canonical API/database producer | Push remains explicitly disabled unless both worker and provider flags are enabled. |

### Status

**Source contracts reconciled; acceptance not passed.** Cross-client authenticated journeys, SSE reconnect/deduplication, Native polling/session switching and Expo delivery receipts are deliberately not tested in this phase because account/device QA requires separate Product Owner approval.

## Migration validation boundary

The PostgreSQL migration source has been inspected for dependency ordering, function replacement signatures, media readiness predicate parity, lease checks, policy rechecks and grants/revokes. This is source-level SQL review only. No local PostgreSQL, isolated branch, staging environment, SQL parser execution, migration replay or production migration was created or run.

## Phase status and next gates

| Work package | Status | Why it is not acceptance-passed |
|---|---|---|
| WP-03 | `in_progress` — source reconciled | Durable worker and snapshot invalidation have not been executed against PostgreSQL or authenticated identities. |
| WP-04 | `in_progress` — source hardened | Scanner/provider configuration and lifecycle workers have not been executed; migration not applied; retention evidence intentionally absent. |
| WP-05 | `in_progress` — source contracts reconciled | Cross-client account/device journeys and runtime delivery have not been authorized or executed. |
| WP-06 | `not_started / locked` | Opens only after WP-05 `acceptance_passed`. |

**Next phase:** finish the remaining source-only WP-05 contract reconciliation and documentation. After source work is complete, request explicit Product Owner approval before any account/device QA. Do not create staging or perform real-world tests without that approval. Do not mark any WP as `integration_verified` or `acceptance_passed` based solely on source inspection.

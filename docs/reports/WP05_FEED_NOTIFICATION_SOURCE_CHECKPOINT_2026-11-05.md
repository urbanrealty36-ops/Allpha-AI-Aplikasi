# WP-05 Feed & Notification — Source Implementation Checkpoint

**Date:** 2026-11-05  
**Repository:** `urbanrealty36-ops/Allpha-AI-Aplikasi`  
**Branch:** `main`  
**Status:** `in_progress` — source changes committed; runtime acceptance remains `DEFERRED / NOT VERIFIED`.

## Product Owner authorization and sequencing

The Product Owner explicitly approved continuing WP-05 against existing canonical contracts while WP-04 remains in progress and ClamAV provisioning remains deferred. The decision is recorded in `docs/ADR/ADR-WP04-003-clamav-deferral.md` and the fixed phase plan. This does not close WP-04, waive WP-03 feed/relationship dependencies, or weaken malware scanning, media readiness, moderation, rights, or publication controls.

## Changes in this checkpoint

- Corrected visibility authorization for a creator viewing/interacting with their own followers-only content. The owner is no longer incorrectly treated as a non-follower for this self-owned resource check; block/mute checks remain enforced.
- Corrected nested reply normalization. A reply-to-reply is attached to the root comment and its notification is addressed to the root comment author, rather than the intermediate reply author. The root comment is re-read and validated as a visible root in the same content thread before the write proceeds.
- Extended the notification push payload allowlist for social Feed events (like, comment, reply, mention, repost, quote). Only a validated content UUID is forwarded as a `feed_content` deep-link target; arbitrary payload fields are not forwarded.
- Native notification taps now open the Feed tab and load the referenced content through the existing owner/visibility-authorized `GET /v1/feed/item/{content_id}` contract.
- Web notification cards now expose a “Buka konten di Feed” link only when the notification payload contains a syntactically valid content UUID. The existing Feed route handles the `?content=` query parameter and performs the canonical content fetch.

## Changed files

- `docs/ADR/ADR-WP04-003-clamav-deferral.md`
- `docs/PHASES/ALLPHA_FIXED_PHASE_PLAN.md`
- `apps/api/src/allpha_api/feed_api.py`
- `apps/api/src/allpha_api/notification_worker.py`
- `apps/client/App.tsx`
- `apps/web/app/notifications/page.tsx`

## Source commits

- ADR sequencing authorization: `5a1ca964fe8cfba436388cfd05f9b6e44a3deb8f`
- Fixed phase-plan authorization record: `9e514367951d698a2dae161adbe630f19e37ee13`
- Feed visibility and nested-reply notification correction: `395e514bc6f16d45fbbade5bf76beb7bdf0e439d`
- Social Feed push payload routing: `f5c80221fc62108fdfca8ebf4ddfadfd2cebc36e`
- Native notification deep-link handling: `ebb1834d42eae99fb24ae3e4a105631f1589eeae`
- Web notification deep-link action: `f6132efba0b46b9b32f7c52a48466fe8e4806632`
- Feed-like push target inclusion and UUID validation cleanup: `4a02732a3c8cbc8ce3ce8e1bb8d7d35fdfb16b38`

## Contract and security boundaries

- Feed and notification data access remains behind the canonical FastAPI routers; Web and Native do not write directly to Supabase business tables.
- Native notification tap deep links resolve the target content through the existing authorized API endpoint, not a client-supplied owner or visibility assertion.
- Push payloads remain minimal and allowlisted. No private comment body, mention identity list, or arbitrary notification payload is copied into the push data.
- WP-04 media readiness remains fail-closed. This checkpoint does not mark unscanned or quarantined media ready or public, and does not change media lifecycle/retention behavior.
- No new notification engine, database table, migration, or duplicate source of truth was introduced.

## Validation boundary

- Source was inspected and updated through GitHub file operations.
- No automated tests, build, lint, typecheck, CI, browser journey, authenticated API mutation, native-device journey, Expo push dispatch/receipt, migration, Supabase data mutation, or deployment was run in this checkpoint.
- Therefore runtime integration and user-journey behavior remain `DEFERRED / NOT VERIFIED`. These source commits do not prove push delivery or phase acceptance.

## Remaining WP-05 gates

1. Reconcile and verify upstream WP-03 visibility/relationship/feed snapshot contracts.
2. Obtain an authorized QA session via secure login and verify Feed writes/read-back with two users.
3. Verify Web SSE event delivery, reconnect, duplicate suppression and account switching.
4. Verify Native incremental polling, retry and account switching on an attached device/emulator.
5. Verify Expo push ticket, receipt, opt-in behavior and visible device delivery.
6. Verify notification preference suppression and failure/recovery behavior against actual configured dependencies.
7. Reconcile WP-04 readiness/scan/media lifecycle dependencies before accepting any media-bearing Feed journey.

**Phase status:** WP-05 remains `in_progress`; WP-04 remains `in_progress`; ENG-P37 remains `not_started`. No phase is marked `integration_verified`, `acceptance_passed`, or `production_verified`.

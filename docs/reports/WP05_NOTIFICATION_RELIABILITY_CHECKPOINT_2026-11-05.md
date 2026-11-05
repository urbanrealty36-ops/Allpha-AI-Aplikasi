# WP-05 Feed & Notification — Reliability Continuation Checkpoint

**Date:** 2026-11-05  
**Repository:** `urbanrealty36-ops/Allpha-AI-Aplikasi`  
**Branch:** `main`  
**Status:** `in_progress` — source reliability improvements committed; authenticated integration and acceptance remain `DEFERRED / NOT VERIFIED`.

## PRD traceability

- **Master PRD:** `ALLPHA-MPRD-003`, consolidated v3.1.0.
- **Canonical owners:** Social Graph / Feed and Content interaction contracts (including Feed visibility and social actions); **Domain 57 — Notification Engine** for inbox, preferences, deduplication, push routing and delivery state.
- **Relevant journey:** publish/view permitted Feed content, perform interactions, notify eligible recipients, receive updates in Web/Native, and open the relevant content from a notification.
- **Operating contract:** all client business reads/writes remain behind the canonical authenticated FastAPI API; server-owned Supabase persistence and the existing notification worker remain authoritative. No parallel engine or client-side business-table access was introduced.

## Repository baseline and source changes

The source changes below were committed directly to `main`:

1. **Native notification polling** — `apps/client/components/NotificationsInbox.tsx`
   - Replaced the fixed interval and shared in-flight ref with an effect-scoped polling lifecycle.
   - Performs an immediate first poll, then schedules the normal five-second cadence.
   - Uses bounded retry backoff (10–30 seconds after failures, reset to five seconds after success).
   - Aborts the active request and clears the timer on unmount/session-token change.
   - Keeps the last confirmed composite cursor on failure; the existing `(created_at, id)` cursor and ID-based deduplication remain intact.
   - Commit: `cf7a3659dc5808d3449c7e0627990c86b82ddfbe`.

2. **Web notification SSE reconnect** — `apps/web/app/notifications/page.tsx`
   - Retains the composite cursor and duplicate suppression.
   - Reconnect delay now grows from three seconds to a bounded 30 seconds after stream/network failures and resets after a successful stream connection.
   - Stops retrying on HTTP 401/403 and surfaces a session-access error rather than repeatedly reconnecting with a rejected credential.
   - Aborts the stream and clears the reconnect timer when the session effect is disposed.
   - Commit: `b7399a10ba83f262e8a140b6a96bbbe1d1515c7e`.

3. **Push preference/category fail-closed behavior** — `apps/api/src/allpha_api/notification_worker.py`
   - Push delivery now suppresses unsupported notification categories with `notification_category_unsupported`.
   - Only the five configured preference categories are eligible for dispatch; category names outside that contract cannot bypass the user's category preference by falling through to a missing JSON key.
   - Existing `push_enabled`, category preference, expiry, Expo ticket, receipt and retry behavior is retained.
   - Commit: `eba3606961684d9b3a0a092c12fb8f0f850c1964`.

## Current integration/acceptance matrix

| Area | Source status | Runtime evidence in this checkpoint | Acceptance |
|---|---|---|---|
| Feed two-user visibility and write/read-back | Existing canonical Feed routes and prior visibility/reply fixes retained | No authorized two-user QA sessions; no real content/comment/share mutations | `NOT VERIFIED` |
| Web SSE | Authenticated stream consumer, composite cursor, dedupe, bounded reconnect and 401/403 stop | No authenticated browser session or live stream journey | `NOT VERIFIED` |
| Native polling | Immediate polling, cursor, dedupe, abort-on-session-change, bounded retry | No attached authenticated Android/iOS device or emulator | `NOT VERIFIED` |
| Expo push ticket/receipt | Existing opt-in worker, preference gate, ticket and receipt polling retained; unsupported categories now fail closed | No registered QA device/token or real ticket/receipt/visible delivery in this checkpoint | `NOT VERIFIED` |
| WP-03 dependency | Relationship/visibility/feed snapshot owner contract remains open in the fixed plan | No new upstream acceptance evidence | `BLOCKED / NOT VERIFIED` |
| WP-04 dependency | Media lifecycle and malware scan/readiness controls remain fail-closed; ClamAV provisioning remains deferred | No new provider/scanner/backup or cross-client lifecycle evidence | `BLOCKED / NOT VERIFIED` |

## Validation and safety boundary

- GitHub source fetch/update operations succeeded for the three changed files.
- **No** unit/contract/integration tests, build, lint, typecheck, CI run, browser journey, authenticated API mutation, Native device journey, Expo push dispatch/receipt, migration, Supabase data mutation, staging or deployment was performed in this checkpoint.
- No QA credentials, access tokens or Expo device tokens were requested or stored in chat.
- No fake user/content/notification records were created.
- No media readiness, malware scanning, moderation, rights or publication gate was bypassed.
- The code improvements are source-level only. They do not prove SSE delivery, two-user authorization, polling behavior on a real device, Expo receipt processing or visible push delivery.

## Required gates before WP-05 acceptance

1. Obtain two authorized QA accounts and run owner/recipient Feed create → read-back, follower-only visibility, block/mute negative paths, comment/reply/mention and repost/quote attribution checks.
2. Exercise Web SSE with a real authenticated session: event arrival, reconnect after network interruption, duplicate suppression, expired/revoked session behavior and account switching.
3. Exercise Native polling on Android and iOS or representative attached emulator/device: first poll, five-second refresh, network retry/backoff, app/session switch, stale response suppression and notification tap deep-link.
4. Register a real opted-in Expo device; dispatch a real test notification; retain Expo ticket and receipt evidence; confirm visible device delivery and DeviceNotRegistered handling.
5. Verify notification preferences suppress both inbox/push behavior as specified, including category changes during queued delivery and recovery after provider/storage failure.
6. Reconcile WP-03 relationship/visibility/feed snapshot acceptance and WP-04 media readiness/scan/moderation/rights/publication gates. Media-dependent Feed journeys remain unavailable until the WP-04 owner lifecycle confirms eligibility.
7. Record reproducible test output and evidence in the fixed phase plan before changing WP-05 to `integration_verified` or `acceptance_passed`.

## Phase status and next work package

- **WP-05:** `in_progress`; source reliability improvements committed; integration acceptance remains `NOT VERIFIED`.
- **WP-03:** remains `in_progress` / upstream dependency open.
- **WP-04:** remains `in_progress` / upstream dependency open; ClamAV deferral remains fail-closed.
- **ENG-P37:** `not_started`; consolidated validation is not being substituted for missing feature implementation.
- **WP-06 — Human + AI Agent Co-authored Social Presence:** is the next work package only after WP-05 actually passes its acceptance criteria and the required upstream dependencies are reconciled. It is **not started** by this checkpoint.

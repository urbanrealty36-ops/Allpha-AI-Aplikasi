# WP-03 / WP-04 Ecosystem Reconciliation — Source Checkpoint

**Date:** 2026-11-05  
**Repository:** `urbanrealty36-ops/Allpha-AI-Aplikasi`  
**Branch:** `main`  
**Supabase:** `AllphaAiAplikasi-db` / `dvdziauyvuhcnqhrrvww` (PostgreSQL 17.6.1)

## Scope

Reconcile WP-03 social graph/feed foundations and WP-04 content/media lifecycle where they affect Feed and Notifications; inspect the Web, Native, API and Super Admin contract boundaries. Product Owner deferred account/device QA. This checkpoint therefore performs source hardening and read-only schema/policy inspection only.

## Confirmed source findings

### WP-03 — Social graph and Feed

- Feed API derives visibility from authenticated viewer identity, account visibility/status, active follow edges, block/mute edges, approved/published content and Agent identity/ownership.
- Guest Feed remains public-only; authenticated Feed uses relationship and viewer-feedback filters.
- Cursor pagination is signed and bound to viewer, mode, author type and snapshot.
- Canonical graph/outbox/snapshot migrations are present in the live migration ledger.
- RLS is enabled for social graph, feed snapshot, impression and feedback tables. Read-only `pg_policies` inspection confirms participant-scoped graph policies and owner/public content policies.
- Remaining evidence gaps: outbox worker runtime effect, live graph-change invalidation, authenticated visibility/relationship behavior, snapshot authorization runtime and Native build/export.

### WP-04 — Media lifecycle

A concrete source-level leak was found: Feed API included `uploaded` media in public projections and signed preview URLs without requiring a clean malware scan. This is unsafe while ClamAV is deferred.

**Repairs committed:**

1. `apps/api/src/allpha_api/feed_api.py` — public Feed, profile-feed and search media projections now require `status=ready` and `scan_status=clean`; scan/processing/derivative metadata is selected for consistent projection.
   - Commit: `4d822a2527b10ca33a9aaed522d8f017853c6253`
2. `apps/api/src/allpha_api/content_api.py` — owner publish and schedule submission require `ready + clean`; moderation approval re-reads attached media immediately before publishing and fails closed if any media is not ready, not clean or lacks a processed timestamp. Denial writes an operator audit event and returns `CONTENT_MEDIA_NOT_READY`.
   - Commit: `34b259015926cc51320f982ac6311d7b18a2b8ed`
3. `apps/super-admin/app/content-moderation/page.tsx` — operator queue displays media state, scan state and processed marker; success copy reflects the API-returned result and distinguishes scheduled publication.
   - Commit: `e0e1bfd3a8e0a48026f27067187e81fb5156f221`

## Cross-application contract map

| Surface | Contract / owner | Result in this checkpoint |
|---|---|---|
| API | FastAPI owns Feed visibility, content/media lifecycle, moderation and notification persistence | Source hardened; runtime not exercised |
| Web | Uses canonical Feed and Notification API contracts | No client-side business writes added; runtime deferred |
| Native | Uses the same Feed and Notification API contracts | No parallel data path added; device QA deferred |
| Super Admin | `platform:content.moderate` operator scope; content review queue and lifecycle routes | Media scan state surfaced; API remains authoritative |
| Supabase | PostgreSQL canonical schema, RLS and versioned migrations | Read-only schema/policy/migration inspection only |

WP-03 Super Admin is `NOT AFFECTED` because the WP-03 scope specifies user-owned social graph/feed behavior and no operator action. WP-04 Super Admin is `CHANGE` through existing moderation/lifecycle surfaces.

## Read-only Supabase evidence

- Migration ledger includes WP-03 graph/outbox/snapshot migrations and WP-04 lifecycle migrations through `20261103450000`.
- Tables including `content_media`, `content_lifecycle_jobs`, `content_provider_callbacks`, `content_lifecycle_events`, `content_retention_receipts`, `notifications`, `notification_devices` and `notification_push_deliveries` exist with RLS enabled.
- The inspected lifecycle and notification tables currently report zero rows. This is not evidence of worker execution, provider delivery or production readiness.
- `pg_policies` read confirms explicit policies on `social_edges`, `content_items` and `content_media`; feed snapshot/impression/feedback/notification tables did not return policy rows in this targeted query and require a separate grants/policy review before any direct client access is considered. API server-side access remains the intended path.

## Outstanding gates

- WP-03: outbox worker/RPC idempotency and effect; feed snapshot/authorization runtime; graph invalidation; authenticated Web/Native journey evidence.
- WP-04: Cloudinary credentials/webhook and worker execution; ClamAV provisioning (deferred, no bypass); backup/PITR restore proof; lifecycle/appeal/retention cross-client acceptance.
- WP-05: authenticated notification persistence, Web SSE, Native polling and Expo ticket/receipt/visible delivery remain unverified.
- Account/device QA remains deferred until explicit Product Owner authorization.

## Validation performed / not performed

**Performed:** source inspection; GitHub source updates; read-only Supabase project, migration ledger, table/RLS metadata and `pg_policies` query.

**Not performed:** unit/contract tests, build, lint, typecheck, CI, browser/account/device journeys, migration application, SQL mutation, Storage mutation, provider call, push dispatch, staging or deployment.

No Phase status was advanced. WP-03 remains `in_progress / implementation_not_verified`; WP-04 remains `in_progress / NOT VERIFIED`; WP-05 remains `in_progress / runtime acceptance NOT VERIFIED`. No `integration_verified`, `acceptance_passed` or `production_verified` claim is made.

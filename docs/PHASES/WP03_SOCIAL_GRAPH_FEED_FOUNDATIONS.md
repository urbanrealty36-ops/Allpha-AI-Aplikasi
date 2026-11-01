# WP-03 — Social Graph and Feed Foundations

**Implementation branch:** `feat/wp-03-social-graph-feed-foundations`  
**Decision:** ADR-0012 — parallel execution exception approved by Product Owner  
**Status:** `IMPLEMENTED — NOT VERIFIED` (no staging or real integration tests by explicit waiver)

## Source-of-truth alignment

- Reuses the canonical `social_edges`, `user_interests`, `feed_preferences`, `content_items`, and existing interaction tables.
- Reuses FastAPI as the business boundary and the existing Supabase Auth/JWT context.
- Reuses the existing Feed API and refreshed `FeedView`, `ExploreView`, Profile and Account surfaces.
- Does not create a second social graph, feed ranking engine, identity registry, database, or client-side privileged write path.

## Existing foundations retained

- Follow/unfollow, private-profile follow requests, accept/reject, block and mute.
- User-owned interest preferences (`interested` / `not_interested`).
- Feed modes: `for_you`, `recent`, and `following`.
- Published/approved content filtering, account visibility, profile visibility, block/mute exclusions, explicit interest matching, observed engagement and creator diversity.
- Cursor pagination with an `as_of` boundary.
- Search/discovery and creator recommendations with account discoverability preference checks.
- Authenticated Web and Native Feed/Discovery surfaces already calling the canonical API.

## WP-03 changes in this branch

1. **Private graph event outbox migration** — `apps/api/supabase/migrations/20261101184803_wp03_social_graph_event_outbox.sql`.
   - Adds `social_graph_events` as an additive transactional outbox.
   - Captures follow request/creation/acceptance/removal, block/mute creation/removal, and interest preference create/update/remove.
   - Trigger execution uses a fixed empty search path and a restricted security-definer function.
   - RLS is enabled; public, anon and authenticated receive no table privileges; service_role receives read/update access for a future canonical consumer.
   - Interest event payloads are explicitly marked `owner_private`; no public Realtime subscription is created.
   - Actor/target references use `ON DELETE SET NULL` so account deletion anonymizes retained outbox rows.
   - This establishes a durable event contract. A downstream asynchronous recommendation/discovery consumer is not claimed as active in this WP.

2. **Owner-scoped follower visibility** — the migration adds a SELECT policy allowing an authenticated user to inspect only active follow edges whose target is that user. It does not make relationship edges globally public.

3. **Social Graph API** — `GET /v1/me/social-graph` now returns `incoming_followers`, a summary of following/followers/pending requests/blocks/mutes/interests, a truncation indicator, and contract version 2. All reads use the caller's JWT through `user_db_request`.

4. **Web Account / Social Graph UI** — `apps/web/app/account/page.tsx` adds username discovery through the existing `/v1/social/discover-users` contract, follow/block/mute actions from discovered accounts, the caller's own follower list, and relationship summary. Existing follow request, outgoing relation and interest controls remain.

5. **Native Account / Social Graph UI** — `apps/client/App.tsx` displays the caller's own follower list and relationship summary using the same API response. Existing native username discovery, follow/block/mute, pending request and interest controls remain.

6. **Feed/Explore integration** — the refreshed Web Feed and Explore components already consume the canonical Feed and Social Graph APIs. This branch keeps their current source-based layouts and API contracts; it does not fork or replace those components.

## Verification and production application

- No staging environment created.
- No real-user, production-data, authenticated browser, live JWT/RLS, Realtime, physical-device, or other real integration test executed, as explicitly waived.
- No test result is claimed for this branch.
- The additive migration was applied successfully to production. Supabase migration ledger records version `20261101184803`, name `wp03_social_graph_event_outbox`. The SQL filename is aligned to that applied ledger version.
- The code was merged to `main` in commit `3f45de82d07f98feb1d2b0ed1f5f20a51732c021`. The first Vercel production deployment for this SHA was observed as `QUEUED`; Railway service statuses were `pending` at the time of inspection. Deployment completion is not yet claimed.
- Before marking `integration_verified`, `acceptance_passed`, or `production_verified`, obtain a later authorized verification window for migration state, actual JWT/RLS behavior, Realtime isolation if/when subscribed, Web/Native runtime, and rollback readiness.

## Acceptance register

| Criterion | Source status |
|---|---|
| Canonical follow/unfollow and private follow requests | Existing implementation reused |
| Block/mute policy and feed exclusion | Existing implementation reused |
| Owner-scoped incoming follower visibility | Implemented in migration source |
| Interest preference management | Existing API and Web/Native UI reused |
| Feed For You / Recent / Following | Existing API and Web/Native UI reused |
| Privacy-aware discovery | Existing API and Web/Native UI reused |
| Durable graph-change event contract | Implemented in migration source; consumer not yet active |
| Web Account social UI | Implemented in branch |
| Native Account social UI | Implemented in branch |
| Production migration application | Applied; ledger version `20261101184803` |
| Runtime/API/RLS/Realtime integration | Not verified by waiver |
| Production deployment | Queued/pending at last inspection; not verified ready |

## Next phase

WP-03 is the active implementation workstream under ADR-0012. The next phase must be taken from the current fixed phase plan only after WP-03's required evidence/waiver disposition is recorded. Do not infer phase completion from this document or branch commits alone.

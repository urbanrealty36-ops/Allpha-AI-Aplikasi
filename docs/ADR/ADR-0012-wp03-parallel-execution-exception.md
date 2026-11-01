# ADR-0012 — Parallel execution exception for WP-03 Social Graph and Feed Foundations

- **Status:** Accepted by Product Owner
- **Date:** 2026-11-02
- **Decision owner:** Product Owner, Allpha Universe
- **Scope:** WP-03 only; this ADR does not waive any other phase dependency or security invariant.

## Context

The fixed phase plan records WP-02 as `IN_PROGRESS` and WP-03 as `BLOCKED`. The Product Owner states that WP-02 testing has been completed and explicitly authorizes WP-03 to proceed in parallel with any remaining WP-02 administrative/acceptance evidence. The Product Owner also explicitly waives staging and real-user/production test execution for this WP-03 implementation window.

The repository's prior WP-02 evidence records successful API/Web/Native source-level checks on tested snapshots, but also records that authenticated browser journeys, complete current-head visual acceptance, and real two-principal JWT/RLS/Realtime verification were not established in the captured evidence. This ADR preserves that distinction rather than rewriting historical test outcomes.

## Decision

1. Begin WP-03 implementation on a dedicated branch while WP-02's recorded acceptance status is reconciled separately.
2. Reuse the existing canonical `social_edges`, `user_interests`, `feed_preferences`, `content_items`, and feed interaction tables. Do not create a second social graph, feed engine, identity registry, or database.
3. Reuse the existing FastAPI business boundary, authenticated Supabase context, feed API, and reference UI components. Clients must not gain privileged direct database writes.
4. No staging environment will be created.
5. No real-user, production-data, or live JWT/RLS/Realtime test will be executed under this waiver. Static/source review and non-live code checks are also deferred unless separately authorized.
6. The implementation status may be reported as `IMPLEMENTED, NOT VERIFIED`; it must not be reported as integration-verified, acceptance-passed, or production-verified solely because files or migrations are committed.
7. No production database migration or deployment is authorized by this ADR alone. Any production DDL/deployment requires a separate change record, migration review, and explicit execution authorization.

## WP-03 implementation scope

- Canonical follow/unfollow and private-profile follow-request lifecycle.
- Block/mute behavior and reciprocal-block enforcement.
- Relationship summaries and privacy-aware relationship reads.
- User-controlled interest preferences and feed personalization controls.
- Feed modes: For You, Recent, Following; stable pagination, visibility filtering, block/mute exclusion, creator diversity, and honest ranking signals.
- Graph change event contract/outbox for downstream discovery/recommendation consumers, without creating a second recommendation engine.
- Integration with the refreshed Feed, Explore/Search, Profile and account/privacy UI surfaces.
- API contract consistency, stable errors, idempotency, and audit/observability where the existing platform provides the canonical mechanism.

## Security and privacy constraints

- Actor identity comes from the authenticated server context, never from a client-supplied owner field.
- Private profile fields and private relationship edges must not be exposed through discovery, feed, or relationship summaries.
- Block is reciprocal for interaction eligibility and must remove conflicting follow edges according to the existing canonical policy.
- Mute suppresses the target from the muting actor's feed without notifying the muted account.
- Interest preferences are private to their owner and may only be used for that owner's personalization.
- Model output, client state, and Realtime delivery do not grant authorization.
- Existing RLS, grants, and service-role isolation remain authoritative; no broad privilege grants are introduced.

## Consequences and limitations

- WP-03 can be implemented independently on the approved branch.
- The absence of staging and real integration tests means data isolation, migration application, realtime delivery, UI behavior, and production runtime remain unverified until a later authorized verification window.
- WP-02's previous test results remain tied to their exact tested source snapshots. This ADR does not retroactively certify the latest main commit.
- WP-03 remains blocked from a `DONE-VERIFIED` or `PRODUCTION` label until the waived evidence is later supplied or the Product Owner explicitly accepts a documented risk disposition.

## Rollback

- Revert the WP-03 code/migration commits on the feature branch before merge.
- Do not drop existing social graph/feed tables or remove production data as part of rollback.
- Any applied additive migration requires a forward-repair or reviewed rollback migration; never manually delete production rows to restore a previous state.

# ADR-WP04-003 — Defer ClamAV Provisioning Without Weakening Media Readiness

- **Status:** ACCEPTED — Product Owner direction recorded 2026-11-04
- **Date:** 2026-11-04
- **Decision owners:** Product Owner, Platform Architecture
- **Scope:** WP-04 Content & Media Lifecycle
- **Implementation owner:** Media/Backend Engineering

## Context

WP-04 source now contains image, video/audio, provider-callback and provider-cleanup workers that use ClamAV before derivatives can be persisted and media can transition to `ready`. The Product Owner directed that ClamAV provisioning be skipped for the current implementation window, while prioritizing coherent code, endpoint, API and database contracts. The Product Owner also deferred real integration tests and staging.

The existing ADR-WP04-001 requires malware/content scanning before media is promoted to `ready`. This decision must not silently weaken that security invariant.

## Decision

1. Defer provisioning and activation of the external ClamAV service. Do not add a fake scanner, no-op scanner, hard-coded clean result, or fabricated scan receipt.
2. Keep scanner integration behind the existing server-side worker configuration. Do not expose scanner configuration or credentials to Web, Native or Super Admin clients.
3. When ClamAV is unavailable, worker jobs must remain retryable/deferred or fail closed with a stable operational error. Media must remain private and must not transition to `ready`, become publicly playable, or become eligible for publication solely because scanning was skipped.
4. Continue source implementation and static contract reconciliation for the rest of WP-04: FastAPI contracts, durable Postgres jobs/RPCs, Cloudinary callbacks, private Supabase Storage derivatives, retention/restore, scheduling, moderation/appeals and operator recovery.
5. Do not apply WP-04 migrations to canonical production as part of this deferral. The migration set must first be reconciled against the live schema and then applied through the approved migration process with a recovery plan.
6. Real provider integration, staging, authenticated cross-client journeys, migration execution verification, scanner operation and production verification remain **DEFERRED / NOT VERIFIED** and are assigned to the consolidated validation gate defined by AGENTS.md §13.
7. **WP-05 may proceed in parallel against the existing, available Feed and Notification contracts**, following the Product Owner's explicit authorization recorded on 2026-11-05. This is a narrow sequencing exception only: it does not declare WP-04 implemented, closed, integration-verified, or accepted; it does not waive WP-03 feed/relationship visibility dependencies; and it does not authorize Feed to expose media that has not passed WP-04 readiness, malware scanning, moderation, rights, and publication gates. WP-05 must treat unavailable or non-ready media as unavailable and must not create a parallel media lifecycle. Any WP-05 behavior whose correctness depends on an unclosed WP-03/WP-04 contract remains blocked or explicitly NOT VERIFIED.

## Product Owner sequencing authorization (2026-11-05)

The Product Owner explicitly approved continuing WP-05 while WP-04 remains in progress and its ClamAV provisioning is deferred. The approval is limited to source implementation and integration against already-available canonical contracts. It does not authorize staging, broad test suites, real-user/device journeys, migration application, deployment, scanner bypass, or changes to media readiness/publication rules. Deferred validation must remain `DEFERRED / NOT VERIFIED` and WP-05 cannot be marked accepted until its own acceptance criteria and upstream dependencies are evidenced.

## Consequences

- Source contracts may be completed and reviewed without provisioning ClamAV.
- Image/video/audio processing cannot be described as fully operational while the required scan dependency is absent.
- Upload reservation and private quarantine may function independently, but unscanned media remains non-public and cannot be published.
- No claim of `integration_verified`, `acceptance_passed`, or `production_verified` is supported by this decision.
- Revisit this ADR when an approved scanner endpoint or an approved equivalent scanning control is available.

## Acceptance / evidence

- Decision recorded from the Product Owner's explicit instruction on 2026-11-04.
- Existing worker and readiness code remains fail-closed; no no-op scan bypass is introduced.
- Migration application, worker runtime, Cloudinary callback, Storage persistence, scheduling, retention executor, cross-client integration and all runtime tests remain NOT VERIFIED.

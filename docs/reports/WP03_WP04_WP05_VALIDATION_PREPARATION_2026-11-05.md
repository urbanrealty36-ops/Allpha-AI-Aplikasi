# WP-03 / WP-04 / WP-05 — Validation Preparation Checkpoint

**Date:** 2026-11-05  
**Repository:** `urbanrealty36-ops/Allpha-AI-Aplikasi`  
**Branch:** `main`  
**Canonical database:** `AllphaAiAplikasi-db` / `dvdziauyvuhcnqhrrvww`  
**Status:** `in_progress` — source contracts extended; isolated migration/runtime verification not yet executed.

## 1. Operating contract and baseline

Read the current repository `AGENTS.md`, canonical Master PRD v3.1 and the single operational fixed phase plan before continuing. Work remains within the existing WP-03, WP-04, WP-05 scope; no phase namespace, backend, worker authority or business-data source was added. Changes were committed directly to `main` as required by the project operating instructions.

## 2. Changes in this checkpoint

| Commit | Change |
|---|---|
| `f8e499bc69fbbe3df060ee7fca13c5fcf468967b` | Added WP-03 outbox lease/effect and both-participant Feed snapshot source-contract tests |
| `751f89aafe6b30446b78a28915914a7d101096b8` | Added WP-04 scheduled-publish readiness and bounded lifecycle orchestration source-contract tests |
| `61488522761daa8800f0e7d802fa3b1dd44af6f6` | Updated the single Fixed Phase Plan with live DB reconciliation and validation gates |

### WP-03

The new tests cover the worker RPC chain (`claim_social_graph_events`, `apply_social_graph_event_effect`, `fail_social_graph_event`), lease-token forwarding, bounded claim parameters, idempotent effect insertion and invalidation of active Feed snapshots for both actor and target. Read-only inspection of the canonical PostgreSQL function confirms the live function currently checks processing state, active lease token and lease expiry; inserts the idempotent event effect; invalidates both participants' active snapshots; and marks the event processed.

### WP-04

The new tests assert that the committed migration enforces equivalent readiness checks in both schedule creation and scheduled publication: media status ready, scan clean, processing timestamp present and non-empty derivatives, together with moderation, rights/disclosure, content-version and lease controls. They also assert the worker orchestrator connects the existing scheduler, media, transcode, callback, cleanup and retention workers with bounded batches and retention safety gates.

## 3. Canonical Supabase read-only reconciliation

The connected project was confirmed as active PostgreSQL 17.6.1. Its migration ledger currently ends with WP-05 migration `20261105061933_wp05_comment_threads_repost_quote_metadata` among the reported latest entries. It does not include `20261105120000_wp04_schedule_media_readiness_guard`.

Read-only `pg_get_functiondef` inspection confirms the existing WP-03 outbox functions and WP-04 scheduling functions exist. The live schedule/publish functions still use the earlier, weaker media check and do not yet enforce the full `ready + scan_status=clean + processed_at + non-empty derivatives` predicate. This is the specific database drift the committed additive migration is intended to resolve.

No DDL, data writes, migration application, production worker invocation, media transition, provider callback, Expo dispatch or deployment was performed.

## 4. Isolated test environment gate

Supabase reports no existing development branches for this project. Creating a development branch may incur recurring charges and requires the Product Owner to review the quoted cost and confirm the organization. No paid branch/resource was created without that explicit cost approval. The current tool environment also has no local PostgreSQL server/client or repository checkout, so the new pytest tests could not be executed here.

## 5. Four-application integration map

| Surface | WP-03/WP-04/WP-05 treatment | Reason |
|---|---|---|
| API / PostgreSQL | CHANGE | Owns canonical outbox, snapshot invalidation, lifecycle jobs, schedule/publish functions and notification contracts |
| Web | INTEGRATE | Consumes authenticated Feed and Notification API contracts; no duplicated business lifecycle |
| Native Android/iOS | INTEGRATE | Consumes the same API contracts; native notification registration/polling/deep-link path remains tied to ENG-P20 Expo worker |
| Super Admin | INTEGRATE | Uses privileged API scopes for moderation, lifecycle inspection and operator recovery; does not own worker state |

WP-03 Super Admin social-graph mutation is NOT AFFECTED: the event outbox and invalidation are system-owned and this work does not introduce an operator mutation surface.

## 6. Validation ledger

| Check | Result |
|---|---|
| Repository and canonical binding | Verified by connector read |
| AGENTS.md / Master PRD / Fixed Phase Plan | Read before changes |
| Supabase project identity and PostgreSQL version | Verified read-only |
| Existing WP-03/WP-04 PostgreSQL function definitions | Inspected read-only |
| Migration ledger and unapplied WP-04 migration | Verified read-only; migration absent from ledger |
| WP-03/WP-04 source-contract tests | Added; NOT RUN |
| PostgreSQL migration fresh-install/upgrade | NOT RUN — isolated branch/test DB unavailable |
| Outbox worker execution and snapshot invalidation journey | NOT VERIFIED |
| ClamAV scanning | NOT VERIFIED; must fail closed if scanner unavailable |
| Cloudinary transcode/callback/cleanup | NOT VERIFIED |
| Scheduled publishing end-to-end | NOT VERIFIED |
| Web/Native/Super Admin runtime contracts | NOT VERIFIED in browser/device/runtime |
| Expo push dispatch and receipts | NOT VERIFIED; no real push sent |
| Account/device QA | DEFERRED pending explicit Product Owner authorization |
| Production migration/deployment | NOT PERFORMED |

## 7. Current phase status and next gates

- **WP-03:** `in_progress`. Source contract and live function definition reconciled; worker effect journey still needs isolated integration evidence.
- **WP-04:** `in_progress`. Readiness migration committed but unapplied; SQL migration test, Cloudinary/ClamAV worker and scheduled-publish evidence remain open.
- **WP-05:** `in_progress`. Source contracts remain aligned in principle; real delivery and account/device acceptance remain deferred/not verified.
- **WP-06 — Human + AI Agent Co-authored Social Presence:** NOT STARTED. It remains gated on WP-05 `acceptance_passed`.

**Next execution order:** (1) provision/authorize an isolated PostgreSQL test target and run fresh-install plus upgrade migration checks; (2) validate WP-03 outbox retry/idempotency and snapshot invalidation; (3) validate WP-04 lifecycle workers and scheduled publishing with real configured scanner/provider dependencies; (4) execute Web/Native/API/Super Admin/Expo contract tests; (5) request explicit approval to reopen account/device QA; (6) proceed to WP-06 only after WP-05 acceptance evidence is complete.


## 8. CI/deployment status observed after latest main commit

Latest inspected commit: `daabfa5ea1f9736ab8a5d9e4e1de3b24f8c3c43f`. GitHub combined status currently reports:

- Railway checks for Allpha Super Admin and Allpha Web: `success`.
- Railway checks for Allpha Notification Delivery, Allpha Stories Cleanup and Allpha API service: `pending` at inspection time.
- Vercel checks for `admin-allpha`, `allpha-universe` and `api-allpha`: `failure`, with target URLs indicating a Vercel build-rate-limit/upgrade gate.

These are CI/deployment status contexts, not proof that WP-03/WP-04/WP-05 journeys or migrations are accepted. No manual deploy, retry, promotion or provider activation was requested or performed. Re-check pending Railway statuses and resolve the Vercel rate-limit gate before using deployment evidence.

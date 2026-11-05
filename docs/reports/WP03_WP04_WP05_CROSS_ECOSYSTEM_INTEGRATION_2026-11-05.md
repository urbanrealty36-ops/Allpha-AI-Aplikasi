# WP-03 / WP-04 / WP-05 — Cross-Ecosystem Source Integration Checkpoint

**Date:** 2026-11-05  
**Repository:** `urbanrealty36-ops/Allpha-AI-Aplikasi`  
**Branch:** `main`  
**Supabase:** `AllphaAiAplikasi-db` / `dvdziauyvuhcnqhrrvww`  
**Specification:** Master PRD v3.1, `AGENTS.md`, `docs/PHASES/ALLPHA_FIXED_PHASE_PLAN.md`

## Executive result

Source-level integration has been extended across canonical Feed, social graph outbox, content/media lifecycle, scheduled publishing, Web/Native notification clients, Expo delivery worker and Super Admin moderation. The implementation preserves one FastAPI business boundary and one Supabase source of truth. No phase acceptance is claimed because migration application, runtime worker/provider evidence and account/device journeys were not executed.

## WP-03 — Social graph outbox and Feed snapshot invalidation

- Existing outbox migration defines private `social_graph_events`, lease-based claim, idempotent effect ledger, retry/backoff and dead-letter state.
- `social_graph_outbox_worker.py` consumes `claim_social_graph_events`, applies effects under lease token and records failures with bounded retries.
- The latest canonical migration `20261102015102_wp03_invalidate_both_graph_participants.sql` invalidates active Feed snapshots for both actor and target, correcting the earlier actor-only behavior.
- Feed API binds snapshots to viewer, mode and author type; rejects invalidated/expired snapshots and checks live visibility before projecting content. Guest Feed remains public-only.
- Worker command is registered in `apps/api/pyproject.toml`; graph mutation path also performs a bounded inline drain and platform cron fallback exists.
- **Not verified:** real outbox trigger-to-worker effect, retry/dead-letter runtime, graph changes under real authenticated sessions, and Native visibility journey.

## WP-04 — Lifecycle workers and scheduled publishing

### Readiness consistency repair

- API publish and schedule submission now require every attached media row to be `status=ready`, `scan_status=clean`, have `processed_at`, and contain a non-empty derivative array.
- Feed public/profile/search projections and Super Admin approval independently enforce the same completed derivative readiness predicate before signing previews or approving publication. Commits: `fe7fc0252a3d7a36b9e87db8f34eddd91021e56d`, `c2652451b7f5f6d362e5cf118848faab43230f73`.
- New migration `20261105120000_wp04_schedule_media_readiness_guard.sql` replaces the canonical `create_content_schedule` and `publish_scheduled_content` functions so the database boundary enforces the same readiness predicate atomically, in addition to moderation approval, rights/disclosure attestations, version and schedule lease checks.
- Migration commits: `cfa6ff7e818a63696351dcaebded4d3f6e099a42`, follow-up defensive JSON-array handling `c513ecf8ec07fd0a38b7d497d28e5061d4b539b7`.
- **Important:** migration is committed to GitHub but was not applied to the live Supabase project.

### Worker orchestration

`wp04_vercel_cron.py` now dispatches one bounded job per configured worker:
- scheduled publisher;
- image processing with real ClamAV;
- Cloudinary transcode;
- authenticated provider callback processing;
- Cloudinary provider cleanup;
- retention purge only when all safety flags are true.

The batch adapter supports both `batch()` and `process_batch()`, so the image worker is invoked through its actual public method. Scanner-dependent workers are skipped/deferred unless the required real ClamAV and provider environment is configured. No fake clean status is produced. Retention remains locked without backup/PITR restore/legal-hold/approval gates.

Commits: `c4293a4da742e13463f5717b335576052a40577b`, `1cdac1bfa95db79b90abe7daa490f82a549b6ee2`.

### Remaining WP-04 gates

- Cloudinary provider credentials/webhook and real callback evidence.
- ClamAV host/service configuration and successful scanner execution.
- Backup/PITR restore drill evidence and legal-hold acceptance before purge.
- Real scheduled publication and media lifecycle integration evidence.
- The current platform Cron remains a bounded fallback; durable worker process deployment/configuration is not verified here.

## WP-05 — Web, Native, API and Expo notification contracts

- Feed event producers persist idempotent social notifications to canonical `notifications`.
- Notification API owns authenticated inbox, unread count, incremental `/updates`, SSE `/stream`, preferences, device registration/unregistration and read-state mutations.
- Web consumes authenticated SSE and REST preference/read endpoints; Native consumes incremental REST polling, registers Expo device tokens through the API and routes `feed_content` notification taps back to Feed.
- ENG-P20 remains the sole Expo push sender and receipt processor. It handles ticket errors, receipt polling, bounded retry and DeviceNotRegistered suppression; unsupported categories fail closed.
- `notification_worker.py` now supports a graceful daemon mode (default) with bounded poll interval and `once` mode for one-shot runs. Dispatch requires explicit `ALLPHA_NOTIFICATION_WORKER_ENABLED=true`, `ALLPHA_NOTIFICATION_PUSH_ENABLED=true` and `ALLPHA_NOTIFICATION_PUSH_PROVIDER=expo`. Otherwise it exits without dispatch.
- Commit: `2dbf5b907552fa20eeb56d10551926e3300b9859`.
- Existing Web SSE bounded reconnect and Native incremental polling retry/backoff changes remain in place from the earlier checkpoint.
- **Not verified:** real worker service deployment, Expo ticket/receipt and visible delivery, session switching, real two-account Feed notifications, and Android/iOS physical-device behavior. Account/device QA remains deferred by Product Owner.

## Super Admin

- WP-04 moderation queue shows media status, scan status and processing marker.
- Approval is authorized through `platform:content.moderate`, rechecks lifecycle state in API and audits denied approval.
- WP-03 Super Admin is `NOT AFFECTED`: the current scope is user-owned social graph/feed behavior and does not specify an operator graph-management action.

## Validation and safety boundary

**Performed:** source review of Master PRD/AGENTS/phase plan; GitHub source edits; read-only Supabase migration/schema/RLS inspection in the prior checkpoint; source reconciliation of worker entry points and RPC names.

**Not performed:** unit/contract tests, SQL execution, migration application, build, lint, typecheck, CI, browser test, account creation, two-user Feed QA, Android/iOS device QA, ClamAV scan, Cloudinary request/callback, Expo push dispatch, retention deletion, staging or deployment.

No real accounts or synthetic social/notification rows were created. No secrets were requested or added to clients.

## Completion status

| Work package | Status | Reason |
|---|---|---|
| WP-03 | `in_progress` | Source wiring and both-participant invalidation exist; runtime/visibility acceptance not verified |
| WP-04 | `in_progress` | Readiness and worker orchestration source hardened; migration not applied and provider/scanner/backup gates open |
| WP-05 | `in_progress` | API/Web/Native/Expo source contracts integrated; worker deployment and real delivery/account/device QA deferred |
| WP-06 | `not_started` | Must wait for WP-05 acceptance |

## Next steps

1. Apply and validate the additive WP-04 migration only through the approved migration/recovery procedure.
2. Run isolated migration, SQL function, outbox idempotency, Feed snapshot invalidation, lifecycle and schedule contract tests.
3. Confirm actual worker deployment/configuration (without sending real notifications during source QA).
4. Obtain explicit Product Owner authorization to reopen account/device acceptance; then test two-user Feed visibility and real Expo delivery.
5. Open WP-06 only after WP-05 reaches `acceptance_passed` with retained evidence.

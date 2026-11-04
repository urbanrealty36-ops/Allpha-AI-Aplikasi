# ADR-WP04-004 — Vercel-native bounded lifecycle execution

- Status: ACCEPTED — Product Owner direction recorded 2026-11-04
- Scope: WP-04 / ENG-P13 Content & Media Lifecycle
- Runtime: existing Vercel project api-allpha, project root apps/api
- Database: existing canonical Supabase project dvdziauyvuhcnqhrrvww; no new database or queue

## Context
WP-04 source workers previously used long-running polling loops. Vercel Functions are request-scoped; persistent daemon loops must not run inside them. The linked Vercel team is on Hobby and supports at most one Cron execution per day.

## Decision
1. One Vercel Cron at 17 3 * * * calls authenticated FastAPI endpoint GET /internal/cron/platform-lifecycle.
2. Cron authentication uses server-only CRON_SECRET and constant-time bearer comparison; missing secret fails closed.
3. Reuse Postgres lifecycle tables/RPCs, leases, idempotency, retries and dead-letter state. Each invocation processes at most one leased batch for scheduled publication and provider cleanup; never invoke daemon run() loops.
4. Cron enqueues due retention candidates in a bounded batch but does not claim or execute purge jobs.
5. Malware scanning remains mandatory. Until an approved scanner adapter compatible with the deployed runtime is available, image/transcode/provider-callback derivative processing stays deferred and private. No no-op scanner, synthetic clean result or readiness bypass.
6. Purge requires all five server-side flags true: CONTENT_RETENTION_PURGE_ENABLED, CONTENT_RETENTION_BACKUP_VERIFIED, CONTENT_RETENTION_RESTORE_DRILL_VERIFIED, CONTENT_RETENTION_LEGAL_HOLD_VERIFIED, CONTENT_RETENTION_APPROVAL_VERIFIED. All default false.
7. Hobby Cron is a daily recovery sweep, not near-real-time scheduled publication. A due schedule may wait until the next daily run; higher-frequency SLA requires more frequent Cron entitlement or an approved Vercel-native event trigger.

## Consequences
No Railway, second database, duplicate queue or persistent daemon is introduced. Cron has no guaranteed retry, so Postgres lease expiry and retry/dead-letter state provide recovery. Cloudinary callback verifies and enqueues only. Runtime activation requires deployment, environment variables, Cron registration and invocation logs. Scanner, provider, backup/PITR and restore evidence remain separate gates.

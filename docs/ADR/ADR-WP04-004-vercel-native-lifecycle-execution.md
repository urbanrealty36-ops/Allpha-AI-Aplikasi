# ADR-WP04-004 — Vercel-native bounded lifecycle execution (historical decision)

- **Status:** SUPERSEDED on 2026-11-22 by `ADR-RAILWAY-001-canonical-runtime-platform.md`.
- **Original status:** ACCEPTED — Product Owner direction recorded 2026-11-04.
- **Original scope:** WP-04 / ENG-P13 Content & Media Lifecycle.
- **Historical runtime:** Vercel project `api-allpha`, root `apps/api`.
- **Canonical database:** Supabase `dvdziauyvuhcnqhrrvww`.

## Historical context and decision

This ADR originally selected one Vercel Cron at `17 3 * * *` to call authenticated FastAPI endpoint `GET /internal/cron/platform-lifecycle`. It required server-only `CRON_SECRET`, constant-time bearer comparison, bounded batches, Postgres leases/idempotency/retries, non-destructive retention enqueue, mandatory malware scanning, and all five retention purge gates.

Those lifecycle and security requirements remain valid. The hosting decision does not.

## Superseding decision

The Product Owner's 2026-11-22 instruction establishes Railway as the only Allpha deployment, backend runtime, worker, Cron and orchestration platform. The previous Vercel runtime/Cron decision is no longer operative.

See `docs/ADR/ADR-RAILWAY-001-canonical-runtime-platform.md` for:
- canonical Railway services and worker inventory;
- single-consumer/single-scheduler ownership;
- worker credentials and activation gates;
- Cron ownership and lifecycle split;
- custom-domain/traffic cutover;
- safe removal of Vercel configuration and integrations.

## Preserved invariants

1. Reuse canonical Supabase lifecycle tables/RPCs; no second database or queue.
2. Use bounded batches, Postgres leases, idempotency, retry/backoff and dead-letter state.
3. Keep malware scanning mandatory; fail closed when the approved scanner is unavailable.
4. Keep retention purge disabled until backup/PITR, restore, legal-hold and approval gates are proven.
5. Never activate duplicate publication, cleanup or outbox consumers.
6. Do not claim runtime activation without deployment, invocation and durable database evidence.

## Migration status

At the time this ADR was superseded, `apps/api/vercel.json` still contained the legacy daily Cron declaration. No Railway lifecycle Cron or dedicated worker service had yet been verified. Do not remove the legacy config until the Railway replacement and traffic cutover satisfy ADR-RAILWAY-001; do not keep both consumers active during handover.

# API background workers

## Social Graph Outbox — Vercel deployment

The production consumer is hosted by the existing **Vercel `api-allpha` project**. No Railway service, second database, or separate queue is created.

### Primary delivery path
- Social graph mutations (follow, follow-request accept/reject, unfollow/block/mute removal, and interest preference changes) commit to canonical Supabase first.
- After a successful mutation, FastAPI performs a bounded best-effort inline drain of one durable outbox event.
- A drain failure does not reverse or misreport the already committed mutation. The event remains pending and lease/retry policy remains owned by Postgres.
- The effect is idempotent: `apply_social_graph_event_effect` verifies the live lease, inserts the unique event effect, invalidates actor/target feed snapshots, and marks the event processed atomically.

### Recovery schedule
- `apps/api/vercel.json` registers `GET /internal/cron/social-graph-outbox` as a daily Vercel Cron recovery sweep.
- The API route requires `Authorization: Bearer <CRON_SECRET>`, uses constant-time comparison, and fails closed when the secret is absent.
- The current Vercel team is on the Hobby plan. Vercel Hobby permits at most one cron execution per day, so this is a **recovery sweep only**, not the primary low-latency delivery mechanism. Social mutation requests trigger the normal inline drain. If a higher-frequency scheduled sweep is required, the Vercel plan must support per-minute cron execution.
- Vercel Cron does not guarantee retries. The durable outbox lease expiry and bounded Postgres retry/dead-letter policy provide recovery; the next cron or graph mutation can reclaim eligible events.
- The cron endpoint is deliberately a single bounded batch so it remains within serverless execution limits.

### Vercel project configuration
- Project: `api-allpha` (existing Vercel project linked to this monorepo; project root is `apps/api`).
- Required production environment variables: existing `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` (or the already-supported `SUPABASE_SECRET_KEY` alias), and `CRON_SECRET`.
- `CRON_SECRET` is stored as a sensitive Vercel Production environment variable. Never commit or expose its value to clients.
- Cron registration occurs only after a successful production deployment containing `apps/api/vercel.json`. Verify it in Vercel Project → Settings → Cron Jobs and inspect runtime logs for `/internal/cron/social-graph-outbox`.
- The legacy `allpha-social-graph-outbox-worker` CLI remains available for controlled local/standalone operations, but is **not** the Vercel production runtime and must not be configured as a Railway service.

### Retry, lease and idempotency contract
- Claims use `FOR UPDATE SKIP LOCKED`, expiring lease tokens and bounded batch/lease configuration.
- The event effect ledger is unique by event ID. Effect insertion, invalidation and event completion are one Postgres transaction.
- Failures return to pending with bounded exponential backoff; the configured maximum attempt count transitions the event to dead. Expired processing leases can be reclaimed.
- Never mark an event processed manually; use only the claim/apply/fail RPCs.

### Activation and evidence
- The source endpoint, daily Vercel Cron declaration and production `CRON_SECRET` variable are configured in the existing Vercel project.
- Runtime activation is verified only after the deployment containing the cron declaration reaches READY, Vercel lists the cron job, and an authorized invocation is visible in runtime logs with corresponding outbox effect/processed-state evidence.
- No synthetic production event is to be injected for this verification. Do not claim a worker event was processed merely because deployment or cron registration succeeded.

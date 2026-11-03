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


## WP-04 Content Image Worker — isolated runtime (source implemented, not activated)

- Image jobs are enqueued by the content_media status transition from uploading to uploaded; the database trigger moves the media to processing.
- The worker claims only image_process jobs using the typed claim RPC, so video/audio jobs remain queued until a managed transcoding provider has been approved and configured.
- Build context: apps/api; Dockerfile: apps/api/Dockerfile.media-worker; entrypoint: allpha-content-media-worker.
- Run as a separate, non-root container with CPU/memory/PID limits and restricted egress. The image worker needs only Supabase Storage/API and the approved ClamAV daemon endpoint; it must not receive unrelated provider credentials.
- Required server-only environment: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY (or supported secret alias), CLAMAV_HOST; optional CLAMAV_PORT, CONTENT_IMAGE_BATCH_SIZE, CONTENT_IMAGE_LEASE_SECONDS, CONTENT_IMAGE_POLL_SECONDS.
- It verifies the source SHA-256, requires ClamAV clean response, decodes with Pillow pixel limits, strips metadata through re-encoding, writes display/thumbnail WebP derivatives, and calls the atomic completion RPC. Only that RPC marks image media ready.
- Missing scanner, invalid images, hash mismatch, or derivative persistence failure must fail closed. No image is marked ready without a clean scan and durable derivative paths.
- This source implementation is NOT runtime activation evidence. Do not activate until the new migrations are reviewed/applied through the approved non-production path, the worker image is built and scanned, secrets/egress/resource limits are configured, and real integration checks are authorized.
- Video/audio transcoding, callback signature verification, retention execution, scheduled publication execution, and provider selection remain separate WP-04 deliverables; their presence in the lifecycle job schema does not mean those workers are implemented.


## WP-04 lifecycle worker contracts (source implemented; activation pending)

### Cloudinary video/audio transcode dispatcher

- Provider decision: Cloudinary, accepted in ADR-WP04-002. Cloudinary uses resource_type=video for audio assets as well as video.
- Entrypoint: allpha-content-transcode-worker; Dockerfile: apps/api/Dockerfile.transcode-worker.
- Required secrets: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY (or supported alias), CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET, ALLPHA_CLOUDINARY_CALLBACK_URL, CLAMAV_HOST. CLAMAV_PORT defaults to 3310.
- Worker downloads the private Supabase original, verifies SHA-256, requires a clean ClamAV INSTREAM result, then uploads server-to-server to Cloudinary with signed upload parameters and asynchronous eager transformations.
- Supabase credentials are not sent to Cloudinary or its CDN. Provider callback signature is verified by FastAPI against the exact raw body + X-Cld-Timestamp + API secret (SHA-1 or SHA-256 constant-time compare) and a two-hour freshness bound.
- Callback validates the expected Cloudinary host/path and asset identity, copies every derivative to the private canonical Supabase bucket, then calls the atomic completion RPC. Only this RPC can promote video/audio media to ready.
- Cloudinary account setup remains a manual activation gate: create/configure the product environment, select the webhook verification API key, configure the callback URL and legacy_hmac signature scheme, review plan/region/quotas/cost/retention, and store secrets in server-side environments. No credentials or account configuration are claimed here.

### Scheduled publication

- Entrypoint: allpha-content-scheduler; Dockerfile: apps/api/Dockerfile.content-scheduler.
- API commands use atomic Postgres RPCs for create/reschedule/cancel, retain UTC execution time and creator IANA timezone, bind schedule to content version, and use deterministic/request Idempotency-Key.
- Worker claims due schedules with leases and invokes publish_scheduled_content. The database transaction rechecks schedule lease, owner, content version/status, moderation approval, rights attestation and every media status before atomically publishing and inserting content.published lifecycle event.
- Retry/backoff and terminal failed state are persisted in content_schedules. Recovery reclaims expired processing leases.

### Retention executor

- Entrypoint: allpha-content-retention-worker; Dockerfile: apps/api/Dockerfile.retention-worker.
- Daily/periodic worker enqueues soft-deleted content after 30 days and abandoned uploading/failed media after 7 days. Operator dry-run preview is read-only.
- Before physical deletion, begin_content_retention_purge locks and checks expiry and active legal/safety holds. A purge lock prevents a new hold being created after physical deletion begins.
- The worker deletes originals and all recorded derivatives from the private Storage bucket, removes canonical rows idempotently, and writes one retention receipt per job. Immutable backups follow their separately managed expiry policy; this worker does not claim immediate deletion from backups.
- Legal hold conflicts are deferred for a day and checked again. Storage deletes accept not-found as idempotent success.

### Super Admin governance and Native parity

- Super Admin: /content-moderation, /content-appeals, /content-lifecycle. Operator routes require platform:content.moderate and audit reads/actions.
- Lifecycle console includes dry-run preview, hold create/release, deletion receipts and event timeline.
- Native Client Creator Studio includes appeal submission/history and deleted-content recovery entry points.

### Activation / acceptance gate

- All listed changes are source-only until migrations are reviewed/applied, workers are deployed/configured, Cloudinary account/webhook is configured, ClamAV is reachable, and authorized real integration tests are completed.
- No migration, worker activation, provider provisioning, destructive purge, or production deployment is performed by this source implementation.
- Video/audio moderation still depends on the independent human content review queue after media readiness; provider completion never publishes content.


### Cloudinary provider asset cleanup

- Entrypoint: allpha-content-provider-cleanup; Dockerfile: apps/api/Dockerfile.provider-cleanup-worker.
- When authenticated Cloudinary derivatives are copied into the private canonical Supabase bucket and the media row is atomically marked ready, a database trigger creates a durable provider_cleanup job.
- The cleanup worker uses the server-only Cloudinary API secret to destroy the authenticated provider original and eager derivatives. Retries are idempotent (provider result ok/not found).
- This removes the temporary provider-side copy; the canonical originals/derivatives remain in Supabase until the approved Allpha retention lifecycle removes them.


### Durable Cloudinary callback processor

- Entrypoint: allpha-content-provider-callback; Dockerfile: apps/api/Dockerfile.provider-callback-worker.
- The FastAPI webhook does only raw-body signature verification, media/asset/batch correlation and an atomic database enqueue. It returns quickly so the provider's notification timeout/retry window is not consumed by large file transfers.
- The callback payload and digest are stored in content_provider_callbacks; a unique provider_callback lifecycle job is inserted in the same Postgres RPC.
- The isolated callback worker claims the job, downloads only signed authenticated Cloudinary URLs from the configured CDN host, enforces size/MIME limits, scans each derivative through ClamAV, copies derivatives into private Supabase Storage, and calls the atomic provider completion RPC.
- A provider_callback job can be operator-retried without clearing the Cloudinary asset/batch identity; if exhausted, media remains non-ready/failed.

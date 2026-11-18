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
- Video/audio transcoding, callback signature verification, retention execution, scheduled publication execution, and provider selection are implemented in source; runtime activation and integration remain pending.


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
- Daily/periodic worker can enqueue soft-deleted content after 30 days and abandoned uploading/failed media after 7 days. Operator dry-run preview is read-only. **Destructive execution is disabled by default** and requires `CONTENT_RETENTION_PURGE_ENABLED=true` in the isolated worker runtime after backup/PITR, legal-hold, restore, and retention approval gates are verified.
- Before physical deletion, begin_content_retention_purge locks and checks expiry and active legal/safety holds. A purge lock prevents a new hold being created after physical deletion begins.
- The worker deletes originals and all recorded derivatives from the private Storage bucket, removes canonical rows idempotently, and writes one retention receipt per job. Immutable backups follow their separately managed expiry policy; this worker does not claim immediate deletion from backups.
- Legal hold conflicts are deferred for a day and checked again. Storage deletes accept not-found as idempotent success.

### Super Admin governance and Native parity

- Super Admin: /content-moderation, /content-appeals, /content-lifecycle. Operator routes require platform:content.moderate and audit reads/actions.
- Lifecycle console includes dry-run preview, hold create/release, deletion receipts and event timeline.
- Native Client Creator Studio includes appeal submission/history and deleted-content recovery entry points.

### Activation / acceptance gate

- All listed changes are source-only until migrations are applied through the repository's version-preserving migration path, workers are deployed/configured, Cloudinary account/webhook is configured, ClamAV is reachable, and authorized real integration tests are completed. Retention purge must remain disabled until backup/PITR and restore evidence is accepted.
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


### Version-preserving production migration path

- Canonical CLI project configuration is `apps/api/supabase/config.toml`; migrations remain in `apps/api/supabase/migrations` with their repository timestamps.
- The manual GitHub Actions workflow is `.github/workflows/wp04-supabase-production-migrations.yml`. It links only project `dvdziauyvuhcnqhrrvww`, prints `supabase migration list --linked` and `supabase db push --linked --dry-run`, and applies only when the workflow-dispatch boolean `confirm_apply` is explicitly true.
- The workflow requires repository Actions secrets `SUPABASE_ACCESS_TOKEN` and `SUPABASE_DB_PASSWORD`. Set them directly in GitHub repository Settings → Secrets and variables → Actions. Never paste either value into chat, source files, or logs.
- Do not use `supabase db reset --linked`. The workflow does not reset the remote database. Inspect the dry-run and migration list before setting `confirm_apply=true`.
- This workflow has been committed but has NOT yet been run. No WP-04 migration has been applied to production through this path.


## WP-04 lifecycle — Vercel-native bounded execution (2026-11-04)

- Existing Vercel project api-allpha (root apps/api) is the sole runtime for FastAPI and Cron. No Railway or persistent worker service is used.
- apps/api/vercel.json registers one daily Cron at 17 3 * * * to GET /internal/cron/platform-lifecycle. The endpoint requires server-only CRON_SECRET, uses constant-time bearer comparison and fails closed when absent.
- The orchestrator runs at most one leased batch each for scheduled publication and Cloudinary provider cleanup. It enqueues up to 100 due retention candidates through the existing Postgres RPC; this enqueue is non-destructive.
- Vercel Hobby permits one Cron run per day. This is a recovery/scheduling sweep, not near-real-time publication. A scheduled post may be delayed until the next daily run (up to roughly 24 hours). Higher-frequency SLA requires a Vercel plan with more frequent Cron or an approved Vercel-native event trigger.
- Image processing, transcode dispatch and callback derivative ingestion remain deferred while the approved malware scanner adapter is unavailable. Cloudinary callback verifies signature and durably enqueues only; it does not download derivatives or mark media ready. Unscanned media remains private and non-publishable.
- Retention purge requires all five server-only gates: CONTENT_RETENTION_PURGE_ENABLED, CONTENT_RETENTION_BACKUP_VERIFIED, CONTENT_RETENTION_RESTORE_DRILL_VERIFIED, CONTENT_RETENTION_LEGAL_HOLD_VERIFIED, CONTENT_RETENTION_APPROVAL_VERIFIED. Every gate defaults false and is enforced by both Cron status and the retention worker.
- Vercel Cron does not guarantee retries. Durable Postgres leases, idempotency, bounded retry/backoff and dead-letter state remain authoritative. Runtime activation still requires deployment, env configuration, Cron registration and invocation logs.


## ENG-P09 durable generation worker (source implemented, not activated)

- Entrypoint: `allpha-generation-worker`; module: `allpha_api.generation_job_worker`.
- The canonical FastAPI endpoint `POST /v1/generation/jobs` requires a verified Premium subscription, a published owner-controlled Agent Skill, an approved Agent capability, an approved active model route, and a currently effective approved AI Credit policy.
- `generation_create_job` calls the existing `credit_ledger_reserve` RPC and inserts the job in the same PostgreSQL transaction. The job snapshots the provider/model/version, pricing version, usage unit, tariff, entitlement, policy approval, cost ceiling, credit reservation, and source Skill version.
- Worker claims use `FOR UPDATE SKIP LOCKED`, a bounded lease and a single attempt. The worker calls only `CanonicalTextGenerationRouter`; it never calls a model provider directly.
- Provider output and durable usage evidence are persisted privately before ledger settlement. The owner API exposes output only after successful settlement and terminal job completion.
- Any provider/metering/settlement uncertainty or expired worker lease moves the job/reservation to `pending_reconciliation`. Unknown outcomes are **never automatically replayed**. No prompt/output is written to worker logs.
- Required server-only environment: `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, approved model-route/runtime-policy configuration, approved model-cost registry row (`policy_approved=true`), and approved `credit_policy_versions` policy. `ALLPHA_GENERATION_WORKER_ENABLED=false` by default; configure poll and batch values only after approval.
- The live model-cost registry previously inspected contains only a test-only NVIDIA NIM/Qwen row with `policy_approved=false`; no approved credit policy rows or active Premium subscription products were evidenced. Therefore the worker and generation endpoint remain fail-closed and must not be enabled using that test row.
- Migration source: `apps/api/supabase/source-only-migrations/20261105130000_eng_p09_durable_generation_jobs.sql`. It has not been applied. No provider call, reservation, settlement, database mutation, or worker execution was performed.

## ENG-P30 Stripe billing and subscription (source implemented, not activated)

- Provider: Stripe, selected by Product Owner. FastAPI routes are mounted from `allpha_api.stripe_billing_api`; Web and Native Billing Centers use the same API. Super Admin product governance requires `platform:billing.manage`.
- Checkout uses only operator-managed active `billing_products` records and their Stripe Price IDs. Client-supplied amount, currency, credit amount, plan, or entitlement are never accepted as authority. Operator activation verifies the Stripe Price amount/currency/recurrence against the product snapshot and checks approved credit-grant policy before publication.
- Webhook: `POST /v1/billing/stripe/webhook`. Configure signed Stripe events for Checkout completion/async result/expiry, subscription updated/deleted, and invoice paid/payment failed. The handler validates the Stripe signature and timestamp, stores a sanitized idempotent event, verifies Checkout state, then finalizes order/receipt and AI Credit grant or subscription/entitlement in PostgreSQL.
- Subscription renewal receipts and monthly Premium AI Credit allowances are recorded idempotently from `invoice.paid` using the existing AI Credit Ledger; no allowance is granted from a checkout redirect. Web/Native users manage active subscriptions through Stripe Billing Portal. Client redirect URLs never fulfill orders or activate entitlements.
- Required server-only environment: `ALLPHA_STRIPE_ENABLED`, `ALLPHA_STRIPE_MODE`, `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, and the allow-listed billing return URLs. Checkout remains disabled by default. Never place Stripe secrets in client apps.
- Super Admin draft/activate/retire product controls require the separately granted `platform:billing.manage` operator scope. No operator grant is created automatically.
- Migration source: `apps/api/supabase/source-only-migrations/20261105120000_eng_p30_stripe_billing_subscriptions_entitlements.sql`. It has not been applied; no Stripe account, secret, Price, webhook, live/test checkout, payment, refund or subscription transaction was configured or executed. No prices, credit packs or Premium quotas are seeded.

## Current activation boundary

- Both new migrations are source-only and un-applied. No staging, browser/device tests, builds, CI, production migration, deployment, provider call, or payment transaction was run in this implementation pass.
- WP-04 remains source implemented / runtime not verified. Cloudinary account credentials/callback, ClamAV scanner, media worker image/runtime, backup/PITR plan and restore evidence remain required. Retention purge stays disabled.
- WP-05 source/acceptance was not changed in this pass. There is a document conflict: `ADR-WP04-003-clamav-deferral.md` §Decision.7 says WP-05 remains locked until WP-04 implementation closure, while the current Fixed Phase Plan's Product Owner directive authorizes continued WP-05 work against available contracts. Per `AGENTS.md` §12.6, stop WP-05 implementation until the Product Owner resolves this exact conflict in the governing documents.
- All runtime integration and acceptance states remain `DEFERRED / NOT VERIFIED`. Do not mark ENG-P09, ENG-P30, WP-04, WP-05 or ENG-P37 as accepted or production verified.


## WP-07 external Consumer generation extension (source implemented, not activated)

- External generation uses an owner-approved Consumer grant pinned to requester, Agent owner, Agent version, published Skill/version, runtime policy, capability, credit scheme, tariff, entitlement, pricing, payer role and settlement permissions.
- The quote and job snapshot the exact immutable `agent_skill_versions.snapshot` plus Agent persona/disclosure/boundaries. Quote fingerprints are revalidated at job creation; the SQL job stores both snapshots and the Skill-instructions digest. The worker verifies the fingerprints and sends Agent/Skill instructions in the canonical Model Router system message, with the user's request and ACL-filtered Knowledge in the user message. Declared tool dependencies are not treated as executable tools on this text-generation path; the prompt explicitly prevents claiming tool execution.
- Knowledge retrieval is restricted to the public scope. The external retrieval service requires public sensitivity, owner consent, ready/version-matched source chunks and provenance. The worker verifies the stored Knowledge context digest before building the provider prompt; private/internal owner Knowledge is never attached to an external Consumer job.
- `generation_jobs` stores requester, Agent owner, payer, Consumer grant, Agent version and runtime-policy snapshot separately. The requester owns the private output artifact and is the only account allowed to obtain a short-lived signed artifact URL.
- The provider result is persisted to private `generation-artifacts` storage, checked against the approved cost ceiling, moderated under an approved output policy, and then completed in one Postgres transaction: payer settlement, policy-approved Agent-owner reward (when applicable), Human↔Agent DM receipt, and terminal job state.
- The Web and Native message clients render the `generation_job_id` receipt as a link to the requester-scoped private Generate result. The DM body itself contains no signed URL.
- Worker execution revalidates the external Consumer grant and its immutable policy snapshot immediately before the provider side effect. Completion rechecks the same grant, Agent/Skill versions, scopes, pricing, payer role and settlement permissions.
- Revocation uses `agent_consumer_grant_revoke`: queued jobs are cancelled and their reservation is released only when the approved failure-release policy permits it; otherwise the reservation is retained for reconciliation. Running jobs are fenced into `pending_reconciliation` because provider outcome may already be unknown. Grant creation and revocation are written to the append-only grant event ledger.
- Schema reconciliation: `20261115140000_eng_p05_agent_version_snapshot_contract.sql` records the Agent version column/trigger already observed in the connected database but missing from repository migration history.
- Source-only migrations: `20261105130000_eng_p09_durable_generation_jobs.sql`, `20261115150000_wp07_external_consumer_dual_account.sql`, `20261115152000_wp07_external_consumer_generation_atomic.sql`, and `20261115153000_wp07_consumer_grant_revocation_lifecycle.sql`. The connected database currently has no `generation_jobs` or `agent_consumer_grant_events` table; these source-only migrations are not applied.
- Worker image: build context `apps/api`, Dockerfile `apps/api/Dockerfile.generation-worker`, entrypoint `allpha-generation-worker`. It runs as non-root UID 10001; set `ALLPHA_GENERATION_WORKER_ENABLED=true` only in the dedicated worker runtime after policy activation. Configure bounded `ALLPHA_GENERATION_WORKER_POLL_SECONDS` and `ALLPHA_GENERATION_WORKER_BATCH_SIZE`; do not reuse the API server container as an unbounded worker process.
- Runtime activation remains blocked until the source-only migrations are reviewed and applied through the approved migration path, approved public model/runtime policy and AI Credit settlement policy exist, the worker is hosted in an approved persistent execution environment, and authorized end-to-end integration verification is permitted. No staging, real integration test, worker activation, provider call, migration application, or deployment is performed by this source implementation.


## WP-07 requester-controlled Generation artifact deletion (source implemented, not activated)

- The authenticated requester can issue `DELETE /v1/generation/jobs/{job_id}/artifact` with an `Idempotency-Key`. FastAPI scopes the job lookup to the authenticated owner and invokes `generation_request_artifact_deletion`; a Consumer or Agent owner cannot delete another requester's private output.
- The Postgres transaction records a durable deletion job and sets `generation_jobs.artifact_deletion_requested_at`. The artifact endpoint denies new signed URLs immediately while the Storage object is pending deletion. Signed URLs already issued remain valid until the object is removed or their 60-second expiry is reached. Completed deletion is recorded in `artifact_deleted_at`; the original job/message provenance remains for audit.
- Worker: `allpha-generation-artifact-deletion-worker`; Dockerfile: `apps/api/Dockerfile.generation-artifact-deletion-worker`; build context: `apps/api`. It runs non-root UID 10001, claims with expiring leases, deletes only the private `generation-artifacts` object, treats Storage 404 as idempotent success, and completes/fails through service-role-only Postgres RPCs with bounded retry and dead-letter state.
- Required server-only environment: `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` (or supported `SUPABASE_SECRET_KEY` alias). Activation requires `ALLPHA_GENERATION_ARTIFACT_DELETION_WORKER_ENABLED=true`; the Dockerfile default is false. Optional bounded controls: `GENERATION_ARTIFACT_DELETE_BATCH_SIZE` (default 5, SQL maximum 20) and `GENERATION_ARTIFACT_DELETE_POLL_SECONDS` (default 10, worker maximum 60).
- Source-only migration: `apps/api/supabase/source-only-migrations/20261115170000_wp07_generation_artifact_owner_deletion.sql`. It depends on the source-only durable Generation Job schema. Do not apply it independently or to canonical production during this source-only work window.
- This is explicit owner-requested deletion only. No automatic artifact TTL is set because the Master PRD lists retention periods and deletion SLAs by data class as open decisions. Do not infer or invent a retention duration.
- The Super Admin Content Moderation page now reads the deletion queue through the operator-scoped API and can retry a dead-letter job only with a recorded reason. The retry RPC records the operator ID and reason; the API writes operator audit events before and after the recovery action.
- The worker is not activated, no Storage object was deleted, and no database migration was applied in this source implementation. Runtime activation requires the approved migration path, service secrets, persistent worker hosting and authorized integration verification.


## WP-07 Agent Runtime planned-task worker (source implemented, not activated)

- Entrypoint: `allpha-agent-runtime-worker`; module: `allpha_api.agent_runtime_worker`; image: `apps/api/Dockerfile.agent-runtime-worker`; build context: `apps/api`.
- The worker polls only canonical `agent_runtime_tasks` rows with a stored `_runtime_plan_version=1` plan in `created` state, plus tasks whose execution lease has expired. It delegates to the existing `_execute_planned_task` and `AgentRuntimeStore`; it does not create another runtime, planner, tool registry or task database.
- Claims, lease fencing, pinned Agent/Skill versions, approved capability/runtime policy, registered pure-tool execution, checkpoint replay, idempotency and terminalization remain enforced by the canonical runtime and Postgres RPCs. The worker never calls model providers directly and does not execute side-effecting tools.
- An expired task with `effect_outcome=started|unknown` is terminalized through `mark_agent_runtime_effect_unknown`; it is never replayed. A persistence uncertainty stops the current batch and leaves lease/recovery semantics authoritative.
- Runtime configuration: `ALLPHA_AGENT_RUNTIME_WORKER_ENABLED=false` by default; bounded `ALLPHA_AGENT_RUNTIME_WORKER_POLL_SECONDS` (0.5–30s) and `ALLPHA_AGENT_RUNTIME_WORKER_BATCH_SIZE` (1–25). The container runs as non-root UID 10001.
- Schema dependency: `agent_runtime_tool_plans` plus `agent_runtime_tool_plans.memory_context_refs/memory_context_sha256` source migrations; the canonical WP-07 Memory Coordinator base, ranked-search and proposal-idempotency migrations are separate source-only files. These migrations are not applied to the connected database.
- **Activation remains disabled.** Do not set `ALLPHA_AGENT_RUNTIME_WORKER_ENABLED=true`, create a persistent worker service, or deploy this image until the source-only migrations are reviewed/applied through the approved migration path, worker hosting/secrets/resource limits are approved, and the relevant runtime verification is authorized. No worker invocation or task execution was performed by this source change.


### Bounded retry and recovery contract

- Source migration `20261118195000_wp07_durable_retry_attempts.sql` adds durable `execution_attempts`, `max_execution_attempts` (default 3, maximum 5), and `next_attempt_at`. The claim RPC increments attempts atomically and only claims due work.
- Only deterministic, registered pure-tool timeout is classified retryable in the current runtime. Retry delay is bounded exponential backoff (default three attempts means 5s and 10s retry delays; a configured five-attempt task may use 20s and 40s; maximum 60s). The retry RPC preserves completed step checkpoints and rejects any task whose effect outcome is `started` or `unknown`.
- Worker crashes/persistence interruptions recover from the last verified checkpoint only when the lease expires and the effect outcome is known safe. Unknown effects are terminalized as `EXECUTION_OUTCOME_UNKNOWN` and are never replayed.
- Exhausted attempts are terminalized as `RUNTIME_RETRY_EXHAUSTED`. Preflight policy/contract failures are also terminalized through an owner/task-version/lease-fenced RPC so the worker does not poll a permanently invalid task forever.
- Lease heartbeat is fenced by owner, task, lease token and task version. A cancellation request is returned to the worker without extending the lease; the worker checkpoints any completed pure step and finalizes the task as cancelled.
- All new database changes are source-only and not present in the connected Supabase migration ledger. Worker activation remains disabled until canonical migrations are applied and runtime verification is authorized.

# API background workers

## Social Graph Outbox — Railway persistent consumer

The canonical production target is a dedicated Railway worker service in the existing Allpha Railway project. The existing FastAPI mutation path remains a bounded best-effort inline drain; it is not a substitute for the durable consumer.

### Primary delivery path
- Social graph mutations commit to canonical Supabase first.
- The dedicated worker runs the existing `allpha-social-graph-outbox-worker` entrypoint from `apps/api/src/allpha_api/social_graph_outbox_worker.py`.
- The worker claims events through the existing Postgres claim RPC, uses expiring lease tokens, and applies each effect through the existing atomic/idempotent effect RPC.
- Do not create a second queue, event table, consumer implementation or feed invalidation engine.

### Railway service contract
- Target service name: `Allpha-Social-Graph-Outbox-Worker` in Railway project `noble-wonder`, production environment.
- Repository: `urbanrealty36-ops/Allpha-AI-Aplikasi`, branch `main`, root directory `/apps/api`.
- Build: existing `apps/api/Dockerfile`; start command: `allpha-social-graph-outbox-worker`.
- Required server-only environment: `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` (or the already-supported `SUPABASE_SECRET_KEY` alias). Optional bounded controls: `SOCIAL_OUTBOX_BATCH_SIZE`, `SOCIAL_OUTBOX_LEASE_SECONDS`, `SOCIAL_OUTBOX_POLL_SECONDS`, `SOCIAL_OUTBOX_MAX_ATTEMPTS`.
- The inspected Railway API service currently exposes `SUPABASE_ROLE_KEY`, but not `SUPABASE_SERVICE_ROLE_KEY` or `SUPABASE_SECRET_KEY`. The worker code does not recognize `SUPABASE_ROLE_KEY`, and its actual privilege type is unverified. Do not alias or use it until its service-role/secret scope is confirmed. No Social Graph worker service exists yet. Therefore this worker is **NOT ACTIVATED**; do not create a non-functional deployment or claim event processing.
- Do not attach a Cron schedule to this polling worker. Postgres lease expiry, bounded retries and dead-letter state provide recovery.

### Retry, lease and idempotency contract
- Claims use `FOR UPDATE SKIP LOCKED`, expiring lease tokens and bounded batches.
- Event effect insertion, participant feed-snapshot invalidation and event completion remain one Postgres transaction.
- Failures return to pending with bounded backoff; exhausted attempts become dead-lettered. Expired processing leases may be reclaimed.
- Never mark an event processed manually; use only the canonical claim/apply/fail RPCs.

### Activation evidence
A successful image build or running container is not processing evidence. Activation requires the canonical worker service, server-only credentials, successful schema/RPC readiness, a real naturally occurring event, a persisted unique effect receipt/processed state, and lease/retry recovery evidence. Do not inject synthetic production events.


## WP-04 Content Image Worker — isolated runtime (source implemented, not activated)

- Image jobs are enqueued by the content_media status transition from uploading to uploaded; the database trigger moves the media to processing.
- The worker claims only image_process jobs using the typed claim RPC, so video/audio jobs remain queued until a managed transcoding provider has been approved and configured.
- Build context: apps/api; Dockerfile: apps/api/Dockerfile.media-worker; entrypoint: allpha-content-media-worker.
- Run as a separate, non-root container with CPU/memory/PID limits and restricted egress. The image worker needs only Supabase Storage/API and the approved ClamAV daemon endpoint; it must not receive unrelated provider credentials.
- Required server-only environment: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY (or supported secret alias), and either the complete authenticated remote scanner contract (ALLPHA_DOCUMENT_SCANNER_URL, ALLPHA_DOCUMENT_SCANNER_API_KEY, ALLPHA_DOCUMENT_SCANNER_ALLOWED_HOSTS, ALLPHA_DOCUMENT_SCANNER_ID, ALLPHA_DOCUMENT_SCANNER_ENGINE_VERSION, ALLPHA_DOCUMENT_SCANNER_SIGNATURE_VERSION) or explicitly enabled/pinned local ClamAV (ALLPHA_DOCUMENT_SCANNER_MODE=clamd, ALLPHA_CLAMAV_ENABLED=true, CLAMAV_HOST). Optional controls: CLAMAV_PORT, CONTENT_IMAGE_BATCH_SIZE, CONTENT_IMAGE_LEASE_SECONDS, CONTENT_IMAGE_POLL_SECONDS.
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
- The isolated callback worker claims the job, downloads only signed authenticated Cloudinary URLs from the configured CDN host, enforces size/MIME limits, scans each derivative through the canonical authenticated remote scanner (or explicitly enabled pinned ClamAV), copies derivatives into private Supabase Storage, and calls the atomic provider completion RPC.
- A provider_callback job can be operator-retried without clearing the Cloudinary asset/batch identity; if exhausted, media remains non-ready/failed.


### Version-preserving production migration path

- Canonical CLI project configuration is `apps/api/supabase/config.toml`; migrations remain in `apps/api/supabase/migrations` with their repository timestamps.
- The manual GitHub Actions workflow is `.github/workflows/wp04-supabase-production-migrations.yml`. It links only project `dvdziauyvuhcnqhrrvww`, prints `supabase migration list --linked` and `supabase db push --linked --dry-run`, and applies only when the workflow-dispatch boolean `confirm_apply` is explicitly true.
- The workflow requires repository Actions secrets `SUPABASE_ACCESS_TOKEN` and `SUPABASE_DB_PASSWORD`. Set them directly in GitHub repository Settings → Secrets and variables → Actions. Never paste either value into chat, source files, or logs.
- Do not use `supabase db reset --linked`. The workflow does not reset the remote database. Inspect the dry-run and migration list before setting `confirm_apply=true`.
- This workflow has been committed but has NOT yet been run. No WP-04 migration has been applied to production through this path.


## WP-04 lifecycle — Railway runtime migration (supersedes Vercel hosting decision)

- Railway is the canonical platform for WP-04 API, persistent workers and scheduled execution under `docs/ADR/ADR-RAILWAY-001-canonical-runtime-platform.md`.
- The previous `apps/api/vercel.json` declaration for `GET /internal/cron/platform-lifecycle` is a legacy migration artifact. Do not create or activate a Vercel Cron or a second Railway scheduler while the lifecycle owner is being reconciled.
- Existing worker entrypoints remain canonical: `allpha-content-media-worker`, `allpha-content-transcode-worker`, `allpha-content-scheduler`, `allpha-content-retention-worker`, `allpha-content-provider-cleanup`, and `allpha-content-provider-callback`. Use their existing Dockerfiles and Postgres lifecycle contracts; do not introduce duplicate engines.
- **Scheduler ownership conflict must be resolved before activation:** `allpha-content-scheduler` claims scheduled publication jobs, while the legacy `platform-lifecycle` endpoint also orchestrates scheduled publication/provider cleanup. Exactly one active consumer may own scheduled publication. Keep both inactive until the canonical ownership split is implemented and verified; provider cleanup and retention may be separated only with explicit queue ownership.
- If a bounded periodic lifecycle sweep is still required after the ownership split, run it as one Railway Cron target with server-only `CRON_SECRET`, constant-time bearer validation, a bounded batch and durable Postgres leases. Preserve the existing daily cadence until a documented operational decision changes it. Railway Cron minimum interval is five minutes; this does not imply a need to increase frequency.
- Image processing and derivative ingestion remain blocked until the approved ClamAV adapter is reachable and all related source-only migrations are reconciled/applied through the approved path. No no-op scanner, synthetic clean response or readiness bypass.
- Cloudinary transcode/callback/cleanup workers require the approved account, server-only Cloudinary credentials, exact callback verification and ClamAV. Missing provider/scanner configuration keeps media private and non-publishable.
- Retention purge remains disabled unless all five existing server-side gates are true: `CONTENT_RETENTION_PURGE_ENABLED`, `CONTENT_RETENTION_BACKUP_VERIFIED`, `CONTENT_RETENTION_RESTORE_DRILL_VERIFIED`, `CONTENT_RETENTION_LEGAL_HOLD_VERIFIED`, and `CONTENT_RETENTION_APPROVAL_VERIFIED`. Do not change these gates during migration.
- Railway worker/Cron activation is verified only through actual deployment status, authenticated invocation, durable lifecycle receipt/state, retry/recovery evidence and absence of a duplicate consumer. Source presence, build success or HTTP health alone is insufficient.


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
- Runtime configuration: `ALLPHA_AGENT_RUNTIME_WORKER_ENABLED=false` by default; bounded `ALLPHA_AGENT_RUNTIME_WORKER_POLL_SECONDS` (0.5–30s), `ALLPHA_AGENT_RUNTIME_WORKER_BATCH_SIZE` (1–25), and `ALLPHA_AGENT_RUNTIME_WORKER_CONCURRENCY` (1–10, default 3). Each task executes in a bounded group and obtains its own canonical Postgres lease before execution; no in-memory queue or lease is introduced. The container runs as non-root UID 10001.
- Schema dependency: `agent_runtime_tool_plans` plus `agent_runtime_tool_plans.memory_context_refs/memory_context_sha256` source migrations; the canonical WP-07 Memory Coordinator base, ranked-search and proposal-idempotency migrations are separate source-only files. These migrations are not applied to the connected database.
- **Railway service is deployed but NOT ACTIVATED:** `allpha-agent-runtime-worker` in project `noble-wonder`, production environment, root `/apps/api`, Dockerfile `Dockerfile.agent-runtime-worker`. It runs with `ALLPHA_AGENT_RUNTIME_WORKER_ENABLED=false`, concurrency 3, batch size 5 and 2s polling configuration. In disabled mode the process waits idly without initializing `AgentRuntimeStore`, opening a Supabase connection, or claiming tasks. No `SUPABASE_URL` or service-role credential is configured on this service yet. Do not enable it until canonical migrations/RPC readiness and the service-role credential scope are verified.


### Bounded retry and recovery contract

- Source migration `20261118195000_wp07_durable_retry_attempts.sql` adds durable `execution_attempts`, `max_execution_attempts` (default 3, maximum 5), and `next_attempt_at`. The claim RPC increments attempts atomically and only claims due work.
- Only deterministic, registered pure-tool timeout is classified retryable in the current runtime. Retry delay is bounded exponential backoff (default three attempts means 5s and 10s retry delays; a configured five-attempt task may use 20s and 40s; maximum 60s). The retry RPC preserves completed step checkpoints and rejects any task whose effect outcome is `started` or `unknown`.
- Worker crashes/persistence interruptions recover from the last verified checkpoint only when the lease expires and the effect outcome is known safe. Unknown effects are terminalized as `EXECUTION_OUTCOME_UNKNOWN` and are never replayed.
- Exhausted attempts are terminalized as `RUNTIME_RETRY_EXHAUSTED`. Preflight policy/contract failures are also terminalized through an owner/task-version/lease-fenced RPC so the worker does not poll a permanently invalid task forever.
- Lease heartbeat is fenced by owner, task, lease token and task version. A cancellation request is returned to the worker without extending the lease; the worker checkpoints any completed pure step and finalizes the task as cancelled.
- All new database changes are source-only and not present in the connected Supabase migration ledger. Worker activation remains disabled until canonical migrations are applied and runtime verification is authorized.


### WP-06 Social event-consumer readiness gate

- The canonical Agent Runtime worker now checks the dedicated `agent_social_automation_schema_readiness()` RPC before invoking the WP-06 event intake or approval reconciler. The predicate verifies the required Social policy/grant/inbox/run/control/audit/approval relations, RLS, service-role table privileges and event lease/dispatch RPC execute grants.
- Both explicit feature flags, `ALLPHA_AGENT_SOCIAL_AUTOMATION_SCHEMA_ENABLED=true` and `ALLPHA_AGENT_SOCIAL_AUTOMATION_WORKER_ENABLED=true`, are required before the readiness RPC is called. A missing/false readiness result leaves WP-06 events and reply tasks queued; unrelated canonical Agent Runtime tasks can continue.
- Migration `20261122130000_wp06_social_automation_schema_readiness.sql` is source-only. It does not create another queue or worker and must be applied only after its WP-06 dependency migrations through the ADR-0024 procedure. No production social event consumer is activated by this source change.
### WP-06 Social event intake digest forward repair

- The historical source-only candidate `20261122100000_wp06_social_event_intake_rate_serialization.sql` calls `public.digest(text,text)`, which is not the installed pgcrypto signature in the canonical database.
- Keep that historical file byte-for-byte unchanged and classify it as superseded for application selection. The forward repair `20261122110000_wp06_social_event_intake_rate_serialization_forward_repair.sql` uses the observed `extensions.digest(bytea,text)` signature through `convert_to(...,'UTF8')` and fails closed if the function or required WP-06 relations are absent.
- Both files remain source-only. This repair is not a production migration result and does not activate the WP-06 consumer; apply only through the WP-07 migration reconciliation and production recovery procedure.

### Worker schema readiness gate

Before reaping, listing or claiming any Agent Runtime task, `run_once` calls the read-only `agent_runtime_worker_schema_readiness()` RPC. The worker stays idle unless the complete canonical task/session/checkpoint/tool-plan tables, retry/lease columns and claim/heartbeat/checkpoint/finalization/retry RPC signatures are present. A missing migration or RPC is reported as missing schema and no task is claimed. This gate is independent of `ALLPHA_AGENT_RUNTIME_WORKER_ENABLED`; both the schema predicate and the explicit worker flag must pass.


## WP-11 AI Cinema screenplay generation (source implemented, schema activation pending)

- Cinema screenplay generation delegates to the canonical `generation_jobs_api`; it does not create a second queue, Model Router, credit ledger, moderation engine, or artifact bucket.
- `cinema_generation_job_links` is a title/owner/idempotency projection over `generation_jobs`. The canonical Generation Job worker owns execution, retries, moderation, private artifact storage and cancellation.
- Cinema checks `cinema_generation_schema_readiness()` before creating a Generation Job, so missing mapping/RPC schema fails closed before AI Credits are reserved. Cinema can inspect, cancel, retrieve the moderated private artifact and apply a screenplay draft to the version-checked production document. The apply RPC rechecks job owner, moderation, artifact availability, title version, collaborator edit permission and idempotent apply receipt.
- Migration `20261122120000_wp11_cinema_generation_job_integration.sql` is source-only and depends on canonical `generation_jobs`, `cinema_titles.production_document` and `cinema_collaborators`. No Cinema generation mapping has been applied to production.
- Migration preflight found that production `cinema_titles` has a primary key on `id` but no unique key on `(id, owner_id)`, while the generation-link FK requires that composite target. Source-only prerequisite `20261122115000_wp11_cinema_title_owner_key_prerequisite.sql` adds and verifies the unique index before the integration migration; it preserves existing rows and the primary key.
- The WP-11 readiness function PL/pgSQL dollar-quote delimiter was corrected to `$$` and guarded by a regression assertion. Both WP-11 migrations remain unapplied pending ADR-0024 recovery and per-migration preflight.
- This implements the text screenplay vertical slice only. Video rendering provider/worker, render callback, export pipeline and distribution remain unimplemented/unverified; do not treat the Cinema rendering lifecycle as complete.

## ENG-P07 Knowledge document ingestion worker — source implemented, activation pending

- Agent Studio upload writes the original to the private agent-knowledge bucket through FastAPI. The owner explicitly starts processing; FastAPI enqueues one idempotent awaiting_malware_scan job through the service-only enqueue RPC.
- Worker entrypoint: allpha-knowledge-ingestion-worker; module: allpha_api.knowledge_ingestion_worker. Under the current Railway resource quota, this consumer runs as an independently gated process on the existing allpha-agent-runtime-worker shared host; it does not create a duplicate Railway service or queue. The shared image uses apps/api/Dockerfile.agent-runtime-worker and conditionally bootstraps local ClamAV through apps/api/docker/shared-worker-entrypoint.sh.
- Worker claims only awaiting_malware_scan jobs using the canonical Postgres lease RPC. It verifies owner/Agent/source version, immutable upload size and SHA-256, requires a clean configured malware-scanner verdict, parses PDF/Markdown/TXT/DOCX in the isolated parser, preserves page/source offsets, chunks bounded text and persists batches through a lease-fenced RPC.
- Chunk replacement is retry-safe; final parse completion atomically checks the current lease/source version, promotes the source only to indexed_pending_embeddings, enqueues the deterministic embedding_indexing job, and finalizes the parse job. It never marks a source retrieval-ready.
- Failure handling atomically updates source and job state. Transient Storage/scanner failures receive bounded retry/backoff; missing scanner configuration, malware rejection, invalid files, parser failure, size/hash mismatch and invalid provenance fail closed. Retry can be requested through Agent Studio after the underlying issue is corrected.
- Knowledge source/job/chunk DML and direct Storage object access are no longer granted to anon/authenticated. Authenticated users retain owner-scoped reads; all lifecycle writes and private object operations pass through FastAPI or service workers.
- Required server-only environment on the shared Railway host: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY (or the supported secret-key alias), ALLPHA_KNOWLEDGE_DOCUMENT_WORKER_ENABLED=true, and either ALLPHA_DOCUMENT_SCANNER_URL or ALLPHA_DOCUMENT_SCANNER_MODE=clamd. The shared host's ClamAV bootstrap updates signatures and health-checks clamd before starting the consumer. Optional controls: KNOWLEDGE_DOCUMENT_LEASE_SECONDS, KNOWLEDGE_DOCUMENT_BATCH_SIZE, KNOWLEDGE_DOCUMENT_POLL_SECONDS.
- The consumer has its own explicit gate and graceful shutdown; it can run alongside the independently gated Workflow consumer while Agent Runtime remains disabled. Do not enable it unless server-only Supabase credentials and a healthy scanner are available.
- The embedding consumer is also available on the same shared host as an independently gated process (`ALLPHA_KNOWLEDGE_EMBEDDING_WORKER_ENABLED=true`, module `allpha_api.knowledge_worker`). It requires `ALLPHA_KNOWLEDGE_WORKER_FACTORY=allpha_api.knowledge_worker_factory:build_worker` and `ALLPHA_KNOWLEDGE_VECTOR_SINK_FACTORY=module:function` whose factory returns `IdempotentKnowledgeVectorSink` backed by a repository implementing atomic `upsert_batch`, to compose the approved canonical Model Router, durable metering and the approved pgvector repository. It remains disabled until the embedding policy/dimension and physical pgvector repository/search adapter are approved and deployed. No second Railway service is required. Embedding jobs remain queued and sources remain indexed_pending_embeddings until vector persistence and retrieval QA succeed.


For planned Agent tasks that carry Knowledge citations, the API and shared worker must use the same `ALLPHA_KNOWLEDGE_POLICY_FACTORY=module:function`. The worker re-resolves the current consent/grant policy and revalidates owner, Agent, source status/version, chunk identity and content digest immediately before executing the plan. Missing/unavailable policy configuration keeps the task unclaimed; revoked consent or stale source versions fail closed. The task envelope and final receipt persist content-free citations only, never raw document text.

## ENG-P07 Knowledge workers and scanner deployment contract

- The shared Railway host uses the canonical knowledge_worker_factory.build_worker composition for embeddings. It requires the server-side Supabase URL/service-role key, an approved complete ALLPHA_EMBEDDING_* Model Router profile, a durable metering contract, and ALLPHA_KNOWLEDGE_VECTOR_GENERATION_ID.
- Before the embedding consumer can claim a job, the canonical vector repository must receive a successful agent_knowledge_vector_generation_readiness(p_generation_id) receipt. Atomic writes use upsert_agent_knowledge_vectors with the current job ID and lease token, owner/Agent/source/version, model/dimension provenance, and stable idempotency key. Both RPCs are source contracts only until the physical index migration is approved and applied; the production RPCs are currently absent, so embedding remains disabled.
- The remote document scanner contract is allpha.document-scan.v1. Configure all three server-only variables together: ALLPHA_DOCUMENT_SCANNER_URL (HTTPS endpoint), ALLPHA_DOCUMENT_SCANNER_API_KEY, and ALLPHA_DOCUMENT_SCANNER_ALLOWED_HOSTS (comma-separated exact hostnames). The response must include contract_version, verdict (clean or malicious), exact uploaded sha256, and scanner.id, scanner.engine_version, and scanner.signature_version. Redirects, unlisted hosts, missing credentials, mismatched digests, unknown verdicts, and incomplete receipts fail closed.
- Local ClamAV startup is opt-in via ALLPHA_CLAMAV_ENABLED=true and ALLPHA_DOCUMENT_SCANNER_MODE=clamd. The current shared Railway worker service is capped at 1 GB, while ClamAV signature loading previously reached approximately 2.5 GB; therefore local ClamAV must remain disabled on that service. Without a configured remote scanner, only the Knowledge document consumer is disabled; Workflow and other shared consumers continue.

## ENG-P09 billable provider retry boundary

- Embedding retries are permitted only when the adapter can prove the request did not execute (connection was never established) or the provider explicitly returned HTTP 429. The adapter honors a bounded Retry-After value for the latter.
- Provider timeouts, post-connect transport errors, HTTP 408/425 and 5xx are outcome-unknown and terminal for the current billable request. They are not replayed by the router or requeued as a fresh provider call; this prevents duplicate provider charges when the first response may have been lost.
- Text generation remains single-attempt and fail-closed after timeout, transport uncertainty or metering uncertainty. Cross-provider fallback is not enabled until every candidate has an independently approved active tariff/policy and an adapter-level non-execution/idempotency contract. No default provider or fallback is inferred.


### Canonical remote scanner reuse for media workers (source implemented)

- Image, subtitle, Cloudinary transcode and Cloudinary callback workers now use the same allpha.document-scan.v1 authenticated scanner contract already implemented for Knowledge documents. This avoids requiring a second scanner service or loading a 2.5 GB ClamAV signature database into the 1 GB shared Railway worker.
- Remote mode is the default. It pins the exact allowlisted HTTPS hostname to validated public DNS addresses, disables redirects and ambient proxies, validates the scanner/engine/signature identity, requires an exact SHA-256 receipt, and fails closed on missing/ambiguous verdicts. Malware verdicts are terminal; unavailable/missing scanner remains fail-closed with stable error codes for bounded retry handling.
- Local ClamAV is available only when ALLPHA_DOCUMENT_SCANNER_MODE=clamd and ALLPHA_CLAMAV_ENABLED=true, with deployment-pinned engine/signature identity and CLAMAV_HOST. Do not use local mode on the current 1 GB shared Railway worker.
- The media workers remain disabled until the remote scanner endpoint, credential, exact hostname allowlist and immutable scanner identity are configured on the actual worker service; Knowledge scanner configuration on another service is not implicitly inherited.


## ENG-P13 shared Railway media consumer host (source implemented)

- The existing allpha-agent-runtime-worker now composes the canonical image/subtitle, Cloudinary transcode, Cloudinary callback and Cloudinary cleanup consumers through allpha_api.content_worker_host. This reuses the current Railway service and the existing typed content_lifecycle_jobs queue; it creates no new Railway service, queue, event table or media engine.
- Each consumer retains its own explicit configuration gate, claim RPC/job_type, lease token, retry/failure RPC and bounded poll interval. A missing scanner or Cloudinary setting disables only that consumer; sibling Agent Runtime, Workflow and Knowledge consumers remain isolated.
- The shared host closes each worker HTTP client on graceful shutdown. Image batch defaults to one job; Cloudinary transforms are performed by the provider, not local FFmpeg. Local ClamAV remains prohibited on the 1 GB shared host; use the canonical remote scanner.
- Runtime activation remains disabled until the actual Railway worker has its server-only Cloudinary references and the complete remote scanner endpoint/credential/allowlist/identity. The worker service must not be reported as processing media until a real persisted lifecycle job is completed.

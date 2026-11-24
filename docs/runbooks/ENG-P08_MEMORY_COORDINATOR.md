# ENG-P08 — Memory Coordinator Runtime

## Canonical ownership

`MemoryCoordinator` in `apps/api/src/allpha_api/memory_coordinator.py` is the only owner of private Memory policy, proposal, approval, retrieval, correction, pin/unpin, expiry and deletion. Conversation Memory remains sourced from canonical conversations/messages; Knowledge documents and their chunks are not Memory items.

The shared Railway worker host runs the optional retention consumer through `memory_retention_worker.py`. It calls the service-only `expire_agent_memory_items_batch(integer)` RPC. Each invocation expires no more than the configured batch size, scrubs content, digest, source reference and provenance, clears pin state, and writes a pseudonymous system event with no human actor attribution. The RPC uses `FOR UPDATE SKIP LOCKED` so concurrent worker replicas do not claim the same rows.

## Runtime configuration

The consumer is disabled unless all of the following are explicitly configured server-side:

- `ALLPHA_MEMORY_RETENTION_WORKER_ENABLED=true`
- `ALLPHA_MEMORY_COORDINATOR_ENABLED=true`
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY` (or the already-supported server-only `SUPABASE_SECRET_KEY`)
- Optional `ALLPHA_MEMORY_RETENTION_BATCH_SIZE` (default 100, range 1–500)
- Optional `ALLPHA_MEMORY_RETENTION_POLL_SECONDS` (default 60, range 10–3600)

Do not enable the consumer until the existing ADR-0022 Privacy/Security and Data Platform activation review and the applicable production migration/recovery requirements are evidenced. The code and migration are source implementation only until the canonical deployment prerequisites are met. Never put credentials in this file, client bundles, logs or Git.

## Failure behavior

- Missing coordinator activation or server credentials prevents startup.
- Invalid boolean or numeric configuration prevents this consumer from starting; the shared host isolates the failure from sibling consumers.
- RPC or database failure is logged without exposing Memory content; the next bounded poll retries.
- A malformed expiry receipt is treated as a persistence failure.
- No Memory text is copied to Workflow checkpoints, events, notifications or logs.
- Retention expiry does not delete immutable audit events; account deletion continues to use the canonical P03 pseudonymous audit policy.

## Focused verification

`apps/api/scripts/verify_eng_p08_memory_coordinator.py` applies the migration to disposable PostgreSQL 17 and verifies bounded expiry, system event attribution, content scrubbing and service-only execution. Unit tests cover the coordinator contract, worker gating, bounded batches and clean shutdown. These checks do not activate the production consumer or prove production recovery.

# ENG-P08 — Memory Coordinator Runtime

## Canonical ownership

`MemoryCoordinator` in `apps/api/src/allpha_api/memory_coordinator.py` is the sole owner of private Memory policy, proposal, approval, retrieval, correction, pin/unpin, expiry and deletion. Conversation Memory remains sourced from canonical conversations/messages; Knowledge documents and their chunks are not Memory items.

Retention uses the existing canonical Supabase PostgreSQL `pg_cron` schedule `allpha-memory-retention` at five-minute cadence. The forward-only migration `20261124100000_eng_p08_memory_retention_worker.sql` defines a service-only bounded batch RPC and replaces the existing cron command with `expire_agent_memory_items_batch(500)`. This keeps one scheduler and one Memory lifecycle; there is no separate Railway retention consumer or duplicate Memory engine.

Each invocation expires at most 500 due items, uses `FOR UPDATE SKIP LOCKED` for safe concurrent claims, scrubs content/digest/source reference/provenance/pin state, and writes a pseudonymous system event without assigning a human actor. The RPC is executable only by `service_role`.

## Runtime behavior

- The existing `allpha-memory-retention` cron job runs every five minutes when the managed `pg_cron` extension is available.
- The migration first removes any existing job with that canonical name, then installs the bounded RPC command at the same cadence. It does not create another job or a Railway worker.
- The owner-scoped Memory API continues to expire its own namespace before listing/retrieval; canonical cron expiry covers due records independently of user traffic.
- If `pg_cron` is unavailable, no substitute scheduler is silently enabled. The migration remains source-only until the existing approved database migration/recovery prerequisites are met.

## Failure and privacy behavior

- The batch limit is bounded to 1–500.
- A database/RPC failure does not produce a successful expiry receipt.
- Expired content is scrubbed; immutable audit events remain.
- No Memory text is copied to Workflow checkpoints, events, notifications or logs.
- Account deletion continues to use the canonical P03 pseudonymous audit policy.

## Focused verification

`apps/api/scripts/verify_eng_p08_memory_coordinator.py` applies the migration to disposable PostgreSQL 17 and verifies bounded expiry, system event attribution, content scrubbing and service-only execution. This does not apply the migration to production or prove production recovery. Production activation remains subject to the existing ADR-0024 backup/PITR/recovery requirements.

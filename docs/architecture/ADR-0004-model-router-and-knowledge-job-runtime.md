# ADR-0004: Model Router and Knowledge Job Runtime

- Status: Accepted for source implementation; non-production validation pending
- Scope: ENG-P09 canonical AI Gateway/Model Router and ENG-P07 knowledge indexing jobs
- Date: 2026-10-14

## Repository evidence

The API currently runs as a single FastAPI container (apps/api/Dockerfile). Its declared dependencies in apps/api/pyproject.toml do not include a broker or worker framework. The knowledge API persists job records in Supabase/PostgREST (agent_knowledge_jobs) and emits an embedding_indexing stage, but no atomic claim/lease worker, canonical embedding router, broker consumer, or job runtime was found in the inspected repository tree.

This supports a durable database-backed job record, but does not prove that a safe multi-worker queue runtime already exists. A database row alone is not an atomic lease/claim protocol.

## Constraints

1. All provider/model execution MUST pass through the canonical AI Gateway/Model Router.
2. ENG-P09 must own model policy/capability selection, provider adapters, timeout and bounded retry policy, usage/cost attribution, and stable provider errors.
3. Feature modules must not call a provider SDK or endpoint directly.
4. Worker claims must be atomic and lease-based; job finalization must verify lease ownership and current source version.
5. A missing router or unsupported embedding capability fails closed. No guessed provider, model, dimension, broker, or worker framework.
6. Vector index schema and retrieval readiness remain blocked until the selected embedding capability and its dimension/version policy are confirmed.
7. All database changes remain source-only until validated in an approved isolated non-production environment.

## Options to evaluate

### A. Postgres-backed queue with atomic RPC claim/lease
- Pros: uses the existing canonical Postgres source of truth and avoids a second queue service.
- Risks: requires carefully tested SKIP LOCKED/lease semantics, concurrency behavior, retry scheduling, visibility timeout, worker deployment and operational monitoring.

### B. Dedicated broker plus worker service
- Pros: purpose-built delivery and worker scaling features.
- Risks: introduces infrastructure, delivery semantics, secrets, operational cost and a new failure boundary; no broker configuration was found in the current repository inspection.

### C. Existing canonical Workflow Engine/runtime
- Pros: avoids duplicating durable orchestration if that runtime already exists and is approved.
- Risks: must verify its actual availability, job contract, deployment and ownership before integrating.

## Decision required

The architecture owner must confirm which runtime is canonical and available in the target environment. Until then, implementation may define typed contracts and tests but must not claim a live worker or create a provider-specific embedding implementation. Physical vector-index dimensions remain an explicit follow-up decision after the Model Router's approved model policy is known.

## Implementation status (2026-10-14)

The source now includes `apps/api/src/allpha_api/knowledge_worker.py`, a lease-based worker entrypoint that claims only `embedding_indexing`, checks the claimed source version and sensitivity classification, routes every batch through the canonical Model Router, and requires an injected idempotent vector sink. The worker finalizes successful embedding work as `embedding_indexed_pending_retrieval_qa` at 95%; it never marks a source `ready`. The executable `allpha-knowledge-worker` refuses to start unless `ALLPHA_KNOWLEDGE_WORKER_FACTORY=module:function` is configured. No factory, approved provider adapter/model policy, or vector sink is configured in the repo/deployment, so this is implemented source, not an enabled live worker.

The source-only migration filters atomic lease claims by stage and adds a nullable constrained source sensitivity field. Existing source records are not assigned a guessed sensitivity. Unit tests cover stage selection, stale source-version refusal, missing router retry, and missing sensitivity fail-closed. Expired lease recovery and database finalization are implemented in SQL but remain unverified until the migration is run in approved isolated non-production with concurrent worker tests.

## Acceptance evidence

- Router contract tests include absent router, valid response, provenance mismatch, invalid dimensions, timeout, retryable and terminal failures.
- Queue tests must prove concurrent claims do not duplicate work, expired leases recover, stale source versions cannot publish, and finalization requires the current lease. SQL concurrency/privilege tests remain pending approved isolated non-production.
- Router tests cover missing route, route identity/provenance mismatch, bounded transient retry, and metering callback. Provider adapter contract, real metering persistence, timeout regression, and deployment configuration remain pending.
- Integration tests use only the approved isolated non-production environment.

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


## ENG-P09 follow-up — approved runtime cost policy and metering contract (2026-10-15)

- `CanonicalModelRouter` now exposes a runtime readiness gate. Knowledge worker startup requires this canonical router, explicit per-sensitivity budgets, route-matched estimates, a `CostPolicyApproval` reference, and an `IdempotentMeteringSink`; missing any prerequisite stops startup before the worker can claim jobs.
- `CostPolicyApproval` records policy ID, version and an external approval reference. The object is only a reference/attestation field; it does not itself create or prove reviewer approval. No production approval or provider pricing has been fabricated.
- `apps/api/src/allpha_api/metering_contract.py` defines the canonical immutable metering record and sink contract. A sink implementation must durably commit before success, treat same idempotency key + same fingerprint as a no-op, reject same key + different fingerprint, and propagate storage errors. The contract has no DB schema, persistence adapter, currency mapping, or provider-specific prices yet.
- Provider SDK integration remains an adapter behind `EmbeddingAdapter` and `CanonicalModelRouter`. No concrete provider was selected or activated; adapter execution is bounded by route identity/version validation, request timeout, bounded transient retries, provenance validation, and cost checks.
- Unit/contract tests were added in `apps/api/tests/test_metering_contract.py` and extended in `apps/api/tests/test_model_router.py`. They have not yet been observed passing in GitHub Actions and must not be reported as passed until a matching run is inspected.
- This source-only change does not enable the worker in a deployment, write production data, apply migrations, select model/dimensions/index, enable pgvector/hybrid retrieval, or establish non-production integration evidence. ENG-P37 remains the consolidated staging acceptance phase.

## ENG-P09 follow-up — explicit units, durable metering adapter and live-schema reconciliation (2026-10-15)

- Reconciled against Master PRD §§20, 63–64: each metering event needs quantity/unit, estimated/actual cost, pricing/entitlement version, timestamp and idempotency; the credit ledger is append-only and must support reservation, release, consumption and reversals. Usage metering is not itself credit settlement.
- Read-only inspection of the connected canonical Supabase project found no existing table/column names matching usage, metering, ledger, credit, billing, cost or budget in non-system schemas. This is a production schema observation only; it is not staging validation. No SQL was executed that changes data/schema.
- CostEstimate, CostBudget, EmbeddingResponse and MeteringRecord now require explicit usage unit, cost unit and pricing version whenever attribution is present. The router checks unit/version consistency and rejects partial attribution. No real unit, currency, rate card or pricing formula has been selected; test identifiers are test-only.
- Added source-only migration apps/api/supabase/migrations/20261015091500_eng_p09_usage_metering_contract.sql. It proposes an append-only service-only usage record and transactional RPC: same idempotency key + same fingerprint is a no-op; same key + different fingerprint raises a conflict. Table access is revoked from clients and service_role direct table access is revoked; the RPC is service_role-only. Migration has NOT been applied to any database.
- Added apps/api/src/allpha_api/supabase_metering_sink.py, a backend-only service-role PostgREST adapter for the RPC. The adapter fails closed on non-success responses and maps idempotency conflicts to a stable contract error. This is a concrete source adapter, not proof of live durability until the migration and concurrency behavior are tested in approved isolated non-production.
- Runtime cost policy now requires a trusted CostPolicyApprovalVerifier to confirm an active approval reference. Missing verifier, denied approval or verifier exception fails closed. No production verifier/configuration or provider is configured, so the knowledge worker remains disabled.
- Credit reservation/settlement/release and the canonical credit ledger remain unimplemented because the connected schema contains no ledger and no approved conversion policy from provider cost units to AI Credits. Do not infer a 1:1 conversion or create financial ledger entries from usage metering.
- Test evidence: GitHub Actions Allpha Smoke run [38712468777](https://github.com/urbanrealty36-ops/Allpha-AI-Aplikasi/actions/runs/38712468777) on commit 1cde6f381276df788bf74bd69e594c6c438da9a8 completed successfully. API pytest apps/api/tests: 216 passed, 1 warning; Web npm test and npm run build passed; Native npm test and npm run typecheck passed. These are source/CI checks, not live database or provider integration.
- Non-production migration, transaction/concurrency, authorization, external provider adapter, and real persistence checks remain deferred to the approved isolated target and consolidated ENG-P37 acceptance. No provider/model/dimension/index choice, pgvector, worker activation or hybrid retrieval is authorized by this source work.


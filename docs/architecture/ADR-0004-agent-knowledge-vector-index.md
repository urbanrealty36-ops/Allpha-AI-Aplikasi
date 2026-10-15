# ADR-0004: Canonical Agent Knowledge Vector Index

- **Status:** Product Owner direction accepted; physical schema activation blocked pending embedding profile/dimension and Data Platform approval.
- **Scope:** ENG-P07–ENG-P09; embedding/indexing, retrieval and Model Router.
- **Decision owner:** Product Owner; Data Platform and AI Platform approval required before schema migration or activation.
- **Last updated:** 2026-10-15

## Context

The canonical application source of truth is Supabase PostgreSQL. The existing knowledge lifecycle includes source/job/chunk contracts and a full-text index, but the inspected repository/schema evidence does not establish an approved physical vector table/column, embedding model/dimension, active index generation, or vector RPC contract. The vector sink already requires stable idempotency, lease/request identity, payload-conflict detection and provenance.

Hybrid retrieval must not run against an invented table, dimension, RPC or unverified index generation.

## Decision

Use **pgvector in the canonical Supabase PostgreSQL project** as the target vector store, conditional on confirming extension availability and approving the embedding profile, fixed index dimension and schema/migration. Do not add an external vector database or second source of truth under this decision. This records the Product Owner's target direction; it is not permission to migrate or activate vectors.

### Logical schema contract (source/design contract, not applied SQL)

A versioned vector-index generation must identify at minimum:

- immutable generation_id and lifecycle state (building, active, retired, failed);
- embedding contract version (allpha.embedding.v1 initially), provider/model identifiers and model version;
- exact embedding dimension and distance metric, plus index type/parameters;
- source/chunk identity, owner ID, Agent ID, source version, content SHA-256 and sensitivity;
- stable idempotency key and payload fingerprint for replay conflict detection;
- created/updated timestamps and operational failure metadata without storing private text in logs.

Each persisted vector record must be uniquely scoped to generation + source version + chunk identity. Ownership/source references must be constrained to the canonical knowledge tables where supported by their actual schema. Vector writes must atomically verify the current source version and worker lease, and retries with the same key and same payload must be idempotent; the same key with a different payload must fail with a conflict.

### Query/index contract

- Use a dimension-specific pgvector index only after the selected Model Router capability pins the exact dimension. Do not guess that value from examples or provider defaults.
- Use cosine distance only if the selected embedding capability and evaluation confirm cosine is appropriate; otherwise record the approved metric. No metric is selected by this ADR alone.
- Query only the active generation. Building a new generation must not change reads until it is fully populated and evaluated; promotion changes the active-generation pointer atomically. Retired generations remain available only for bounded rollback and are removed according to the approved deletion/retention policy.
- The vector query must apply owner, Agent, source status ready, sensitivity, consent/grant and source-version filters inside the canonical database query before returning candidates. RLS remains defense in depth.
- Hybrid ranking merges keyword and vector candidates with stable source/chunk/version identity. Results may be labeled hybrid only when both real adapters run against the same authorized corpus and active approved generation. Keyword-only results remain keyword.
- Return and trace the generation ID and embedding provider/model/version provenance. Never expose private embedding values to clients.

### Versioning and rebuild protocol

1. Register an immutable embedding profile/version and fixed dimension through the canonical Model Router capability contract.
2. Create a new index generation; do not overwrite vectors from a different model, dimension, contract or source version in place.
3. Backfill/index via lease-fenced, idempotent jobs; reject stale source versions and conflicting idempotency replays.
4. Evaluate retrieval against an approved relevance dataset and thresholds, plus latency/cost and zero-cross-owner/Agent leakage requirements.
5. Atomically promote the generation only after acceptance; retain the prior generation for the approved rollback window.
6. On model change, dimension change, policy change affecting source eligibility, or incompatible contract, create a new generation and re-index. On source deletion/revocation, remove or make the affected vectors immediately ineligible and propagate deletion to all generations.
7. Rollback disables vector search or restores the previous verified generation; never fall back to unrestricted search.

## Explicit blockers before physical schema/migration

The provider/model/model-version, exact dimension, distance metric, index type/parameters, active-generation pointer contract, metering persistence contract, relevance dataset/thresholds, deletion/retention semantics and actual pgvector availability must be verified/approved. This ADR does not fabricate those values. Until then, keep the vector repository injected/unconfigured, do not add/apply a physical vector migration, do not activate the worker, and do not enable hybrid retrieval.

## Acceptance evidence

- Contract tests validate model/profile/version/dimension compatibility, response provenance and chunk hashes, source-version fencing, stable idempotency and conflict rejection.
- Schema/migration tests cover fresh install, upgrade, grants/RLS, index creation, concurrent claims, lease expiry, stale source versions, promotion/rollback and deletion propagation in an already-existing isolated non-production environment.
- Relevance, leakage, latency and cost acceptance thresholds are recorded before activating hybrid retrieval.
- Data Platform and AI Platform approval is recorded before any physical schema migration or runtime activation. Production DB is not a test environment.

## Rollback

Disable the vector adapter and retain explicit keyword-only mode only if ADR-0003 policy is implemented, approved and configured. If neither safe path is available, retrieval returns the stable unavailable error; never fall back to unrestricted retrieval.

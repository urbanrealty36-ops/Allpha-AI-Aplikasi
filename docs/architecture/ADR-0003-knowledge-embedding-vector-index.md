# ADR-0003: Knowledge Embedding and Vector Index Contract

- Status: Proposed — provider/model and physical vector-index dimension require an explicit architecture decision before production implementation.
- Date: 2026-10-14
- Scope: ENG-P07 knowledge ingestion and ENG-P09 Model Router integration.

## Context

The Master PRD sections 18–20 and 27–30 require durable bounded jobs, canonical AI Gateway/Model Router routing, owner-private knowledge, hybrid vector + keyword retrieval, provenance, evaluation, and fail-closed readiness. The current ENG-P07 API emits durable `embedding_indexing` jobs, but the repository does not yet contain a canonical Model Router embedding adapter or a vector retrieval implementation.

The PRD explicitly leaves embedding/reranking providers and worker technology open. A provider, model, vector dimension, or public endpoint must not be guessed.

## Proposed contract

An embedding request MUST contain:
- `contract_version`, `task_id`, `trace_id`;
- `owner_id`, `agent_id`, `source_id`, `source_version`;
- ordered chunk identifiers, content hashes and text;
- sensitivity classification and permitted data policy;
- bounded timeout, attempt number, and idempotency key.

A successful response MUST include:
- selected provider/model identity and immutable model version;
- output dimensions, normalized vector values and matching chunk identifiers/hashes;
- usage/cost metadata when available, request/trace IDs, and completion timestamp.

The caller MUST validate response cardinality, finite numeric values, dimensions, exact chunk/hash correspondence and model identity. Provider errors must use a stable error code and be classified as retryable or terminal. Retries must be bounded, exponential/jittered, budget-aware and idempotent where supported. Secrets and document text must not be logged.

## Required indexing invariants

1. Every job, chunk, embedding, evaluation and index record is scoped by owner, Agent, source ID and source version.
2. Worker claims must be atomic and lease-based; only the current lease holder may finalize a job.
3. A job whose source version is no longer current may finish cleanup but MUST NOT publish an index or change the current source to `ready`.
4. A source can become `ready` only after every eligible chunk has a matching embedding, index metadata matches the selected model/version/dimension, hybrid retrieval filters enforce access at query time, and a versioned retrieval evaluation passes.
5. Failure, timeout, missing scanner verdict, incomplete embeddings, failed evaluation or stale source version leaves the source not-ready.
6. Source replacement/deletion must invalidate or remove derived chunks, embeddings, caches and index entries according to the same ownership/version scope.

## Open decisions required before physical vector index

- Select the approved embedding capability/model policy through the canonical Model Router; do not hard-code a provider.
- Decide how model dimensions are represented/indexed (fixed-dimension index per configured model versus a validated model-specific index strategy).
- Confirm the queue/lease mechanism supported by the canonical worker runtime.
- Confirm retrieval evaluation dataset, thresholds and evaluator version.
- Confirm the isolated non-production environment for migration/RLS/integration testing.

## Options and trade-offs

- Fixed-dimension vector column/index: fast and simple retrieval, but locks a dimension and needs a versioned migration when changing dimensions.
- Separate physical index per model/dimension: supports controlled model migration and parallel evaluation, but increases schema/operations complexity.
- Unindexed flexible vectors: flexible for prototypes, but does not satisfy production vector-index performance/acceptance and is not a release solution.

## Consequences

Until the open decisions are approved and the canonical router/worker exist, do not claim vector indexing, retrieval readiness, or ENG-P07 completion. Keep migrations source-only and do not apply them to production Supabase.

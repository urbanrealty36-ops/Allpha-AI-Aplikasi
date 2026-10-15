# ADR-0004: Canonical Agent Knowledge Vector Index

- **Status:** Proposed — awaiting Product Owner and Data Platform approval
- **Scope:** ENG-P07–ENG-P09; embedding/indexing, retrieval and Model Router
- **Decision owner:** Product Owner with Data Platform and AI Platform owners
- **Last updated:** 2026-10-15

## Context

The canonical application source of truth is Supabase PostgreSQL. The existing knowledge lifecycle includes source/job/chunk contracts and a full-text index, but the currently inspected migration/schema evidence does not establish an approved physical vector table/column, embedding model/dimension, active index generation, or vector RPC contract. The vector sink already requires stable idempotency, lease/request identity, payload-conflict detection and provenance.

Hybrid retrieval must not run against an invented table, dimension, RPC or unverified index generation.

## Options

1. **PostgreSQL full-text only.** Lowest operational complexity; valid fallback but does not provide vector retrieval.
2. **pgvector in the canonical Supabase PostgreSQL project.** Keeps source of truth and authorization close to canonical data; requires extension availability, approved embedding dimensions/model contract, indexing strategy, query performance tests and RLS/SQL review.
3. **External vector database.** Potentially useful for scale, but adds a second data system, synchronization/deletion obligations, tenant-isolation and operational failure modes; requires an explicit ADR and security review before adoption.
4. **Use an unversioned or guessed vector RPC/schema.** Rejected: cannot prove dimension compatibility, active-generation fencing, authorization or safe rollout.

## Proposed decision

Prefer option 2, conditional on read-only inspection confirming pgvector support and an approved provider-neutral embedding contract through the canonical Model Router. This is a recommendation, not an approval to migrate or activate the index.

Before implementation, approve and version:
- embedding provider/model capability, dimension and version;
- canonical vector schema, ownership/source/version/chunk foreign-key or equivalent constraints;
- index type/parameters and query function contract;
- active index generation and source-version fencing;
- owner/Agent/sensitivity/status=`ready` filtering in the database query;
- idempotency key and conflicting-payload behavior;
- backfill, reindex, rollback/forward-repair and deletion propagation;
- retrieval relevance dataset, thresholds, latency and cost budgets.

## Consequences and acceptance evidence

- Keep keyword-only retrieval explicitly labeled `keyword`; do not return `hybrid` until the approved vector adapter and active generation are real.
- Do not add or apply a database migration until this ADR and the schema contract are approved.
- Verify fresh-install and upgrade migrations, concurrent workers, stale source versions, lease expiry, idempotent retries and payload-conflict rejection.
- Test cross-owner/Agent isolation, sensitivity filters, RLS and real retrieval against isolated Supabase staging.
- Record index generation and embedding/model provenance in returned results and traces.

## Rollback

Disable the vector adapter and retain the explicit keyword-only mode only if its sensitivity policy is independently approved and configured. If neither safe path is configured, retrieval must return a stable unavailable error; never fall back to unrestricted retrieval.

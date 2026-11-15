# ADR-0022 — Canonical Agent Memory Coordinator and Lifecycle

- **Status:** PROPOSED — NOT APPROVED
- **Date:** 2026-11-16
- **Scope:** WP-07 / ENG-P06 and ENG-P10 (Memory, Knowledge, Agent Runtime, Generation and Workflow context)
- **Decision owners:** Product Owner, Platform Architecture, Security/Privacy
- **Implementation owner:** Agent Intelligence Engineering
- **Approval required before:** memory schema creation, persistent memory writes, retention-policy activation, embedding/index changes, or exposing memory controls as enabled product functionality.

## Context

The Master PRD v3.1 defines six distinct memory classes: Working, Conversation, Episodic, Semantic, Procedural and Long-term. It separately defines the Knowledge corpus and Published Knowledge. The model may propose a memory write, but cannot force persistence. Memory writes require consent, purpose, classification, ownership, provenance, duplication/conflict handling, confidence, retention/expiry and correction/deletion controls.

The current repository contains:
- canonical conversations and messages tables, already used for bounded Conversation Memory;
- Knowledge ingestion, chunks, full-text search and a provider-neutral EmbeddingRequest / EmbeddingResponse contract;
- Agent Runtime policy, pinned Agent/Skill versions and durable task/workflow state;
- no dedicated canonical Memory Coordinator API/service or memory-specific persistence tables in the inspected public schema;
- no ADR-0004 or ADR-0005 memory documents in docs/ADR, despite older phase notes referring to them as memory gates.

Knowledge corpus and personal/Agent memory must remain separate authorities. A vector table or a Knowledge chunk must not silently become private memory.

## Proposed decision

### 1. One coordinator, no competing memory engine

Create one FastAPI-owned MemoryCoordinator service under apps/api. It is the only authority for memory policy, proposal, persistence, retrieval scope, expiry, correction, deletion and audit. Agent Runtime and Workflow Engine call this coordinator; they do not create private memory stores or duplicate memory policy.

### 2. Canonical class mapping

| Class | Proposed canonical representation | Lifecycle |
|---|---|---|
| Working | Short-lived task/session context owned by the coordinator | Expiry-bound; never promoted automatically |
| Conversation | Read from canonical conversations / messages | No duplicate transcript store; existing message retention applies |
| Episodic | Persisted event/interaction summary with actor, time and provenance | Proposal → policy decision → active/expired/deleted |
| Semantic | Normalized fact/concept with source, confidence, version and scope | Proposal → policy decision → indexed/retrievable → corrected/deleted |
| Procedural | Reusable task pattern/instruction with source and version | Memory only; never grants tool authority; must pass Skill/Workflow validation |
| Long-term | Owner-approved persistent item with explicit purpose and retention | Consent-bound; inspect/correct/export/delete |

Knowledge corpus, chunks, embeddings and Published Knowledge remain distinct from these six classes.

### 3. Consent and privacy defaults

- Persistent memory is disabled by default for each owner/Agent/type until an explicit owner policy and consent version are recorded.
- The model may create a proposal; only the coordinator may accept or reject it.
- Each item records owner, Agent, scope, purpose, classification, provenance/source reference, content digest, confidence where applicable, policy version and an explicit retention/expiry decision.
- External Consumers receive no owner-private memory by default. A public Agent or a Consumer Grant does not publish or grant access to private memory.
- Procedural memory never authorizes tools, network access, filesystem access, publication or financial effects.
- Deletion first makes an item inaccessible, then propagates through derived summaries, indexes, caches and linked artifacts. The system records completion evidence; it does not claim immediate physical erasure without evidence.

### 4. Proposed persistence boundary

The preferred implementation is one owner-scoped memory item store plus a versioned owner/Agent memory policy and append-only memory lifecycle events. Working Memory may use the same store with mandatory short expiry; Conversation Memory remains sourced from messages. A deletion queue may be added only if asynchronous propagation is needed.

All memory business operations go through FastAPI and the coordinator. Tables remain inaccessible for direct client business writes; RLS is defense-in-depth. No second database or vector store is introduced.

Exact table names, indexes, RLS predicates, RPC boundaries and migration sequence are intentionally deferred until this ADR is approved and the existing consent, retention and deletion contracts are reconciled.

### 5. Retrieval and embeddings

- Retrieval must apply owner/Agent/session/tenant/visibility filters before search and before model-context assembly.
- Use the existing provider-neutral Embedding contract and canonical Model Router only; no feature-specific provider SDK or hard-coded model.
- The embedding model profile, dimensions, index strategy, pricing and fallback behavior must be pinned to an approved route before a memory vector schema is created.
- Keyword/full-text and metadata retrieval can be implemented without guessing embedding dimensions. It must not be described as full hybrid vector retrieval until the approved embedding path and vector index are implemented.
- Memory and Knowledge retrieval traces preserve source IDs, versions, hashes and ACL decisions without logging private memory text.

### 6. Runtime integration

The coordinator exposes bounded context retrieval and write-proposal APIs to:
- Agent Runtime before planning/execution;
- Generation Jobs before Model Router invocation;
- Workflow Engine memory nodes;
- Messaging for Conversation Memory context;
- owner-facing Memory & Knowledge Studio for policy, inspect, correction and deletion.

The runtime receives only the scopes returned by the coordinator. A Consumer task receives only explicitly published memory/knowledge permitted by its current grant; private owner scope remains empty.

## Options considered

1. **One polymorphic memory store + coordinator (recommended):** consistent policy, provenance, retention and deletion; fewer competing schemas. Requires strict type-specific validation and indexes.
2. **Separate physical table per memory class:** stronger physical separation but duplicates lifecycle, policy and deletion logic and risks creating six competing stores.
3. **Reuse Knowledge tables for all memory:** rejected because Knowledge corpus and personal memory have different ownership, consent, purpose, retention and publication semantics.

## Consequences

- Conversation Memory continues to use canonical messages.
- Existing Knowledge ingestion/retrieval remains unchanged and is not relabelled as Memory.
- No memory schema, memory vector dimension, retention default or persistent memory write is activated by this proposal.
- WP-07 Memory acceptance remains blocked until the Product Owner approves this ADR and the implementation adds schema, coordinator, API, owner controls, deletion propagation and source-level evidence.
- Full integration/acceptance remains deferred until the user's specified verification window; source presence alone is not acceptance.

## Approval checklist

- [ ] Product Owner approves the single MemoryCoordinator ownership model.
- [ ] Product Owner approves per-type explicit consent with persistent memory disabled by default.
- [ ] Security/Privacy approves scope, retention, deletion propagation and export/correction behavior.
- [ ] Architecture approves the persistence model and embedding/index profile.
- [ ] Only after approval: implement the versioned migration and FastAPI coordinator in the existing WP-07 / ENG-P06, ENG-P10 owners.

## Rollback

Disable memory writes and retrieval through the coordinator policy; preserve message and Knowledge authorities; revoke public memory projections; mark affected items inaccessible; retain audit and deletion-job state until propagation is reconciled. Do not delete canonical conversations/messages or Knowledge sources as a rollback shortcut.

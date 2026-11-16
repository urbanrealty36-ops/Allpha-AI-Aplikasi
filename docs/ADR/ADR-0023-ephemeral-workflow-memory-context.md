# ADR-0023 — Ephemeral Memory Context for Durable Workflow Execution

- **Status:** PARTIALLY APPROVED — Product Owner approved Option B on 2026-11-16; Privacy/Security, Platform Architecture and Data Platform approval remain required before activation
- **Date:** 2026-11-16
- **Scope:** WP-07 / ENG-P06, ENG-P10 and ENG-P11
- **Owners:** Product Owner, Platform Architecture, Privacy/Security, Data Platform

## Context

ADR-0022 establishes one FastAPI-owned MemoryCoordinator. It owns consent, policy, proposal, retrieval, retention, correction, deletion and audit. Workflow Engine state is durable: workflow inputs, step outputs, checkpoints and events are persisted in Supabase/PostgreSQL.

Persisting Memory text in workflow input/output/checkpoints would create a second durable copy outside the MemoryCoordinator. That copy could survive Memory correction, policy revocation or deletion and would violate the single memory lifecycle and deletion-propagation boundary. A Workflow node must therefore not serialize private Memory content into durable workflow state.

The current canonical Workflow Engine supports deterministic nodes and Agent task scheduling. Memory nodes are not yet implemented. This ADR proposes the safe contract; it does not enable a Memory node or change the accepted Workflow Engine owner.

## Decision drivers

1. MemoryCoordinator remains the only authority for private Memory retrieval and lifecycle.
2. Workflow Engine remains the only authority for durable workflow definitions, runs, steps, checkpoints and recovery.
3. No private Memory text, embedding, snippet, provenance payload or derived summary may be copied to workflow durable records, logs, events, notifications or artifacts.
4. A workflow must re-check current owner, Agent, policy version, consent, purpose, classification and retention at every execution/resume boundary.
5. Revocation/deletion must stop subsequent context resolution; an already-running model invocation must be bounded and must not persist the retrieved text into a checkpoint.
6. Workflow execution must remain resumable without replaying completed side effects or depending on an expired private-context lease.

## Options

### Option A — Persist Memory content in step output/checkpoint (rejected)

This makes replay simple but duplicates private content into a second lifecycle. Deletion and policy revocation cannot reliably scrub every workflow run, event, derived output and export. It violates ADR-0022 and is not acceptable.

### Option B — Persist opaque context lease and resolve at runtime (recommended)

The workflow stores only a non-content selector and a coordinator-issued opaque reference. The reference is bound to owner, Agent, workflow run, node, purpose, policy version and a short expiry. It contains no Memory text and cannot be used as a bearer authorization by a client.

At node execution:
1. Workflow worker claims a step using the canonical lease/fencing contract.
2. The worker asks MemoryCoordinator to resolve the opaque reference using trusted server-side run identity.
3. MemoryCoordinator re-checks current owner/Agent ownership, consent, purpose, classification, policy version, expiry and deletion state before retrieval.
4. Retrieved text exists only in bounded worker memory and the immediate Model Router request context.
5. The worker discards the context after the invocation. It must not place it in step output, checkpoint, workflow event details, exception messages, logs, artifact storage or notification payload.
6. The durable step output stores only non-sensitive execution metadata: coordinator reference ID, policy version, result status, usage evidence and a digest of the resolved source identifiers where approved. No content or source excerpt is persisted.
7. If the lease expires, consent changes, policy version changes, deletion is pending, or the coordinator is unavailable, the step fails closed with a stable policy/re-consent error. Resume must re-resolve current context; it must never reuse stale cached text.

The opaque reference is short-lived and revocable. It is not a general access token, is not exposed to Web/Native clients, and cannot grant tool permissions. A reference must be invalidated when the run is cancelled, the owner revokes consent, the Agent ownership changes, or any referenced Memory item is deleted/expired.

### Option C — Do not support Memory in Workflow

This is the safest immediate fallback and remains the active behavior until Option B is approved and implemented. Workflows may continue to use explicit user input and published Knowledge under their own ACL contract, but may not access owner-private Memory.

## Proposed contract

### Workflow definition

A future memory_context node may declare:
- stable node key and node version;
- memory_type allowlist;
- fixed purpose (workflow_context only after explicit owner consent);
- maximum item count and context byte/token budget;
- classification ceiling;
- retention and expiry behavior;
- failure policy (fail_closed; no silent fallback to unfiltered content).

The node definition must not embed Memory text, a raw query containing private text, user credentials, service-role keys, or a reusable bearer token. Any query input must be separately classified and explicitly authorized; query content must not be emitted to logs or event payloads.

### Coordinator reference

A future coordinator reference must be:
- opaque, unguessable and server-only;
- bound to owner ID, Agent ID, workflow run ID, node key, purpose and policy version;
- short-lived and single-run/single-node scoped;
- revocable on consent/policy/item lifecycle changes;
- unusable by External Consumers and public Agents;
- excluded from user-visible URLs, client storage and exported workflow definitions.

### Runtime data boundary

| Data | Durable workflow state | Runtime-only |
|---|---:|---:|
| Node key/version and purpose | Yes | Yes |
| Opaque reference ID | Yes, if approved | Yes |
| Owner/Agent/run binding metadata | Yes, minimal | Yes |
| Memory content/snippets | **No** | Yes, bounded |
| Memory embeddings/vector payload | **No** | Coordinator only |
| Raw private retrieval query | **No**, unless separately classified and approved | Yes, bounded |
| Policy version / result status | Yes | Yes |
| Source IDs and hashes | Digest/reference only, if approved | Yes |
| Prompt/model output containing Memory | No automatic persistence | Model Router request only; normal output classification/retention still applies |

### Cancellation, recovery and deletion

- Cancellation prevents any new resolution and revokes outstanding context references.
- Worker lease expiry invalidates the in-memory context; a resumed worker must resolve again from current policy.
- If Memory is deleted or expires during a run, no subsequent node may retrieve it. Already-submitted provider requests cannot be recalled; the system must retain only minimal non-content audit evidence and must not create further durable copies.
- Any downstream output that contains derived Memory content requires a separate output classification, retention and deletion-propagation contract before it may be persisted or published.
- Workflow checkpoints store only safe metadata and non-sensitive outputs. If a node cannot satisfy this boundary, it is not eligible for checkpointing and must remain blocked.

## External Consumer and tool authority boundary

The existing ENG-P18 agent_consumer_grants schema permits only public_invoke. It does not grant tool_invoke, arbitrary tool keys, private Memory, Workflow execution, or resource access. The current runtime explicitly blocks External Consumer tool dependencies. This is intentional fail-closed behavior, not an incomplete interpretation of public_invoke.

A future External Consumer tool grant requires a separate approved contract covering per-tool allowlists, permission scopes, Agent/Skill/policy version pinning, consumer identity, budgets/metering, expiry/revocation, idempotency, approval/risk thresholds and durable audit. Do not broaden the existing public_invoke grant or infer tool permission from Skill metadata.

## Consequences

- Option C remains active until Option B receives approval and its source contract is implemented.
- No Workflow Memory node, context lease table, RPC or runtime integration is authorized by this proposal alone.
- Existing Workflow Engine and MemoryCoordinator remain separate canonical owners.
- No new database, broker, vector store, or second Workflow Engine is introduced.
- Acceptance requires source-level tests for content non-persistence, owner isolation, consent revocation, deletion, expiry, lease recovery, replay, output leakage and External Consumer denial; real database/concurrency and cross-client verification remain in ENG-P37.

## Approval checklist

- [x] Product Owner approves Option B as the target contract (explicit approval recorded 2026-11-16).
- [ ] Privacy/Security approves non-persistence, context lifetime, deletion and downstream output boundaries.
- [ ] Platform Architecture approves the opaque reference and Workflow/Coordinator API contract.
- [ ] Data Platform approves schema/RPC, retention and audit implications.
- [ ] Implementation and evidence added to WP-07 fixed phase row.

## Rollback

Disable Memory resolution for Workflow nodes and revert to Option C. Preserve canonical Workflow run history and MemoryCoordinator records. Revoke outstanding references. Do not delete or mutate canonical conversation messages or Knowledge records as a rollback shortcut.

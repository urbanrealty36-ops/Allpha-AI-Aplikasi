# ADR-0007 — Agent Runtime Durable Checkpoints and Approved Policy Binding

- **Status:** Proposed — Product Owner / architecture owner approval required
- **Date:** 2026-10-15
- **Scope:** ENG-P10 Agent Runtime; dependency on canonical orchestration/worker decision in ADR-0004
- **Authority:** Master PRD v3.0 §§24–25, Phase 05 acceptance, Part XIX §§83–86, and AGENTS.md

## Context from verified repository state

- The Master PRD requires durable checkpoints and interruption recovery, with acceptance that a task resumes from the latest valid checkpoint without repeating completed external effects.
- The current ENG-P10 API claims a task by conditional state update, executes the tool in the request worker, then persists the terminal result. It has no durable per-step checkpoint, execution lease token, checkpoint hash, or worker crash/resume protocol.
- The registered executable tool is currently `text.normalize`, a pure deterministic transformation. This is not proof that future side-effecting tools support idempotency.
- Runtime execution currently trusts a non-empty `agent_capabilities.policy_version` string when capability status is approved. No canonical immutable runtime-policy registry was found in the inspected source/migration tree to resolve the string to an approved policy document and verify tool/scope authorization.
- Existing ADR-0004 leaves canonical queue/worker semantics unresolved and requires atomic lease claims and finalization against the current lease/source version. This proposal must not silently override that decision.

## Decision required A — durable execution and checkpoints

### Option A: Postgres-backed canonical task engine

Add immutable versioned checkpoint/effect-receipt records and a server-only atomic claim/finalize RPC with lease ownership, lease expiry, monotonic checkpoint sequence, task version, step key, input fingerprint, and output/result reference. Side-effecting adapters must accept and propagate a stable idempotency key. Resume may skip an effect only when a durable completed receipt matches the exact task/step/input fingerprint. A started effect with no confirmed receipt is an unknown outcome and must not be replayed automatically.

- Pros: one transactional source of truth and auditable state.
- Risks: requires tested SQL concurrency, lease expiry, privileges, crash injection, and adapter idempotency; integration checks remain ENG-P37.

### Option B: Dedicated queue/worker broker

- Pros: purpose-built delivery and worker scaling.
- Risks: new infrastructure and failure semantics; requires an approved broker/worker stack.

### Option C: Delegate to an existing canonical Workflow Engine

- Pros: avoids duplicate orchestration.
- Risks: availability and execution contract must be verified first; no competing runtime may be created.

**Recommendation for review, not an approved decision:** evaluate Option A against ADR-0004. Until the architecture owner approves the canonical execution owner and lease/checkpoint semantics, do not claim crash-safe resume or add a competing worker engine.

## Decision required B — immutable runtime policy reference

Propose a canonical server-owned policy registry with immutable versions scoped to an Agent (or an explicitly approved platform scope), containing a canonical policy document/digest, approved tool keys, required permission scopes, risk constraints, lifecycle status, approver identity and approval timestamp. Capability approval must reference an existing active approved policy version for the same Agent; runtime execution must resolve the reference and verify policy digest/status and tool/scope membership on every execution. Free-form version strings alone are not authorization.

Options:
1. Add an Agent-scoped immutable policy registry and privileged review/approval lifecycle with audit and composite referential integrity.
2. Bind to an already-existing canonical policy registry if the architecture owner can identify and prove its schema/API and lifecycle.

No existing canonical policy registry was identified in this repository inspection. Option 1 is a proposal only; do not implement until approved. Missing registry/reference, revoked policy, mismatched Agent, digest mismatch, or tool/scope mismatch must fail closed.

## Acceptance tests required after decision approval

- Crash before an effect starts: resume safely from the prior checkpoint.
- Crash after effect completion and durable receipt: resume skips the completed effect.
- Crash after effect starts but before completion receipt: mark outcome unknown and do not automatically replay.
- Duplicate effect request with same idempotency key and same fingerprint: one effect; same key with a different fingerprint: conflict.
- Lease expiry/reclaim: only current lease holder may checkpoint/finalize; stale worker cannot overwrite newer state.
- Cancellation racing with claim/finalization cannot overwrite a newer state; terminal states are immutable.
- Event log is ordered and agrees with state transitions.
- Policy reference resolves to an immutable approved policy; revoked/unknown/wrong-agent/wrong-tool/wrong-scope policy is denied.
- Real SQL transaction, privilege, concurrency, RLS/grants, owner-isolation and authenticated cross-app tests run only in the approved isolated staging target under ENG-P37.

## Consequences and current gate

- Source regressions independent of this architecture decision may proceed.
- Durable checkpoint/resume and policy-registry implementation are **BLOCKED pending approval**.
- Existing migrations remain source-only. Do not execute them against production or claim integration verification.
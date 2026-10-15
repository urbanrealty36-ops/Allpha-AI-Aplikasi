# ADR-0007 — Agent Runtime Durable Checkpoints and Approved Policy Binding

- **Status:** Accepted by Product Owner on 2026-10-15; source implementation authorized
- **Scope:** ENG-P10 Agent Runtime; must remain aligned with canonical orchestration/worker decision in ADR-0004
- **Authority:** Master PRD v3.0 §§24–25, Phase 05 acceptance, Part XIX §§83–86, and AGENTS.md

## Accepted decision A — durable execution and checkpoints

The Product Owner approved Option A: PostgreSQL-backed canonical task lifecycle and checkpoint/effect receipts. This does **not** authorize a second queue or competing workflow engine. The existing canonical task API remains the entry point; durable claims, checkpoints and finalization use server-only database functions with lease ownership, expiry and monotonic versions.

Implementation contract:
- Immutable, sequenced checkpoints record task version, step key, input fingerprint, checkpoint hash and result reference/payload.
- Effect receipts are keyed by task/step/idempotency key and input fingerprint. A completed receipt may be reused only when all identity/fingerprint fields match.
- A started effect without a confirmed completed receipt is an unknown outcome. Never replay it automatically.
- Atomic claim/finalize operations compare current lease token, expiry and task version. A stale worker cannot checkpoint or finalize.
- Side-effecting adapters must accept and propagate stable idempotency keys. Current `text.normalize` is pure and does not prove future adapters satisfy this contract.
- Do not claim crash-safe resume until the database implementation is exercised with crash/concurrency tests in ENG-P37.

## Accepted decision B — immutable runtime policy reference

Use an Agent-scoped server-owned policy registry with canonical JSON document and SHA-256 digest, approved tool keys, required permission scopes, risk constraints, lifecycle status, approver identity and approval timestamp. Capability approval must reference an existing active approved policy for the same Agent. Runtime execution resolves and validates the policy on every run; a free-form version string alone never authorizes execution. Missing, revoked, mismatched, or digest-invalid policies fail closed.

Policy content is immutable after creation. Revocation changes lifecycle status and blocks future execution; historical task/checkpoint/effect records remain auditable.

## Scope and compatibility

- This decision selects the Postgres source-of-truth contract; it does not silently settle a separate queue/broker technology or introduce another worker. Any execution-worker deployment details still need to conform to ADR-0004 and must not create a competing lifecycle owner.
- All new migrations remain source-only until ENG-P37's approved isolated staging window. Do not apply migrations or run concurrency experiments against production.
- Real SQL transaction, privilege, concurrency, RLS/grants, owner-isolation and authenticated cross-app tests remain ENG-P37.

## Acceptance criteria

- Crash before effect: resume from the prior valid checkpoint.
- Crash after completed receipt: resume skips the completed effect.
- Started effect without completion receipt: mark unknown and do not replay.
- Same idempotency key/fingerprint is deduplicated; same key with a different fingerprint conflicts.
- Lease expiry/reclaim permits only the current lease holder to checkpoint/finalize.
- Cancellation races cannot overwrite newer state; terminal states are immutable.
- Event order agrees with state transitions.
- Unknown, revoked, wrong-Agent, wrong-tool, wrong-scope or digest-mismatched policies are denied.
- Source/unit/contract checks run in CI; real PostgreSQL behavior remains explicitly unverified until ENG-P37.

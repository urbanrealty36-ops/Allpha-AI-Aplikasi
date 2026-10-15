# ADR-0008 — Canonical Durable Workflow Engine Runtime

- **Status:** Proposed — Product Owner decision required before implementation
- **Date:** 2026-10-15
- **Scope:** ENG-P11 durable workflow orchestration, checkpoint/resume and workflow-run lifecycle
- **Authority:** Master PRD v3.0 §§18, 25–26.4; AGENTS.md §§0–6; fixed phase plan; ADR-0004 (Model Router and Knowledge Job Runtime); ADR-0007 (Agent Runtime durable task lifecycle)

## Context and repository evidence

The Master PRD requires one canonical Workflow Engine with versioned declarative workflows, durable runs and steps, bounded execution, worker leases, retries, cancellation, checkpoints/resume, idempotent effects, progress and trace/cost aggregation. The orchestration layer must delegate durable graph execution to that canonical engine rather than becoming a second hidden workflow engine.

Repository inspection on `main` found:
- ENG-P10 provides authenticated Agent session/task APIs and a server-only Postgres/Supabase task lifecycle/checkpoint/effect-receipt contract. It is the Agent task lifecycle, not a general workflow-definition/run/step engine.
- ENG-P07 `knowledge_worker.py` and its lease-based knowledge job store are specialized for knowledge indexing; they are not a general workflow engine.
- No general Workflow Engine module, workflow definition/version/run/step persistence schema, or canonical workflow worker was found in the inspected API source and migration tree.
- ADR-0004 explicitly states that the canonical runtime/queue choice is unresolved and warns against assuming an existing worker or broker.
- No live schema changes or staging experiments were run for this decision.

Therefore the first ENG-P11 implementation cannot safely assume an existing canonical Workflow Engine or silently choose a second runtime.

## Decision drivers

1. One canonical engine owns workflow definitions, run/step lifecycle and business truth.
2. PostgreSQL/Supabase remains the transactional source of truth; do not introduce another database.
3. Workflow definitions are declarative, typed, schema-validated, versioned and non-executable.
4. Reuse ENG-P10's lease/checkpoint/effect idempotency principles where compatible without making Agent tasks and general workflow runs the same domain entity.
5. Bounded retries, execution time, loops, concurrency and spend; cancellation and recovery must be durable.
6. No provider SDK bypass: model execution routes through the canonical AI Gateway/Model Router.
7. Source-level tests can be implemented now after decision approval; actual migration, SQL concurrency, RLS/grants and cross-app acceptance remain at ENG-P37.
8. Do not introduce a broker, worker framework, or deployment topology without explicit evidence and an approved decision.

## Options

### Option A — PostgreSQL-backed canonical Workflow Engine (recommended)

Implement a single Workflow Engine in `apps/api` backed by canonical Supabase/PostgreSQL. Store immutable workflow definition versions and schema-validated node/edge definitions; durable run/step/event/checkpoint records; execution lease/version fencing; idempotent effect receipts; bounded retry/cancel/resume operations; and typed FastAPI contracts. Use atomic database RPCs for claim/finalize where needed. A worker process/deployment is a separate decision only if operational evidence shows it is required; do not invent a broker now.

**Pros:** one transactional source of truth, aligns with ADR-0007's Postgres-backed lease/checkpoint/effect contract, no additional database/broker, can start with bounded deterministic node types.

**Trade-offs:** PostgreSQL claim/lease contention and retry scheduling require careful SQL and real concurrency tests; worker polling/throughput and operational monitoring need explicit limits; schema/RPC complexity is higher than a simple in-process runner.

**Consequences:** add versioned migrations after approval; source implementation starts with declarative schema validation and deterministic no-side-effect nodes, then durable run/step lifecycle. External side effects remain disabled unless an approved adapter provides idempotency and outcome reconciliation.

### Option B — Dedicated broker and worker runtime

Use a dedicated broker plus worker service to deliver workflow jobs, while keeping PostgreSQL as the business source of truth.

**Pros:** purpose-built delivery and scaling characteristics; worker pools can be isolated by workload.

**Trade-offs:** new infrastructure, secrets, delivery/replay failure boundaries, deployment and cost; does not remove the need for canonical workflow/run/step persistence and idempotency. No broker configuration was found in the current repository.

**Consequences:** requires a separate ADR covering broker choice, worker topology, delivery semantics, operations, secrets, migration and rollback. Not recommended as the first implementation without measured requirements.

### Option C — Adopt an existing canonical Workflow Engine

Integrate an existing approved workflow engine/runtime if one is demonstrably present and deployed.

**Pros:** may avoid implementing durable orchestration primitives.

**Trade-offs:** repository inspection did not find a general workflow engine or canonical workflow run/step store. Selecting an external service or undocumented runtime would be an unsupported assumption.

**Consequences:** remains viable only if the Product Owner identifies an existing canonical engine and provides verifiable repo/deployment/configuration evidence. Do not infer one from the specialized ENG-P07 knowledge worker or ENG-P10 Agent Runtime.

## Recommendation / approval request

Approve **Option A** as the canonical Workflow Engine implementation for ENG-P11, subject to these boundaries:
- PostgreSQL/Supabase is the only durable source of truth.
- ENG-P10 remains the Agent task lifecycle; workflow steps may reference or invoke Agent tasks through the canonical API/engine contract, but do not duplicate task state.
- ENG-P07 knowledge worker remains specialized and must not become the general workflow runner.
- Do not add a broker, external workflow service, or separate database in this ADR.
- Do not apply migrations to canonical production. Real SQL/concurrency/RLS/grants and authenticated cross-app acceptance stay in ENG-P37 on an explicitly approved isolated non-production target.
- Build the first implementation slice only after the Product Owner approves this decision.

## Rollback and compatibility

No database or runtime changes are part of this proposal. After approval, use additive versioned migrations; preserve immutable workflow versions and run history. Any schema rollback must use a reviewed forward-repair or compatibility migration rather than deleting run/checkpoint/effect history. External effects must never be replayed blindly during recovery.

## Acceptance criteria after approval

- Workflow definitions are versioned, declarative and validated; arbitrary code is never executed.
- A run pins an immutable workflow version and trusted owner/tenant context.
- Every step has explicit input/output schema, permission scope, side-effect classification, timeout/retry policy, idempotency rule and bounded resource budget.
- A validated step result/checkpoint is durably recorded before dependent steps advance.
- Lease/version fencing rejects stale workers; cancellation cannot overwrite newer/terminal state.
- Retry/resume skips completed safe steps and does not replay an uncertain side effect.
- Owner-scoped authorization and fail-closed behavior are covered by tests.
- Unit/contract/regression CI is green before changing source status; real database and cross-app acceptance remains deferred to ENG-P37 until actually executed.


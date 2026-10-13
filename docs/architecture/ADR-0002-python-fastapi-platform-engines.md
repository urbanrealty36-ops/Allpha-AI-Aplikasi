# ADR-0002: Python + FastAPI for Canonical Backend and Platform Engines

- **Status:** Accepted
- **Date:** 2026-10-13
- **Scope:** Canonical backend and domain engines across ENG-P01–ENG-P37
- **Decision owner:** Product owner (explicit direction)

## Decision

All server-side business authority and platform engines use **Python with FastAPI** as the canonical backend/API stack. This includes API gateway; identity, authorization and system security; AI Gateway and Model Router; Agent Runtime and Orchestration Engine; durable workflows and workers; Memory, Knowledge, retrieval and privacy filters; usage metering, quotas, audit and observability; spatial/asset catalog APIs; and privileged domain operations.

The current canonical service is `apps/api`. Keep it modular with explicit route/schema, service, repository, policy, worker, event and test boundaries. Split a process into a separate deployable worker only when isolation, scaling or resource needs justify it; do not create duplicate engines or sources of truth.

## Boundaries

- `apps/client` (React Native + Expo native prebuild), `apps/web` and `apps/super-admin` are clients. They call versioned FastAPI contracts and never become authorities for permissions, model routing, memory access, budgets, workflow state or business settlement.
- Supabase PostgreSQL remains the transactional source of truth; migrations are version-controlled. RLS is defense in depth, not a substitute for API authorization.
- All model/provider calls go through the canonical Python Model Router. Feature modules must not call providers directly.
- Private memory is authorized and filtered by the backend before context reaches a model. Model output cannot grant access or trigger privileged effects by itself.
- Long-running orchestration uses durable job state, bounded retries, idempotency, cancellation, checkpoints and traceable recovery.
- No secrets or service-role keys are shipped to native/web clients.

## Consequences

- Python/FastAPI is the default implementation language/framework for backend, engines, orchestration, model routing, memory and security.
- ENG-P01 establishes service boundaries and honest health/readiness signals. Domain engines are implemented in their owning phases, not duplicated prematurely in the foundation phase.
- Tests cover contracts, authorization-deny paths, budget/policy enforcement, provider failures and workflow recovery as each engine is implemented.

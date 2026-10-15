# ADR-0003: Agent Knowledge Sensitivity Policy

- **Status:** Proposed — awaiting Product Owner and Privacy/Security approval
- **Scope:** ENG-P07–ENG-P09; Agent knowledge ingestion, retrieval and context assembly
- **Decision owner:** Product Owner with Privacy/Security and Data Platform owners
- **Last updated:** 2026-10-15

## Context

The current retrieval boundary authenticates the Human, verifies active Agent ownership, uses the caller's Supabase access token so RLS remains authoritative, and accepts no owner ID or sensitivity allowlist from client input. Keyword runtime is opt-in and fails closed when `ALLPHA_KNOWLEDGE_ALLOWED_SENSITIVITIES` is absent or invalid. That deployment-level allowlist is a safety switch, not a complete owner/Agent/tenant policy.

The Master PRD requires private memory and documents to remain private by default, query-time authorization, provenance, consent-aware lifecycle and deletion propagation. A broad platform allowlist alone cannot express the owner’s purpose, sharing scope, retention or Agent-specific permissions.

## Options

1. **Deployment-wide allowlist only.** Minimal and fail-closed; insufficient for owner/Agent-specific consent and data scopes. Keep only as a temporary disabled-by-default gate.
2. **Client-supplied sensitivity.** Rejected: clients cannot authorize access or elevate allowed classifications.
3. **Server-side policy resolution.** Resolve permitted classifications from authenticated owner, Agent, tenant/resource scope, consent, purpose and source lifecycle. Enforce it in the canonical API/data query; deny when policy or provenance is missing. This is the recommended target, subject to approved schema and policy contract.
4. **Allow every classification to simplify retrieval.** Rejected: violates least privilege and private-memory boundaries.

## Proposed decision

Adopt option 3. The API derives identity from the authenticated session and resolves a versioned server-side policy before retrieval. The database query must apply owner, Agent, source readiness and sensitivity predicates before returning candidate chunks. Policy version/decision reference should be observable without exposing private policy contents. The UI displays returned classification/provenance but cannot choose allowed classifications.

Until the policy contract, storage mapping, deletion/consent behavior and negative tests are approved, keep retrieval opt-in and fail-closed. Do not enable hybrid retrieval based on this proposal alone.

## Consequences and acceptance evidence

- Define canonical policy fields and owner/Agent override semantics before schema changes.
- Add tests for each classification, missing/invalid policy, revoked consent, deleted/unready source, cross-owner and cross-Agent attempts.
- Verify RLS and query-time filtering against an isolated Supabase staging project.
- Record policy decision version/trace in retrieval observability without logging retrieved private content.
- Deployment allowlist may remain a secondary maximum ceiling, never a replacement for the owner-specific policy.

## Rollback

Disable retrieval by removing/invalidating the explicit runtime configuration. Do not relax policy or fall back to unrestricted search when policy resolution fails.

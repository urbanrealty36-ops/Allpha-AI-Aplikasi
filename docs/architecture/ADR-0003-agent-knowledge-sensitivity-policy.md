# ADR-0003: Agent Knowledge Sensitivity Policy

- **Status:** Product Owner decision accepted for source implementation; Privacy/Security approval and isolated non-production verification pending before activation.
- **Scope:** ENG-P07–ENG-P09; Agent knowledge ingestion, retrieval and context assembly.
- **Decision owner:** Product Owner; Privacy/Security and Data Platform are required reviewers for activation/schema changes.
- **Last updated:** 2026-10-15

## Context

The retrieval boundary authenticates the Human, verifies active Agent ownership, uses the caller's Supabase access token so RLS remains authoritative, and accepts no owner ID or sensitivity allowlist from client input. Keyword runtime is opt-in and fails closed when ALLPHA_KNOWLEDGE_ALLOWED_SENSITIVITIES is absent or invalid. That deployment-level allowlist is a safety switch, not a complete owner/Agent/tenant policy.

The Master PRD requires private memory and documents to remain private by default, query-time authorization, provenance, consent-aware lifecycle and deletion propagation. A broad platform allowlist cannot express the owner's purpose, sharing scope, retention or Agent-specific permissions.

## Decision

Adopt **server-side, versioned policy resolution** (Option 3). This is the Product Owner's decision for source-level implementation direction; it does not assert Privacy/Security approval or authorize a live policy rollout.

1. Derive the Human/owner identity from the authenticated session and Agent identity from the route/resource. Never trust caller-supplied owner IDs, sensitivity allowlists, purpose, consent or sharing scope as authorization.
2. Resolve an explicit versioned policy on the server using authenticated owner, Agent, tenant/resource scope where applicable, consent, purpose, source lifecycle and explicit sharing grants. Missing, invalid, stale or ambiguous policy denies retrieval.
3. Apply authorization at query time, before candidate chunks are returned. Database predicates must include owner, Agent, source status ready, permitted sensitivity and source/chunk version consistency; retain caller-token RLS as defense in depth.
4. The deployment allowlist ALLPHA_KNOWLEDGE_ALLOWED_SENSITIVITIES may remain only as a secondary maximum ceiling. It is not the policy source and cannot broaden a resource-specific decision.
5. Record policy version and decision/trace reference in observability without logging private content or exposing policy internals in API responses.
6. Consent revocation, source deletion, owner/Agent grant revocation and source version changes must invalidate access to affected knowledge. No stale index may make a deleted, revoked, unready or superseded source retrievable.
7. Keep retrieval disabled/fail-closed until the canonical policy contract and its storage mapping are implemented and approved for activation. The current environment-configured allowlist remains a compatibility safety gate, not proof that this full decision is implemented.

## Explicit non-decisions / implementation gates

- The precise consent/grant schema and canonical source of consent truth must be reconciled with existing schema before any migration. Do not invent columns, RPCs or consent semantics.
- Privacy/Security approval and real RLS/query-time isolation checks must occur before enabling the policy in a live environment.
- No production migration or production tenant-isolation test is authorized by this ADR.

## Acceptance evidence

- Unit/contract tests cover each sensitivity class; missing, invalid and stale policy; revoked consent/grants; deleted/unready/superseded sources; cross-owner and cross-Agent attempts; and query-time predicates.
- Retrieval result provenance and policy version are traceable without private-content logging.
- Verify RLS and query-time filtering against an already-existing, positively verified isolated Supabase non-production environment. If none exists, report this check as blocked/not verified; do not create a new project/branch or use production.
- Keep keyword-only mode labeled keyword. This ADR does not authorize hybrid/vector retrieval.

## Rollback

Disable retrieval by removing/invalidating its explicit runtime configuration. Do not relax policy or fall back to unrestricted search when policy resolution fails.

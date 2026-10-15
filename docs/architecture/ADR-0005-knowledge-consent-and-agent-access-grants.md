# ADR-0005: Canonical Knowledge Consent and Agent Access Grants

- **Status:** Option B audit completed: no qualifying canonical engine/schema/API evidenced in the inspected repository. Awaiting Product Owner approval to proceed with fallback Option C, plus Privacy/Security + Data Platform review; NOT approved for schema implementation or activation.
- **Scope:** ENG-P08 knowledge retrieval authorization; dependency for ENG-P09 indexing/publishing and later derived-data deletion.
- **Decision owner:** Product Owner. Required reviewers: Privacy/Security and Data Platform.
- **Date:** 2026-10-15
- **Supersedes:** Nothing. This proposal refines the unresolved storage mapping in ADR-0003; ADR-0003 remains authoritative for fail-closed policy behavior.

## Context and evidence

The Master PRD separates private memory, knowledge corpus, and owner-selected published knowledge; knowledge sources and personal memory must be separately permissioned. Published knowledge requires an explicit audience and purpose, and publishing a knowledge subset does not publish the original private file. Consent, revocation, provenance, retention and deletion must propagate to downstream chunks, embeddings, summaries, caches and indexes.

Repository evidence:
- `apps/api/supabase/migrations/20261013053438_eng_p03_human_identity_preferences_and_consent.sql` constrains `public.user_consents.consent_type` to `terms_of_service`, `privacy_policy`, and `product_updates`. It is not a knowledge-consent or Agent-specific grant contract.
- Current `knowledge_policy.py` defines a fail-closed, versioned provider interface but deliberately has no database implementation.
- A live Supabase schema inspection was not available through the current connector permissions. Therefore this proposal does not claim the live database has or lacks any table beyond what was verifiably inspected, and no migration may be applied based on this proposal alone.
- A second targeted audit of the current `main` tree at `a82c90f44668799484d8d33894695ab0f06d1687` found no separate Permission/Privacy Engine module, knowledge-consent API, or per-Agent knowledge-grant API in the repository file inventory.
- `apps/api/supabase/migrations/20261013052302_eng_p02_identity_authorization_baseline.sql` defines organization membership/owner/admin helpers; those are organization-scoped roles, not consent for knowledge processing or owner-to-Agent resource grants.
- `apps/api/supabase/migrations/20261014140000_eng_p06_platform_operator_grants_and_audit.sql` defines platform-operator-only scopes and privileged audit. Those grants authorize platform operations, not an Agent's access to an owner's knowledge.
- `apps/api/src/allpha_api/main.py` exposes `user_consents` for only `terms_of_service`, `privacy_policy`, and `product_updates`; the schema constraint confirms those semantics.
- **Option B audit outcome:** no repository-backed canonical engine/schema/API satisfying ADR-0005's required semantics was evidenced. This is a bounded source-repository finding, not proof that no such capability exists outside this repository; live Supabase schema inspection remains unavailable through the current connector permissions.

## Options

### Option A — Reuse `user_consents`
**Reject for knowledge authorization.** Its current constraint and product semantics cover legal/product consents, not per-Agent knowledge processing, sharing audience, retrieval purpose, or grant revocation. Expanding its meaning would blur consent domains and risks treating acceptance of Terms/Privacy as permission to read private knowledge.

### Option B — Map to an existing canonical Permission/Privacy engine and storage contract
**Preferred if proven to exist.** Reuse it only if Data Platform can identify the actual canonical schema/API and demonstrate that it records owner-scoped knowledge consent, Agent/resource scope, purpose/audience, current grant/revocation state, versioning, and audit/provenance. No matching implementation has yet been proven in the inspected repository. If such a source is identified, update this ADR with exact evidence and do not create duplicate tables.

### Option C — Add a dedicated knowledge consent and access-grant contract
**Proposed fallback if Option B cannot be evidenced.** Introduce versioned, server-owned records for:
- owner consent for defined knowledge-processing purposes, with policy/consent version, effective state, grant/revocation timestamps and audit reference;
- explicit owner-to-Agent/resource access grants with scope/audience, allowed purposes and sensitivity ceiling, lifecycle/revocation state and version;
- stable identifiers and provenance needed to trace each retrieval decision and invalidate downstream derived artifacts.

This is a logical contract proposal, not an approved physical schema. Table/column names, uniqueness rules, constraints, RLS, RPCs, grant privileges, history/retention behavior, and migration/rollback strategy must be designed against a read-only inspection of the actual canonical schema and approved by Data Platform and Privacy/Security before implementation. Do not create a second permission engine or duplicate an existing canonical lifecycle.

## Proposed decision and runtime invariants

Pending approval, keep ENG-P08 retrieval disabled/fail-closed unless a trusted provider supplies a valid current policy snapshot. The server must derive owner identity from authentication and Agent identity from the route/resource. Client-supplied owner, consent, grant, purpose, sensitivity or audience is never authorization.

The eventual canonical provider must resolve and validate:
1. owner and Agent/resource identity match;
2. current explicit knowledge consent for the requested purpose;
3. consent/grant are active and not revoked/expired;
4. audience/scope and allowed purpose permit this retrieval;
5. permitted sensitivity and source lifecycle/version constraints;
6. policy version, consent version, grant version and decision/provenance reference.

Any missing, stale, ambiguous, cross-owner/cross-Agent, revoked or malformed state must deny before repository search. The response/trace may expose safe policy and consent version identifiers, but must not log private source content or expose internal policy details. Revocation must block future retrieval immediately according to the approved consistency contract and trigger downstream derived-data cleanup.

## Acceptance and verification gates

- Product Owner chooses Option B or Option C.
- Privacy/Security and Data Platform review the selected contract and lifecycle/retention/deletion implications.
- Read-only inspection identifies the actual canonical schema and RLS/grants before provider implementation.
- Provider tests cover missing/invalid versions, inactive/revoked consent, inactive/revoked grant, purpose/sensitivity/scope mismatch, cross-owner and cross-Agent attempts, source-version conflict, provider/database failure, and provenance.
- Route tests prove denied policy prevents repository search and successful results trace the resolved policy/consent/grant versions without private-content logging.
- CI passes on the exact implementation commit.
- Real Supabase/RLS integration is marked NOT VERIFIED until an already-existing isolated non-production target is positively identified and tested. Do not create a new project/branch, apply migrations to production, or use production for tenant-isolation tests. The staging-based integration/security/release checks assigned to ENG-P37 remain pending until that phase.
- ENG-P08 cannot reach acceptance while the canonical provider/schema mapping is unresolved. ENG-P09 remains blocked until ENG-P08 acceptance.

## Consequences and rollback

- Until approval and implementation, the provider remains unconfigured and retrieval must fail closed; this is intentional.
- If the approved provider is unhealthy or policy state cannot be resolved, disable retrieval rather than fall back to the environment sensitivity allowlist or unrestricted search.
- Any future migration requires versioned SQL, least-privilege grants/RLS, fresh-install and upgrade tests, and a forward-repair/rollback plan approved before applying it.

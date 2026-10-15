# ADR-0005: Canonical Knowledge Consent and Agent Access Grants

- **Status:** Product Owner approved the direction to pursue Option C on 2026-10-15. A read-only canonical schema snapshot was successfully obtained on 2026-10-15; the earlier connector-permission blocker below is superseded by the later evidence section. Physical schema/provider/migration remain NOT approved until object-level reconciliation and Privacy/Security + Data Platform review are complete.
- **Scope:** ENG-P08 knowledge retrieval authorization; dependency for ENG-P09 indexing/publishing and later derived-data deletion.
- **Decision owner:** Product Owner. Required reviewers: Privacy/Security and Data Platform.
- **Date:** 2026-10-15
- **Supersedes:** Nothing. This proposal refines the unresolved storage mapping in ADR-0003; ADR-0003 remains authoritative for fail-closed policy behavior.

## Operational update — read-only audit succeeded (2026-10-15)

This section supersedes the earlier statements in this ADR that the canonical live-schema audit was unavailable due to connector permissions. A corrected binding to the canonical project `dvdziauyvuhcnqhrrvww` allowed read-only catalog queries. The resulting inventory and preliminary migration reconciliation are recorded in [ENG-P08 Canonical Schema Reconciliation](../SECURITY/ENG-P08_CANONICAL_SCHEMA_RECONCILIATION.md).

Confirmed findings from that snapshot:
- Seven application tables were detected in `public`; all seven have RLS enabled and none has FORCE RLS.
- Twenty-seven RLS policies were detected in `public`; no policies were detected in `storage` in the captured policy inventory.
- Broad `anon` table privileges and broad default privileges in `public` were observed and require least-privilege review.
- The live migration ledger contains 20 entries, while the repository contains 29 SQL migration files; one file is byte-identical to another, and eight unique files are not present in the captured ledger.
- The live catalogue does not contain several objects referenced by migration SQL whose versions appear in the ledger, including `organizations`, `organization_memberships`, and `audit_events`. The exact cause and original applied SQL cannot be inferred from ledger version/name alone.
- The `vector` extension is installed, but this does not resolve the approved embedding model/version, vector dimension, index parameters, retrieval evaluation or production pipeline.

**Operational decision:** no SQL was mass-applied and no database write, provider, migration, project or branch was created. Do not replay historical or missing migrations to make the ledger look aligned. First complete object-by-object reconciliation, prepare narrow forward repairs with tested preconditions and recovery paths, obtain required Privacy/Security and Data Platform review, and validate against an already-existing positively identified isolated non-production target. The canonical project is production and must not be used for destructive or cross-tenant tests. ENG-P08 remains `in_progress`; ENG-P09 remains `blocked`.

## Context and evidence

The Master PRD separates private memory, knowledge corpus, and owner-selected published knowledge; knowledge sources and personal memory must be separately permissioned. Published knowledge requires an explicit audience and purpose, and publishing a knowledge subset does not publish the original private file. Consent, revocation, provenance, retention and deletion must propagate to downstream chunks, embeddings, summaries, caches and indexes.

Repository evidence:
- `apps/api/supabase/migrations/20261013053438_eng_p03_human_identity_preferences_and_consent.sql` constrains `public.user_consents.consent_type` to `terms_of_service`, `privacy_policy`, and `product_updates`. It is not a knowledge-consent or Agent-specific grant contract.
- Current `knowledge_policy.py` defines a fail-closed, versioned provider interface but deliberately has no database implementation.
- The later read-only canonical Supabase catalog inspection on 2026-10-15 succeeded and supersedes this earlier limitation. See the confirmed inventory and object-level findings in `docs/SECURITY/ENG-P08_CANONICAL_SCHEMA_RECONCILIATION.md` and `docs/SECURITY/ENG-P08_FORWARD_REPAIR_REVIEW_PACKET.md`. Those snapshots establish current catalog facts, but do not establish historical SQL checksums or reviewer approval; no migration may be applied based on this proposal alone.
- A second targeted audit of the current `main` tree at `a82c90f44668799484d8d33894695ab0f06d1687` found no separate Permission/Privacy Engine module, knowledge-consent API, or per-Agent knowledge-grant API in the repository file inventory.
- `apps/api/supabase/migrations/20261013052302_eng_p02_identity_authorization_baseline.sql` defines organization membership/owner/admin helpers; those are organization-scoped roles, not consent for knowledge processing or owner-to-Agent resource grants.
- `apps/api/supabase/migrations/20261014140000_eng_p06_platform_operator_grants_and_audit.sql` defines platform-operator-only scopes and privileged audit. Those grants authorize platform operations, not an Agent's access to an owner's knowledge.
- `apps/api/src/allpha_api/main.py` exposes `user_consents` for only `terms_of_service`, `privacy_policy`, and `product_updates`; the schema constraint confirms those semantics.
- **Option B audit outcome:** no repository-backed canonical engine/schema/API satisfying ADR-0005's required semantics was evidenced. The read-only live catalog was subsequently inspected; its seven public application tables include no dedicated knowledge-consent or per-Agent knowledge-grant table among the inspected objects. This is a bounded finding for the inspected canonical catalog and repository, not proof that no external service exists. The explicit mapping and reviewer decision remain open.

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

## Option C direction and canonical schema audit (2026-10-15)

The Product Owner approved the **direction** to pursue Option C; this is not approval of a physical schema or migration.

Read-only inspection was attempted against the canonical Supabase project `AllphaAiAplikasi-db` (project ref `dvdziauyvuhcnqhrrrww`) using project metadata, table inventory, migration inventory, branch inventory, and a read-only `information_schema.tables` query. Each connector operation returned a permission error (`MCP error -32600: You do not have permission to perform this action`). Therefore:
- The live schema, applied migration ledger, grants/RLS and any existing canonical privacy engine remain **UNVERIFIED**.
- Do not infer that the live database lacks a capability from the denied inspection.
- No schema changes, provider, migration, branch, or project were created.

### Review-ready logical design (not physical DDL)

The following is a logical contract for Privacy/Security and Data Platform review only. It intentionally specifies no table names, columns, SQL, RPCs, or physical constraints before schema inspection.

1. **Consent decision:** resolve an explicit owner consent for a named knowledge-processing purpose; include effective status, policy/consent version, recorded/revoked timestamps and audit/provenance reference.
2. **Agent/resource grant:** resolve an owner-authorized grant scoped to the exact Agent and permitted knowledge resource/source set; include audience, purpose, sensitivity ceiling, lifecycle/expiry/revocation and version.
3. **Trusted context:** derive owner from authenticated server identity and Agent/resource from the authorized route/domain record. Ignore caller-supplied ownership, consent, grant, audience and sensitivity as authority.
4. **Decision trace:** bind each allow/deny decision to policy, consent, grant, source and source-version identifiers; never include private source text in audit logs.
5. **Revocation semantics:** deny subsequent retrieval as soon as revocation is effective under an explicitly reviewed consistency contract; enqueue/track deletion or invalidation of chunks, embeddings, summaries, caches and indexes derived from the revoked scope.
6. **Fail-closed behavior:** missing, stale, ambiguous, cross-owner/cross-Agent, expired, revoked or unavailable authorization state denies before search. No fallback to general terms/privacy consent or sensitivity allowlists.
7. **Review questions:** confirm whether any existing canonical service/API outside the inspected repository should own these semantics; determine canonical source-of-truth and lifecycle; define retention/deletion and audit access; confirm RLS/privilege boundaries and revocation propagation; approve consistency/availability behavior and test strategy.

### Required next evidence

An authorized read-only Supabase connector/session with schema inspection permissions is required to inventory canonical schemas, tables/columns, constraints, functions/RPCs, RLS policies, grants, extensions and applied migrations. Reconcile that inventory against repository migrations before deciding whether Option C needs any physical objects. After the evidence is captured, Privacy/Security and Data Platform must review and explicitly approve the mapping before provider implementation or migration design proceeds.
 
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

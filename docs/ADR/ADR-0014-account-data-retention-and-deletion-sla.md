# ADR-0014 — Account data retention, deletion SLA and shared-record disposition

- **Status:** PROPOSED — DATA POLICY VALUES UNRESOLVED
- **Date:** 2026-11-23
- **Decision owner:** Privacy / Legal & Data Governance
- **Implementation owner:** Platform Engineering
- **Scope:** ENG-P03 Human Identity; account export, deletion executor, retention enforcement and FK dependency resolution
- **Authority:** Master PRD v3.1.0 consolidated at the canonical v3.0.0 repository path; Part XXI decision 12

## Context

The Master PRD requires retention periods by data class, account export/deletion workflows, deletion propagation to derived data, legal holds, and auditable privacy operations. Part XXI decision 12 explicitly leaves retention periods and deletion SLAs by data class unresolved.

ENG-P03 now has:
- 106 enabled account-export sources, all covered by either generic owner-column deletion or an explicit relationship-safe handler;
- canonical source-handler capability returned by the database registry;
- a lease-fenced worker for storage cleanup and transactional account deletion;
- legal-hold checks, FK action/parent guards, export cleanup and governance APIs;
- six database-supported data classes: `owner_private`, `agent_operational`, `tenant_shared`, `published_knowledge`, `session_scoped`, and `public_catalog`.

The live policy registries still contain zero active source policies and zero active retention policies. Fifty-seven FK dependency rules remain fail-closed. This is deliberate: the engine must not invent retention periods, legal bases, or shared-record dispositions.

## Decision to be made

The policy owner must define, for each of the six data classes:

1. Minimum retention duration and the event from which the clock starts.
2. Deletion SLA after an eligible request or retention expiry.
3. Whether the class is hard-deleted, soft-deleted then purged, preserved, or anonymized.
4. Required legal basis and exceptions.
5. Legal-hold behavior, release behavior and evidence requirements.
6. Treatment of immutable provider-managed backups and restore points.

Shared-record rules must separately state how to handle other participants' messages, community content, workspace documents, published content, creator attribution, financial ledgers, billing records and moderation/audit evidence.

## Options

### Option A — Per-data-class policy (recommended)

Use the existing canonical retention-policy and source-policy registries. Each source is mapped to one approved data class and a disposition. Retention and deletion SLA are configured per class, with legal holds overriding scheduled deletion. Shared records are handled through explicit source handlers and attribution rules.

**Trade-offs:** Most accurate and auditable; requires the policy owner to supply class-level values.

### Option B — One uniform retention period

Apply one duration to every data class.

**Trade-offs:** Simpler configuration but risks deleting financial, legal, shared or published records too early, while retaining ephemeral/private data longer than necessary. Not recommended.

### Option C — Indefinite retention

Keep all account data indefinitely and block physical deletion.

**Trade-offs:** Avoids accidental deletion but conflicts with the PRD's account-deletion and data-minimization requirements. Not recommended as a product policy.

## Proposed engineering safeguards

1. Keep destructive execution disabled by default until the approved source and retention policy rows exist.
2. Default unknown, unmapped, composite-FK, or unsupported dependencies to `block`.
3. Permit generic FK row deletion only for a validated single-column reference to `auth.users(id)`; require the actual PostgreSQL delete action to match the configured resolution.
4. Preserve records belonging to other participants in shared conversations, communities and workspaces. Delete only the account-authored/owned rows covered by the explicit handler.
5. Do not delete billing, wallet, settlement, credit-ledger, moderation or security-audit records until their retention and anonymization rules are explicit.
6. Apply legal holds before storage deletion begins; record the known limitation that provider-managed immutable backups expire according to the configured provider backup policy, as separately described by ADR-WP04-003.
7. Keep all non-destructive implementation work moving. This ADR does not require Product Owner Acceptance for code, builds, migrations, API contracts, worker logic or client integration. It only prevents enabling destructive account deletion with invented policy values.

## Consequences

- ENG-P03 remains `in_progress`, not `implemented` or `production_verified`.
- Real-account testing and native EAS signed builds remain DEFERRED / NOT VERIFIED and are not development blockers.
- No retention duration, deletion SLA, legal basis, or data disposition is fabricated by engineering.
- Once the policy owner supplies the values, Platform Engineering can populate the existing registries, resolve the remaining FK rules, and verify the executor without redesigning the worker/API architecture.

## References

- Master PRD Part XXI, decision 12 — retention periods and deletion SLAs by data class.
- ADR-WP04-001 — media content recovery and abandoned upload retention; this ADR does not override its media-specific values.
- ADR-WP04-003 — provider-managed backup retention and deletion evidence.

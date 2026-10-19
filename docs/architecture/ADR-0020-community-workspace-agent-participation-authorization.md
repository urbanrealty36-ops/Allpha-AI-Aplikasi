# ADR-0020 Proposal — Community and Workspace Agent Participation Authorization

- **Status:** Proposed — requires Product Owner approval before schema/API implementation
- **Date:** 2026-10-19
- **Scope:** ENG-P19 Communities, Collaboration, Missions & Workspaces; dependency for any Agent participation in community/workspace content
- **Decision owner:** Product Owner. Required reviewers: Security/Privacy and Platform Engineering.
- **Related decisions:** Master PRD v3.0.0 §§6, 59–60; ADR-0005 (knowledge consent and Agent access grants); ADR-0019 (public Agent Consumer messaging authorization; **not** a community/workspace grant).

## Context

The Master PRD requires explicit, labeled, permissioned Agent participation in conversations and community permissions for community participation. Workspace assistance may use only workspace-permitted data. Human ownership of an Agent does not automatically grant the Agent access to every resource owned by that human, and membership of a human must not be treated as membership of the human's Agent.

ADR-0019 defines public Agent Consumer messaging authorization for ENG-P18 only. It does not authorize community membership, workspace access, or reading/writing community/workspace resources. ADR-0005's knowledge consent/access-grant direction is also not a ready-to-use community/workspace schema and explicitly requires separate schema reconciliation and review before physical implementation.

## Proposed decision

**Option B: explicit, resource-scoped Agent participation grants, enforced by the canonical FastAPI backend and fail-closed by default.**

1. An Agent participates only when a resource owner/admin with the required server-verified authority explicitly grants that exact Agent access to the exact community or workspace. A human membership, Agent ownership, public Agent status, community membership, or invitation to a human is not sufficient.
2. The authorization record must bind resource type and ID, Agent ID and version, the actual owner/approver, granted scopes, policy version, lifecycle status, timestamps, optional expiry, revocation reason, and audit reference. Scopes must be least-privilege and explicit (proposed examples: `read_published_content`, `read_workspace_documents`, `create_agent_post`, `comment`). No wildcard or implicit admin scope.
3. The backend verifies current Agent ownership, resource state, approver's role, exact active grant, Agent/resource versions where relevant, and allowed scope on every operation. Revocation, suspension, removal, expiry, or version/policy mismatch denies access immediately. The model output is never authorization.
4. Agent access to owner-private memory, credentials, unrelated DMs, private knowledge, hidden content, or unshared workspace documents remains denied. A resource grant does not imply knowledge consent; sensitive knowledge requires the separately approved knowledge policy/grant path.
5. Agent-created content must be labeled as Agent-authored and attributed to the Agent plus its responsible owner. Moderation, reporting, rate/budget limits, idempotency, and audit apply. Agent membership cannot grant human membership, owner/moderator roles, invite privileges, or permission escalation.
6. No Agent participation is enabled until the canonical data mapping is reconciled against Production's existing schema and Security/Privacy + Platform review approve the migration and contract. Do not apply speculative tables or migrations to Production. Use existing canonical grant/policy infrastructure if proven to satisfy these semantics; do not create a duplicate permission engine.

## Alternatives considered

- **A. Implicit inheritance from human membership:** rejected; it creates confused-deputy access and can expose private content.
- **B. Explicit resource-scoped grant with fail-closed checks:** preferred; clear revocation, audit, and least-privilege boundaries.
- **C. Reuse ADR-0019 Consumer grants:** rejected for this purpose; those grants authorize a public Agent Consumer messaging path, not community/workspace resource membership or content access.
- **D. Let the model decide access:** rejected; model output is not an authority source.

## Required implementation/acceptance evidence

- Canonical schema/object reconciliation and reviewer approval before migration.
- Server-only grant/revoke/list APIs with owner/admin checks, stable errors, audit, idempotency and expiry/revocation handling.
- Authorization coverage for no grant, wrong resource, wrong Agent/version, revoked/expired grant, suspended community/workspace, non-member approver, scope escalation, private memory isolation, and Agent-authored content moderation.
- Web/Native UI for explicit Agent selection, scope disclosure, approval/revocation, and clear disabled/denied states.
- Automated CI evidence only at this stage. No manual/real-user, staging, physical-device, or authenticated E2E tests are authorized by the current Product Owner instruction; mark such acceptance evidence NOT VERIFIED until separately authorized.

## Consequences and rollout

Until this ADR is approved and the contract implemented, community/workspace Agent participation remains disabled. Human-only community, workspace, mission, document, invite and moderation flows continue under their existing server-side permissions. Rollback is to keep Agent participation disabled; no resource membership or private data access is inferred.

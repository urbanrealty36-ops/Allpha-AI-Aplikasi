# ENG-P19 / ADR-0020 Security & Platform Review Packet

- **Status:** Awaiting Security/Privacy and Platform Engineering review; not approval to apply a Production migration.
- **Product decision:** ADR-0020 approved by Product Owner on 2026-10-19.
- **Scope:** Exact Agent grants for one community or workspace only.
- **Canonical project:** Supabase project `dvdziauyvuhcnqhrrvww`. All findings below are from read-only catalog inspection on 2026-10-20. No grant schema migration was applied and no data was written.

## Decision and invariants

ADR-0020 selects explicit resource-scoped grants, least privilege, fail-closed behavior, audit/revocation, and no automatic permission inheritance. Human membership, Agent ownership, public visibility, or an invitation to a human never implies Agent membership or resource access. The model is never an authorization authority.

Agent participation remains disabled until all relevant runtime read/write paths enforce the grant contract and required review/CI gates pass.

## Canonical schema reconciliation

Read-only inspection confirmed the following existing objects:
- Agent identity/ownership: `public.ai_agents` (has a monotonically versioned `version` column), `public.agent_ownerships`.
- Community: `public.communities`, `public.community_memberships`, `public.community_posts`, `public.community_invites`, `public.community_missions`, `public.community_mission_progress`.
- Workspace: `public.workspaces`, `public.workspace_memberships`, `public.workspace_documents`, `public.workspace_document_versions`, `public.workspace_annotations`, `public.workspace_presence`.
- `public.agent_consumer_grants` exists but is ENG-P18 public Agent Consumer messaging authorization; it is not a community/workspace grant contract and must not be repurposed.

The live catalog did not contain `public.agent_resource_grants`, `public.agent_resource_grant_audit`, `public.grant_agent_resource_access(...)`, or `public.revoke_agent_resource_access(...)`. The migration ledger's latest inspected ENG-P19 entry was `20261019155233_eng_p19_pinned_resources`. The ADR-0020 migration remains repository-only.

RLS is enabled on the inspected existing community/workspace tables. In the inspected table-grant snapshot, only `service_role` held table privileges for these objects. The proposed grant/audit tables similarly enable RLS and revoke table access from `anon` and `authenticated`, with server-only `service_role` access.

## Proposed migration and API contract

Migration file: `apps/api/supabase/migrations/20261019220000_eng_p19_agent_resource_grants.sql`.

It proposes:
1. Grant record binds exact `agent_id`, `agent_version`, one resource type and ID, approver, scopes, policy version, status, creation/expiry/revocation timestamps and reason.
2. Separate audit records bind the grant, Agent/version, resource, actor, action, scopes and optional revocation reason.
3. `grant_agent_resource_access` validates active Agent and active ownership, current resource state, resource approver role, allowed scope/resource combinations and expiry; grant and audit insert are one transaction.
4. `revoke_agent_resource_access` revalidates current resource authority, serializes revocation, and writes grant status plus audit event in one transaction. Resource suspension does not prevent revocation.
5. Both RPCs use `SECURITY DEFINER`, empty `search_path`, reject non-`service_role` execution, revoke execute from `public`, `anon`, and `authenticated`, and grant execute only to `service_role`.
6. FastAPI remains the client-facing authority boundary. The API derives the actor from authenticated identity and validates resource approval. Client applications do not access these tables directly.

Proposed scope allowlist:
- Community: `read_published_content`, `create_agent_post`, `comment`.
- Workspace: `read_workspace_documents`, `comment`.

The grant metadata alone does not authorize any Agent runtime operation. Runtime must deny if the grant is absent, revoked, expired, for a different resource, Agent version mismatch, scope mismatch, Agent/resource suspended, or policy version mismatch. Private memory, credentials, unrelated DMs, hidden content and unshared workspace documents remain excluded.

## Required reviewer decisions

Security/Privacy and Platform Engineering should review and explicitly record decisions on:

- [ ] Is the proposed grant/audit schema consistent with the canonical authorization and audit lifecycle, or should an existing canonical engine own it?
- [ ] Are resource approver roles correct: community owner/moderator; workspace owner only?
- [ ] Are `SECURITY DEFINER`, `auth.role() = service_role`, empty search path, execute grants and function ownership safe under the production role model?
- [ ] Are atomic grant/revoke plus audit semantics sufficient, including race/conflict behavior and suspension/revocation ordering?
- [ ] Should grant records also bind a resource version/policy snapshot beyond Agent version and policy version?
- [ ] Is the scope allowlist complete and appropriately narrow for ENG-P19? Are content attribution, moderation, rate/budget controls and owner disclosure fully specified before runtime activation?
- [ ] Are indexes, foreign keys, uniqueness, expiry handling, audit retention and forward-repair/rollback acceptable?
- [ ] What evidence is required before the migration is allowed to Production? The Product Owner currently prohibits manual/real-user, staging, physical-device and authenticated E2E testing; automated CI evidence is permitted.

## Rollout/rollback guard

- Do **not** apply this migration to Production before the two reviewer groups approve the physical contract.
- Do **not** enable Agent participation before runtime checks are implemented across every relevant read/write path.
- If implementation is rolled back, keep participation disabled and leave no implicit membership or private-data access.
- The migration has not been applied; rollback is therefore not required at this checkpoint. Any future approved Production rollout must include a reviewed forward-repair and rollback plan.

## Evidence links

- ADR-0020: https://github.com/urbanrealty36-ops/Allpha-AI-Aplikasi/blob/main/docs/architecture/ADR-0020-community-workspace-agent-participation-authorization.md
- Fixed phase plan: https://github.com/urbanrealty36-ops/Allpha-AI-Aplikasi/blob/main/docs/PHASES/ALLPHA_FIXED_PHASE_PLAN.md
- Migration proposal: https://github.com/urbanrealty36-ops/Allpha-AI-Aplikasi/blob/main/apps/api/supabase/migrations/20261019220000_eng_p19_agent_resource_grants.sql

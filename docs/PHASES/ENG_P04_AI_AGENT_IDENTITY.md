# ENG-P04 — AI Agent Identity

**Status:** `in_progress`  
**Implementation branch:** `main`  
**Scope:** Agent identity/passport metadata, explicit Human ownership, persona, disclosure and behavior boundaries.

## PRD traceability

- Master PRD v3 §14 domain 2, **AI Agent Identity**: Agent identity, owner link, visibility, status, versions and public profile; every Agent has an explicit owner or declared platform ownership.
- Master PRD v3 §14 domain 3, **Agent Persona**: tone/behavior profile and communication style.
- Master PRD v3 §14 domain 7, **Agent Passport**: owner-approved identity, capability claims, disclosures and usage terms.
- Product journey: Human creates an Agent → configures identity/scope → publishes selected public identity → revokes public access.
- Canonical phase-numbering reconciliation: the Master PRD roadmap labels the Agent Identity/Persona/Passport work **Phase 02**; the phase-plan initial board labels Agent identity/passport **Phase 05**; the ENG-P03 note calls this engineering package **ENG-P04**. This document preserves the requested engineering identifier ENG-P04 and records the product-phase crosswalk rather than silently renumbering the roadmap. The canonical phase plan should reconcile this discrepancy.

## Implemented

### Data and migrations

- `20261013054429_eng_p04_ai_agent_identity.sql`: `public.ai_agents` and `public.agent_ownerships`, unique handle, status/visibility constraints, indexes, RLS and atomic `public.create_ai_agent(...)` RPC.
- `20261013054446_eng_p04_agent_ownership_rls_helpers.sql`: private security-definer ownership helper to avoid recursive RLS evaluation and updated-at trigger.
- `20261013054513_eng_p04_agent_owner_insert_policy.sql` and `20261013054613_eng_p04_agent_creator_rls_fix.sql`: creator validation for atomic owner-link creation without recursive policy lookup.
- `20261013054639_eng_p04_agent_disclosure_boundaries.sql`: first-class disclosure and behavior-boundary fields; expanded atomic create RPC.
- Migrations were applied to canonical Supabase project `dvdziauyvuhcnqhrrvww` (AllphaAiAplikasi-db). No human profile row is repurposed as an Agent identity.

### API

- `POST /v1/agents`: authenticated create; owner identity is derived from validated Supabase Auth `auth.uid()`, not client input. Agent and owner relation are created atomically.
- `GET /v1/agents`: returns Agents with an active owner relationship for the caller.
- `GET /v1/agents/{agent_id}` and `PATCH /v1/agents/{agent_id}`: owner-scoped retrieval and updates.
- `GET /v1/agent-passports/{handle}`: returns only public, active passport fields; private persona and boundaries are not included.
- `apps/web/app/agents/passport/[handle]/page.tsx`: authenticated Passport UI fetches the public projection with the user's bearer session; the browser does not open the protected API endpoint without auth headers.
- Strict Pydantic schemas reject client-supplied `owner_user_id`, `created_by`, role and other unknown authority fields. Updates are limited to identity, disclosure/boundaries, visibility and lifecycle status.

### UI

- `.github/workflows/ci.yml`: lightweight API pytest + web production build workflow.
- `apps/web/app/agents/page.tsx`: real-session Agent workspace; create Agent with handle, display name, description, persona JSON, disclosure, behavior-boundaries JSON and visibility; view ownership relation; change lifecycle status; open public passport.
- `apps/web/app/page.tsx`: authenticated entry link to AI Agent Studio.
- `apps/web/app/globals.css`: responsive Agent workspace styling.
- UI calls the FastAPI backend with the active Supabase session token. It does not write privileged Agent data directly from the browser.

### Tests

- `apps/api/tests/test_agent_identity.py`: unauthenticated-route checks, strict schema validation, rejection of owner/creator authority fields, and disclosure/boundary payload validation.

## Security and privacy controls

- Human profile and Agent identity use separate tables and API contracts.
- Canonical owner relationship is explicit in `agent_ownerships`; owner is derived server-side from the signed-in Supabase user.
- Row-level security scopes private Agent reads and mutations to active ownership. Public passport reads require `visibility=public` and `status=active`.
- Private persona and behavior-boundary configuration are not exposed by the public passport projection.
- The ownership helper functions live in non-exposed `private` schema; the public create RPC remains `SECURITY INVOKER`. A deferred database constraint trigger rejects any Agent insert whose transaction does not create an active owner relation. Direct ownership update/delete is revoked from `authenticated`; no service-role key is used by the API.
- Security Advisor returned no findings after the final ownership/RPC migration.

## Acceptance evidence and known gaps

- **Migration evidence:** Supabase connector confirmed each migration application returned success; re-check live migration history and table/RLS definitions before final acceptance.
- **Not yet verified:** current GitHub Actions result for the latest commit, real signed-in create/list/update/passport journey, cross-user IDOR denial, and browser/mobile responsive E2E.
- Public/active is currently the owner-controlled publication state. A dedicated moderation/eligibility approval lifecycle and version history are not implemented in ENG-P04; do not claim this endpoint proves a moderated or verified Agent.
- Activating an Agent updates identity lifecycle only; it does not start an Agent Runtime, Model Router, tools, memory, skills, billing, usage metering or execution permissions.
- Ownership transfer/delegated operator management is not exposed yet. The schema supports role values but this slice only provisions the primary owner.
- Duplicate handle conflict, database unavailability and invalid persona/boundary JSON must be exercised against live integration before acceptance.

## Acceptance checklist

- [x] Separate Agent identity table and explicit ownership relation added.
- [x] Authenticated API contracts and owner-derived atomic create path implemented.
- [x] Responsive UI for creating and managing identity implemented.
- [x] Schema/authorization smoke tests added.
- [ ] CI green on latest main commit.
- [ ] Real authenticated integration and cross-user ownership tests pass.
- [ ] Public passport journey and revocation verified end-to-end.
- [ ] Moderation/publication eligibility and Agent versioning contract reconciled with the owning domains.

The phase remains `in_progress` until the unchecked integration/security/acceptance items have reproducible evidence.

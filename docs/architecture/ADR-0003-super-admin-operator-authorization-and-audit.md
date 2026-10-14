# ADR-0003 — Super Admin Operator Authorization and Durable Audit

- **Status:** Proposed — requires Product Owner / security decision before privileged implementation
- **Date:** 2026-10-14
- **Scope:** ENG-P06 operator authentication, privileged permission scopes, capability governance and platform-wide audit
- **Authority:** Master PRD v3.0 §5.9, §7.3 and Part XVI §78; `AGENTS.md` security and authorization invariants

## Context from the current repository

- `apps/super-admin/app/page.tsx` currently performs only unauthenticated liveness/readiness/diagnostic probes and explicitly states privileged operations remain restricted until operator authentication, scope enforcement, audit, and official backend endpoints exist.
- `apps/api/src/allpha_api/auth.py` validates a Supabase bearer session through `/auth/v1/user`. This authenticates a human identity; it does **not** establish platform-operator status.
- `apps/api/src/allpha_api/main.py` has no verified platform-operator authorization dependency or privileged governance API.
- Source migration `20261013052409_eng_p02_authz_audit_and_org_creation.sql` defines organization-scoped `public.audit_events`, but the current fixed phase plan records a live-schema discrepancy and says `organizations`, `organization_memberships`, and `audit_events` were absent during read-only inspection. Do not assume that table is available for global operator audit or apply reconstructed migrations to production.
- No operator grant registry or approved platform-wide audit write path has been verified in the repository/live schema.

## Decision required

Choose the authoritative source for platform-operator grants and how those grants are provisioned/revoked. Candidate options:

1. **Trusted Supabase `app_metadata` claims.** Small implementation footprint, but claim changes/revocation can remain stale until tokens refresh; requires a tightly controlled administrative provisioning path and a defined scope schema.
2. **Dedicated server-queried operator grant records (recommended).** A canonical database table keyed to `auth.users`, with active status, explicit scopes, grant/revocation metadata and server-side lookup on each privileged request. This gives clearer revocation and audit semantics, but requires a reconciled, versioned migration and an authorized provisioning mechanism.

Separately decide whether platform-wide operator events extend a verified canonical audit engine/table or require a dedicated append-only platform audit contract. Organization-scoped `audit_events` must not be silently repurposed as a global audit system.

## Recommended security contract

- Supabase Auth proves identity only; a verified operator grant is a separate required check.
- Use backend-only dependencies for operator authentication and per-action scope checks; default deny on missing, malformed, inactive or unavailable grants.
- Never accept operator roles/scopes from client request bodies, query parameters, or user-editable `user_metadata`. UI visibility is not authorization.
- Require least-privilege action scopes, resource/context checks, request ID correlation and bounded confirmation for high-risk operations.
- Persist allow/deny and mutation audit records through a canonical server-owned write path. Record actor, action, resource, result, request ID, timestamp and safe metadata; never log bearer tokens, secrets or private payloads.
- Do not expose capability approval/revocation or other privileged controls until authorization and durable audit are implemented and regression-tested.
- Add positive and negative tests: no session, ordinary authenticated user, missing scope, wrong scope, revoked grant, audit-write failure, forged client role/scope, and successful authorized operation.
- Keep real Supabase migration/RLS, live operator sessions, cross-app E2E and consolidated staging validation deferred to ENG-P37 as directed by `AGENTS.md`; do not use production as staging.

## Consequences and implementation gate

Until the decision is approved and the canonical schema/write path is reconciled, Super Admin privileged actions remain disabled. ENG-P06 stays `in_progress`. This ADR is a proposal, not evidence that operator authorization or audit is implemented.

# ADR-0003 — Super Admin Operator Authorization and Durable Audit

- **Status:** Accepted by Product Owner — dedicated grant table + server-owned append-only audit
- **Date:** 2026-10-14
- **Scope:** ENG-P06 operator authentication, privileged permission scopes, capability governance and platform-wide audit
- **Authority:** Master PRD v3.0 §5.9, §7.3 and Part XVI §78; `AGENTS.md` security and authorization invariants

## Context from the current repository

- `apps/super-admin/app/page.tsx` currently performs only unauthenticated liveness/readiness/diagnostic probes and explicitly states privileged operations remain restricted until operator authentication, scope enforcement, audit, and official backend endpoints exist.
- `apps/api/src/allpha_api/auth.py` validates a Supabase bearer session through `/auth/v1/user`. This authenticates a human identity; it does **not** establish platform-operator status.
- `apps/api/src/allpha_api/main.py` has no verified platform-operator authorization dependency or privileged governance API.
- Source migration `20261013052409_eng_p02_authz_audit_and_org_creation.sql` defines organization-scoped `public.audit_events`, but the current fixed phase plan records a live-schema discrepancy and says `organizations`, `organization_memberships`, and `audit_events` were absent during read-only inspection. Do not assume that table is available for global operator audit or apply reconstructed migrations to production.
- No operator grant registry or approved platform-wide audit write path has been verified in the repository/live schema.

## Accepted decision

The Product Owner approved option 2: **dedicated server-queried operator grant records** keyed to `auth.users`, with explicit scopes, active/revoked lifecycle, optional expiry, grant/revocation metadata, and per-request backend lookup. The first grant/bootstrap must be provisioned through a trusted Supabase administrative channel after the migration is verified; no user can self-assign operator status. Operator grant management API prevents self-grant and scope escalation.

Platform-wide privileged events use the dedicated append-only `public.platform_operator_audit_events` table. The organization-scoped `public.audit_events` table is not repurposed. Grant insert/revocation is captured by a database trigger in the same transaction; API scope decisions are recorded through a server-only Supabase key. If the audit sink is unavailable, privileged requests fail closed.

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

Implementation has begun under ENG-P06: versioned source migration, backend operator scope dependencies, server-only audit writes, operator grant list/create/revoke endpoints, and regression tests are present. The migration has **not** been applied to canonical Supabase; do not issue grants or enable these endpoints in production until the migration lifecycle and server-only key configuration are verified in isolated non-production. Capability approval remains disabled until its specific route/UI is implemented and tested. ENG-P06 stays `in_progress`.

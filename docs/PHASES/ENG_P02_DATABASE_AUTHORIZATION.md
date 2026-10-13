# ENG-P02 — Supabase Database, Authentication & Authorization

**Status:** IN_PROGRESS (implementation exists; integration acceptance still required)  
**Canonical project:** AllphaAiAplikasi-db (dvdziauyvuhcnqhrrvww)  
**Execution:** direct commits to main, per AGENTS.md.

## Scope and traceability

| Requirement | Implementation | Evidence / exit criterion |
|---|---|---|
| PostgreSQL schema and versioned migration | apps/api/supabase/migrations/20261013053000_eng_p02_authz_audit_and_org_creation.sql | Migration exists in repo and was applied through the canonical Supabase connector; verify migration history and live schema before acceptance. |
| Authentication | apps/api/src/allpha_api/auth.py validates Bearer tokens against Supabase Auth /auth/v1/user; no locally trusted JWT claims | Real valid, expired, and invalid token integration tests. |
| User identity | GET /v1/me, PATCH /v1/me/profile | Real authenticated profile read/update; profile ownership and validation tests. |
| Tenant ownership | organizations.owner_id; owner membership is created by a database trigger | Authenticated organization create/list; owner membership persisted exactly once. |
| Authorization | User JWT is passed to PostgREST so RLS applies; tenant membership policies; client membership writes denied | Cross-user and cross-tenant denial tests; admin/member separation. |
| Audit | audit_events with RLS; client insert/update/delete denied | Backend-only audit write path and admin visibility tests still required for full acceptance. |
| Secrets | Only URL and publishable key documented for runtime; no service-role key in client | Verify deployment secret configuration; do not put real keys in repository. |
| Operations | /readyz reports configuration state; request IDs preserved | Deployment and actual dependency health checks. |

## Live schema reconciliation

Initial inspection found existing profiles, organizations, and organization_memberships tables and existing RLS policies in the canonical project, despite an earlier phase note saying public was empty. The implementation preserves that schema (notably organizations.owner_id and organization_memberships.invited_by) and applies additive changes. No product rows were intentionally deleted.

The database migration tool reported a pre-existing migration named eng_p02_identity_authorization_baseline; its source SQL is not present in the current repository tree. Reconcile that migration's origin and commit the corresponding baseline migration before treating repository-to-database migration history as fully reproducible.

## Security boundaries

- Supabase Auth validates identity; the API does not accept client-supplied user IDs or roles as authority.
- The API uses the caller's bearer token for PostgREST, preserving RLS. The service-role key is not used by these endpoints.
- Profile updates whitelist editable fields; extra authority fields are rejected.
- Membership mutations are database-controlled and denied to direct authenticated client writes. Invitation/role-management API is intentionally not exposed yet.
- Errors returned to callers do not expose raw Postgres messages or credentials.
- audit_events is append-only from client roles; a privileged backend audit writer is still needed before sensitive domain mutations are considered fully audited.

## Verification still required

1. Confirm the GitHub Actions run for the latest main commit is green.
2. Run API unit tests and add real Supabase integration tests using dedicated test identities in an isolated environment.
3. Verify signup/profile trigger behavior, login/session expiration, profile update, organization creation, owner membership trigger, member visibility, cross-tenant isolation, and forbidden role escalation.
4. Run Supabase Security Advisor and resolve all ENG-P02-related findings.
5. Configure the actual deployment's SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY secrets and exercise deployed endpoints.
6. Reconcile the pre-existing database migration baseline into the repository.

Do not mark ENG-P02 integration_verified, acceptance_passed, or production_verified until the corresponding evidence exists.

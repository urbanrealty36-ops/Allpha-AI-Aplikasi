# ENG-P01 Client/API Access Audit — evidence snapshot

Date: 2026-10-14
Branch: `main`
Scope: source-level inventory of the three clients and current FastAPI routes. This is an evidence snapshot, not a claim that security acceptance is complete.

## Canonical boundary

- `apps/web`: browser client.
- `apps/client`: React Native / Expo client.
- `apps/super-admin`: Super Admin client.
- `apps/api`: the single FastAPI backend.
- Business operations must use FastAPI contracts. Supabase Auth/session operations are permitted in clients. Clients must not query business tables or privileged RPCs directly.

## Client source audit

| Client/file | Observed provider calls | Classification |
|---|---|---|
| `apps/web/lib/supabase.ts` | `createClient` with publishable key and session persistence | Auth/session client factory; inspect all imports/call sites before treating the helper as active business access |
| `apps/web/app/page.tsx` | `supabase.auth.getSession`, `onAuthStateChange`, `signUp`, `signInWithPassword`, `signOut`; profile/settings calls via `fetch(apiBase + /v1/...)` | Auth is allowed; observed business profile/settings operations use FastAPI |
| `apps/web/app/agents/page.tsx` | Auth session listener and sign-out; no `.from()`, `.rpc()`, Storage or Realtime calls found in this file | Auth is allowed; continue tracing its fetch calls and imported helpers |
| `apps/web/app/agents/passport/[handle]/page.tsx` | No direct Supabase table/RPC/Storage/Realtime calls found | No direct provider bypass observed in this file |
| `apps/client/App.tsx` | Supabase `signUp`, `signInWithPassword`, `signOut`, `getSession`, `onAuthStateChange`; profile request through API | Auth/session is allowed; UI explicitly describes profile as API-backed |
| `apps/super-admin/app/page.tsx` | No Supabase JS client, direct PostgREST, table, RPC, Storage or Realtime calls found | Observed diagnostics use API routes; this does not prove full admin authorization/business workflows |
 
Search scope covered `createClient`, `.from(`, `.rpc(`, `/rest/v1/`, `.storage.`, `.channel(`, Realtime references, and Auth/session calls in the tracked client entry points. This source-level scan does not by itself prove that no indirect calls exist in every dependency or uninspected file.

## Current backend route-to-data map

All routes below are declared in `apps/api/src/allpha_api/main.py`. Authenticated routes use `Depends(current_user)` in the observed source unless stated otherwise. Data access is performed by `user_db_request` in `apps/api/src/allpha_api/auth.py`, which forwards the user's access token to Supabase PostgREST. The source currently does not show a separate domain-service/engine/repository layer between most route handlers and `user_db_request`; this is a layering gap to resolve, not by itself proof of an authorization bypass.

| Endpoint | Auth / observed data path | Status / follow-up |
|---|---|---|
| `GET /healthz` | Public health probe; no business data | Railway healthcheck logs observed HTTP 200 |
| `GET /readyz` | Readiness handler; inspect exact dependency checks | Must verify with runtime probe |
| `GET /v1/system/status` | System diagnostics handler | Confirm operator/public exposure policy and data returned |
| `GET /v1/me` | `current_user` → `user_db_request` → identity/profile rows | Add/retain token and owner-scope regressions |
| `PATCH /v1/me/profile` | `current_user` → `user_db_request` → profile update | Confirm user ID is derived server-side and RLS is enforced |
| `GET /v1/me/settings` | `current_user` → `user_db_request` → settings rows | Confirm owner-scoped query and policy |
| `PATCH /v1/me/settings` | `current_user` → `user_db_request` → settings writes | Confirm no client-supplied owner ID can change scope |
| `GET /v1/me/consents` | `current_user` → `user_db_request` → consent rows | Confirm owner scope and migration policy |
| `POST /v1/me/deactivation-request` | `current_user` → `user_db_request` → deactivation request | Confirm idempotency and authorization |
| `GET /v1/organizations` | `current_user` → `user_db_request` → organization membership/data | Review tenant membership predicates and RLS |
| `POST /v1/organizations` | `current_user` → `user_db_request` → organization creation | Confirm creator/membership fields are server-derived/atomic |
| `GET /v1/organizations/{organization_id}/memberships` | `current_user` → organization membership lookup, then organization lookup | Explicit cross-tenant negative test required |
| `GET /v1/agents` | `current_user` → ownership-scoped `user_db_request` | Existing tests assert current owner and active owner filters |
| `POST /v1/agents` | `current_user` → `rpc/create_ai_agent` through backend PostgREST | Existing test asserts owner is server-derived and atomic RPC is used |
| `PATCH /v1/agents/{agent_id}` | `current_user` → ownership check → agent update | Existing negative test checks non-owner receives 404 without update |
| `GET /v1/agent-passports/{handle}` | Public projection via `user_db_request` with public/active filters | Existing tests assert private fields are not projected |
| `GET /v1/agents/{agent_id}` | `current_user` → ownership check → agent row | Existing tests assert owner filter; expand cross-user/tenant cases |

## Current evidence

- Existing API security tests reject missing and malformed bearer tokens.
- Existing agent tests cover server-derived ownership, active-owner filtering, non-owner update rejection, and public passport field projection.
- One recent GitHub Actions Smoke run completed successfully. ENG-P01 workflow was still in progress at the last status check; that is not a complete acceptance result.
- Railway reports the API, Web and Super Admin services Online with successful latest deployments. API logs contain `GET /healthz` → `200 OK`. External HTTP probing from the current execution environment failed at DNS resolution, so no independent HTTP response is claimed for Web/Admin in this audit.

## Acceptance still required

1. Finish tracing every tracked client file, import/helper and generated provider client.
2. Trace the exact SQL/RPC, tables, grants, RLS policies and tenant predicates for every data route.
3. Add missing negative regressions for organization cross-tenant reads, ID manipulation, invalid/expired tokens and any confirmed access-control defects.
4. Run integration tests only against dedicated staging Supabase with separate test identities and tenant fixtures; do not use canonical production for destructive tests.
5. Capture final CI run/job evidence and independently probe all three deployed URLs when network access is available.
6. Keep ENG-P01 `in_progress` until all acceptance evidence is present.

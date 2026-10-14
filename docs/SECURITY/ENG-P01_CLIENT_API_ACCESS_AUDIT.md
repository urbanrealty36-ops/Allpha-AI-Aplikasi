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
| `GET /readyz` | Checks configured Supabase URL/publishable key, then probes `/auth/v1/health` and `/rest/v1/` with bounded timeout; returns `reachable` only for HTTP 200 on both | Unit test mocks both upstream probes; deployed runtime probe remains unverified |
| `GET /v1/system/status` | System diagnostics handler | Confirm operator/public exposure policy and data returned |
| `GET /v1/me` | `current_user` → `user_db_request` → identity/profile rows | Add/retain token and owner-scope regressions |
| `PATCH /v1/me/profile` | `current_user` → `user_db_request` → profile update | Confirm user ID is derived server-side and RLS is enforced |
| `GET /v1/me/settings` | `current_user` → `user_db_request` → settings rows | Confirm owner-scoped query and policy |
| `PATCH /v1/me/settings` | `current_user` → `user_db_request` → settings writes | Confirm no client-supplied owner ID can change scope |
| `GET /v1/me/consents` | `current_user` → `user_db_request` → consent rows | Confirm owner scope and migration policy |
| `POST /v1/me/deactivation-request` | `current_user` → `rpc/request_account_deactivation` → `profiles` | API regression checks scoped RPC invocation; migration is not applied to production and real integration remains unverified |
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
- Allpha Smoke run [`38490988430`](https://github.com/urbanrealty36-ops/Allpha-AI-Aplikasi/actions/runs/38490988430) on commit `c6ae8ae32c53c825c6a27e35bf3d84c2f832eb21` completed successfully; its jobs show API regression tests and Web build passed. It does not exercise a real browser-authenticated journey or native device UI.
- ENG-P01 run [`38490988221`](https://github.com/urbanrealty36-ops/Allpha-AI-Aplikasi/actions/runs/38490988221) for the same commit was pending at the last inspection. An older run on commit `3800125cf84fdbc696fd5fe80c55c9dfc569824a` had one API test failure and Android/iOS builds still in progress; no artifacts from that run were available when queried. Do not treat its partial build steps as final evidence.
- Railway connector had previously reported the API, Web and Super Admin services Online, and API logs contained `GET /healthz` → `200 OK`. Independent external HTTP probes to the known Railway URLs failed due DNS resolution in this execution environment; no independent response is claimed for any of the three URLs in this session.
- The last source-level inventory found no direct Supabase business-table/RPC/Storage/Realtime access in the inspected client entry points; Web and Native use Supabase for Auth/session while observed business data calls go through FastAPI. This remains a bounded source audit, not proof of no indirect access in every dependency.

## Acceptance still required

1. Finish tracing every tracked client file, import/helper and generated provider client.
2. Trace the exact SQL/RPC, tables, grants, RLS policies and tenant predicates for every data route.
3. Add missing negative regressions for organization cross-tenant reads, ID manipulation, invalid/expired tokens and any confirmed access-control defects.
4. Run integration tests only against dedicated staging Supabase with separate test identities and tenant fixtures; do not use canonical production for destructive tests.
5. Capture final CI run/job evidence and independently probe all three deployed URLs when network access is available.
6. Keep ENG-P01 `in_progress` until all acceptance evidence is present.

## Expanded client/provider inventory (2026-10-14)

Repository tree at audited commit contained 32 files across the three clients. Runtime classification:

| Path | Provider/API access | Classification |
|---|---|---|
| `apps/web/lib/supabase.ts` | Lazy browser-only Supabase client, publishable key, session persistence/refresh | Active shared Auth/session helper; imported by Web identity and Agent pages |
| `apps/web/app/page.tsx` | Supabase Auth methods; FastAPI `/v1/me`, `/v1/me/profile`, `/v1/me/settings`, `/v1/me/deactivation-request` | Active; business profile/settings operations via API |
| `apps/web/app/agents/page.tsx` | Supabase Auth/session; FastAPI Agent endpoints | Active; Agent business operations via API |
| `apps/web/app/agents/passport/[handle]/page.tsx` | Public FastAPI passport endpoint; no Supabase import | Active public read; no provider bypass found |
| `apps/client/App.tsx` | Native Supabase Auth/session client, Expo SecureStore; FastAPI `/v1/me` | Active native thin slice; Auth/session is allowed |
| `apps/super-admin/app/page.tsx` | FastAPI `/healthz`, `/readyz`, `/v1/system/status`; no Supabase client | Active diagnostics only; privileged operational workflows are not established by this page |
| `apps/*/app/layout.tsx`, `globals.css`, Next config, ESLint config, Dockerfiles | No runtime business provider calls observed in inspected contents | Active build/presentation configuration, not data-access helpers |
| `apps/*/package.json`, lockfiles, `tsconfig.json`, `app.json` | Dependency/build configuration | Build-time, not runtime data access |
| `apps/client/scripts/smoke-test.mjs`, `apps/super-admin/scripts/smoke-test.mjs` | Local smoke-test scripts | Test-only |
| `apps/client/README.md`, `apps/super-admin/README.md` | Documentation | Not runtime code |

No standalone Web/Super Admin provider helper beyond the listed Web helper was observed in the tracked tree. Native has an inline Supabase client in `App.tsx`; this is active Auth/session use, not a shared helper. The three client package lockfiles are not runtime access paths. The source audit does not label code as dead solely because it has few call sites; no confirmed unused runtime provider helper was found in this inventory.

## Endpoint → SQL/RPC → table → grant/RLS map

The live canonical Supabase project was inspected read-only on 2026-10-14. The database reported RLS enabled for `profiles`, `organizations`, `organization_memberships`, `audit_events`, `user_settings`, `user_consents`, `ai_agents`, and `agent_ownerships`. Applied migration history included ENG-P02/P03/P04 migrations through `20261013090730_eng_p02_least_privilege_identity_tenant_grants`. This is production schema inspection only; no destructive integration was run against it.

| Endpoint | Data operation | Table/RPC | Authorization evidence / gap |
|---|---|---|---|
| `GET /healthz` | No DB call | None | Public liveness only |
| `GET /readyz` | Env configuration check, not a live DB query | None | Reports Supabase configured from env; it does not prove DB reachability |
| `GET /v1/system/status` | Env/configuration diagnostics | None | Review exposure/operational authorization as a follow-up; current response includes environment and capability booleans |
| `GET /v1/me` | GET; if missing, POST self profile | `profiles` | `id=auth user id`; RLS profile self/public read and self insert; column-level insert grant restricts mutable fields |
| `PATCH /v1/me/profile` | PATCH selected fields | `profiles` | Filter uses authenticated user's ID; profile schema rejects authority fields; column grant limits updates |
| `GET /v1/me/settings` | GET; if missing, POST self settings | `user_settings` | `user_id=auth user id`; RLS self-scoped; grants currently include select/insert/update to authenticated |
| `PATCH /v1/me/settings` | PATCH selected settings, fallback self insert if absent | `user_settings` | Filter and RLS use authenticated user's ID; payload schema rejects `user_id` |
| `GET /v1/me/consents` | GET consent history | `user_consents` | Query filters `user_id=auth user id`; RLS self select; client updates/deletes denied |
| `POST /v1/me/deactivation-request` | POST RPC after correction | `rpc/request_account_deactivation` → `profiles` | New migration makes target derive from `auth.uid()`; direct update to `account_status` remains excluded from column-level grants. Migration still needs staging application/integration verification |
| `GET /v1/organizations` | GET organizations | `organizations` | RLS requires membership/ownership; result set relies on RLS rather than an explicit user filter |
| `POST /v1/organizations` | POST organization; trigger creates owner membership and audit path | `organizations`, `organization_memberships`, `audit_events` | API derives `owner_id` from verified Auth identity; insert grant limited to slug/name/owner_id; membership direct mutations denied |
| `GET /v1/organizations/{id}/memberships` | GET memberships then organization existence lookup | `organization_memberships`, `organizations` | RLS scopes membership to self/admin and organization to member/owner; handler returns 404 when RLS hides tenant. Real cross-tenant staging proof pending |
| `GET /v1/agents` | GET ownership relationships and related Agent rows | `agent_ownerships`, `ai_agents` | Query scopes owner to verified user and active ownership; RLS applies |
| `POST /v1/agents` | POST atomic RPC | `rpc/create_ai_agent` → `ai_agents`, `agent_ownerships` | RPC is SECURITY INVOKER, derives `auth.uid()`, validates payload, inserts active owner; execute granted to authenticated; direct ownership updates/deletes denied |
| `PATCH /v1/agents/{id}` | Owner check then PATCH | `agent_ownerships`, `ai_agents` | API owner predicate plus RLS; existing regression covers non-owner 404/no update |
| `GET /v1/agent-passports/{handle}` | Anonymous/public projection read | `ai_agents` | Public/active filters; anonymous SELECT grant/policy uses public projection; private persona/boundaries/ownership excluded |
| `GET /v1/agents/{id}` | GET Agent after ownership check | `agent_ownerships`, `ai_agents` | Owner predicate plus RLS; expand direct cross-user staging test |

### Confirmed code/grant mismatch and correction

The former deactivation handler directly PATCHed `profiles.account_status`, but the applied least-privilege migration grants `UPDATE` only on `username, display_name, avatar_url, bio, visibility, locale`. `account_status` is deliberately server-owned, so that handler's write path was inconsistent with the grants.

Correction committed to `main`:
- Endpoint now calls `POST rpc/request_account_deactivation`.
- Migration `20261014100000_eng_p01_scoped_account_deactivation_rpc.sql` defines a SECURITY DEFINER function with empty search_path, derives the target only from `auth.uid()`, and grants execute only to `authenticated`.
- API regression asserts the handler calls the scoped RPC with an empty body and does not pass a caller-selected user ID.

This is a source-level correction. The new migration has not been applied to the production database, and must not be applied to production as part of this audit. Validate the migration and the behavior in isolated staging first.

## Regression coverage added/retained

- Added invalid Supabase bearer token test: Auth 401/403 → stable `401 INVALID_TOKEN`, no token leakage.
- Added expired-token fixture test for the same fail-closed contract.
- Added handler-level manipulated foreign organization ID test: memberships and organization queries carry the supplied ID but the foreign tenant is returned as `404 NOT_FOUND` when RLS hides it.
- Added deactivation route regression for the scoped RPC.
- Existing Agent regressions cover client-forged ownership/authority fields, server-derived owner, active-owner filtering, and non-owner update denial.
- Mocked handler tests prove API query construction/error behavior only; they do not prove live RLS, SQL grants, expired JWT semantics at Supabase, or tenant isolation. Those require isolated staging integration.

## Staging and live verification status

- Supabase connector lists only canonical project `dvdziauyvuhcnqhrrvww` (`AllphaAiAplikasi-db`); `list_branches` returned no development branches. No separate staging Supabase project or provisioned two-user/two-tenant fixtures were found through the connected account.
- Do not run tenant integration against the canonical production project. Creating a Supabase branch/project requires a separate explicit cost confirmation; therefore live two-identity integration remains blocked pending an approved isolated staging target and fixtures.
- The latest ENG-P01 run `38468039718` on commit `1fd62a442fafa099524cf94e9c25b24a6566d3f8` had Web typecheck/build, configured Supabase journey, API regressions, Super Admin build and staging tenant-isolation job successful; Android native prebuild/debug APK failed and iOS simulator build was still in progress at inspection. The run must be rechecked after the current security commits.
- Latest Allpha Smoke run `38468039854` on the same prior commit completed successfully. It does not include the newer deactivation fix or expanded token/tenant regressions.
- Independent external HTTP probes remain unverified because the execution environment previously failed DNS resolution. Railway connector status/logs are not equivalent to independent external HTTP response evidence.

## Current decision

ENG-P01 remains `in_progress`. Do not promote status until (a) current commit's CI jobs are final and Android failure is fixed or properly explained, (b) the new SQL migration and tests pass in isolated staging, (c) real two-user/two-tenant access tests pass, and (d) endpoint verification evidence is recorded.


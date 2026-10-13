# Allpha monorepo application boundaries

## Direct-main delivery

All implementation commits go directly to `main`. Routine changes do not require a branch or pull request. The main smoke workflow is intentionally small; deeper hardening is delivered alongside features instead of as a blanket blocker.

## Application boundaries

| Area | Path | Responsibility | Extraction path |
|---|---|---|---|
| End-user client | `apps/client` | Native Android/iOS product client; web client may share contracts and design tokens | Own package/config/build and API contracts |
| Web | `apps/web` | Current web thin slice; integrate with client-facing API | Can be deployed or extracted independently |
| Super Admin | `apps/super-admin` | Operator-facing control plane | Own app/config/build and backend API integration |
| Backend | `apps/api` | Current FastAPI service; canonical domain/API owner | Can be extracted as backend service/repository |
| Shared contracts | `packages/contracts` (create as needed) | Versioned API schemas/types shared by clients | Publish/version independently when extracted |

Do not duplicate a domain engine or data registry to satisfy directory naming. Keep API boundaries explicit so any app can move to a separate repository later without changing its domain behavior. Supabase `AllphaAiAplikasi-db` remains the canonical data platform. Client apps must not embed service-role or provider secrets.

## GLB developer flow

Developer uploads/registers a GLB through the backend API, the backend stores metadata and the object reference in the canonical asset catalog, and the client/renderer consumes the catalog manifest. Local/developer preview should not require a manual approval chain. The UI must show a useful error for unreadable or unsupported files. Public distribution still needs rights and access to be clear; preview visibility alone does not grant public permissions.

## Implementation order

1. ENG-P01 web/API foundation (present in `apps/web` and `apps/api`).
2. ENG-P02 Supabase connection, auth/session, and ownership boundaries.
3. ENG-P03 profile and settings vertical slice.
4. Asset catalog + direct GLB-to-renderer integration as an early spatial slice.
5. Continue product domains with real backend data and connected UI.

# Allpha AI Aplikasi

Monorepo for Allpha's client applications and canonical backend API.

## Current foundation

- apps/web: Next.js web thin slice.
- apps/api: FastAPI with Supabase Auth token validation, user-scoped PostgREST access, identity and organization endpoints.
- apps/api/supabase/migrations: versioned schema, tenant authorization, and audit migrations.
- apps/client: boundary for native Android/iOS client work.
- apps/super-admin: boundary for the separate operator console.
- docker-compose.yml: local web/API launch.
- Canonical database: Supabase AllphaAiAplikasi-db (dvdziauyvuhcnqhrrvww).

## Run locally

API:
```bash
cd apps/api
python -m venv .venv
# Linux/macOS: source .venv/bin/activate
# Windows: .venv\\Scripts\\activate
python -m pip install -e ".[dev]"
uvicorn allpha_api.main:app --reload
```

Web in another terminal:
```bash
cd apps/web
npm install
npm run dev
```

Open http://localhost:3000; the browser client checks the API at http://localhost:8000.

With Docker Compose:
```bash
cp .env.example .env
# Set SUPABASE_PUBLISHABLE_KEY in the local .env (never commit the populated file).
docker compose up --build
```

Open the web app at http://localhost:3000; API health is http://localhost:8000/healthz.

## Supabase configuration

Set SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY only in the backend runtime environment. SUPABASE_PUBLISHABLE_KEY is safe for public client contexts, but these API routes use it server-side together with the user's bearer token; RLS is enforced by forwarding that token to PostgREST. Do not configure a service-role key for these endpoints and never expose privileged keys to clients.

Authenticated endpoints:
- GET /v1/me
- PATCH /v1/me/profile
- GET /v1/organizations
- POST /v1/organizations
- GET /v1/organizations/{organization_id}/memberships

No bearer token returns 401. Unconfigured Supabase returns a controlled 503. Tenant membership role changes are intentionally not exposed through client routes.

## Quick checks

```bash
cd apps/api && python -m pip install -e ".[dev]" && pytest -q
cd apps/web && npm install && npm run build
```

GitHub Actions runs API tests and the web production build on pushes to main. The workflow is intentionally lightweight.

## Phase status

ENG-P02 is IN_PROGRESS: code and additive migrations are committed to main and applied to the canonical Supabase project. It is not yet acceptance-passed: latest CI, real authenticated flows, cross-tenant negative tests, and target deployment verification remain required. See docs/PHASES/ENG_P02_DATABASE_AUTHORIZATION.md.

Full transitive dependency lockfiles and deployment-platform-specific production URLs/secrets remain outstanding from ENG-P01. Native Android/iOS application behavior is not claimed as implemented.

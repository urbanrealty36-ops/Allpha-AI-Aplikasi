# Allpha AI Aplikasi

Monorepo for Allpha's client applications and canonical backend API.

## Current foundation

- apps/web: Next.js web thin slice.
- apps/api: FastAPI with Supabase Auth token validation, user-scoped PostgREST access, identity and organization endpoints.
- apps/api/supabase/migrations: versioned schema, tenant authorization, and audit migrations.
- apps/client: React Native + Expo native Android/iOS thin slice with Supabase Auth, SecureStore session persistence, API health, and authenticated `GET /v1/me`.
- apps/super-admin: independent Next.js operator console with live read-only checks for `/healthz`, `/readyz`, and `/v1/system/status`; privileged operations stay disabled until operator authorization/audit endpoints exist.
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

Super Admin (run separately; default port 3000, use `--port 3001` when Web is also running):
```bash
cd apps/super-admin
npm install
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000 npm run dev -- --port 3001
```

Native Android/iOS (see `apps/client/README.md` for Supabase configuration and platform-specific API origins):
```bash
cd apps/client
npm install
npm run typecheck && npm test
npx expo prebuild --platform android && npx expo run:android
# macOS + Xcode:
npx expo prebuild --platform ios && npx expo run:ios
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

Set SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY only in the backend runtime environment. For the web browser build, set NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY to the canonical project's URL and publishable key. SUPABASE_PUBLISHABLE_KEY is safe for public client contexts, but these API routes use it server-side together with the user's bearer token; RLS is enforced by forwarding that token to PostgREST. Do not configure a service-role key for these endpoints and never expose privileged keys to clients.

Human Identity UI: open the web app root to sign in/sign up, then edit profile fields and persisted user preferences. The browser uses Supabase Auth for sessions and the API for profile/settings data. See docs/PHASES/ENG_P03_HUMAN_IDENTITY.md for scope and remaining acceptance evidence.

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

ENG-P01 remains `in_progress`: native source, Expo prebuild configuration, auth/profile API slice, Super Admin diagnostics UI, CORS allowlist, and platform CI are committed. Acceptance still requires successful Android APK and iOS simulator builds, the full latest CI run, configured real Supabase Auth session/profile journey, target-device verification, deployment-specific URLs/secrets, and reproducible dependency lockfiles. Do not claim production readiness from source checks or CI alone.

# Allpha AI Aplikasi

Monorepo for Allpha's client applications and canonical backend API.

## Current foundation

- `apps/web`: Next.js web thin slice.
- `apps/api`: FastAPI service with health/readiness endpoints.
- `apps/client`: boundary for native Android/iOS client work.
- `apps/super-admin`: boundary for the separate operator console.
- `docker-compose.yml`: local web/API launch.
- Canonical database: Supabase `AllphaAiAplikasi-db`; actual DB/auth integration is the next phase, not claimed complete by this thin slice.

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

Open `http://localhost:3000`; the browser client checks the API at `http://localhost:8000`.

With Docker Compose:
```bash
docker compose up --build
```

Open the web app at `http://localhost:3000`; API health is `http://localhost:8000/healthz`.

## Environment

Copy `.env.example` to `.env` for Compose overrides. Never commit populated secrets. Browser-exposed `NEXT_PUBLIC_*` values are public.

## Quick checks

```bash
cd apps/api && python -m pip install -e ".[dev]" && pytest -q
cd apps/web && npm install && npm run build
```

GitHub Actions runs the API tests and web production build on pushes to `main`. The workflow is intentionally lightweight.

## Current status

ENG-P01 has a successful GitHub Actions run for API tests and web production build: [run details](https://github.com/urbanrealty36-ops/Allpha-AI-Aplikasi/actions/runs/38350451270).

Direct dependency versions are pinned. Full transitive dependency lockfiles and deployment-platform-specific production URLs/secrets remain outstanding; therefore dependency reproducibility and production deployment configuration are not yet fully complete. Supabase and native mobile are not claimed as integrated by this foundation.

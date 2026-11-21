# Railway deployment — Web PWA

Canonical source: `urbanrealty36-ops/Allpha-AI-Aplikasi`, branch `main`.

- Application root: `apps/web`
- Build context: `apps/web`
- Dockerfile: `apps/web/Dockerfile`
- Framework: Next.js 15, standalone output
- Build command in image: `npm run build` (includes the repository smoke assertions and `next build`)
- Runtime: `node server.js`, with Railway-provided `PORT`
- Public service domain: `allpha-web-production.up.railway.app`
- Container port: Railway runtime port `8080`
- Health check: `/login` (the home route redirects to `/welcome`, so `/` is not a valid 200 health-check target)
- Required public build variables: `NEXT_PUBLIC_API_BASE_URL`, `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`
- Backend authority: canonical `apps/api` FastAPI service; no privileged Supabase or provider secrets belong in this client.

The Native app under `apps/client` is built/distributed through Expo/EAS and is not a persistent Railway web service. The Super Admin client is independently deployed from `apps/super-admin`.

This file records the service boundary and deployment contract; successful build/health-check is not proof of complete authenticated business-flow integration.

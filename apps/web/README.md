# Allpha Web

Next.js Web/PWA application. The production deployment is the Railway service `Allpha-Web` in the Allpha Railway project.

## Production API contract

- Set `NEXT_PUBLIC_API_BASE_URL` in the Railway `Allpha-Web` service to the canonical Railway FastAPI service URL.
- Current API service URL: `https://allpha-ai-aplikasi-production.up.railway.app`.
- Browser requests must use the canonical FastAPI API. Do not use Vercel API/runtime URLs or add business logic to this client.
- `NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` are public client configuration only. Never expose a Supabase service-role/secret key, provider secret, or worker credential to the browser.
- The API service's CORS allowlist must include the approved production Web and Super Admin origins.

## Local development

```bash
npm install
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000 npm run dev
npm run test && npm run build
```

Railway builds use the service root directory `/apps/web` and the existing Dockerfile. The public API base URL is a build-time Next.js setting; rebuild the Web service after changing it.

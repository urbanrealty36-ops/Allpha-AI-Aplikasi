# Allpha Super Admin
Independent Next.js operator console. The ENG-P01 slice performs read-only checks against the canonical FastAPI service.

```bash
npm install
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000 npm run dev
npm run typecheck && npm test && npm run build
```

It calls actual `/healthz`, `/readyz`, and `/v1/system/status` endpoints. It does not synthesize user/business data. Identity/tenant management, moderation, asset operations and privileged actions remain disabled until operator authentication, scopes, authorization, audit and backend endpoints exist. Never place service-role credentials in browser-visible variables.


## Railway production API contract

- The production service is Railway `Allpha-Super-Admin` in the Allpha Railway project.
- Set `NEXT_PUBLIC_API_BASE_URL` in that Railway service to the canonical FastAPI URL: `https://allpha-ai-aplikasi-production.up.railway.app`.
- Operator actions must call FastAPI and require the canonical operator authentication, scopes, authorization and audit contracts.
- Never place Supabase service-role/secret keys or provider/worker credentials in `NEXT_PUBLIC_*` variables or browser code.
- The public API base URL is a build-time Next.js setting; rebuild the Super Admin service after changing it.

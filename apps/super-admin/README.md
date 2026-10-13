# Allpha Super Admin
Independent Next.js operator console. The ENG-P01 slice performs read-only checks against the canonical FastAPI service.

```bash
npm install
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000 npm run dev
npm run typecheck && npm test && npm run build
```

It calls actual `/healthz`, `/readyz`, and `/v1/system/status` endpoints. It does not synthesize user/business data. Identity/tenant management, moderation, asset operations and privileged actions remain disabled until operator authentication, scopes, authorization, audit and backend endpoints exist. Never place service-role credentials in browser-visible variables.

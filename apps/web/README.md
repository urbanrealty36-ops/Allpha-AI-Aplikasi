# Allpha Web

Next.js Web/PWA application. The production deployment is the Railway service `Allpha-Web` in the Allpha Railway project.

## Production API contract

- Set `NEXT_PUBLIC_API_BASE_URL` in the Railway `Allpha-Web` service to the canonical FastAPI origin `https://api.allpha.web.id`.
- Current API service URL: `https://api.allpha.web.id`.
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


## Static asset delivery

- The production Docker runner copies the complete sanitized `public/` directory beside the Next.js standalone server. Public image/icon paths remain same-origin under `/assets/*` and `/icon.svg`; `/_next/static/*` is copied from the generated Next build and uses Next's immutable hashed-asset cache behavior.
- `npm run test` generates `public/asset-manifest.json` with sorted public paths, byte sizes and SHA-256 digests, then verifies the required slide/district assets and the Docker runtime copy contract.
- The pinned reference UI PRD copies under `assets/aistudio/` are intentionally mirrored by the reference-asset capture workflow and are included in the public asset manifest. The manifest generator allowlists only those exact reference files; other Markdown documents are rejected so private docs cannot be added to `public/` accidentally.
- No GLB binaries are tracked in this Web public tree. Spatial GLB delivery remains through the canonical Spatial manifest/API and authorized Supabase Storage references; do not copy private or unpublished GLBs into `public/`.
- There is no custom `basePath` or `assetPrefix`; production public paths resolve from the `https://allpha.web.id` origin.


### Runtime asset health

Railway's Web health check uses `/asset_health`. This route performs HEAD requests through the running Next.js HTTP server for the generated asset manifest, icon, and representative Welcome/Cinema/Live/District/Citadel files. It returns 200 only when all required static URLs respond with the expected MIME type; otherwise it returns 503. The Docker build separately verifies the same files exist in the final non-root runner image.

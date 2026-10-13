# Environment and Secret Handling — ENG-P01

## Environment separation

Use separate configuration and credentials for local development, automated tests, staging and production. Do not copy production credentials into developer machines or CI logs. Each deployment environment must be explicitly identified through `ALLPHA_ENVIRONMENT`.

## API configuration

| Variable | Purpose | Secret? | Initial behavior |
|---|---|---|---|
| `ALLPHA_ENVIRONMENT` | Environment label | No | Defaults to `development` |
| `ALLPHA_API_VERSION` | Version returned by readiness/diagnostics | No | Defaults to package baseline `0.1.0` |
| `PORT` | Container HTTP port | No | Docker defaults to `8000` |
| `NEXT_PUBLIC_API_BASE_URL` | Browser-visible API origin | No | Defaults to `http://localhost:8000` |

Do not add Supabase service-role keys, database passwords, JWT signing keys, payment credentials, AI provider credentials, or other secrets to `NEXT_PUBLIC_*` variables. Browser-exposed variables are public.

## Secret storage

- Local-only secrets belong in an ignored `.env.local` or a local secret manager; never commit populated secret files.
- CI secrets must be configured through GitHub Actions secrets or a dedicated secret manager, scoped to the minimum environment and job.
- Production credentials belong in the deployment platform's secret manager and must never be included in container images or client bundles.
- Redact authorization headers, tokens, passwords, user content and provider payloads from logs.
- Rotate/revoke exposed credentials promptly and record incident follow-up.

## Current limitations

No deployment platform, external dependency credentials, database connectivity or production secret wiring has been configured by this foundation scaffold. The API readiness payload explicitly reports external services as `not_configured`. Configure and verify each dependency in its own approved phase before changing that status.

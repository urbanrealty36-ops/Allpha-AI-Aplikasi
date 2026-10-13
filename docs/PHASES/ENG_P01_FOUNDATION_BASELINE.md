# ENG-P01 — New Platform Foundation & Deployable Thin Slice

- **Status:** `in_progress`
- **Started:** 2026-10-13
- **Branch:** `feat/eng-p01-platform-foundation`
- **Decision context:** ADR-0001 accepted by Product Owner direction; Phase 00 remains independently evidence-gated.
- **Scope:** Minimal web client, FastAPI service, health/readiness/version diagnostics, standard request correlation, container entry point, CI checks and environment guidance.
- **Non-goals:** Authentication/tenant isolation (ENG-P02), production database wiring, real business domains, AI Gateway, production deployment, native mobile framework selection (ADR-0002 remains open), and claiming external dependencies are healthy when they are not configured.

## Initial implementation

| Requirement | Implementation | Evidence/status |
|---|---|---|
| API liveness | `GET /healthz` | Implemented; automated test added |
| API readiness | `GET /readyz` | Implemented; external dependencies explicitly report `not_configured` |
| API diagnostics | `GET /v1/system/status` | Implemented; version, uptime, environment, capability flags, request ID |
| Request correlation | `X-Request-ID` middleware | Implemented; request ID preserved or generated |
| Safe error contract | `INTERNAL_ERROR` envelope for unexpected errors | Implemented; exception details are not returned |
| Web thin slice | Next.js app in Bahasa Indonesia | Implemented; displays live API readiness or a clear unavailable/retry state |
| API container | `apps/api/Dockerfile` | Added; container build not yet verified |
| CI | API tests, web lint/build, dependency audit workflow | Added; execution result pending PR workflow |
| Dependency reproducibility | Exact direct web dependency versions; Python ranges | **Open:** committed lockfiles and transitive pinning still needed |
| Native mobile | Not selected | **Blocked on ADR-0002**; no framework decision invented |
| Deployable environments | Not configured | **Open:** deployment target, secrets, environment separation, smoke test |

## Local commands

API:

```bash
cd apps/api
python -m pip install -e ".[dev]"
pytest
uvicorn allpha_api.main:app --reload
```

Web:

```bash
cd apps/web
npm install
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000 npm run dev
npm run lint
npm run build
```

API endpoints:
- `GET /healthz` — process liveness only.
- `GET /readyz` — process readiness plus explicit dependency configuration states.
- `GET /v1/system/status` — basic non-secret diagnostics.

## Security and operational notes

- Health endpoints do not claim that Postgres, Supabase, object storage, or AI providers are connected.
- Diagnostics disclose no secret values. The environment name is non-secret configuration.
- Authentication is not yet implemented; do not expose this initial service as a production business API.
- Unexpected exception details are withheld from clients; request ID is returned for correlation.
- No business data, demo accounts, mock social content, or fake production records are created.
- Dependency audit and CI must be inspected after the PR workflow runs. A workflow file existing is not proof that it passed.

## Remaining exit criteria

- [ ] Add committed lockfiles / reproducible transitive dependency resolution.
- [ ] Run API tests and record result.
- [ ] Run web lint, type-check and production build; fix findings.
- [ ] Run dependency and secret scanning; resolve high/critical findings.
- [ ] Add deployment target/configuration and environment/secret guide.
- [ ] Verify deployed API health/readiness and web-to-API connectivity.
- [ ] Add native mobile thin slice after ADR-0002 is decided.
- [ ] Capture workflow run links, commit SHA and review evidence.
- [ ] Separate Phase 00 exit sign-off from ENG-P01 acceptance.

**No completion claim:** this phase remains `in_progress` until its evidence-based exit gate passes.

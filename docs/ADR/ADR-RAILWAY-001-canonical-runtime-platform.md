# ADR-RAILWAY-001 — Railway as the canonical Allpha runtime and deployment platform

- **Status:** ACCEPTED — explicit Product Owner architecture decision, 2026-11-22
- **Scope:** Platform-wide deployment, backend runtime, workers, cron, orchestration, networking and production traffic
- **Repository:** `urbanrealty36-ops/Allpha-AI-Aplikasi`, branch `main`
- **Railway project:** `noble-wonder` / `49dccd43-0ebe-4128-8010-164a273d8cad`
- **Canonical database:** Supabase `AllphaAiAplikasi-db` / `dvdziauyvuhcnqhrrvww`
- **Supersedes:** The deployment-provider clauses of Master PRD v3.1.0 and the Vercel runtime decision in ADR-WP04-004. Product/domain semantics, security controls, Postgres leases, idempotency, retry and retention invariants are unchanged.

## Context

The previous architecture assigned Web deployment to Vercel and WP-04 lifecycle execution to a Vercel project/Cron. That is no longer the Product Owner's deployment decision. The existing Allpha monorepo already has three Railway production services connected to `main`, while the worker source contains dedicated entrypoints and Dockerfiles that have not yet been activated as Railway services.

## Decision

1. **Railway is the sole Allpha deployment and runtime platform** for Web, Super Admin, FastAPI, persistent workers, scheduled jobs, Cron and orchestration. Do not create or retain a second production runtime on Vercel.
2. The existing Railway services remain the only application entrypoints:
   - `Allpha-AI-Aplikasi` → `apps/api` (FastAPI control plane and canonical business API).
   - `Allpha-Web` → `apps/web` (Next.js Web/PWA).
   - `Allpha-Super-Admin` → `apps/super-admin` (operator console).
3. Native Android/iOS remains React Native + Expo/EAS. It consumes the canonical Railway FastAPI API; it is not redeployed as a WebView.
4. Supabase remains the sole canonical PostgreSQL/Auth/Storage/Realtime data platform. Railway workers reuse existing Postgres tables, RPCs, leases, event inboxes, ledger and domain engines. No second database, queue, ledger, registry, API or runtime is permitted.
5. Each long-running worker runs as an isolated Railway service/process using the existing `apps/api` package, entrypoint and Dockerfile where one exists. A worker service is not a new backend. Resource limits, non-root execution, restricted egress, restart policy, health/readiness, logs and least-privilege environment must follow its worker contract.
6. A domain queue/event inbox has exactly one active consumer owner. A scheduled lifecycle has exactly one active scheduler. Do not run a Railway worker and a Vercel Cron/consumer in parallel against the same work. Preserve Postgres lease fencing and idempotency during handover.
7. The existing Vercel Cron declaration and Vercel project references are legacy migration inputs only. They are not authorization to create new Vercel deployments or keep a second production runtime. Remove the Vercel Cron/configuration and disable residual Vercel integrations only after the Railway replacement is deployed, verified, domain traffic is switched, and no Vercel consumer remains active.
8. Do not activate a worker merely because its source/Dockerfile exists. Require its canonical migration/RPC/schema readiness, server-only credentials, provider/scanner dependencies, feature-policy gates and runtime verification. Missing dependencies remain explicit blockers and fail closed.
9. Keep all existing workstream ownership unchanged: WP-06 Agent Social Automation, WP-11 AI Cinema, ENG-P25–P27 Live/Stage, and Authentication continue in parallel. Do not promote any workstream from a deployment or build result.

## Canonical worker inventory

The following entrypoints already exist in `apps/api/pyproject.toml` and/or `apps/api/src/allpha_api`. They are process targets, not a claim that Railway services are already deployed.

| Worker process | Existing entrypoint | Existing image/build contract | Activation boundary |
|---|---|---|---|
| Agent Runtime / WP-06 Social consumer | `allpha-agent-runtime-worker` | `Dockerfile.agent-runtime-worker` | WP-06/07 migrations, schema readiness, policy, credit and receipt contracts |
| Social Graph outbox | `allpha-social-graph-outbox-worker` | `apps/api/Dockerfile` with worker command | Server-side Supabase key and existing outbox RPC |
| Agent task scheduler | `allpha-agent-task-scheduler` | `apps/api/Dockerfile` with worker command | Schedule schema/RPC and canonical Workflow Engine |
| Workflow worker host | `allpha-workflow-worker` | `apps/api/Dockerfile` with worker command | Workflow schema, lease/retry and Agent Runtime dependencies |
| Notification delivery | `allpha-notification-worker` | `apps/api/Dockerfile` with worker command | Notification delivery schema/provider configuration |
| Knowledge ingestion | `allpha-knowledge-worker` | `apps/api/Dockerfile` with worker command | Canonical Knowledge authorization and ingestion schema |
| Generation jobs | `allpha-generation-worker` | `Dockerfile.generation-worker` | Approved model route, provider, credit policy, entitlement and source-only migrations |
| Generation artifact deletion | `allpha-generation-artifact-deletion-worker` | `Dockerfile.generation-artifact-deletion-worker` | Deletion migration, owner authorization and Storage credentials |
| Content image processing | `allpha-content-media-worker` | `Dockerfile.media-worker` | Applied media-job migrations, approved ClamAV endpoint and private Storage credentials |
| Content video/audio transcode | `allpha-content-transcode-worker` | `Dockerfile.transcode-worker` | Approved Cloudinary account, ClamAV and callback configuration |
| Scheduled content publication | `allpha-content-scheduler` | `Dockerfile.content-scheduler` | Exactly-one scheduler ownership and applied lifecycle schema |
| Content retention | `allpha-content-retention-worker` | `Dockerfile.retention-worker` | Backup/PITR, restore, legal-hold and approval gates; purge disabled by default |
| Provider callback processor | `allpha-content-provider-callback` | `Dockerfile.provider-callback-worker` | Provider signature configuration, scanner and callback schema |
| Provider cleanup | `allpha-content-provider-cleanup` | `Dockerfile.provider-cleanup-worker` | Cloudinary credentials and cleanup lifecycle schema |

Do not create duplicate worker services for the same entrypoint or add a second worker queue. The existing `agent_runtime_worker.py` owns WP-06 event dispatch and Agent Runtime tasks; a separate WP-06 event-consumer implementation is prohibited.

## Cron and scheduler ownership

- Long-running polling workers remain Railway services, not HTTP request handlers.
- Bounded periodic jobs use Railway Cron only when no persistent worker already owns that lifecycle.
- The previous `GET /internal/cron/platform-lifecycle` schedule must be reconciled against `allpha-content-scheduler` and provider-cleanup/retention workers before activation. The same scheduled publication or cleanup batch must never have two active consumers.
- Keep the existing daily schedule semantics until a documented cadence change is justified. Railway's minimum Cron interval is five minutes; do not change cadence simply because the platform allows it.
- Social Graph outbox is a durable event consumer with Postgres claim/lease/retry semantics, not a second daily cron consumer.

## Migration and cutover order

1. Keep current Railway application services and verify their source, branch, root directory, Dockerfile, health checks and production deployments.
2. Reconcile every worker entrypoint against `WORKERS.md`, its Dockerfile, required environment, migration/RPC readiness, resource limits and single-consumer ownership.
3. Configure server-only secrets in Railway. Never copy secrets into Git, build arguments, public variables, logs or client applications.
4. Deploy only workers whose schema, secrets, policy and external dependencies are ready. Verify each worker by durable receipt/state evidence, not process startup alone.
5. Configure the single Railway Cron/scheduler owner and verify its authenticated invocation and resulting Postgres lifecycle evidence.
6. Attach the approved custom domains to Railway services, verify TLS/DNS/health and switch traffic. The current auto-generated Railway service domains do not themselves prove custom-domain cutover.
7. Stop the corresponding Vercel Cron/consumer at the cutover boundary; verify no duplicate consumer or scheduled execution remains.
8. Remove `apps/api/vercel.json`, Vercel project references, environment bindings, workflows and integrations only after all traffic and workloads have been moved and verified. Then disable/delete residual Vercel deployments/integrations. Do not perform a premature cutover that interrupts production.

## Current evidence and blockers at acceptance of this ADR

- Railway project `noble-wonder` exists with three production services connected to repository `main`; their latest application deployments were SUCCESS and services were online at inspection.
- The three service descriptions had no custom domains configured. No custom-domain traffic cutover is evidenced.
- The Railway API service variable-name inventory did not contain `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_SECRET_KEY`, `CRON_SECRET`, `CLAMAV_HOST`, or Cloudinary credentials. OAuth values were redacted; no secret values were read. Worker services therefore cannot be truthfully marked activated.
- No worker service exists in the Railway production environment at this checkpoint; only the three application services exist.
- Supabase migration history ends at `20261115185633`. WP-06 event-intake/claim, DM approval and event-rate serialization migrations are source-only and not applied. Do not activate the WP-06 consumer before canonical schema readiness.
- ADR-0005 approves the Option C direction only. It does not approve physical knowledge-consent/grant schema or provider. Knowledge retrieval remains fail-closed.
- Live Chat remains fail-closed until ENG-P25 exposes canonical Agent participant/session permission and role authority.
- ClamAV, Cloudinary, approved generation model/credit policy, and retention backup/restore/legal-hold approvals remain separate activation gates.
- No Vercel service was disabled by this ADR. Cutover requires the ordered traffic and worker evidence above.

## Consequences

Railway is the only target for new and migrated Allpha runtime workloads. Source implementations remain reusable, but runtime activation is individually gated. The previous Vercel-specific WP-04 decision is historical and superseded only for deployment/runtime hosting; its security, media scanning, retention and lifecycle invariants remain in force.

# Allpha Railway Migration — Implementation Checkpoint

**Date:** 2026-11-22  
**Repository:** `urbanrealty36-ops/Allpha-AI-Aplikasi`  
**Branch:** `main`  
**Status:** `in_progress / runtime-worker-activation-blocked / traffic-cutover-not-verified`  
**Architecture authority:** `docs/ADR/ADR-RAILWAY-001-canonical-runtime-platform.md`

## Implemented in this checkpoint
- Recorded Railway as the sole deployment/runtime platform in a new accepted ADR.
- Marked ADR-WP04-004's Vercel hosting decision superseded while preserving its security, lease, scanner and retention invariants.
- Updated `apps/api/WORKERS.md` to replace Vercel-specific worker/runtime instructions with Railway service and single-consumer contracts.
- Appended the Railway deployment amendment to the consolidated Master PRD.
- No new phase, database, queue, domain engine or worker implementation was created.

## Railway production evidence
- Project: `noble-wonder` / `49dccd43-0ebe-4128-8010-164a273d8cad`.
- Existing application services: `Allpha-AI-Aplikasi`, `Allpha-Web`, `Allpha-Super-Admin`.
- All three were online with latest deployments in SUCCESS at inspection.
- No custom domains were configured on the three services.
- No worker service existed in the production environment at inspection.

## Activation blockers
1. Railway API service variable names do not include `SUPABASE_SERVICE_ROLE_KEY` or `SUPABASE_SECRET_KEY`; worker processes requiring privileged Supabase access cannot be started.
2. No Railway worker services or Railway Cron lifecycle service are deployed.
3. `apps/api/vercel.json` still contains the legacy `platform-lifecycle` Cron declaration; do not remove it until the Railway lifecycle owner is deployed and verified, and do not run duplicate consumers.
4. WP-06 event-intake/claim, DM approval and event-rate serialization migrations remain source-only. Supabase applied migration head is `20261115185633`.
5. ADR-0005 Option C direction is approved, but physical knowledge-consent/grant schema/provider is not approved; retrieval remains fail-closed.
6. Live Chat remains blocked until ENG-P25 provides canonical Agent participant/session permission and role authority.
7. ClamAV, Cloudinary credentials/callback, approved generation model/credit policy, Stripe configuration, and retention backup/restore/legal-hold approvals remain unverified or unavailable.

## Verification boundary
- Railway service inventory, configuration, deployment status and bounded logs were inspected.
- The Web and Super Admin `NEXT_PUBLIC_API_BASE_URL` variables were set to the canonical Railway FastAPI service URL; FastAPI CORS was updated for the known production and Railway Web/Admin origins.
- Supabase migration history and object existence were inspected read-only.
- No production migration, data mutation, worker activation, Cron activation, provider call, domain cutover, Vercel shutdown, build or integration test was executed in this checkpoint.
- This report does not claim full backend completion, production readiness, or successful Vercel retirement.

## Next executable work
- Configure server-only Supabase credentials in Railway without exposing them in source or client variables.
- Reconcile WP-06 source-only migrations with the approved isolated verification/release gate before enabling the canonical Agent Runtime consumer.
- Resolve WP-04 scheduler ownership before creating any Railway Cron or starting a second scheduler.
- Configure and verify worker services one by one against their existing entrypoints and dependency gates.
- Attach the actual production custom domains to Railway and verify traffic before disabling residual Vercel integrations.


## Railway routing changes after initial checkpoint
- Set `NEXT_PUBLIC_API_BASE_URL` on Web and Super Admin to the canonical Railway FastAPI service URL.
- Set the FastAPI CORS allowlist to include the two expected custom domains and Railway service domains.
- Added Railway custom domains and received these DNS instructions:
  - `allpha.web.id`: CNAME `allpha.web.id` → `l8pb0wos.up.railway.app`; TXT `_railway-verify.allpha.web.id` → `railway-verify=61623232d173e516702258706cdd5972a173ac9f0e75e8ae838a94c833ce0d89`.
  - `adm.allpha.web.id`: CNAME `adm.allpha.web.id` → `lsfgdohu.up.railway.app`; TXT `_railway-verify.adm.allpha.web.id` → `railway-verify=1c17fa6a891adcd14a56e3ab7980781ac8825b96dec3c233c52b0553ea2625f3`.
- DNS records are not yet changed. Railway reported the Admin CNAME currently points to `1c29ded5c1993149.vercel-dns-017.com`.


## Additional read-only Supabase schema evidence (2026-11-22)

- Applied migration ledger remains at `20261115185633`.
- Existing objects include `generation_jobs` and `content_schedules`; the canonical Social Graph RPCs `claim_social_graph_events`, `apply_social_graph_event_effect`, and `fail_social_graph_event` are present.
- Missing from the inspected `public` schema: `agent_social_automation_events`, `agent_social_automation_grants`, `agent_runtime_tool_plans`, `agent_runtime_worker_schema_readiness()`, `agent_task_schedules`, `live_sessions`, `live_participants`, `live_stage_events`, `production_document`, and `cinema_assets`.
- These findings explain why the WP-06 event consumer, full Agent Runtime worker readiness, Agent schedule worker, Live Chat Agent participation, and parts of the Cinema production workspace cannot be activated. They are not reasons to create parallel tables or bypass the existing migration/release controls.
- No production DDL, data write, migration application or worker activation was performed.


## Canonical domain and cross-origin API binding — 2026-11-22 continuation

- Product Owner confirmed the three production hostnames: Web `https://allpha.web.id`, FastAPI `https://api.allpha.web.id`, and Super Admin `https://adm.allpha.web.id`.
- Railway production variables were updated: Web and Super Admin `NEXT_PUBLIC_API_BASE_URL=https://api.allpha.web.id`; FastAPI `ALLPHA_CORS_ORIGINS=https://allpha.web.id,https://adm.allpha.web.id,http://localhost:3000,http://localhost:3001,http://localhost:19006,http://localhost:8081`. Values are public origin/config values; no secret was written to client configuration.
- Documentation aligned in `apps/web/README.md`, `apps/super-admin/README.md`, `apps/api/.env.example`, and `apps/client/README.md`. Native production/EAS builds are documented to use `https://api.allpha.web.id`; local simulator defaults remain local.
- Source commits: Web README `ab783c54f28537dfd81568d0c47fd489b4829191`; Super Admin README `61659f2a107f5e71373f611c4096d22e23cb7380`; API env template `521c04c0406662c0694dbcbab22e30b0f4b4c42b`; Native README `95f418a9ab426d3c386346e0711320aa93efe7bf`.
- Railway deployments for the three service-scoped documentation/config updates reached SUCCESS: Web `9c561dae-c145-4d38-bdf4-59fc77b849b7`; Super Admin `e8a167ed-4579-4ef4-ad7f-3015b47ed3cb`; API `264e8659-bdb2-488b-81c6-96bb7f52281d`. Latest app services remain live.
- Live HTTP checks: `/healthz` 200; `/readyz` 200; `/openapi.json` 200 with 300 registered paths; `/v1/system/status` 200; Web `/login` 200; Super Admin `/` 200. Readiness reports Supabase authentication and database reachable. Object storage and AI gateway are explicitly `not_checked` by `/readyz`.
- Cross-origin browser calls from both `https://allpha.web.id` and `https://adm.allpha.web.id` to protected FastAPI routes reached the API and returned the expected `401 INVALID_TOKEN` for deliberately invalid test tokens; no browser CORS/network failure occurred. This verifies origin-to-API transport only, not an authenticated customer/admin journey.
- `/v1/workflows` root is not a route and returns 404 by design; the implemented workflow routes are under `/v1/workflows/definitions` and `/v1/workflows/runs`. Do not classify the root-only 404 as an API outage.
- Railway domain-status still reports API/Admin CNAME traffic records as requiring update even though live HTTP traffic was observed on both hosts. Keep DNS status under observation; do not treat TLS validity alone as route proof.
- **Completion boundary unchanged:** no authenticated end-to-end journey was executed; no Supabase migration or production data write was applied; no worker/Cron was activated; no provider/storage/AI gateway integration was verified; no Vercel shutdown or traffic cutover was performed. Supabase migration ledger remains at `20261115185633`; WP-06/WP-11/ENG-P25–P27 and Authentication remain in their existing phase statuses. No phase promotion.

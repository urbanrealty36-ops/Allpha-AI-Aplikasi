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

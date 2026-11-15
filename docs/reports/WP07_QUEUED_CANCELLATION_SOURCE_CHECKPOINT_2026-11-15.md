# WP-07 — Queued Generation Cancellation Source Checkpoint

**Date:** 2026-11-15  
**Repository:** `urbanrealty36-ops/Allpha-AI-Aplikasi`  
**Branch:** `main`  
**Scope:** ENG-P09/P10/P11 and WP-07 durable Generation Job lifecycle  
**Status:** `source_implemented / migration_source_only / acceptance_not_verified`

## Change delivered

Added an owner-scoped cancellation command for a Generation Job that is still in the `queued` state:

- FastAPI: `POST /v1/generation/jobs/{job_id}/cancel`.
- PostgreSQL source-only RPC: `generation_cancel_queued_job(p_command jsonb)`.
- Durable cancellation audit: `generation_job_cancellation_events`.
- Web: the reference `GenerateModal` exposes “Batalkan antrean” only while the latest polled state is `queued`.
- Native: `NativeGenerateCenter` exposes the same queued-only action and uses the same FastAPI contract.

## Safety and financial semantics

- The cancellation RPC locks the owner-scoped job row and accepts only `queued` jobs. A worker claim and cancellation serialize on the same row, so a successfully cancelled job cannot subsequently be claimed by the worker.
- Running jobs are not force-cancelled. Once a provider may have accepted a request, the outcome and cost are uncertain; the API returns a conflict and does not pretend the provider was stopped.
- If the snapshotted credit policy permits definitive failure release, the RPC releases the reservation with an idempotency key and marks the job `cancelled`.
- If release is not permitted, the RPC marks the reservation and job `pending_reconciliation`. It does not invent a refund or silently release credits.
- Repeated cancellation requests return the durable cancellation outcome without applying a second ledger effect.
- The cancellation table and RPC are service-role only; clients use the authenticated FastAPI endpoint.

## Files changed

- `apps/api/src/allpha_api/generation_jobs_api.py`
- `apps/api/supabase/source-only-migrations/20261115180000_wp07_generation_queued_cancellation.sql`
- `apps/web/components/reference-ui/GenerateModal.tsx`
- `apps/web/app/generate/page.tsx`
- `apps/client/components/NativeGenerateCenter.tsx`

## Commits

- API: `240158eef66cde058f7742cc97306458948e2e06`
- Migration: `957cc430f46c91cd40c888fd37367b233df0743c`
- Web modal: `d02141d4f26387502164d84323c19d76beca7f74`
- Web route: `c05e86429846c285349fb959d73385c57e399414`
- Native: `1aadff08a331a945f33702d1186158a87dafd205`

## Not performed

Per requester instruction, no tests, builds, lint, typecheck, CI, provider invocation, real database mutation, migration application, worker activation, staging, browser/device QA, or deployment was performed.

## Remaining WP-07 blockers

This source change closes only the queued-cancellation contract. WP-07 remains open because:

1. The complete Generation Job / external consumer / output moderation / artifact deletion migration chain is still source-only and is not applied to the canonical Supabase database.
2. A production-approved output moderation adapter and effective moderation policy are not configured.
3. Approved owner-reward tariff values and their Finance/Product approval reference are still required; no numeric reward was invented.
4. The persistent Generation Job worker is disabled unless its approved runtime service configuration enables it.
5. Multimodal media-input snapshots are not yet connected to a provider adapter capable of consuming those inputs. The current canonical execution adapter is text generation; the UI must not claim uploaded images/videos were interpreted by the model.
6. Web/Native integration acceptance and authorized lifecycle evidence have not been run, as explicitly requested.

Therefore WP-07 remains `IN_PROGRESS / ACCEPTANCE_NOT_VERIFIED`. Do not advance the formal sequence to WP-06 until the WP-07 blockers and acceptance gate are resolved.

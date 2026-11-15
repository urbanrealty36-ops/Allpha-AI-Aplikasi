# WP-07 — Production Supabase Schema Migration Checkpoint

**Date:** 2026-11-16  
**Repository:** `urbanrealty36-ops/Allpha-AI-Aplikasi`  
**Branch:** `main`  
**Supabase:** `AllphaAiAplikasi-db` / `dvdziauyvuhcnqhrrvww`  
**Database:** PostgreSQL 17.6, region `ap-northeast-2`  
**Status:** `schema_migrated / acceptance_not_verified`

## Owner authorization and scope

The Product Owner explicitly authorized direct migration to the connected production Supabase project on 2026-11-16. The applied scope is the WP-07 Generation Job chain and its required entitlement/version prerequisites. The Stripe billing and playback-entitlement schema was also promoted because the existing WP-07 API and billing routes require those canonical tables.

No staging environment was used. No test/build/lint/typecheck/CI/browser/device QA was run. No provider generation, Stripe request, Storage object mutation, credit transaction, or production user data mutation was performed.

## Applied migration ledger

All ten migrations below are present in the Supabase migration ledger, in this order:

| Version | Migration |
|---|---|
| `20261115185037` | `wp07_premium_entitlement_projection_prerequisite` |
| `20261115185125` | `eng_p05_agent_version_snapshot_contract_reconciliation` |
| `20261115185143` | `wp07_durable_generation_jobs` |
| `20261115185203` | `wp07_external_consumer_dual_account` |
| `20261115185221` | `wp07_external_consumer_generation_atomic` |
| `20261115185238` | `wp07_consumer_grant_revocation_lifecycle` |
| `20261115185259` | `wp07_generation_manual_moderation` |
| `20261115185438` | `wp07_generation_artifact_owner_deletion` |
| `20261115185455` | `wp07_generation_queued_cancellation` |
| `20261115185633` | `eng_p30_stripe_billing_subscriptions_entitlements` |

Matching canonical migration files were committed under `apps/api/supabase/migrations/` on `main`.

## Schema included

- Durable Generation Jobs with idempotency, leases, owner/payer snapshots, usage and moderation state.
- External Agent Consumer grants and policy snapshot fields; generated payer-role contract.
- Atomic Generation Job creation, credit reservation, metering settlement, approved Agent-owner reward grant, DM conversation/message receipt and in-app notifications.
- Grant revocation lifecycle and queued/running job fencing.
- Append-only manual output review events and safe review finalization.
- Private artifact owner deletion queue, lease/retry/dead-letter RPCs.
- Requester queued cancellation and cancellation audit events.
- Private Storage bucket `generation-artifacts`.
- Premium subscription projection and the full Stripe billing/order/receipt/webhook/playback-entitlement schema used by the existing FastAPI billing routes.

No products, Stripe prices, orders, receipts, subscriptions, playback entitlements, webhook events, generation jobs, consumer grants, review events or artifact deletion jobs were seeded.

## SQL/source corrections made before promotion

1. Atomic DM delivery now passes the UUID Generation Job ID into `messages.client_message_id` (the column is UUID), rather than casting it to text.
2. The artifact deletion retry function's dollar-quote delimiters were repaired before applying the migration.
3. Stripe checkout snapshot mismatch now persists `review_required` and failed webhook state by returning a structured result instead of raising inside the same transaction (which would roll back those state updates). FastAPI now checks the returned fulfillment result and does not acknowledge a mismatch as processed.

## Read-only post-migration verification

The following checks were read-only catalog/data inspection, not workflow tests:

- All 12 expected Generation, moderation, artifact, grant-audit, billing and playback-entitlement tables are present.
- RLS is enabled on all inspected tables.
- `anon` and `authenticated` have no direct SELECT privilege on the new private tables; the intended service-role table privileges are present.
- Generation, grant-revocation, moderation, artifact deletion, cancellation and billing RPC execution is restricted to `service_role` in the inspected privilege checks.
- Storage bucket `generation-artifacts` exists with `public=false`, 10 MiB limit and `text/plain` only.
- The expanded external Consumer scope constraint is present.
- All inspected new business tables have zero rows.
- There are currently zero approved Generation output moderation policies, zero active Consumer grants, zero billing products and zero active subscriptions.

## Remaining activation and acceptance blockers

1. **Output moderation is not configured.** The moderation policy table has no approved policy rows; the Generation worker must remain safely idle for this path until an approved adapter/policy is configured.
2. **Premium billing is schema-only.** No product/price is registered, no subscription is active, and no Stripe checkout/webhook was exercised. Stripe activation remains disabled until its environment secrets and approved commercial/credit policies are configured.
3. **Creator-owner reward is policy-gated.** No reward rate, split, grant amount or payout value was invented or activated.
4. **No runtime workflow has been executed.** Quote/create, provider execution, usage metering, settlement, private artifact retrieval, DM delivery, moderation, revocation, cancellation, deletion and recovery remain acceptance-unverified.
5. **Multimodal generation input remains separate work.** The currently promoted Storage bucket and Generation artifact contract are text-output only; image/video input snapshots, scanning/quarantine, rights and approved provider capability remain open.
6. **UI-COPY-03 remains open.** Source route/component inspection is not visual/browser/device acceptance.

## Phase status and next order

WP-07 remains:

`IN_PROGRESS / SCHEMA_MIGRATED / ACCEPTANCE_NOT_VERIFIED`

This migration does **not** close WP-07 and does not promote another phase. The requested order remains:

1. WP-07 — Ask AI, Generate & DM Delivery
2. WP-06 — AI Social Automation & Human Takeover
3. WP-11 — AI Cinema Creator Studio
4. WP-12 — Cinema Subscription & Creator Economy

Live Stage remains under WP-10 / ENG-P25/P26 pending the approved ADR decision.

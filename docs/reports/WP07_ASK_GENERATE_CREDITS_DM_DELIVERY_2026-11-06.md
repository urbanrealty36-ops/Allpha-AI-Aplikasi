# WP-07 — Ask AI, Generate Content and DM Delivery Economy

**Date:** 2026-11-06  
**Repository:** `urbanrealty36-ops/Allpha-AI-Aplikasi`  
**Branch:** `main`  
**Canonical database:** `AllphaAiAplikasi-db` / `dvdziauyvuhcnqhrrvww`  
**Status:** `in_progress` — source implementation advanced; full WP-07 acceptance is NOT VERIFIED.

## Governing scope

WP-07 is the fixed work package “Ask AI, Generate Content and DM delivery economy”, owned by ENG-P05–P11, P18, P29, P30, P32 and P36. Its required outcomes include eligible Agent/Skill/Model/Knowledge resolution, quote and credit reservation, durable runs/checkpoints, output safety, private artifact storage, DM delivery, owner revenue credit, provider/model metering, and failure/refund/reconciliation.

Master PRD v3.1 requires a policy-backed quote before confirmation, atomic reservation, durable run with version snapshots, ACL-filtered retrieval, Model Router execution, output validation/moderation, private storage, secure requester DM, idempotent settlement, and requester debit plus Agent-owner credit under one settlement reference. Monetary conversion and cash payout remain subject to approved policy/ADR.

## Baseline findings

Existing source already contains:
- AI Credit contracts, lifecycle service, Supabase ledger adapter and append-only ledger migration.
- Provider-neutral usage metering contract and Supabase sink.
- Canonical Model Router and text-generation adapter.
- Source-only durable Generation Job migration, API and worker.
- Agent Runtime task/checkpoint APIs and existing ENG-P18 Human↔Agent messaging.
- Reference UI components for Ask AI and Generate.

Important baseline gaps found:
1. The durable Generation Job migration was under `source-only-migrations`, not the canonical applied migrations directory. Its `output_sha256` CHECK expression was malformed (unterminated regex/string). The source-only migration was corrected to a complete SHA-256 regex constraint. It remains unapplied.
2. `/ask-ai` was rendering the reference view without a submit callback, so it could not create or poll a real generation job.
3. The reference `GenerateModal` still uses legacy `/api/agent/interact`, demo brand presets and a fabricated success fallback. It is not a trusted business flow.
4. The Generation Job API creates jobs for the requesting user’s own Agent and requires that user’s Premium entitlement. It does not yet implement the full external Agent consumer/owner separation required by WP-07.
5. Generation worker stores private output and settles consumer credits/metering, but does not yet deliver a canonical ENG-P18 DM or create a separately addressable artifact object.
6. Current generation job does not bind Knowledge retrieval ACL/provenance, does not invoke a dedicated output moderation/safety gate, and does not implement Agent-owner reward credit.
7. No approved creator reward formula, owner revenue split, or cash/payout policy may be inferred. Those remain governed by approved policy/ADR.

## Source changes in this checkpoint

- `apps/web/components/reference-ui/AskAiView.tsx`
  - The existing visual reference is retained.
  - The view now accepts a real generation callback, appends the Human request and the returned Agent output to the conversation, and preserves explicit error/loading states.
- `apps/web/app/ask-ai/page.tsx`
  - Loads the authenticated Human identity and active owned Agent through canonical API.
  - Resolves only published Skills and approved capabilities.
  - Calls the policy-backed generation quote endpoint, requires explicit confirmation, submits the job with the quoted credit amount, and polls the owner-scoped job endpoint.
  - Stops on failed or pending-reconciliation outcomes; it does not silently replay provider work.
- `apps/api/src/allpha_api/generation_jobs_api.py`
  - Adds `POST /v1/generation/quote`, which resolves current Model Router route, published Skill, approved capability, Premium entitlement and approved tariff policy.
  - Returns estimate, model/policy/tariff version and short quote expiry.
  - Job creation re-computes all trusted inputs and rejects a stale quoted credit amount with `GENERATION_QUOTE_STALE`.
  - The API remains the authority; the client-supplied quote is never the source of the debit amount.
- `apps/web/app/generate/page.tsx`
  - Adds a canonical Generate Content page using the existing Allpha reference visual language.
  - Selects only active owned Agents, published Skills and approved capabilities.
  - Requires quote confirmation and displays actual Generation Job output/status; no mock result or fake balance is introduced.
- `apps/api/supabase/source-only-migrations/20261105130000_eng_p09_durable_generation_jobs.sql`
  - Corrected the malformed output SHA-256 constraint.
  - The migration remains source-only and is not applied to production.

## Validation and deployment

- GitHub CI observed on commit `32fea1354f1ebacb58f1400324fa0e9e0daae707`:
  - Railway API: success
  - Railway Notification Delivery: success
  - Railway Stories Cleanup: success
  - Railway Super Admin: success
  - Railway Web: pending at inspection time
  - Vercel Web/API/Admin: failed due `build-rate-limit`
- No Vercel deployment was triggered by this work.
- No Supabase migration was applied.
- No real provider generation, credit debit, DM delivery, owner reward, or production data mutation was performed.
- Browser/device, isolated SQL, concurrency, replay, rollback, and actual provider integration tests were not run in this checkpoint.

## Acceptance matrix

| Requirement | Current evidence | Status |
|---|---|---|
| Quote and eligible owned Agent/Skill/capability | New quote API and Ask AI/Generate clients | Source implemented; runtime not verified |
| External consumer selecting another Agent | Current generation RPC still requires requester to own Agent | NOT IMPLEMENTED |
| Model resolution | Canonical Model Router route snapshot and preflight | Source integration present; provider runtime not verified |
| Knowledge ACL/retrieval/provenance | Not connected to generation job worker | NOT IMPLEMENTED |
| Credit reservation and immutable ledger | Existing ledger RPC migration and generation-create transaction source | Migration source-only; not applied/verified |
| Durable run/checkpoint | Generation Job claim/lease and Agent Runtime checkpoint system exist separately | Generation checkpoint/recovery integration incomplete |
| Output safety/moderation | No generation output moderation gate found in worker | NOT IMPLEMENTED |
| Private artifact storage | Output persisted in private owner-scoped Generation Job row | Partial; separate artifact object/reference delivery incomplete |
| ENG-P18 DM delivery | Messaging engine exists; generation worker does not deliver result to inbox | NOT IMPLEMENTED |
| Agent-owner revenue credit | No approved creator reward policy/formula or atomic dual-account settlement | BLOCKED pending approved policy/ADR |
| Provider/model metering | Existing idempotent metering contract and sink | Source present; generation integration/runtime evidence incomplete |
| Failure/refund/reconciliation | Worker marks uncertain outcomes pending; ledger supports release/refund/reversal/reconcile | Partial; job-to-ledger recovery and tests not verified |
| Web UI Reference parity | Ask AI and Generate screens use existing Allpha reference styling | Source implementation; browser QA not run |
| Native parity | Not yet connected to generation quote/job lifecycle | NOT IMPLEMENTED |
| Super Admin governance | No WP-07 operator surface required until financial/reconciliation policy is approved | NOT AFFECTED for current slice; future policy review may require CHANGE |

## Remaining work before WP-07 can be closed

1. Reconcile external Agent consumer grants with generation quote/create and separate requester payer from Agent owner.
2. Connect authorized Knowledge retrieval and pinned source versions to the generation run.
3. Add output safety/moderation gate and explicit blocked/review states.
4. Persist generated artifacts in the approved private storage path with owner-scoped retrieval.
5. Add atomic, idempotent ENG-P18 DM delivery receipt to the durable job completion transaction.
6. Define and approve creator-owner credit reward policy, platform share, cost treatment, fraud/quality gates and reversal semantics; then implement balanced dual-account settlement. Do not invent a numerical split.
7. Integrate Native client and confirm Super Admin governance impact.
8. Add focused tests for quote tampering/staleness, duplicate job creation, concurrent overspend, provider unknown outcome, output moderation, artifact access control, DM replay and settlement/reversal.
9. Run the authorized migration lifecycle and focused verification before acceptance.

**Decision:** WP-07 remains `in_progress`. Do not mark `implemented`, `integration_verified`, `acceptance_passed` or `production_verified` from source changes/CI alone. WP-08 must not begin until WP-07’s required acceptance gate is met.


## Correction discovered during post-edit inspection

A subsequent raw-file inspection found that the source-only Generation Job SQL file has a duplicated trailing SQL segment after its first `COMMIT;` (the file is 33,260 bytes and contains two `COMMIT;` terminators). The attempted cleanup was blocked by the repository write safety check and did not succeed. Therefore the migration must be treated as **invalid and unusable** until the duplicate tail is removed and the complete SQL is parsed/reviewed. The earlier statement that the malformed SHA-256 expression was repaired remains true for the first copy, but the file as a whole is not clean. Do not apply it. No database migration was applied.


## Source reconciliation checkpoint — 2026-11-15 (main)

**Execution mode:** direct-to-main source implementation only. Product Owner has explicitly deferred tests, builds, lint, typecheck, CI, browser/device QA, staging, migration application and deployment. Those activities are not represented as passed.

### Reconciled source contracts

- The canonical Generation Job migration remains under `source-only-migrations`; it is not an applied production schema. The current source file has one terminal transaction and no duplicated trailing SQL segment.
- `20261115150000_wp07_external_consumer_dual_account.sql` is the schema prerequisite for external Consumer generation. It now also defines the generated `payer_role` and durable `error_code` columns required by the worker/API lifecycle. The generated payer role prioritizes the Agent owner identity for owner-paid generation, then the requesting Consumer identity for consumer-paid generation.
- `20261115152000_wp07_external_consumer_generation_atomic.sql` replaces the initial owner-only create/complete RPCs. It validates current Agent ownership/version, published Skill snapshot/version, approved capability, active external grant/scope/expiry, public visibility/sensitivity, payer identity and Premium entitlement; reserves against the selected payer; pins Agent/Skill/Knowledge snapshots; settles actual usage; issues only policy-approved Agent-owner AI Credit grants; and creates the Human↔Agent DM plus requester/owner inbox notifications in the same completion transaction.
- `20261115153000_wp07_consumer_grant_revocation_lifecycle.sql` owns external grant revocation, queued-job cancellation/release where policy allows, and fencing of running work into reconciliation rather than provider replay.
- `20261115160000_wp07_generation_manual_moderation.sql` provides append-only review evidence and a safe finalization lease for review-required output. Rejected or unapproved artifacts remain private.
- FastAPI generation quote/create paths now contain external Agent grant resolution, payer selection, owner reward policy gating, ACL-filtered Knowledge snapshot binding, stale quote checks, and the canonical Model Router boundary. The worker revalidates the grant before provider side effects, checks pinned Agent/Skill snapshots, stores private artifacts, requires an approved output moderation adapter/policy, and delegates settlement/DM/notification to the transactional completion RPC.
- Web Ask AI/Generate and Native Generate source adapters exist. The generation artifact endpoint issues a short-lived signed URL only for the authenticated job owner after success and moderation approval.

### Corrections committed during this execution

- `fa8acd460cbeabc8fa55e9f2d063711ae688e431` — repaired the malformed Auto Reply save payload in `apps/web/app/agent-social/page.tsx` that caused the known JSX compile error.
- `351494ec1bff0e9cf0ca8e03df0c39ff879cdbe0` — added missing dual-account schema fields `payer_role` and `error_code` to the WP-07 prerequisite migration.
- `43686c01d8a078541cbe42ea7748643e63b375d7` — aligned generated payer-role precedence with the owner-paid generation contract.
- `09594bddd061a16c46858b4667c0a0d41e5b612f` — aligned worker grant revalidation with the same derived payer-role semantics.

### Remaining blockers — WP-07 stays IN_PROGRESS

1. The durable Generation Job, external Consumer, grant-revocation and manual-moderation migrations remain source-only and have not been applied to the canonical Supabase database.
2. The moderation adapter and approved effective output-moderation policy are not configured; the worker intentionally remains idle.
3. The provider metering → credit settlement → Agent-owner grant → DM/notification transaction has not been exercised against an isolated database with approved policy fixtures.
4. The exact consumer grant, payer/owner dual-account, Knowledge ACL/provenance, grant revocation during queued/running work, output review/rejection, artifact authorization, idempotent DM and ledger reversal paths remain unverified.
5. Creator-owner reward policy has no approved business values in this environment. The implementation is policy-gated; no rate, split, credit amount or payout value is invented or activated.
6. Native Generate source is present, but Android/iOS build/device acceptance is deferred. Web and Super Admin journey acceptance is also deferred.
7. The full UI source parity audit remains open under UI-COPY-03; this checkpoint does not close that owner.

**Status:** `in_progress / source_reconciled / acceptance_not_verified`. No migration was applied, no provider call or production credit transaction was made, no test/build/CI was run, and no staging or deployment was performed. Do not start WP-06 as a completed next phase until WP-07's remaining implementation blockers and the approved acceptance waiver are explicitly reconciled in the fixed phase plan. The Product Owner's requested order remains WP-07 → WP-06 → WP-11 → WP-12.


## Web reference Generate Studio and DM navigation — 2026-11-15

- The Web Generate route now mounts the source-derived `GenerateModal` from `Allpha-Front-End-UI-New` and passes its structured request through the existing canonical `/v1/generation/quote` → user confirmation → `/v1/generation/jobs` → durable job polling → private artifact retrieval lifecycle. The reference modal no longer uses its former local simulation or provider bypass.
- The modal's “Buka Direct Message” action is no longer a cosmetic close button. The Generate page captures `dm_conversation_id` from the authorized Generation Job status response; the button is enabled only after that canonical conversation ID is returned. It navigates to `/messages?conversation_id=...`, and the Messages route opens that conversation only after it is found in the authenticated user's canonical conversation list.
- If the completion transaction does not return a conversation ID, the DM action remains disabled and the modal explicitly reports that delivery is not confirmed. No client-side conversation or message is fabricated.
- Commits: `6fe6f3bd4d4771a8fcd0527b7f7969511fb91da2`, `c2bbaff1b18702d42cc1eb41d281f8e66aa31aca`, `ff13ae2b79b701782db5342698f116644c27059d`, `4a30b1dc556b86543c07b35e1cc406383ff20f9a`, `555e7edef6494df00bd4b13832aecb6e4617165e`, `432fd1575e1fc276130c8ce8a2cc875ce7bd4181`.
- The Generate reference modal's local logo/product file upload remains intentionally disabled. Current Generation Job input contract has no `input_media_ids` or media provenance snapshot, and the provider worker currently builds text-only prompts. Re-enabling local file selection without a server-side media-intake, ownership, malware/moderation, signed-provider-input and immutable snapshot contract would bypass the existing content-media pipeline. This is a remaining WP-07 implementation gap, not a completed feature.
- WP-07 remains `in_progress / source_reconciled / acceptance_not_verified`. The source-only SQL chain has not been applied to canonical Supabase; output moderation adapter/policy and approved Agent-owner reward policy remain unconfigured; no isolated SQL/API settlement, DM delivery, idempotency, revocation or moderation journey was exercised. No tests/build/typecheck/CI, provider call, staging or deployment was run.

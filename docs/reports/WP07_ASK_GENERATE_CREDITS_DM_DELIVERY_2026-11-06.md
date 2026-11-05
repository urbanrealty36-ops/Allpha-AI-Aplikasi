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

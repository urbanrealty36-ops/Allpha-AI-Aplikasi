# ADR-0021 — AI Generation Jobs, Credit Policy, Billing and Entitlement

- **Status:** PARTIALLY ACCEPTED — technical architecture and Stripe payment provider accepted; AI provider/model and numerical financial policy remain open
- **Date:** 2026-11-05
- **Decision owners:** Product Owner, Finance/Economy, Platform Engineering
- **Scope:** ENG-P09/P10/P11/P28/P29/P30, AI Cinema, Creator Studio, subscription, credits, billing and playback
- **This ADR does not create a new Phase.** Work remains within the existing fixed phase plan.

## Context and live evidence

The canonical API already contains:
- Provider-neutral `CanonicalTextGenerationRouter` and an OpenAI-compatible adapter. Provider, model, model version, cost policy and metering are deployment-configured; there is deliberately no default route.
- `ai_model_cost_configs` registry and separate runtime-policy verifier.
- Policy-neutral usage metering and the durable AI Credit ledger schema/RPCs, including atomic reserve/settle/release/reconciliation.
- Owner-scoped balance API.
- AI Cinema creator drafts, episode/media readiness, rights and moderation lifecycle.

Read-only inspection of canonical Supabase project `dvdziauyvuhcnqhrrvww` on 2026-11-05 found:
- One active model-cost row: `nvidia-nim / qwen/qwen2.5-coder-32b-instruct`, pricing `test-only-nim-v1`, `policy_approved=false`. This is test-only and must not be promoted as a production route.
- Zero approved `credit_policy_versions`, credit accounts, ledger entries, reservations, balance projections, reconciliation events and usage metering rows.
- Existing media lifecycle, notification, and credit tables are present in the live schema; payment order/receipt, subscription, playback entitlement and AI generation-job tables are absent.
- No live payment provider selection, plan price/quota, or production model route was established.

The Master PRD and ADR-0006 expressly prohibit inferring provider price, credit conversion, subscription pricing, or creator reward formula from code or test fixtures.

## Decisions accepted now

### 1. AI Gateway / Model Router

- Keep the single canonical FastAPI AI Gateway and `CanonicalTextGenerationRouter`; no feature-specific provider calls or second router.
- The integration contract is the existing OpenAI-compatible adapter protocol. Provider, model, model version, API base URL and server-only secret are supplied through deployment configuration and verified against the active cost registry before execution.
- No provider/model fallback is selected. No default provider is inferred. The live NVIDIA NIM/Qwen row is explicitly test-only and remains unapproved.
- Every billable request must have bounded prompt/output/time/cost, a durable idempotency key, provider/model/version snapshot, durable usage evidence, and a recoverable job state. Unknown provider outcomes are never replayed automatically.

### 2. Cost and AI Credit policy

- Adopt **ADR-0006 Option C**: versioned capability tariffs are separate from actual provider/infrastructure cost attribution. AI Credits are not currency and are not converted to cash implicitly.
- The credit ledger already provides atomic reserve, settle, release, reversal and reconciliation. Generation must reserve before provider execution, settle only from durable verified usage, release unused reservation on definitive success/failure according to policy, and leave unknown provider outcomes pending reconciliation.
- Use integer usage units only. No implicit fractional rounding or cross-unit conversion.
- No tariff can be active until an operator-approved, effective `credit_policy_versions` record defines capability tariff, credit scheme, cost unit/pricing version, cost ceiling, entitlement limits, and failure/partial/refund/expiry rules.
- No numeric tariff, credit scale, currency conversion, or free-tier credit grant is approved by this ADR.

### 3. Plans and product entitlement

- Adopt the existing product direction: **Free** users can use the social/product surfaces but do not receive AI generation; **Premium** access includes an approved AI-credit allowance; users may top up additional AI Credits. AI Credits remain non-cash and usage is charged only through the canonical ledger.
- Plan names and entitlement shape are established; exact monthly credit allowance, request/concurrency quotas, top-up packs, prices, billing interval, expiry and refund rules remain Finance/Product decisions and must be stored as versioned configuration, not hard-coded.
- Entitlement is calculated server-side from plan, verified subscription/payment state, effective policy, usage and suspension/revocation state. Clients never supply plan, balance, payment status or entitlement as authority.
- AI Cinema catalog exposes only published, rights-cleared and moderated titles. Episodes explicitly marked free preview may be viewed without premium entitlement. Full premium playback requires a current server-side playback entitlement. Territory, maturity and concurrent-stream policy remain open until approved.

### 4. Generation job architecture

- Use a durable PostgreSQL-backed generation job/outbox with leases, `FOR UPDATE SKIP LOCKED`, bounded attempts, checkpoints, cancellation, idempotency, terminal state and dead-letter/reconciliation paths. PostgreSQL remains the source of truth; no new queue database or workflow engine.
- Job payloads are private and owner-scoped. Store only necessary prompt/context and output; never put secrets or raw prompt/output into logs. Retention/deletion follows the content/privacy data-class policy.
- Worker invokes only the canonical Model Router. It does not call a provider directly.
- Reservation and job creation must be transactionally coupled or compensated with a durable release/reconciliation record. Provider timeouts are `unknown`, not failed or succeeded by assumption.

### 5. Billing and payment boundary

- Implement a provider-neutral payment adapter interface and canonical order/receipt/webhook/reconciliation contracts. Provider-specific code is isolated behind the adapter.
- Payment settlement is server-verified, signature/authentication checked, idempotent and reconciled. Client redirect never grants credits or subscription.
- **Stripe is the selected payment provider for Allpha.** Implement Stripe behind the canonical FastAPI payment adapter; clients must never call Stripe directly or hold secret keys. Use server-created Checkout Sessions (or the approved Stripe billing flow), signed webhook verification, idempotent event processing, durable payment/order receipts and reconciliation. Redirect/success URLs are informational only and never grant credits, subscriptions or playback.
- Stripe integration source may be implemented now, but checkout/webhook activation remains fail-closed until server-side Stripe secrets and webhook signing secret are configured, Stripe account/capabilities are verified, and Finance/Product approve currency, payment methods, tax/invoice, refunds, chargebacks, settlement, and reconciliation terms. Do not invent prices or enable live-mode charging.
- Stripe Connect, creator payouts and transfers are explicitly out of scope until the separate creator-economy policy and legal/finance approval exist.
- Subscription activation, credit top-up and playback entitlement are granted only after a verified provider receipt and an idempotent ledger/order transaction.

### 6. Creator economy

- No creator revenue share, payout, withdrawal or cash conversion is enabled in this scope until a separate approved economic policy defines attribution, qualified usage, creator/platform split, fraud/hold period, settlement, reversal, payout provider, tax and legal controls.

## Existing accepted media decisions reused by this ADR

- Reuse the accepted WP-04 hybrid media architecture: private Supabase Storage is canonical for originals/derivatives; Cloudinary is the configured managed video/audio transcode adapter; ClamAV scanning and verified callbacks are required before readiness.
- Reuse the accepted 30-day soft-delete recovery period and 7-day abandoned-upload review eligibility.
- Physical retention purge remains fail-closed until backup configuration, restore evidence, legal-hold verification and explicit operational approvals are verified. Provider-managed immutable backup expiry is not represented as immediate erasure.
- No second storage provider or media lifecycle engine is introduced.

## Explicitly unresolved decisions

| Decision | Owner | Needed before |
|---|---|---|
| Production AI provider, model and route credentials | Product Owner + Platform | Provider execution |
| Approved model cost rates, unit and cost ceiling | Finance + Platform | Provider execution |
| Credit scheme scale, capability tariffs, quota, expiry and failure/partial rules | Finance/Economy + Product | Credit reservation/settlement |
| Stripe account/capabilities, secret and webhook signing secret | Platform + Finance | Checkout/webhook activation |
| Currency, payment methods, tax/invoice, refunds, chargebacks, settlement and reconciliation terms | Finance | Payment activation |
| Currency, payment methods, tax/invoice, refunds and chargebacks | Finance | Payment activation |
| Premium price, interval, monthly credits, top-up packs | Product + Finance | Subscription/top-up activation |
| Playback territory, maturity and concurrent stream rules | Product + Legal | Premium playback |
| Creator revenue share/payout | Product + Finance + Legal | Creator cash settlement |
| Supabase backup/PITR retention, RPO/RTO and restore evidence | Project Owner + Platform | Destructive retention purge |

## Consequences and implementation gates

- Technical architecture, Stripe as the payment provider, and existing media/credit contracts are accepted; no AI model provider, price, tariff or entitlement value is fabricated.
- Source implementation may add durable job/order/entitlement contracts and operator-managed versioned policy configuration, but execution remains fail-closed until the corresponding approvals and secrets exist.
- Existing live schema is inspected. Any new schema is source-only until the required non-production target/recovery conditions in AGENTS.md and the fixed phase plan are satisfied. Do not apply a production migration as a substitute for skipped staging.
- The user's current instruction waives real/staging functional tests for this work. Report those as `DEFERRED / NOT VERIFIED`; do not change phase acceptance status or claim integration/production verification.
- ENG-P37 remains a later gate only after source implementation is ready and validation is explicitly authorized. It must not be used to defer missing feature source work.

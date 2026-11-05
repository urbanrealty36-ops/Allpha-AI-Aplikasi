# ADR-0021 — AI Generation Jobs, Credit Policy, Billing and Playback Entitlement

- **Status:** Proposed — implementation contract blocked by missing Product Owner policy decisions
- **Date:** 2026-11-05
- **Owners:** Product Owner + Allpha Platform Engineering
- **Scope:** ENG-P09 / AI Gateway and Model Router / AI Cinema / Creator Studio / billing and playback entitlement
- **This ADR does not create a new Phase.** Work remains within the existing fixed phase plan.

## Context

The repository already contains canonical foundations:
- `CanonicalTextGenerationRouter` and provider adapters in `apps/api/src/allpha_api/model_router.py` and `text_generation_adapters.py`.
- Durable, idempotent AI Credit ledger contracts and a Supabase RPC store in `credit_ledger_contract.py`, `credit_ledger_service.py`, and `supabase_credit_ledger_store.py`.
- A server-derived balance endpoint at `GET /v1/credits/balance`.
- AI Cinema owner-scoped film and episode draft contracts, plus media readiness and operator review routes.

The canonical Supabase project currently has:
- One active `ai_model_cost_configs` row, but `policy_approved = false`.
- Zero rows in `credit_policy_versions`, `credit_ledger_accounts`, `credit_ledger_entries`, `credit_reservations`, and `agent_model_usage_metering`.
- No dedicated generation-job, payment/subscription, or playback-entitlement tables in the current public schema.

Therefore the router has no approved cost policy, the credit ledger has no approved tariff/scheme to reserve or settle against, and there is no authoritative payment receipt or playback entitlement record to consult. The presence of code and tables alone does not authorize model execution, charging, payment acceptance, or premium playback.

## Decision required

The following product and operational values must be approved before production generation/billing/entitlement implementation can be completed:

1. **Generation job contract:** job types, lifecycle states, retry/idempotency semantics, provider callback/reconciliation behavior, cancellation and timeout handling, output ownership, retention, and whether AI Cinema generation is a direct user capability or Agent Runtime task.
2. **Model and cost policy:** approved provider/model routes, sensitivity classes, token/output limits, provider-cost pricing version, budget ceilings, and fallback policy.
3. **Credit scheme:** credit unit definition, capability tariffs, estimate/reservation rules, success/partial/failure settlement, unknown-outcome reconciliation, expiry/refund/reversal behavior, and the approved policy version/approval reference.
4. **Billing and payments:** payment provider, supported payment methods/currencies, payment intent/receipt verification contract, webhook authentication/idempotency, refund/chargeback handling, tax/invoice requirements, and reconciliation owner.
5. **Subscription and entitlement:** plan catalogue, free/premium limits, AI generation allowance, top-up semantics, entitlement start/expiry/suspension/revocation, premium playback rules, free-preview rules, and the authoritative entitlement lookup used by API playback.
6. **Creator economics:** whether AI Cinema has creator revenue share, payout, or reward obligations, and the settlement/ledger model if applicable.

## Options

- **A. Implement a provider-specific billing and entitlement stack now.** Rejected until the Product Owner selects the provider and approves payment, plan, tariff, refund and entitlement policy. Choosing these values in code would invent business policy.
- **B. Reuse the existing AI Credit ledger as the sole billing authority.** Necessary for AI usage charging, but insufficient for cash payment verification, subscriptions, premium playback or payment refunds without additional approved payment/entitlement contracts.
- **C. Keep execution fail-closed while completing non-billing creator and governance integration.** Selected as the safe interim behavior.

## Interim decision

- Keep the existing AI Gateway/Model Router and Credit Ledger as the only canonical execution and credit boundaries; do not add a second provider router, ledger, or backend.
- Do not execute generation, reserve/settle credits, accept payment, or grant premium playback while the approved policy/provider/entitlement contracts are absent.
- Do not fabricate a default tariff, price, plan, provider, balance, payment status, generation result, or entitlement.
- Keep AI Cinema draft creation, owner-scoped clean-media attachment, rights evidence review, moderation, and lifecycle operations available through the canonical FastAPI boundary.
- Keep generation jobs, billing, and playback entitlement visibly unavailable until their schema, policies, migrations, and source-to-client integration are implemented.

## Consequences and next action

The Product Owner must approve the decisions listed above (or provide an existing approved policy document/ADR that answers them). Engineering can then implement a versioned generation-job migration, worker/reconciliation flow, policy loader, reservation/settlement API, payment adapter/webhook, billing records, and entitlement API in the existing ENG phase owners. Any migration must include least-privilege grants/RLS, idempotency and recovery design, and an upgrade path. Do not apply a production migration or claim generation/billing readiness based only on source code.

Until then, `GET /v1/cinema/creator/status` reports generation jobs, billing and playback entitlement as unavailable, and creator UI must keep those actions disabled.

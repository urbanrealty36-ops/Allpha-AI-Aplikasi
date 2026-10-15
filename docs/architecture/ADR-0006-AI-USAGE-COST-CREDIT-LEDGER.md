# ADR-0006 — AI Usage, Cost Attribution, and Credit Ledger Contract

- **Status:** PARTIALLY ACCEPTED — Product Owner approved Option C direction on 2026-10-15; detailed Finance/Economy parameters and technical/security reviews remain open.
- **Date:** 2026-10-15
- **Owner:** Allpha Product Owner + Finance/Economy owner; API/Data Platform and Security review required before persistence implementation.
- **Scope:** ENG-P09 AI Gateway / Model Router cost attribution and its boundary with the canonical AI Credit ledger.
- **Authority:** Master PRD §§20.2–20.3, 34, 63–66; AGENTS.md §§5–9. This proposal does not amend the PRD until approved.

## Context

The current provider-neutral contracts carry usage quantity/unit, estimated and actual cost, cost unit, and pricing version. The source-only metering migration stores attribution and idempotency but explicitly does not settle an AI Credit ledger. The phase plan records no canonical credit-ledger schema or reservation/settlement/release implementation. No provider price, currency, conversion rate, credit scale, or creator reward formula may be inferred from existing code.

Usage metering and AI Credit accounting are distinct records:
- **Usage/cost attribution:** what operation ran, quantity and unit, selected provider/model/version, actual cost amount/unit, pricing version, trace and idempotency identity.
- **AI Credit ledger:** append-only account-level credit movements and reservations, with balances derived from ledger entries or a safely reconciled projection. AI Credits are not automatically cash.

## Decision record and remaining policy decisions

**Product Owner decision (2026-10-15): Option C accepted as the target policy direction** — versioned capability tariffs with independent actual-cost attribution and cost guardrails. This is not approval of any numeric tariff, credit scale, currency/FX policy, rounding rule, free-tier treatment, or failure/partial-delivery charge. The implementation in this commit is therefore limited to policy-neutral domain contracts and source tests. Runtime settlement and durable ledger persistence remain disabled.

### 1. Usage units

Proposed contract: each capability registry entry defines a stable `usage_unit` and integer `usage_units` (examples from PRD include tokens, model calls, embedding batches, audio duration, media minutes, storage/bandwidth, GPU time, and generation jobs). Units from different capability classes are never added together without an explicit conversion rule. Unknown units fail closed.

**Approval required:** canonical unit vocabulary, rounding rules for fractional quantities, aggregation windows, and which units are billable per capability.

### 2. Cost units and pricing versions

Proposed contract: `cost_microunits` remains an integer amount only when paired with an explicit, policy-owned `cost_unit`; the name does not imply a currency or FX scale. Every estimate and actual usage record carries immutable `pricing_version`. A budget and estimate must match on provider/model version, usage unit, cost unit, and pricing version. No silent cross-unit comparison or conversion is allowed.

**Approval required:** the meaning and scale of each cost unit, supported currencies (if any), rounding/FX policy (if any), immutable rate-card source, effective dates, and version rollout/rollback rules. No rates are specified by this proposal.

### 3. AI Credit conversion policy — options

- **Option A — fixed cost-to-credit conversion:** convert approved measured cost to credits using a versioned exchange ratio. Simple to reason about, but exposes credit price to provider-price/FX changes and requires precise rounding and margin policy.
- **Option B — capability tariffs independent of actual provider cost:** charge a published credit tariff per eligible capability/unit, while actual infrastructure cost remains a separate cost ledger. Predictable user experience, but requires tariff versioning and margin monitoring.
- **Option C — versioned capability tariffs with cost guardrails (recommended for review):** each capability has an approved credit tariff and unit/rounding policy; actual provider/infra cost is recorded separately; budget admission checks both the credit entitlement and approved cost ceiling; tariff changes are versioned and do not rewrite prior entries. This avoids pretending cost units and AI Credits are the same currency.

**Option C is selected as the target direction, not as a complete economic policy.** Finance/Economy must approve the credit scale, per-capability tariff schedule, billable units, rounding/fractional-unit handling, free-tier treatment, budget thresholds, expiry and failed/partial-operation behavior before credit settlement can be enabled.

### 4. Ledger record and invariants

Proposed minimum append-only entry fields:
- immutable entry ID and unique idempotency key;
- account/owner identity derived from trusted server state;
- entry type, signed or direction-normalized integer credit amount, explicit credit-unit/scheme version;
- source event/task/trace and capability;
- related reservation/settlement entry references;
- created/effective timestamps and optional expiry;
- reversal/reference link and reason;
- tariff/entitlement policy version;
- actor/audit metadata where required.

Balances are derived from entries or a reconciled projection; never accept a client-provided balance as authority. Existing entries are never updated/deleted to erase history. Duplicate key + same canonical payload is a no-op; duplicate key + different payload is a conflict. Ledger writes and balance projection/outbox updates must be transactionally consistent or use a proven transactional outbox.

### 5. Reservation, settlement, release, and reversal lifecycle

Proposed state/flow, subject to approved policy:
1. Validate authenticated actor, entitlement, capability, consent/policy and budget.
2. Estimate cost and credit tariff using the same approved policy versions; reject if either required budget is unavailable or exceeded.
3. Reserve credits with an idempotent append-only reservation entry before execution; reservation must not make spendable balance negative.
4. Execute with bounded timeout/retry and the same logical request idempotency identity.
5. On successful completion, record actual usage/cost, settle the actual credit tariff once, and release the unused reservation. Settlement is linked to the reservation and usage event.
6. On terminal failure before chargeable delivery, release the reservation. For partial success, charge only according to an explicitly approved capability-specific partial-delivery rule; otherwise fail closed.
7. Refund/reversal/adjustment creates a new linked compensating entry; it never mutates or deletes the original entry. Reversal amount cannot exceed the eligible original settled amount and must itself be idempotent.
8. Reconcile stale reservations, late outcomes, retries and projection drift with an auditable repair path; do not infer settlement from a client redirect or a provider timeout alone.

### 6. Failure and security rules

- Missing/expired/unverifiable pricing, tariff, entitlement, approval, or budget policy => deny before provider execution.
- A missing actual cost when policy requires it => do not report a fully metered successful charge; retain a recoverable pending/error state without silently fabricating a value.
- Provider retry/fallback must preserve request correlation and avoid duplicate reservation or settlement.
- Do not log prompts, raw chunks, credentials, or sensitive payloads in the ledger.
- Database authorization must be server-only for privileged ledger writes; clients must use the canonical API. RLS/grants, append-only guarantees, transaction semantics and concurrency must be validated against an approved isolated non-production target before deployment.

## Consequences if approved

- Usage metering remains separate from AI Credit ledger entries.
- The metering source-only migration does not become the credit ledger and must not be applied to production as an integration test.
- A new/updated versioned migration may be proposed only after canonical schema and policy approval, with forward-repair/rollback design.
- Implement deterministic domain contracts and unit/contract tests first. Live database transaction/concurrency/RLS and cross-system acceptance remains deferred to ENG-P37.

## Required approvals before ledger implementation

- [x] Product Owner: select Option C as the target policy direction (2026-10-15); detailed product behavior remains subject to the approvals below.
- [ ] Finance/Economy: approve credit unit scale, tariff/pricing versions, rounding, budget and reversal/expiry policy.
- [ ] API/Data Platform: approve canonical schema, transaction/outbox, uniqueness and projection-reconciliation design.
- [ ] Security/Privacy: approve trusted ownership, least-privilege grants/RLS, audit and data-minimization controls.

Until the remaining approvals are recorded, only deterministic source-level contracts and tests that do not activate charging are permitted. Do not implement a production credit conversion, durable ledger schema/migration, provider adapter, or runtime settlement activation based on this document.

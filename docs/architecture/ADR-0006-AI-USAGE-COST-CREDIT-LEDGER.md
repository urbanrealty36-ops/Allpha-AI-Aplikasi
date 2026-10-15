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


## Implementation design proposal — review required before persistence (2026-10-15)

This section records a candidate design to accelerate API/Data Platform and Security review. It is **not an approved schema**, does not authorize a migration, and must be reconciled with existing canonical Supabase tables and permissions before implementation.

### A. Finance/Economy decision register

The following values are intentionally unresolved. No implementation may infer them from test fixtures or the name of an integer field.

| Decision | Required signed-off value | Owner | Gate |
|---|---|---|---|
| Credit scheme / scale | Stable scheme identifier and meaning of one credit | Finance/Economy | Before tariff activation |
| Capability catalog | Billable capability IDs and canonical usage units | Product + Finance | Before tariff activation |
| Tariff schedule | Integer credits per usage unit, version, effective window, approval reference | Finance/Economy | Before reservation/settlement |
| Fractional usage | Unit quantization and rounding rule per capability | Finance/Economy | Before charge calculation |
| Quotas / budgets | Plan/entitlement limits, cost ceilings, reset window, concurrency behavior | Product + Finance | Before admission control |
| Free tier | Included allowance and behavior after allowance is consumed | Product + Finance | Before user-facing charging |
| Expiry | Which grant types expire, expiry timestamp semantics and ordering | Finance/Economy | Before expiry job |
| Failed operations | Charge/no-charge conditions and provider timeout ambiguity | Product + Finance | Before settlement |
| Partial delivery | Chargeable delivered units, minimum charge, cancellation cutoff | Product + Finance | Before partial settlement |
| Refund/reversal | Eligibility, maximum reversible amount, approvals and audit reason | Finance/Economy | Before compensating entries |
| Cost policy | Cost unit scale/currency if applicable, rate-card source/version, guardrail threshold | Finance + Platform | Before provider execution |
| Creator rewards | Eligibility, accrual/settlement, reversals and any cash-conversion policy | Product + Finance | Separate approval under PRD §§34, 66 |

### B. Candidate persistence boundaries

1. **Usage metering** remains a distinct append-only attribution stream. It records actual usage and cost by request/task/trace and pricing version. It must not be used as the credit balance.
2. **Credit ledger entries** are the financial/accounting source of truth: append-only, uniquely idempotent, owner/account-bound, versioned by credit scheme and tariff/entitlement policy, and linked to the originating task/event.
3. **Reservations** should be represented by ledger entries or a transactionally consistent reservation record linked to entries. A reservation is not a completed charge.
4. **Balance projection** is a derived, rebuildable optimization. Ledger entries remain authoritative. Projection changes and ledger append must commit atomically, or use a proven transactional outbox with a replay/reconciliation contract.
5. **Outbox/reconciliation** must be idempotent and auditable. It may repair projections or stale reservations but must never invent provider usage, tariffs, or successful delivery.
6. **Policy registry** must resolve an immutable active tariff and cost policy version for the operation. Missing, expired, mismatched, or unapproved policy fails closed before provider execution.

### C. Candidate transaction protocol

The canonical API command should run under a trusted authenticated owner context, derive the account from server-side identity, and accept a client idempotency key only as an untrusted request identifier. It must never accept a client-supplied account balance, owner ID as authority, or final charge as truth.

- **Reserve:** validate capability, entitlement, policy approval, tariff version, cost budget and available spendable balance; atomically append reservation and update/reconcile projection; prevent concurrent reservations from overspending.
- **Execute:** only after reservation commits, dispatch through the canonical Model Router with the same logical request/task correlation. Do not call providers from Web, Native or Super Admin.
- **Settle:** on a definitive chargeable outcome, atomically append one settlement tied to the reservation and usage event, release unused reservation, and update the projection/outbox. Repeated identical command is a no-op; same key with different canonical payload is a conflict.
- **Release:** on a definitive non-chargeable terminal outcome, release the remaining reservation once. A timeout with unknown provider outcome remains recoverable/pending; it must not automatically be treated as either success or failure.
- **Partial outcome:** settle only under an approved capability-specific rule and verified delivered usage. Without such a rule, do not settle a guessed amount.
- **Reverse/refund:** append a linked compensating entry with reason and authorized actor; never mutate/delete original entries. Enforce reversal caps atomically.
- **Reconcile:** detect stale reservations, duplicate/out-of-order events, projection drift, and metering-without-settlement; expose an auditable repair action. Automated repair may not manufacture charge data.

### D. Candidate data model (logical, not a migration)

| Logical record | Minimum responsibility | Key constraints |
|---|---|---|
| `credit_ledger_entries` | Append-only grant/reserve/settle/release/expiry/refund/reward/reversal/adjustment | Unique idempotency key in its defined scope; positive integer amount plus explicit entry type; policy/scheme version; linked source and compensating entry |
| `credit_reservations` (or equivalent ledger-derived state) | Track pending reservation lifecycle and recoverable outcome | Unique request/task reservation identity; state transitions guarded transactionally; no overspend under concurrent requests |
| `credit_balance_projection` | Fast spendable/reserved/expired balance view | Derived only; version/sequence or replay watermark; updated atomically or via transactional outbox |
| `credit_policy_versions` | Immutable approved scheme/tariff/entitlement references | Effective dates, approval references, no in-place edits to policies already used by entries |
| `credit_reconciliation_events` | Repair, stale reservation, projection drift and audit evidence | Idempotent repair command, actor/reason, before/after references, no raw prompt or credential data |

These are logical names only. Before a migration is authored, inspect existing Supabase schema, naming conventions, roles/grants, RLS and the current API repository; reuse or adapt canonical objects instead of creating duplicate tables.

### E. Security/Privacy review checklist

- Owner/account derives from verified API auth context; cross-owner account IDs from request bodies are rejected.
- Privileged ledger mutation is server-only through FastAPI/domain service; clients cannot insert/update/delete ledger rows or invoke privileged RPCs.
- RLS and SQL grants are complementary: deny client roles ledger mutation, expose only authorized owner-scoped read projections where product requirements permit, and restrict policy administration to explicitly authorized operators.
- Use least-privilege service credentials, never expose service-role secrets to client bundles or logs.
- RPCs (if approved) validate trusted caller context, parameter bounds, idempotency, linkage, and transaction invariants; do not rely on client-side validation.
- Append-only behavior is enforced at the database permission/trigger/service boundary and tested with negative cases; privileged repair paths are separately audited.
- Audit metadata records actor, request/task/trace, policy version, idempotency key, reason and timestamps, but excludes prompts, raw document chunks, credentials and unnecessary sensitive payloads.
- Add cross-owner, forged-account, duplicate-key/different-payload, concurrent overspend, stale reservation, reversal-cap, RLS/grant and direct-DB-bypass negative tests.
- Review retention, deletion/erasure interactions, export and legal/accounting obligations before final schema approval.

### F. Implementation gates

1. Finance/Economy fills and approves the decision register in section A.
2. API/Data Platform reviews sections B–D against the live canonical schema and writes the transaction/repair contract; Security/Privacy signs off section E.
3. Only after these approvals, implement the durable sink, transaction service, approved migration and source/unit/contract tests in ENG-P09. Do not apply migration to production as a test.
4. ENG-P37 validates real isolated non-production Supabase transaction atomicity, concurrency, RLS/grants, cross-owner negative paths, recovery/reconciliation, and authenticated Web/Native/Super Admin journeys where applicable.

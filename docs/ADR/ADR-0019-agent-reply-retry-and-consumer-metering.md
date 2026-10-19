# ADR-0019: Idempotent Agent Reply Recovery and Consumer Metering

- **Status:** Proposed for implementation; not acceptance-approved
- **Date:** 2026-10-19
- **Scope:** ENG-P18 Agent messaging retries, consumer grants, runtime execution, credit reservation and usage metering
- **Decision owner:** Product Owner

## Context

The Master PRD requires typed domain boundaries, authenticated/authorized requests, budget reservation before chargeable execution, durable usage records, idempotency keys, explicit task lifecycle states, and reconciliation when an external outcome is uncertain. The canonical backend remains FastAPI; Supabase/PostgreSQL remains the transactional source of truth. This ADR does not create a second message registry, runtime, router, ledger, or queue.

The current messaging handler uses a persisted human message ID as the stable source for the deterministic Agent-reply idempotency key. Consumer calls require a current owner-approved grant and an approved Consumer credit policy. Unknown provider outcomes must not be treated as success or automatically refunded.

## Decision

1. **Stable reply identity.** Derive the Agent reply's client idempotency key deterministically from the persisted human message ID. Repeated client submissions with the same (conversation_id, sender_user_id, client_message_id) reuse the existing human message; a conflicting reuse must not create a second message.
2. **Recover before generating.** On a retry, first query the canonical messages table for the deterministic Agent reply key. If a reply is already persisted, return it without calling the model or charging again.
3. **At-most-one billable attempt unless outcome is reconciled.** If a previous provider attempt may have executed but no durable outcome exists, mark its reservation pending_reconciliation; do not blindly repeat the model call. Retry only after the canonical runtime/ledger can establish a safe retry state or a new explicitly authorized attempt.
4. **Reservation and settlement.** Consumer execution must reserve credits before provider invocation using the approved policy and canonical ledger lifecycle. Settlement uses actual metered token usage/cost and the pricing/policy versions recorded by the routed execution. Release unused reservation only under the approved settlement contract.
5. **Unknown outcomes.** Network timeouts, process interruption after provider submission, missing metering evidence, or persistence ambiguity are unknown outcomes. Preserve the reservation for reconciliation; never infer zero usage or successful settlement from a missing response.
6. **Idempotent durable writes.** Persist the deterministic reply ID under a database uniqueness constraint covering the canonical message identity. Handle duplicate/unique conflicts by reading the existing row and comparing its immutable identity. A replay must not create a second reply or second ledger charge.
7. **Policy remains fail-closed.** No tariff, payer, entitlement, maximum usage, or settlement permission may be invented in code. If the approved Consumer policy or matching active Model Router route is absent, deny Consumer execution before provider invocation. Owner/private behavior remains governed by the existing runtime policy.
8. **Observability.** Record stable task/trace/source-event IDs, safe failure categories, reservation state, actual usage and pricing version. Never log credentials or raw sensitive prompts by default.

## Consequences and constraints

- The deterministic reply key supports recovery after a successful persistence whose HTTP response was lost.
- A provider call that completed without durable metering/reply evidence cannot safely be repeated automatically; it needs reconciliation.
- The message endpoint alone cannot guarantee atomicity across an external model provider and PostgreSQL. The canonical ledger/runtime must preserve idempotency and unknown-outcome state.
- Existing schema constraints must be inspected before relying on uniqueness; if the required constraint is absent, add a versioned migration after reconciling the live schema. Do not claim database-level exactly-once execution without that evidence.
- This ADR does not approve Consumer tariffs or change payer responsibility.

## Required implementation evidence

- API source uses the stable human message identity and checks for an already-persisted reply before invoking generation on replay.
- Duplicate message/reply writes recover by reading the canonical row and do not re-invoke or re-charge.
- Consumer reservation, settlement and unknown-outcome reconciliation use the canonical ledger and pinned pricing/policy versions.
- Existing CI evidence is inspected; no tests, device runs, or staging are claimed unless actually run and reported.
- ENG-P18 remains in_progress until its phase-plan closure criteria have evidence. This ADR alone is not proof of acceptance.

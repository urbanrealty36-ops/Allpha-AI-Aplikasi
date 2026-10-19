# ADR-0019 Proposal — Public Agent Consumer Messaging Authorization

- **Status:** Approved for canonical runtime contract; consumer enablement remains gated
- **Date:** 2026-10-19
- **Scope:** ENG-P18 Messaging Human/Agent only
- **Decision owner:** Product Owner (approved by implementation directive on 2026-10-19); Security/Platform implementation checks remain required

## Context

The Master PRD defines an Agent Consumer who can discover public Agents, ask questions, provide permitted inputs, and understand capability limitations and credit usage. The existing canonical `AgentRuntime.execute_skill_generation` contract explicitly requires `requester_id == owner_id`. The runtime's durable tool-task path also verifies active ownership, pinned Agent/Skill versions, published Skills, approved capabilities, approved runtime policy, scopes, deadlines, checkpoints and idempotency.

Messaging cannot safely call the existing generation method for a non-owner without changing an explicit authorization invariant. Treating the consumer as the owner, calling the provider directly from Messaging, or bypassing runtime policy/metering is not acceptable.

## Options

1. **Owner-only Agent conversations for ENG-P18.** Safe with the current generation contract, but does not satisfy the full Agent Consumer journey for public Agents.
2. **Add a consumer-authorized execution contract to the canonical Agent Runtime.** Runtime verifies the Agent is public/active, consumer-facing capability and Skill are published, owner-approved policy explicitly permits consumer invocation, sensitivity/data scopes exclude owner-private memory by default, provider route and durable metering are ready, budgets/credits and rate limits are enforced, and trace/idempotency are durable. Requester identity remains the actual consumer; owner identity remains the Agent owner.
3. **Create a parallel generation path in Messaging.** Rejected: duplicates the canonical runtime and risks bypassing permission, budget, metering, and audit controls.

## Proposal

**Decision: Option 2.** Implement a typed consumer authorization contract in the canonical Agent Runtime and test it independently before Messaging enables public-consumer replies. The contract fails closed unless the caller supplies server-resolved authorization bound to the actual requester, owner, Agent/Skill versions, public/active status, owner-approved grant, approved policy, public sensitivity, empty owner-private memory scope, budget reservation and metering readiness. Until approval and implementation, Messaging may only generate a reply where the authenticated user is the Agent owner and the existing private route/policy is available. Public Agent consumer messages must fail closed with a stable safe error and must never imply a successful Agent reply.

## Consequences and acceptance

- No provider/model fallback is selected by Messaging.
- Public consumer inputs do not access owner-private memory, credentials, or tools unless separately and explicitly authorized.
- Usage/cost metering, rate/budget limits, policy version pinning, safe failures, idempotency and audit evidence remain mandatory.
- Add tests for owner vs consumer identity, private/public Agent visibility, published/unpublished Skill, revoked policy, scope denial, quota/metering unavailability, retry/idempotency and no owner-private retrieval.
- Rollback is to disable consumer generation while preserving ordinary human messaging; no direct database writes or schema bypass.
- **Implementation state:** ADR decision approved and the canonical runtime contract is implemented with fail-closed unit coverage. Public consumer replies remain disabled until a durable owner-grant lifecycle/API, policy and budget/metering integration are wired into the authenticated request path and verified.

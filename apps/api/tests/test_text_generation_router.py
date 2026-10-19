from __future__ import annotations

import asyncio
import pytest

from allpha_api.agent_runtime import AgentRuntime, AgentRuntimeBlocked
from allpha_api.model_router import (
    CanonicalTextGenerationRouter,
    TextGenerationPolicy,
    TextGenerationRequest,
    TextGenerationResponse,
    TextGenerationRoute,
    TextGenerationRouterRejected,
    TextGenerationRouterUnavailable,
)


class FakeAdapter:
    def __init__(self, *, model_id: str = "model-a", cost: int = 3):
        self.model_id = model_id
        self.cost = cost
        self.calls = 0

    async def generate(self, request: TextGenerationRequest, *, model_id: str) -> TextGenerationResponse:
        self.calls += 1
        return TextGenerationResponse(
            task_id=request.task_id,
            trace_id=request.trace_id,
            provider_id="provider-a",
            model_id=self.model_id,
            model_version="version-a",
            output_text='{"answer":"grounded test output"}',
            input_tokens=11,
            output_tokens=7,
            cost_microunits=self.cost,
            cost_unit="approved-unit",
            pricing_version="pricing-v1",
        )


class MemorySink:
    def __init__(self):
        self.rows = {}

    async def write_idempotent(self, evidence):
        existing = self.rows.get(evidence.idempotency_key)
        if existing and existing.evidence_sha256 != evidence.evidence_sha256:
            raise ValueError("idempotency conflict")
        self.rows[evidence.idempotency_key] = evidence


def make_router(adapter=None, *, route=True, sink=True, cost=3, max_cost=10, preflight=None):
    adapter = adapter or FakeAdapter(cost=cost)
    return CanonicalTextGenerationRouter(
        routes={"private": TextGenerationRoute("provider-a", "model-a", "version-a")} if route else {},
        adapters={"provider-a": adapter},
        policies={
            "private": TextGenerationPolicy(
                policy_id="policy-test",
                policy_version="v1",
                approved=True,
                max_prompt_bytes=1024,
                max_output_tokens=100,
                max_cost_microunits=max_cost,
                max_latency_ms=5000,
                cost_unit="approved-unit",
                pricing_version="pricing-v1",
            )
        } if route else {},
        metering_sink=MemorySink() if sink else None,
        runtime_preflight=preflight,
    )


def request():
    return TextGenerationRequest(
        task_id="task-1",
        trace_id="trace-1",
        idempotency_key="idempotency-1",
        sensitivity="private",
        prompt="Use the pinned Skill instructions to answer this test.",
        max_output_tokens=32,
        timeout_ms=1000,
    )


def test_text_generation_returns_route_and_usage_bound_evidence():
    router = make_router()
    response, evidence = asyncio.run(router.generate(request()))
    assert response.output_text == '{"answer":"grounded test output"}'
    assert evidence.provider_id == "provider-a"
    assert evidence.model_id == "model-a"
    assert evidence.model_version == "version-a"
    assert evidence.input_tokens == 11
    assert evidence.output_tokens == 7
    assert evidence.cost_microunits == 3
    assert len(evidence.prompt_sha256) == 64
    assert len(evidence.output_sha256) == 64
    assert len(evidence.evidence_sha256) == 64


def test_text_generation_fails_closed_without_approved_route_or_metering():
    with pytest.raises(TextGenerationRouterUnavailable):
        asyncio.run(make_router(route=False).generate(request()))
    with pytest.raises(TextGenerationRouterUnavailable):
        asyncio.run(make_router(sink=False).generate(request()))


def test_text_generation_rejects_provider_model_mismatch():
    router = make_router(FakeAdapter(model_id="unapproved-model"))
    with pytest.raises(TextGenerationRouterRejected, match="identity"):
        asyncio.run(router.generate(request()))


def test_text_generation_rejects_cost_over_approved_policy():
    router = make_router(FakeAdapter(cost=11), max_cost=10)
    with pytest.raises(TextGenerationRouterRejected, match="cost"):
        asyncio.run(router.generate(request()))


def test_text_generation_rejects_unapproved_policy():
    with pytest.raises(ValueError, match="must be approved"):
        TextGenerationPolicy(
            policy_id="policy-test", policy_version="v1", approved=False,
            max_prompt_bytes=1024, max_output_tokens=100, max_cost_microunits=10,
            max_latency_ms=5000,
            cost_unit="approved-unit", pricing_version="pricing-v1",
        )


def test_agent_runtime_executes_pinned_skill_via_model_router():
    runtime = AgentRuntime()
    router = make_router()
    result, evidence = asyncio.run(runtime.execute_skill_generation(
        requester_id="owner-1", owner_id="owner-1",
        agent_id="agent-1", agent_version=2, skill_id="skill-1", skill_version=3,
        skill_published=True, policy_version="v1", router=router, request=request(),
    ))
    assert result.output_text == '{"answer":"grounded test output"}'
    assert evidence.policy_version == "v1"


def test_agent_runtime_rejects_owner_or_skill_authority_mismatch():
    runtime = AgentRuntime()
    router = make_router()
    with pytest.raises(AgentRuntimeBlocked, match="consumer authorization is required"):
        asyncio.run(runtime.execute_skill_generation(
            requester_id="attacker", owner_id="owner-1",
            agent_id="agent-1", agent_version=2, skill_id="skill-1", skill_version=3,
            skill_published=True, policy_version="v1", router=router, request=request(),
        ))
    with pytest.raises(AgentRuntimeBlocked, match="published"):
        asyncio.run(runtime.execute_skill_generation(
            requester_id="owner-1", owner_id="owner-1",
            agent_id="agent-1", agent_version=2, skill_id="skill-1", skill_version=3,
            skill_published=False, policy_version="v1", router=router, request=request(),
        ))


def test_metering_failure_does_not_replay_provider_generation():
    class BrokenSink:
        async def write_idempotent(self, evidence):
            raise RuntimeError("storage unavailable")

    adapter = FakeAdapter()
    router = CanonicalTextGenerationRouter(
        routes={"private": TextGenerationRoute("provider-a", "model-a", "version-a")},
        adapters={"provider-a": adapter},
        policies={"private": TextGenerationPolicy(
            policy_id="policy-test", policy_version="v1", approved=True,
            max_prompt_bytes=1024, max_output_tokens=100, max_cost_microunits=10,
            max_latency_ms=5000, cost_unit="approved-unit", pricing_version="pricing-v1",
        )},
        metering_sink=BrokenSink(),
    )
    with pytest.raises(TextGenerationRouterUnavailable, match="automatic replay is blocked"):
        asyncio.run(router.generate(request()))
    assert adapter.calls == 1


def test_runtime_preflight_blocks_provider_call_when_active_tariff_is_missing():
    adapter = FakeAdapter()

    async def deny_unverified_tariff(sensitivity, route, policy):
        raise RuntimeError("no active tariff")

    router = make_router(adapter, preflight=deny_unverified_tariff)
    with pytest.raises(TextGenerationRouterUnavailable, match="active model-cost configuration"):
        asyncio.run(router.generate(request()))
    assert adapter.calls == 0

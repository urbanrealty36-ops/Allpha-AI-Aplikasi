import asyncio
from datetime import datetime, timezone

import pytest

from allpha_api.embedding_contract import EmbeddingFailure, EmbeddingRequest, EmbeddingResponse
from allpha_api.model_router import (
    CanonicalModelRouter,
    EmbeddingRoute,
    ModelRouterRejected,
    ModelRouterUnavailable,
    ModelRouterTransient,
    route_embedding,
)


def request():
    return EmbeddingRequest(task_id="task-1", idempotency_key="idem-1", trace_id="trace-1", owner_id="owner-1", agent_id="agent-1", source_id="source-1", source_version=1, sensitivity="internal", attempt=1, timeout_ms=5000, chunks=[{"chunk_id":"chunk-1","content_sha256":"a"*64,"text":"example"}])


def response(provider_id="router-policy", model_id="selected-model", model_version="version-1", digest=None, usage_units=None, cost_microunits=None):
    return EmbeddingResponse(task_id="task-1", provider_id=provider_id, model_id=model_id, model_version=model_version, dimensions=2, vectors=[{"chunk_id":"chunk-1","content_sha256":digest or "a"*64,"values":[0.1,0.2]}], trace_id="trace-1", completed_at=datetime.now(timezone.utc), usage_units=usage_units, cost_microunits=cost_microunits)


class FakeRouter:
    def __init__(self, value):
        self.value = value
        self.calls = 0

    async def embed(self, payload):
        self.calls += 1
        return self.value


class FakeAdapter:
    def __init__(self, values):
        self.values = list(values)
        self.calls = 0

    async def embed(self, payload, *, model_id):
        self.calls += 1
        value = self.values.pop(0)
        if isinstance(value, Exception):
            raise value
        return value


def test_missing_canonical_router_fails_closed():
    async def scenario():
        with pytest.raises(ModelRouterUnavailable):
            await route_embedding(None, request())
    asyncio.run(scenario())


def test_router_response_with_matching_provenance_is_accepted():
    async def scenario():
        router = FakeRouter(response())
        result = await route_embedding(router, request())
        assert result.model_id == "selected-model"
        assert router.calls == 1
    asyncio.run(scenario())


def test_router_response_with_wrong_chunk_hash_is_rejected():
    async def scenario():
        invalid = response(digest="b"*64)
        with pytest.raises(ModelRouterRejected) as error:
            await route_embedding(FakeRouter(invalid), request())
        assert error.value.failure.code == "MODEL_ROUTER_RESPONSE_INVALID"
        assert error.value.failure.retryable is False
    asyncio.run(scenario())


def test_canonical_router_selects_configured_route_and_records_metering():
    async def scenario():
        class Meter:
            def __init__(self):
                self.records = []
            async def write_idempotent(self, record):
                self.records.append(record)
        meter = Meter()
        adapter = FakeAdapter([response(usage_units=5, cost_microunits=20)])
        router = CanonicalModelRouter(
            routes={"internal": EmbeddingRoute("router-policy", "selected-model", "version-1")},
            adapters={"router-policy": adapter},
            metering_sink=meter,
        )
        result = await router.embed(request())
        assert result.model_id == "selected-model"
        assert adapter.calls == 1
        assert len(meter.records) == 1
        assert isinstance(meter.records[0], MeteringRecord)
        assert meter.records[0].idempotency_key == "idem-1"
        assert meter.records[0].usage_units == 5
        assert meter.records[0].cost_microunits == 20
    asyncio.run(scenario())


def test_canonical_router_fails_closed_without_sensitivity_policy():
    async def scenario():
        router = CanonicalModelRouter(routes={}, adapters={})
        with pytest.raises(ModelRouterUnavailable):
            await router.embed(request())
    asyncio.run(scenario())


def test_canonical_router_retries_only_transient_adapter_failures():
    async def scenario():
        adapter = FakeAdapter([ModelRouterTransient("temporary"), response()])
        router = CanonicalModelRouter(
            routes={"internal": EmbeddingRoute("router-policy", "selected-model", "version-1", max_attempts=2)},
            adapters={"router-policy": adapter},
            retry_delay_seconds=0,
        )
        result = await router.embed(request())
        assert result.model_id == "selected-model"
        assert adapter.calls == 2
    asyncio.run(scenario())


def test_canonical_router_rejects_wrong_model_identity_without_retry():
    async def scenario():
        adapter = FakeAdapter([response(model_id="unapproved-model"), response()])
        router = CanonicalModelRouter(
            routes={"internal": EmbeddingRoute("router-policy", "selected-model", "version-1", max_attempts=2)},
            adapters={"router-policy": adapter},
            retry_delay_seconds=0,
        )
        with pytest.raises(ModelRouterRejected) as error:
            await router.embed(request())
        assert error.value.failure.code == "MODEL_ROUTER_ROUTE_IDENTITY_MISMATCH"
        assert adapter.calls == 1
    asyncio.run(scenario())


def test_canonical_router_times_out_and_returns_retryable_failure():
    async def scenario():
        class HangingAdapter:
            async def embed(self, payload, *, model_id):
                await asyncio.sleep(0.05)
                return response()
        router = CanonicalModelRouter(
            routes={"internal": EmbeddingRoute("router-policy", "selected-model", "version-1", max_attempts=1)},
            adapters={"router-policy": HangingAdapter()},
            retry_delay_seconds=0,
        )
        payload = request().model_copy(update={"timeout_ms": 5})
        with pytest.raises(ModelRouterRejected) as error:
            await router.embed(payload)
        assert error.value.failure.code == "MODEL_ROUTER_TIMEOUT"
        assert error.value.failure.retryable is True
    asyncio.run(scenario())


def test_canonical_router_does_not_retry_terminal_provider_rejection():
    async def scenario():
        adapter = FakeAdapter([ModelRouterRejected(
            EmbeddingFailure(
                task_id="task-1", code="POLICY_REJECTED", retryable=False, trace_id="trace-1"
            )
        )])
        router = CanonicalModelRouter(
            routes={"internal": EmbeddingRoute("router-policy", "selected-model", "version-1", max_attempts=3)},
            adapters={"router-policy": adapter},
            retry_delay_seconds=0,
        )
        with pytest.raises(ModelRouterRejected):
            await router.embed(request())
        assert adapter.calls == 1
    asyncio.run(scenario())


from allpha_api.cost_policy import CostBudget, CostEstimate
from allpha_api.metering_contract import MeteringRecord


def test_canonical_router_cost_policy_denies_missing_estimate_before_provider_call():
    async def scenario():
        adapter = FakeAdapter([response()])
        router = CanonicalModelRouter(
            routes={"internal": EmbeddingRoute("router-policy", "selected-model", "version-1")},
            adapters={"router-policy": adapter},
            cost_budgets={"internal": CostBudget("internal", 100, 1000)},
            cost_estimates={},
        )
        with pytest.raises(ModelRouterUnavailable):
            await router.embed(request())
        assert adapter.calls == 0
    asyncio.run(scenario())


def test_canonical_router_cost_policy_rejects_actual_cost_over_reservation():
    async def scenario():
        adapter = FakeAdapter([response(usage_units=100, cost_microunits=1200)])
        router = CanonicalModelRouter(
            routes={"internal": EmbeddingRoute("router-policy", "selected-model", "version-1")},
            adapters={"router-policy": adapter},
            cost_budgets={"internal": CostBudget("internal", 100, 1000)},
            cost_estimates={"internal": CostEstimate("router-policy", "selected-model", "version-1", 100, 900)},
        )
        with pytest.raises(ModelRouterRejected) as error:
            await router.embed(request())
        assert error.value.failure.code == "MODEL_ROUTER_COST_POLICY_REJECTED"
    asyncio.run(scenario())


def test_canonical_router_cost_policy_requires_matching_route_version():
    async def scenario():
        adapter = FakeAdapter([response()])
        router = CanonicalModelRouter(
            routes={"internal": EmbeddingRoute("router-policy", "selected-model", "version-1")},
            adapters={"router-policy": adapter},
            cost_budgets={"internal": CostBudget("internal", 100, 1000)},
            cost_estimates={"internal": CostEstimate("router-policy", "selected-model", "other-version", 10, 100)},
        )
        with pytest.raises(ModelRouterUnavailable):
            await router.embed(request())
        assert adapter.calls == 0
    asyncio.run(scenario())


def test_runtime_router_requires_explicit_cost_policy_and_durable_metering():
    async def scenario():
        router = CanonicalModelRouter(
            routes={"internal": EmbeddingRoute("router-policy", "selected-model", "version-1")},
            adapters={"router-policy": FakeAdapter([])},
        )
        with pytest.raises(ModelRouterUnavailable, match="cost budgets"):
            router.require_runtime_ready()

        class Meter:
            async def write_idempotent(self, record):
                return None

        configured = CanonicalModelRouter(
            routes={"internal": EmbeddingRoute("router-policy", "selected-model", "version-1")},
            adapters={"router-policy": FakeAdapter([])},
            cost_budgets={"internal": CostBudget("internal", 100, 1000)},
            cost_estimates={"internal": CostEstimate("router-policy", "selected-model", "version-1", 10, 100)},
            metering_sink=Meter(),
        )
        configured.require_runtime_ready()
        assert configured.has_approved_cost_policy
        assert configured.has_durable_metering_contract
    asyncio.run(scenario())


def test_runtime_router_rejects_callable_only_non_durable_metering_sink():
    async def scenario():
        router = CanonicalModelRouter(
            routes={"internal": EmbeddingRoute("router-policy", "selected-model", "version-1")},
            adapters={"router-policy": FakeAdapter([])},
            cost_budgets={"internal": CostBudget("internal", 100, 1000)},
            cost_estimates={"internal": CostEstimate("router-policy", "selected-model", "version-1", 10, 100)},
            metering_sink=lambda request, response: None,
        )
        with pytest.raises(ModelRouterUnavailable, match="durable idempotent metering"):
            router.require_runtime_ready()
    asyncio.run(scenario())

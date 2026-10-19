from datetime import datetime, timezone
import json

import httpx
import pytest

from allpha_api.embedding_contract import EmbeddingRequest, EmbeddingResponse
from allpha_api.metering_contract import MeteringContractError, build_metering_record
from allpha_api.supabase_metering_sink import SupabaseMeteringSink
from allpha_api.model_router import TextGenerationEvidence


def record():
    request = EmbeddingRequest(
        task_id="task-1", idempotency_key="stable-key", trace_id="trace-1",
        owner_id="owner-1", agent_id="agent-1", source_id="source-1",
        source_version=3, sensitivity="internal", attempt=1, timeout_ms=1000,
        chunks=[{"chunk_id": "chunk-1", "content_sha256": "a" * 64, "text": "x"}],
    )
    response = EmbeddingResponse(
        task_id="task-1", provider_id="provider", model_id="model",
        model_version="v1", dimensions=2,
        vectors=[{"chunk_id": "chunk-1", "content_sha256": "a" * 64, "values": [0.1, 0.2]}],
        trace_id="trace-1", completed_at=datetime(2026, 10, 15, tzinfo=timezone.utc),
        usage_units=10, usage_unit="embedding_input_unit",
        cost_microunits=100, cost_unit="policy_cost_microunit",
        pricing_version="test-pricing-v1",
    )
    return build_metering_record(request, response)


def test_supabase_sink_calls_transactional_idempotent_rpc_with_fingerprint():
    seen = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["authorization"] = request.headers.get("Authorization")
        seen["body"] = json.loads((await request.aread()).decode())
        return httpx.Response(200, json=True)

    sink = SupabaseMeteringSink(
        supabase_url="https://example.supabase.co",
        service_key="test-only-service-key",
        transport=httpx.MockTransport(handler),
    )
    import asyncio
    asyncio.run(sink.write_idempotent(record()))
    assert seen["url"].endswith("/rest/v1/rpc/record_agent_model_usage_metering")
    assert seen["authorization"] == "Bearer test-only-service-key"
    payload = seen["body"]["p_record"]
    assert payload["idempotency_key"] == "stable-key"
    assert len(payload["payload_fingerprint"]) == 64
    assert payload["usage_unit"] == "embedding_input_unit"
    assert payload["cost_unit"] == "policy_cost_microunit"


def test_supabase_sink_maps_idempotency_conflict_without_exposing_response_body():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(409, json={"code": "23505", "message": "METERING_IDEMPOTENCY_CONFLICT"})
    sink = SupabaseMeteringSink(
        supabase_url="https://example.supabase.co",
        service_key="test-only-service-key",
        transport=httpx.MockTransport(handler),
    )
    import asyncio
    with pytest.raises(MeteringContractError, match="different metering payload"):
        asyncio.run(sink.write_idempotent(record()))


def test_supabase_sink_fails_closed_on_non_success_rpc_result():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=False)
    sink = SupabaseMeteringSink(
        supabase_url="https://example.supabase.co",
        service_key="test-only-service-key",
        transport=httpx.MockTransport(handler),
    )
    import asyncio
    with pytest.raises(RuntimeError, match="did not confirm durable persistence"):
        asyncio.run(sink.write_idempotent(record()))


def test_text_generation_metering_persists_approved_billing_account():
    seen = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads((await request.aread()).decode())
        return httpx.Response(200, json=True)

    sink = SupabaseMeteringSink(
        supabase_url="https://example.supabase.co",
        service_key="test-only-service-key",
        transport=httpx.MockTransport(handler),
    )
    evidence = TextGenerationEvidence(
        task_id="consumer-message:message-1",
        trace_id="trace-1",
        idempotency_key="message-agent-reply:message-1",
        policy_id="public-agent-policy",
        policy_version="policy-v1",
        provider_id="provider",
        model_id="model",
        model_version="model-v1",
        prompt_sha256="a" * 64,
        output_sha256="b" * 64,
        input_tokens=11,
        output_tokens=7,
        cost_microunits=99,
        cost_unit="USD_microunit",
        pricing_version="price-v1",
        latency_ms=100,
        latency_budget_ms=5000,
        cost_budget_microunits=500,
        status="succeeded",
        owner_id="agent-owner",
        agent_id="agent-1",
        source_id="skill-1",
        source_version=3,
        sensitivity="public",
        evidence_sha256="c" * 64,
        billing_account_id="consumer-payer",
        completed_at="2026-10-19T15:00:00+00:00",
    )
    import asyncio
    asyncio.run(sink.write_idempotent(evidence))
    payload = seen["body"]["p_record"]
    assert payload["owner_id"] == "agent-owner"
    assert payload["billing_account_id"] == "consumer-payer"
    assert payload["task_id"] == "consumer-message:message-1"
    assert payload["idempotency_key"] == "message-agent-reply:message-1"
    assert payload["usage_units"] == 18
    assert payload["usage_unit"] == "token"

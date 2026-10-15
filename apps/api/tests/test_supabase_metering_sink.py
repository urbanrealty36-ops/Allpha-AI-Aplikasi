from datetime import datetime, timezone
import json

import httpx
import pytest

from allpha_api.embedding_contract import EmbeddingRequest, EmbeddingResponse
from allpha_api.metering_contract import MeteringContractError, build_metering_record
from allpha_api.supabase_metering_sink import SupabaseMeteringSink


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

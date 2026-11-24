from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from allpha_api.embedding_router_factory import build_embedding_router_from_environment
from allpha_api.embedding_adapters import EmbeddingProviderConfigurationError
from allpha_api.model_router import ModelRouterRejected, ModelRouterUnavailable
from allpha_api.embedding_contract import EmbeddingRequest


def configure_profile(monkeypatch):
    values = {
        "ALLPHA_EMBEDDING_BASE_URL": "https://embedding.example/v1",
        "ALLPHA_EMBEDDING_API_KEY": "server-side-secret",
        "ALLPHA_EMBEDDING_PROVIDER_ID": "generic-provider",
        "ALLPHA_EMBEDDING_MODEL_ID": "embed-model-1",
        "ALLPHA_EMBEDDING_MODEL_VERSION": "model-build-1",
        "ALLPHA_EMBEDDING_DIMENSIONS": "3",
        "ALLPHA_EMBEDDING_POLICY_ID": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        "ALLPHA_EMBEDDING_POLICY_VERSION": "policy-v1",
        "ALLPHA_EMBEDDING_POLICY_APPROVAL_REFERENCE": "EMBEDDING-POLICY-APPROVAL-01",
        "ALLPHA_EMBEDDING_PRICING_VERSION": "price-v1",
        "ALLPHA_EMBEDDING_COST_UNIT": "USD_microunits",
        "ALLPHA_EMBEDDING_INPUT_COST_MICROUNITS_PER_TOKEN": "2",
        "ALLPHA_EMBEDDING_MAX_INPUT_TOKENS": "4096",
        "ALLPHA_EMBEDDING_MAX_COST_MICROUNITS": "8192",
        "ALLPHA_EMBEDDING_MAX_PROMPT_BYTES": "4096",
        "ALLPHA_EMBEDDING_MAX_LATENCY_MS": "30000",
        "ALLPHA_EMBEDDING_ALLOWED_SENSITIVITIES": "public,internal",
        "ALLPHA_EMBEDDING_MAX_ATTEMPTS": "2",
        "SUPABASE_URL": "https://db.example.supabase.co",
        "SUPABASE_SERVICE_ROLE_KEY": "service-role-secret",
    }
    for key, value in values.items():
        monkeypatch.setenv(key, value)


def model_cost_row():
    now = datetime.now(timezone.utc)
    return {
        "id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        "capability": "embedding",
        "policy_version": "policy-v1",
        "provider_id": "generic-provider",
        "model_id": "embed-model-1",
        "model_version": "model-build-1",
        "pricing_version": "price-v1",
        "cost_unit": "USD_microunits",
        "input_micro_cost_per_token": 2,
        "output_micro_cost_per_token": 0,
        "max_cost_microunits": 8192,
        "max_prompt_bytes": 4096,
        "max_latency_ms": 30000,
        "policy_approved": True,
        "status": "active",
        "effective_at": (now - timedelta(minutes=1)).isoformat(),
        "policy_approval_reference": "EMBEDDING-POLICY-APPROVAL-01",
        "policy_approved_by": "11111111-1111-4111-8111-111111111111",
        "policy_approved_at": (now - timedelta(minutes=1)).isoformat(),
    }


def embedding_request(sensitivity="internal"):
    text = "one private chunk"
    return EmbeddingRequest(
        task_id="knowledge-job-1:0",
        idempotency_key="knowledge:job-1:v1:batch0",
        trace_id="trace-1",
        owner_id="owner-1",
        agent_id="agent-1",
        source_id="source-1",
        source_version=1,
        sensitivity=sensitivity,
        attempt=1,
        timeout_ms=5000,
        chunks=[{
            "chunk_id": "chunk-1",
            "content_sha256": hashlib.sha256(text.encode()).hexdigest(),
            "text": text,
        }],
    )


def test_embedding_router_is_not_created_without_explicit_provider_profile(monkeypatch):
    for key in (
        "ALLPHA_EMBEDDING_BASE_URL", "ALLPHA_EMBEDDING_API_KEY",
        "ALLPHA_EMBEDDING_PROVIDER_ID", "ALLPHA_EMBEDDING_MODEL_ID",
        "ALLPHA_EMBEDDING_MODEL_VERSION", "ALLPHA_EMBEDDING_DIMENSIONS",
        "ALLPHA_EMBEDDING_POLICY_ID", "ALLPHA_EMBEDDING_POLICY_VERSION",
        "ALLPHA_EMBEDDING_POLICY_APPROVAL_REFERENCE", "ALLPHA_EMBEDDING_PRICING_VERSION",
        "ALLPHA_EMBEDDING_COST_UNIT", "ALLPHA_EMBEDDING_INPUT_COST_MICROUNITS_PER_TOKEN",
        "ALLPHA_EMBEDDING_MAX_INPUT_TOKENS", "ALLPHA_EMBEDDING_MAX_COST_MICROUNITS",
        "ALLPHA_EMBEDDING_MAX_PROMPT_BYTES", "ALLPHA_EMBEDDING_MAX_LATENCY_MS",
        "ALLPHA_EMBEDDING_ALLOWED_SENSITIVITIES", "SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY",
    ):
        monkeypatch.delenv(key, raising=False)

    async def scenario():
        assert await build_embedding_router_from_environment() is None
    asyncio.run(scenario())


def test_embedding_router_rejects_partial_provider_profile(monkeypatch):
    monkeypatch.setenv("ALLPHA_EMBEDDING_BASE_URL", "https://provider.example/v1")

    async def scenario():
        with pytest.raises(EmbeddingProviderConfigurationError, match="profile is incomplete"):
            await build_embedding_router_from_environment()
    asyncio.run(scenario())


def test_embedding_router_verifies_policy_routes_provider_and_persists_metering(monkeypatch):
    configure_profile(monkeypatch)
    observed = {"metering": None, "provider": None}

    def handler(request):
        if request.method == "GET" and request.url.path.endswith("/ai_model_cost_configs"):
            return httpx.Response(200, json=[model_cost_row()])
        if request.method == "POST" and request.url.path.endswith("/embeddings"):
            body = json.loads(request.content)
            observed["provider"] = body
            return httpx.Response(200, json={
                "model": "embed-model-1",
                "data": [{"index": 0, "embedding": [0.1, 0.2, 0.3]}],
                "usage": {"prompt_tokens": 10},
            })
        if request.method == "POST" and request.url.path.endswith("/record_agent_model_usage_metering"):
            observed["metering"] = json.loads(request.content)["p_record"]
            return httpx.Response(200, json=True)
        raise AssertionError(f"unexpected provider/database request: {request.method} {request.url.path}")

    async def scenario():
        transport = httpx.MockTransport(handler)
        router = await build_embedding_router_from_environment(transport=transport)
        assert router is not None
        assert router.has_approved_cost_policy is True
        assert router.has_durable_metering_contract is True
        result = await router.embed(embedding_request())
        assert result.provider_id == "generic-provider"
        assert result.model_version == "model-build-1"
        assert result.dimensions == 3
        assert observed["provider"]["model"] == "embed-model-1"
        assert observed["metering"]["idempotency_key"] == "knowledge:job-1:v1:batch0"
        assert observed["metering"]["usage_units"] == 10
        assert observed["metering"]["cost_microunits"] == 20
        assert observed["metering"]["payload_fingerprint"]
        assert "one private chunk" not in json.dumps(observed["metering"])

    asyncio.run(scenario())


def test_embedding_router_rejects_policy_registry_mismatch_before_provider_call(monkeypatch):
    configure_profile(monkeypatch)
    row = model_cost_row()
    row["capability"] = "text_generation"
    calls = []

    def handler(request):
        calls.append(request.url.path)
        return httpx.Response(200, json=[row])

    async def scenario():
        with pytest.raises(ModelRouterUnavailable, match="approved active embedding cost-policy"):
            await build_embedding_router_from_environment(transport=httpx.MockTransport(handler))
        assert calls == ["/rest/v1/ai_model_cost_configs"]

    asyncio.run(scenario())


def test_embedding_router_rejects_dimension_mismatch_before_metering(monkeypatch):
    configure_profile(monkeypatch)
    calls = {"provider": 0, "meter": 0}

    def handler(request):
        if request.method == "GET":
            return httpx.Response(200, json=[model_cost_row()])
        if request.url.path.endswith("/embeddings"):
            calls["provider"] += 1
            return httpx.Response(200, json={
                "model": "embed-model-1",
                "data": [{"index": 0, "embedding": [0.1, 0.2]}],
                "usage": {"prompt_tokens": 10},
            })
        if request.url.path.endswith("/record_agent_model_usage_metering"):
            calls["meter"] += 1
            return httpx.Response(200, json=True)
        raise AssertionError(request.url.path)

    async def scenario():
        router = await build_embedding_router_from_environment(transport=httpx.MockTransport(handler))
        with pytest.raises(ModelRouterRejected) as error:
            await router.embed(embedding_request())
        assert error.value.failure.code == "EMBEDDING_PROVIDER_RESPONSE_INVALID"
        assert calls == {"provider": 1, "meter": 0}

    asyncio.run(scenario())



def test_embedding_router_never_replays_provider_after_metering_confirmation_failure(monkeypatch):
    configure_profile(monkeypatch)
    calls = {"provider": 0, "meter": 0}

    def handler(request):
        if request.method == "GET":
            return httpx.Response(200, json=[model_cost_row()])
        if request.url.path.endswith("/embeddings"):
            calls["provider"] += 1
            return httpx.Response(200, json={
                "model": "embed-model-1",
                "data": [{"index": 0, "embedding": [0.1, 0.2, 0.3]}],
                "usage": {"prompt_tokens": 10},
            })
        if request.url.path.endswith("/record_agent_model_usage_metering"):
            calls["meter"] += 1
            return httpx.Response(503, json={"message": "temporary database failure"})
        raise AssertionError(request.url.path)

    async def scenario():
        router = await build_embedding_router_from_environment(transport=httpx.MockTransport(handler))
        with pytest.raises(ModelRouterRejected) as error:
            await router.embed(embedding_request())
        assert error.value.failure.code == "MODEL_ROUTER_METERING_UNCONFIRMED"
        assert error.value.failure.retryable is False
        assert calls == {"provider": 1, "meter": 1}

    asyncio.run(scenario())

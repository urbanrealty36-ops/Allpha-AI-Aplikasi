from __future__ import annotations

import asyncio
import hashlib
import json

import httpx
import pytest

from allpha_api.embedding_adapters import (
    EmbeddingProviderConfigurationError,
    OpenAICompatibleEmbeddingAdapter,
    build_embedding_adapter_from_environment,
)
from allpha_api.embedding_contract import EmbeddingRequest
from allpha_api.model_router import ModelRouterRejected, ModelRouterTransient


def request() -> EmbeddingRequest:
    texts = ["first private chunk", "second private chunk"]
    return EmbeddingRequest(
        task_id="job-1:0",
        idempotency_key="knowledge:job-1:v1:batch0",
        trace_id="trace-1",
        owner_id="owner-1",
        agent_id="agent-1",
        source_id="source-1",
        source_version=1,
        sensitivity="internal",
        attempt=1,
        timeout_ms=5000,
        chunks=[
            {"chunk_id": f"chunk-{i}", "content_sha256": hashlib.sha256(text.encode()).hexdigest(), "text": text}
            for i, text in enumerate(texts)
        ],
    )


def adapter(handler, *, priced: bool = False):
    return OpenAICompatibleEmbeddingAdapter(
        base_url="https://embedding.example/v1",
        api_key="server-only-secret",
        provider_id="deployment-provider",
        model_version="immutable-model-build-7",
        expected_dimensions=3,
        pricing_version="approved-tariff-v1" if priced else None,
        cost_unit="USD_microunits" if priced else None,
        input_cost_microunits_per_token=4 if priced else None,
        transport=httpx.MockTransport(handler),
    )


def test_embedding_adapter_maps_out_of_order_vectors_and_calculates_configured_cost():
    def handler(request):
        body = json.loads(request.content)
        assert request.url.path == "/v1/embeddings"
        assert body["model"] == "model-pinned-by-router"
        assert body["input"] == ["first private chunk", "second private chunk"]
        return httpx.Response(200, json={
            "model": "model-pinned-by-router",
            "data": [
                {"index": 1, "embedding": [0.4, 0.5, 0.6]},
                {"index": 0, "embedding": [0.1, 0.2, 0.3]},
            ],
            "usage": {"prompt_tokens": 11},
        })

    async def scenario():
        result = await adapter(handler, priced=True).embed(request(), model_id="model-pinned-by-router")
        assert result.provider_id == "deployment-provider"
        assert result.model_version == "immutable-model-build-7"
        assert result.dimensions == 3
        assert [item.chunk_id for item in result.vectors] == ["chunk-0", "chunk-1"]
        assert result.vectors[0].values == [0.1, 0.2, 0.3]
        assert result.usage_units == 11
        assert result.usage_unit == "input_tokens"
        assert result.cost_microunits == 44
        assert result.pricing_version == "approved-tariff-v1"

    asyncio.run(scenario())


@pytest.mark.parametrize(
    ("status", "safe_to_retry"),
    [(408, False), (425, False), (429, True), (500, False), (503, False)],
)
def test_embedding_adapter_classifies_transient_http_status_without_replaying_unknown_outcomes(status, safe_to_retry):
    async def scenario():
        with pytest.raises(ModelRouterTransient) as error:
            await adapter(lambda request: httpx.Response(status, headers={"Retry-After": "2"})).embed(
                request(), model_id="model",
            )
        assert error.value.safe_to_retry is safe_to_retry
        if safe_to_retry:
            assert error.value.retry_after_ms == 2000
    asyncio.run(scenario())


@pytest.mark.parametrize("status", [400, 401, 403, 404])
def test_embedding_adapter_classifies_terminal_http_status(status):
    async def scenario():
        with pytest.raises(ModelRouterRejected) as error:
            await adapter(lambda request: httpx.Response(status)).embed(request(), model_id="model")
        assert error.value.failure.code == "EMBEDDING_PROVIDER_REQUEST_REJECTED"
        assert error.value.failure.retryable is False
    asyncio.run(scenario())


def test_embedding_adapter_rejects_model_or_dimension_mismatch():
    async def scenario():
        wrong_model = lambda request: httpx.Response(200, json={
            "model": "other-model",
            "data": [{"index": 0, "embedding": [0.1, 0.2, 0.3]}, {"index": 1, "embedding": [0.4, 0.5, 0.6]}],
        })
        with pytest.raises(ModelRouterRejected) as error:
            await adapter(wrong_model).embed(request(), model_id="model")
        assert error.value.failure.code == "EMBEDDING_PROVIDER_RESPONSE_INVALID"

        wrong_dimensions = lambda request: httpx.Response(200, json={
            "model": "model",
            "data": [{"index": 0, "embedding": [0.1, 0.2]}, {"index": 1, "embedding": [0.4, 0.5]}],
        })
        with pytest.raises(ModelRouterRejected):
            await adapter(wrong_dimensions).embed(request(), model_id="model")
    asyncio.run(scenario())


def test_embedding_adapter_rejects_duplicate_and_non_finite_vectors():
    async def scenario():
        duplicate = lambda request: httpx.Response(200, json={
            "model": "model",
            "data": [{"index": 0, "embedding": [0.1, 0.2, 0.3]}, {"index": 0, "embedding": [0.4, 0.5, 0.6]}],
        })
        with pytest.raises(ModelRouterRejected):
            await adapter(duplicate).embed(request(), model_id="model")
        non_finite = lambda request: httpx.Response(200, content=b'{"model":"model","data":[{"index":0,"embedding":[NaN,0.2,0.3]},{"index":1,"embedding":[0.4,0.5,0.6]}]}')
        with pytest.raises(ModelRouterRejected):
            await adapter(non_finite).embed(request(), model_id="model")
    asyncio.run(scenario())


def test_embedding_adapter_requires_https_and_complete_tariff():
    with pytest.raises(EmbeddingProviderConfigurationError):
        OpenAICompatibleEmbeddingAdapter(
            base_url="http://unsafe.example/v1", api_key="x", provider_id="p",
            model_version="v1", expected_dimensions=3,
        )
    with pytest.raises(EmbeddingProviderConfigurationError):
        OpenAICompatibleEmbeddingAdapter(
            base_url="https://safe.example/v1", api_key="x", provider_id="p",
            model_version="v1", expected_dimensions=3, pricing_version="tariff",
        )


def test_environment_adapter_is_absent_until_explicit_profile_is_complete(monkeypatch):
    for name in (
        "ALLPHA_EMBEDDING_BASE_URL", "ALLPHA_EMBEDDING_API_KEY",
        "ALLPHA_EMBEDDING_PROVIDER_ID", "ALLPHA_EMBEDDING_MODEL_VERSION",
        "ALLPHA_EMBEDDING_DIMENSIONS", "ALLPHA_EMBEDDING_PRICING_VERSION",
        "ALLPHA_EMBEDDING_COST_UNIT", "ALLPHA_EMBEDDING_INPUT_COST_MICROUNITS_PER_TOKEN",
    ):
        monkeypatch.delenv(name, raising=False)
    assert build_embedding_adapter_from_environment() is None

    monkeypatch.setenv("ALLPHA_EMBEDDING_BASE_URL", "https://provider.example/v1")
    with pytest.raises(EmbeddingProviderConfigurationError, match="partially configured"):
        build_embedding_adapter_from_environment()



def test_embedding_adapter_enforces_approved_input_byte_limit():
    async def scenario():
        limited = OpenAICompatibleEmbeddingAdapter(
            base_url="https://embedding.example/v1",
            api_key="server-only-secret",
            provider_id="deployment-provider",
            model_version="immutable-model-build-7",
            expected_dimensions=3,
            max_input_bytes=10,
            transport=httpx.MockTransport(lambda request: httpx.Response(500)),
        )
        with pytest.raises(ModelRouterRejected) as error:
            await limited.embed(request(), model_id="model")
        assert error.value.failure.code == "EMBEDDING_INPUT_LIMIT_EXCEEDED"
    asyncio.run(scenario())



def test_embedding_adapter_marks_pre_connection_failure_safe_to_retry():
    async def scenario():
        def handler(request):
            raise httpx.ConnectError("connection was not established")
        with pytest.raises(ModelRouterTransient) as error:
            await adapter(handler).embed(request(), model_id="model")
        assert error.value.safe_to_retry is True
    asyncio.run(scenario())

from datetime import datetime, timezone

import pytest

from allpha_api.embedding_contract import EmbeddingRequest, EmbeddingResponse
from allpha_api.model_router import ModelRouterRejected, ModelRouterUnavailable, route_embedding


def request():
    return EmbeddingRequest(task_id="task-1", idempotency_key="idem-1", trace_id="trace-1", owner_id="owner-1", agent_id="agent-1", source_id="source-1", source_version=1, sensitivity="internal", attempt=1, timeout_ms=5000, chunks=[{"chunk_id":"chunk-1","content_sha256":"a"*64,"text":"example"}])


def response():
    return EmbeddingResponse(task_id="task-1", provider_id="router-policy", model_id="selected-model", model_version="version-1", dimensions=2, vectors=[{"chunk_id":"chunk-1","content_sha256":"a"*64,"values":[0.1,0.2]}], trace_id="trace-1", completed_at=datetime.now(timezone.utc))


class FakeCanonicalRouter:
    def __init__(self, value):
        self.value = value
        self.calls = 0

    async def embed(self, payload):
        self.calls += 1
        return self.value


@pytest.mark.asyncio
async def test_missing_canonical_router_fails_closed():
    with pytest.raises(ModelRouterUnavailable):
        await route_embedding(None, request())


@pytest.mark.asyncio
async def test_router_response_with_matching_provenance_is_accepted():
    router = FakeCanonicalRouter(response())
    result = await route_embedding(router, request())
    assert result.model_id == "selected-model"
    assert router.calls == 1


@pytest.mark.asyncio
async def test_router_response_with_wrong_chunk_hash_is_rejected():
    invalid = response().model_copy(update={"vectors": [{"chunk_id":"chunk-1","content_sha256":"b"*64,"values":[0.1,0.2]}]})
    with pytest.raises(ModelRouterRejected) as error:
        await route_embedding(FakeCanonicalRouter(invalid), request())
    assert error.value.failure.code == "MODEL_ROUTER_RESPONSE_INVALID"
    assert error.value.failure.retryable is False

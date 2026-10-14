import asyncio
import hashlib
from datetime import datetime, timezone

import pytest

from allpha_api.embedding_contract import EmbeddingRequest, EmbeddingResponse
from allpha_api.knowledge_vector_store import (
    IdempotentKnowledgeVectorSink,
    VectorPersistenceConflict,
    build_vector_records,
)


def fixture_values():
    text = "private note"
    digest = hashlib.sha256(text.encode()).hexdigest()
    request = EmbeddingRequest(
        task_id="job-1:0", idempotency_key="knowledge:job-1:v1:batch0",
        trace_id="trace-1", owner_id="owner-a", agent_id="agent-a",
        source_id="source-a", source_version=1, sensitivity="internal",
        attempt=1, timeout_ms=5000,
        chunks=[{"chunk_id":"chunk-a","content_sha256":digest,"text":text}],
    )
    response = EmbeddingResponse(
        task_id=request.task_id, provider_id="selected-provider", model_id="selected-model",
        model_version="immutable-version", dimensions=2,
        vectors=[{"chunk_id":"chunk-a","content_sha256":digest,"values":[0.1,0.2]}],
        trace_id=request.trace_id, completed_at=datetime.now(timezone.utc),
    )
    job = {"id":"job-1","lease_token":"lease-a","owner_id":"owner-a","agent_id":"agent-a",
           "source_id":"source-a","source_version":1}
    return job, request, response


def test_vector_record_preserves_model_and_source_provenance_without_defaults():
    job, request, response = fixture_values()
    record = build_vector_records(job, request, response)[0]
    assert record.provider_id == "selected-provider"
    assert record.model_id == "selected-model"
    assert record.model_version == "immutable-version"
    assert record.dimensions == 2
    assert record.owner_id == "owner-a"
    assert record.source_version == 1
    assert record.content_sha256 == request.chunks[0].content_sha256


def test_vector_sink_rejects_job_identity_or_version_mismatch():
    job, request, response = fixture_values()
    job["owner_id"] = "owner-b"
    with pytest.raises(VectorPersistenceConflict):
        build_vector_records(job, request, response)


def test_vector_sink_requires_lease_fence():
    job, request, response = fixture_values()
    job["lease_token"] = ""
    with pytest.raises(VectorPersistenceConflict):
        build_vector_records(job, request, response)


def test_vector_sink_delegates_atomic_upsert_with_deterministic_idempotency_key():
    class Repo:
        def __init__(self): self.calls = []
        async def upsert_batch(self, records, *, expected_source_version, idempotency_key):
            self.calls.append((records, expected_source_version, idempotency_key))
    async def scenario():
        job, request, response = fixture_values()
        repo = Repo()
        await IdempotentKnowledgeVectorSink(repo)(job, request, response)
        await IdempotentKnowledgeVectorSink(repo)(job, request, response)
        assert len(repo.calls) == 2
        assert repo.calls[0][1] == 1
        assert repo.calls[0][2] == repo.calls[1][2]
        assert repo.calls[0][0] == repo.calls[1][0]
    asyncio.run(scenario())

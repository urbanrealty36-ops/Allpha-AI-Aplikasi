from __future__ import annotations

import asyncio

import pytest

from allpha_api.knowledge_worker_factory import build_worker
from allpha_api.knowledge_worker import WorkerConfigurationError


def test_knowledge_embedding_factory_fails_closed_without_vector_repository(monkeypatch):
    monkeypatch.delenv("ALLPHA_KNOWLEDGE_VECTOR_SINK_FACTORY", raising=False)

    async def scenario():
        with pytest.raises(WorkerConfigurationError, match="durable pgvector repository"):
            await build_worker()

    asyncio.run(scenario())


def test_knowledge_embedding_factory_rejects_invalid_vector_factory_reference():
    from allpha_api.knowledge_worker_factory import _load_factory

    with pytest.raises(WorkerConfigurationError, match="module:function"):
        _load_factory("not-a-module-path")



def test_embedding_factory_rejects_noncanonical_vector_sink():
    from allpha_api.knowledge_worker_factory import _require_canonical_vector_sink

    async def arbitrary_sink(*args, **kwargs):
        return None

    with pytest.raises(WorkerConfigurationError, match="canonical IdempotentKnowledgeVectorSink"):
        _require_canonical_vector_sink(arbitrary_sink)


def test_embedding_factory_accepts_only_canonical_idempotent_vector_repository():
    from allpha_api.knowledge_vector_store import IdempotentKnowledgeVectorSink
    from allpha_api.knowledge_worker_factory import _require_canonical_vector_sink

    class Repository:
        async def upsert_batch(self, records, *, expected_source_version, idempotency_key):
            return None

    sink = IdempotentKnowledgeVectorSink(Repository())
    assert _require_canonical_vector_sink(sink) is sink

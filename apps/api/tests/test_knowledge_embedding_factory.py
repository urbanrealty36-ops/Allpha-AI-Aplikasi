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

from __future__ import annotations

import asyncio

import pytest

from allpha_api import knowledge_ingestion_worker, knowledge_worker


def test_knowledge_document_consumer_is_disabled_by_default(monkeypatch):
    monkeypatch.delenv("ALLPHA_KNOWLEDGE_DOCUMENT_WORKER_ENABLED", raising=False)
    assert knowledge_ingestion_worker.enabled() is False


def test_knowledge_document_consumer_rejects_ambiguous_gate(monkeypatch):
    monkeypatch.setenv("ALLPHA_KNOWLEDGE_DOCUMENT_WORKER_ENABLED", "sometimes")
    with pytest.raises(SystemExit, match="must be true or false"):
        knowledge_ingestion_worker.enabled()


def test_knowledge_document_consumer_stops_cleanly_between_batches():
    async def scenario():
        stop = asyncio.Event()

        class Worker:
            def __init__(self):
                self.calls = 0

            async def process_once(self):
                self.calls += 1
                stop.set()
                return False

        worker = Worker()
        await knowledge_ingestion_worker.run_forever(
            worker, poll_seconds=30, stop_event=stop,
        )
        assert worker.calls == 1

    asyncio.run(scenario())



def test_knowledge_embedding_consumer_is_disabled_by_default(monkeypatch):
    monkeypatch.delenv("ALLPHA_KNOWLEDGE_EMBEDDING_WORKER_ENABLED", raising=False)
    assert knowledge_worker.enabled() is False


def test_knowledge_embedding_consumer_rejects_ambiguous_gate(monkeypatch):
    monkeypatch.setenv("ALLPHA_KNOWLEDGE_EMBEDDING_WORKER_ENABLED", "yes")
    with pytest.raises(SystemExit, match="must be true or false"):
        knowledge_worker.enabled()

from __future__ import annotations

import asyncio

import pytest

from allpha_api import agent_runtime_worker, knowledge_ingestion_worker, knowledge_worker


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



def test_invalid_optional_consumer_gate_does_not_abort_shared_host():
    assert agent_runtime_worker._consumer_enabled(
        "Knowledge embedding", lambda: (_ for _ in ()).throw(SystemExit("missing approved profile"))
    ) is False


def test_one_consumer_startup_failure_does_not_cancel_sibling_consumers():
    async def scenario():
        sibling_finished = asyncio.Event()

        async def failing_consumer():
            raise SystemExit("strict consumer configuration failure")

        async def healthy_consumer():
            sibling_finished.set()

        await asyncio.gather(
            agent_runtime_worker._serve_consumer_isolated("Knowledge embedding", failing_consumer()),
            agent_runtime_worker._serve_consumer_isolated("Workflow", healthy_consumer()),
        )
        assert sibling_finished.is_set()

    asyncio.run(scenario())

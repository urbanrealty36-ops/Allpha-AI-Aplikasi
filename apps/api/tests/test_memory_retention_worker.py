from __future__ import annotations

import asyncio
import pytest

from allpha_api.memory_retention_worker import MemoryRetentionWorker, run_forever, _enabled


def test_memory_retention_worker_is_disabled_by_default(monkeypatch):
    monkeypatch.delenv("ALLPHA_MEMORY_RETENTION_WORKER_ENABLED", raising=False)
    assert _enabled() is False


def test_memory_retention_worker_rejects_ambiguous_gate(monkeypatch):
    monkeypatch.setenv("ALLPHA_MEMORY_RETENTION_WORKER_ENABLED", "enabled")
    with pytest.raises(SystemExit, match="must be true or false"):
        _enabled()


def test_memory_retention_worker_processes_one_bounded_batch():
    class Store:
        def __init__(self):
            self.limits = []

        async def expire_due_batch(self, *, limit):
            self.limits.append(limit)
            return {"expired_count": 2}

    store = Store()
    worker = MemoryRetentionWorker(store, batch_size=7)
    assert asyncio.run(worker.process_once()) == 2
    assert store.limits == [7]


def test_memory_retention_worker_rejects_malformed_expiry_receipt():
    class Store:
        async def expire_due_batch(self, *, limit):
            return {"expired_count": limit + 1}

    with pytest.raises(Exception, match="invalid expiry count"):
        asyncio.run(MemoryRetentionWorker(Store(), batch_size=3).process_once())


def test_memory_retention_worker_stops_cleanly_between_polls():
    async def scenario():
        stop = asyncio.Event()

        class Worker:
            def __init__(self):
                self.calls = 0

            async def process_once(self):
                self.calls += 1
                stop.set()
                return 0

        worker = Worker()
        await run_forever(worker, poll_interval_seconds=10, stop_event=stop)
        assert worker.calls == 1

    asyncio.run(scenario())

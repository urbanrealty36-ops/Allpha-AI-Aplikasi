import asyncio

from allpha_api import social_graph_outbox_worker as worker


def test_social_graph_outbox_shared_consumer_requires_explicit_flag(monkeypatch):
    monkeypatch.delenv("ALLPHA_SOCIAL_GRAPH_OUTBOX_WORKER_ENABLED", raising=False)
    monkeypatch.delenv("ALLPHA_ACCOUNT_LIFECYCLE_WORKER_ENABLED", raising=False)
    assert worker.enabled() is False
    monkeypatch.setenv("ALLPHA_SOCIAL_GRAPH_OUTBOX_WORKER_ENABLED", "true")
    assert worker.enabled() is True


def test_shared_consumer_runs_outbox_and_account_lifecycle_until_shutdown(monkeypatch):
    monkeypatch.setenv("ALLPHA_SOCIAL_GRAPH_OUTBOX_WORKER_ENABLED", "true")
    monkeypatch.setenv("ALLPHA_ACCOUNT_LIFECYCLE_WORKER_ENABLED", "true")
    state = {"outbox_started": False, "account_started": False, "account_stopped": False}

    class FakeOutbox:
        async def run(self, stop_event=None):
            state["outbox_started"] = True
            await stop_event.wait()

    class FakeAccount:
        def __init__(self):
            self.stopping = False

        async def run(self):
            state["account_started"] = True
            while not self.stopping:
                await asyncio.sleep(0.001)
            state["account_stopped"] = True

    monkeypatch.setattr(worker, "OutboxWorker", FakeOutbox)
    monkeypatch.setattr(worker, "AccountLifecycleWorker", FakeAccount)

    async def scenario():
        stop_event = asyncio.Event()
        task = asyncio.create_task(worker.serve_enabled(stop_event=stop_event))
        await asyncio.sleep(0.01)
        assert state["outbox_started"] is True
        assert state["account_started"] is True
        stop_event.set()
        await task

    asyncio.run(scenario())
    assert state["account_stopped"] is True


def test_shared_consumer_can_run_social_outbox_without_account_worker(monkeypatch):
    monkeypatch.setenv("ALLPHA_SOCIAL_GRAPH_OUTBOX_WORKER_ENABLED", "true")
    monkeypatch.setenv("ALLPHA_ACCOUNT_LIFECYCLE_WORKER_ENABLED", "false")
    state = {"started": False}

    class FakeOutbox:
        async def run(self, stop_event=None):
            state["started"] = True
            await stop_event.wait()

    monkeypatch.setattr(worker, "OutboxWorker", FakeOutbox)

    async def scenario():
        stop_event = asyncio.Event()
        task = asyncio.create_task(worker.serve_enabled(stop_event=stop_event))
        await asyncio.sleep(0.01)
        stop_event.set()
        await task

    asyncio.run(scenario())
    assert state["started"] is True

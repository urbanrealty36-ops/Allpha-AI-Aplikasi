import asyncio

from allpha_api.main import app, app_lifespan


def test_account_lifecycle_worker_starts_and_stops_with_api_lifespan(monkeypatch):
    monkeypatch.setenv("ALLPHA_ACCOUNT_LIFECYCLE_WORKER_ENABLED", "true")

    class FakeWorker:
        def __init__(self):
            self.stopping = False
            self.started = asyncio.Event()
            self.closed = False

        async def run(self):
            self.started.set()
            try:
                await asyncio.Future()
            finally:
                self.closed = True

    worker = FakeWorker()

    class WorkerFactory:
        def __new__(cls):
            return worker

    monkeypatch.setattr("allpha_api.account_lifecycle_worker.AccountLifecycleWorker", WorkerFactory)

    async def exercise():
        async with app_lifespan(app):
            assert app.state.account_lifecycle_worker is worker
            await asyncio.wait_for(worker.started.wait(), timeout=1)
            assert not worker.stopping
        assert worker.stopping
        assert worker.closed
        assert app.state.account_lifecycle_worker is None

    asyncio.run(exercise())


def test_account_lifecycle_worker_remains_disabled_by_default(monkeypatch):
    monkeypatch.delenv("ALLPHA_ACCOUNT_LIFECYCLE_WORKER_ENABLED", raising=False)

    async def exercise():
        async with app_lifespan(app):
            assert app.state.account_lifecycle_worker is None

    asyncio.run(exercise())

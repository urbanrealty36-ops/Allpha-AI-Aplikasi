from __future__ import annotations

import asyncio

from allpha_api import content_worker_host


def test_content_media_host_is_disabled_when_all_consumers_are_disabled(monkeypatch):
    for name in (
        "ALLPHA_CONTENT_MEDIA_WORKER_ENABLED",
        "ALLPHA_CONTENT_TRANSCODE_WORKER_ENABLED",
        "ALLPHA_CONTENT_PROVIDER_CALLBACK_WORKER_ENABLED",
        "ALLPHA_CONTENT_PROVIDER_CLEANUP_WORKER_ENABLED",
    ):
        monkeypatch.setenv(name, "false")
    assert content_worker_host.enabled() is False


def test_content_media_host_processes_one_claimed_batch_and_stops(monkeypatch):
    stop = asyncio.Event()
    calls = []

    class FakeClient:
        async def aclose(self):
            calls.append("closed")

    class FakeWorker:
        def __init__(self):
            self.client = FakeClient()

        async def process_batch(self):
            calls.append("processed")
            stop.set()
            return 1

    monkeypatch.setattr(content_worker_host.content_media_worker, "enabled", lambda: True)
    monkeypatch.setattr(content_worker_host.content_media_worker, "MediaWorker", FakeWorker)
    monkeypatch.setattr(content_worker_host.content_transcode_worker, "enabled", lambda: False)
    monkeypatch.setattr(content_worker_host.content_provider_callback_worker, "enabled", lambda: False)
    monkeypatch.setattr(content_worker_host.content_provider_cleanup_worker, "enabled", lambda: False)

    asyncio.run(content_worker_host.serve_enabled(stop_event=stop))
    assert calls == ["processed", "closed"]


def test_content_media_host_isolates_invalid_consumer_configuration(monkeypatch):
    monkeypatch.setattr(
        content_worker_host.content_media_worker,
        "enabled",
        lambda: (_ for _ in ()).throw(SystemExit("missing scanner")),
    )
    monkeypatch.setattr(content_worker_host.content_transcode_worker, "enabled", lambda: False)
    monkeypatch.setattr(content_worker_host.content_provider_callback_worker, "enabled", lambda: False)
    monkeypatch.setattr(content_worker_host.content_provider_cleanup_worker, "enabled", lambda: False)
    assert content_worker_host.enabled() is False

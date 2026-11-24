from __future__ import annotations

import asyncio
from pathlib import Path

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


def test_shared_worker_image_excludes_memory_heavy_local_clamav():
    root = Path(__file__).resolve().parents[1]
    dockerfile = (root / "Dockerfile.agent-runtime-worker").read_text(encoding="utf-8")
    script = (root / "docker" / "shared-worker-entrypoint.sh").read_text(encoding="utf-8")
    assert "apt-get install -y --no-install-recommends gosu ca-certificates" in dockerfile
    assert "apt-get install -y --no-install-recommends clamav" not in dockerfile.lower()
    assert "freshclam" not in script
    assert "clamd --" not in script
    assert 'clamd)' in script
    assert "local ClamAV is not supported on the resource-constrained shared worker" in script
    assert "export ALLPHA_KNOWLEDGE_DOCUMENT_WORKER_ENABLED=false" in script


def test_dedicated_knowledge_worker_image_owns_local_clamav_scanning():
    root = Path(__file__).resolve().parents[1]
    dockerfile = (root / "Dockerfile.knowledge-ingestion-worker").read_text(encoding="utf-8")
    entrypoint = (root / "docker" / "knowledge-worker-entrypoint.sh").read_text(encoding="utf-8")
    assert "clamav clamav-daemon" in dockerfile
    assert "freshclam --quiet" in entrypoint
    assert "clamd --foreground=true" in entrypoint
    assert "clamdscan --ping=1" in entrypoint


def test_remote_scanner_configuration_requires_authenticated_allowlisted_endpoint():
    script = (
        Path(__file__).resolve().parents[1]
        / "docker" / "shared-worker-entrypoint.sh"
    ).read_text(encoding="utf-8")
    assert 'remote)' in script
    assert 'clamd)' in script
    assert 'SCANNER_API_KEY="${ALLPHA_DOCUMENT_SCANNER_API_KEY:-}"' in script
    assert 'SCANNER_ALLOWED_HOSTS="${ALLPHA_DOCUMENT_SCANNER_ALLOWED_HOSTS:-}"' in script
    assert "remote scanner URL, API key and exact hostname allowlist are all required" in script
    assert "RemoteDocumentScanner.from_environment()" in script


def test_shared_worker_keeps_other_consumers_alive_when_remote_scanner_is_missing():
    script = (
        Path(__file__).resolve().parents[1]
        / "docker" / "shared-worker-entrypoint.sh"
    ).read_text(encoding="utf-8")
    assert "disable_knowledge_documents" in script
    assert "export ALLPHA_KNOWLEDGE_DOCUMENT_WORKER_ENABLED=false" in script
    assert 'exec gosu worker "$@"' in script

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



def test_shared_worker_entrypoint_disables_only_knowledge_when_clamav_is_unavailable():
    script = (
        Path(__file__).resolve().parents[1]
        / "docker" / "shared-worker-entrypoint.sh"
    ).read_text(encoding="utf-8")
    start = script.index('if [ "$READY" -ne 1 ]')
    end = script.index("    fi", start) + len("    fi")
    failure_branch = script[start:end]
    assert "only the Knowledge document consumer will be disabled" in failure_branch
    assert "return 1" in failure_branch
    assert "exit 1" not in failure_branch
    assert "elif ! start_local_clamav; then" in script
    assert "export ALLPHA_KNOWLEDGE_DOCUMENT_WORKER_ENABLED=false" in script



def test_clamav_worker_limits_concurrency_without_disabling_signature_scanning():
    script = (
        Path(__file__).resolve().parents[1]
        / "docker" / "shared-worker-entrypoint.sh"
    ).read_text(encoding="utf-8")
    for setting in (
        "MaxFileSize 10M",
        "MaxScanSize 20M",
        "StreamMaxLength 20M",
        "MaxThreads 1",
        "MaxConnectionQueueLength 4",
        "MaxQueue 8",
        "ConcurrentDatabaseReload no",
    ):
        assert setting in script
    assert "Bytecode no" not in script
    assert "ScanArchive no" not in script



def test_clamav_scanner_uses_permissioned_unix_socket_for_readiness():
    script = (
        Path(__file__).resolve().parents[1]
        / "docker" / "shared-worker-entrypoint.sh"
    ).read_text(encoding="utf-8")
    assert "LocalSocket /run/clamav/clamd.ctl" in script
    assert "LocalSocketGroup clamav" in script
    assert "LocalSocketMode 660" in script
    assert "--config-file=/run/clamav/clamdscan.conf --ping=1" in script
    assert "TCPSocket 3310" not in script



def test_knowledge_document_scanner_uses_same_socket_config_as_readiness_probe():
    source = (
        Path(__file__).resolve().parents[1]
        / "src" / "allpha_api" / "knowledge.py"
    ).read_text(encoding="utf-8")
    entrypoint = (
        Path(__file__).resolve().parents[1]
        / "docker" / "shared-worker-entrypoint.sh"
    ).read_text(encoding="utf-8")
    assert '"clamdscan","--config-file=/run/clamav/clamdscan.conf","--no-summary"' in source
    assert "--config-file=/run/clamav/clamdscan.conf --ping=1" in entrypoint
    assert "timeout 3s gosu worker clamdscan" in entrypoint
    assert "seq 1 30" in entrypoint
    assert '"--fdpass"' not in source



def test_shared_worker_does_not_start_memory_heavy_clamav_without_explicit_resource_gate():
    script = (
        Path(__file__).resolve().parents[1]
        / "docker" / "shared-worker-entrypoint.sh"
    ).read_text(encoding="utf-8")
    assert "ALLPHA_CLAMAV_ENABLED:-false" in script
    assert 'clamd)' in script
    assert 'if [ "$CLAMAV_ENABLED" != "true" ]; then' in script
    assert "remote scanner URL, API key and exact hostname allowlist are all required" in script
    assert "export ALLPHA_KNOWLEDGE_DOCUMENT_WORKER_ENABLED=false" in script


def test_remote_scanner_configuration_skips_local_clamav_bootstrap():
    script = (
        Path(__file__).resolve().parents[1]
        / "docker" / "shared-worker-entrypoint.sh"
    ).read_text(encoding="utf-8")
    assert 'remote)' in script
    assert 'clamd)' in script
    assert 'SCANNER_API_KEY="${ALLPHA_DOCUMENT_SCANNER_API_KEY:-}"' in script
    assert 'SCANNER_ALLOWED_HOSTS="${ALLPHA_DOCUMENT_SCANNER_ALLOWED_HOSTS:-}"' in script
    assert 'remote scanner URL, API key and exact hostname allowlist are all required' in script
    assert "RemoteDocumentScanner.from_environment()" in script



def test_shared_worker_scanner_startup_failure_isolated_from_other_consumers():
    script = (
        Path(__file__).resolve().parents[1]
        / "docker" / "shared-worker-entrypoint.sh"
    ).read_text(encoding="utf-8")
    assert "timeout 60s freshclam --quiet || return 1" in script
    assert "elif ! start_local_clamav; then" in script
    assert "only the Knowledge document consumer will be disabled" in script
    assert "other shared consumers will continue" in script

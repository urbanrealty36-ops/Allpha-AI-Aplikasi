from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from allpha_api import agent_runtime_worker, knowledge_ingestion_worker, knowledge_worker
from knowledge_worker_fakes import FakePolicyResolver


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
    assert 'SCANNER_ID="${ALLPHA_DOCUMENT_SCANNER_ID:-}"' in script
    assert 'SCANNER_ENGINE_VERSION="${ALLPHA_DOCUMENT_SCANNER_ENGINE_VERSION:-}"' in script
    assert 'SCANNER_SIGNATURE_VERSION="${ALLPHA_DOCUMENT_SCANNER_SIGNATURE_VERSION:-}"' in script
    assert "remote scanner URL, API key, exact hostname allowlist and pinned scanner identity are all required" in script
    assert "RemoteDocumentScanner.from_environment()" in script


def test_shared_worker_keeps_other_consumers_alive_when_remote_scanner_is_missing():
    script = (
        Path(__file__).resolve().parents[1]
        / "docker" / "shared-worker-entrypoint.sh"
    ).read_text(encoding="utf-8")
    assert "disable_knowledge_documents" in script
    assert "export ALLPHA_KNOWLEDGE_DOCUMENT_WORKER_ENABLED=false" in script
    assert 'exec gosu worker "$@"' in script


def _base_env(monkeypatch):
    monkeypatch.setattr("allpha_api.knowledge_ingestion_worker.load_policy_resolver_from_environment", lambda: FakePolicyResolver())
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service")
    for name in ("URL", "API_KEY", "ALLOWED_HOSTS", "ID", "ENGINE_VERSION", "SIGNATURE_VERSION", "MODE"):
        monkeypatch.delenv(f"ALLPHA_DOCUMENT_SCANNER_{name}", raising=False)


@pytest.mark.parametrize("url,key,hosts", [
    ("https://scanner.example.com/scan", "", "scanner.example.com"),
    ("https://scanner.example.com/scan", "k", ""),
    ("http://scanner.example.com/scan", "k", "scanner.example.com"),
    ("https://10.0.0.1/scan", "k", "10.0.0.1"),
    ("https://scanner.example.com/scan", "k", "other.example.com"),
])
def test_document_consumer_refuses_to_start_on_invalid_remote_scanner_config(monkeypatch, url, key, hosts):
    _base_env(monkeypatch)
    monkeypatch.setenv("ALLPHA_DOCUMENT_SCANNER_URL", url)
    monkeypatch.setenv("ALLPHA_DOCUMENT_SCANNER_API_KEY", key)
    monkeypatch.setenv("ALLPHA_DOCUMENT_SCANNER_ALLOWED_HOSTS", hosts)
    with pytest.raises(SystemExit, match="disabled"):
        knowledge_ingestion_worker.build_worker_from_environment()


def test_document_consumer_refuses_to_start_without_any_scanner(monkeypatch):
    _base_env(monkeypatch)
    with pytest.raises(SystemExit, match="disabled"):
        knowledge_ingestion_worker.build_worker_from_environment()


def test_document_consumer_starts_with_valid_remote_scanner_config(monkeypatch):
    _base_env(monkeypatch)
    monkeypatch.setenv("ALLPHA_DOCUMENT_SCANNER_URL", "https://scanner.example.com/scan")
    monkeypatch.setenv("ALLPHA_DOCUMENT_SCANNER_API_KEY", "k")
    monkeypatch.setenv("ALLPHA_DOCUMENT_SCANNER_ALLOWED_HOSTS", "scanner.example.com")
    monkeypatch.setenv("ALLPHA_DOCUMENT_SCANNER_ID", "scanner-prod-1")
    monkeypatch.setenv("ALLPHA_DOCUMENT_SCANNER_ENGINE_VERSION", "engine-1.4.6")
    monkeypatch.setenv("ALLPHA_DOCUMENT_SCANNER_SIGNATURE_VERSION", "2026-11-24T00:00:00Z")
    assert knowledge_ingestion_worker.build_worker_from_environment().batch_size == 50



def test_document_consumer_refuses_to_start_without_canonical_policy_provider(monkeypatch):
    _base_env(monkeypatch)
    monkeypatch.setattr("allpha_api.knowledge_ingestion_worker.load_policy_resolver_from_environment", lambda: None)
    monkeypatch.setenv("ALLPHA_DOCUMENT_SCANNER_URL", "https://scanner.example.com/scan")
    monkeypatch.setenv("ALLPHA_DOCUMENT_SCANNER_API_KEY", "k")
    monkeypatch.setenv("ALLPHA_DOCUMENT_SCANNER_ALLOWED_HOSTS", "scanner.example.com")
    monkeypatch.setenv("ALLPHA_DOCUMENT_SCANNER_ID", "scanner-prod-1")
    monkeypatch.setenv("ALLPHA_DOCUMENT_SCANNER_ENGINE_VERSION", "engine-1.4.6")
    monkeypatch.setenv("ALLPHA_DOCUMENT_SCANNER_SIGNATURE_VERSION", "2026-11-24T00:00:00Z")
    with pytest.raises(SystemExit, match="canonical Knowledge consent/source-grant provider"):
        knowledge_ingestion_worker.build_worker_from_environment()


def test_invalid_scanner_config_failure_does_not_starve_runtime_consumers(monkeypatch):
    _base_env(monkeypatch)
    monkeypatch.setenv("ALLPHA_DOCUMENT_SCANNER_URL", "http://scanner.example.com/scan")
    assert agent_runtime_worker._consumer_enabled(
        "Knowledge document", lambda: knowledge_ingestion_worker.build_worker_from_environment() and True
    ) is False

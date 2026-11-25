import hashlib

import pytest

from allpha_api.generation_job_worker import _build_memory_context_evidence, _database


def test_generation_memory_evidence_preserves_full_and_bounded_excerpt_digests():
    full = "M" * 7000
    excerpt = full[:3000]
    item = {
        "id": "memory-1",
        "content": excerpt,
        "content_sha256": hashlib.sha256(full.encode()).hexdigest(),
        "retrieved_content_sha256": hashlib.sha256(excerpt.encode()).hexdigest(),
        "memory_type": "long_term",
        "version": 4,
        "policy_version": 2,
        "classification": "internal",
        "retrieval_method": "keyword",
        "retrieval_score": 0.9,
    }

    context, evidence = _build_memory_context_evidence([item], "owner preferences")

    assert excerpt in context
    assert evidence["items"][0]["content_sha256"] == hashlib.sha256(full.encode()).hexdigest()
    assert evidence["items"][0]["retrieved_text_sha256"] == hashlib.sha256(excerpt.encode()).hexdigest()
    assert evidence["items"][0]["content_sha256"] != evidence["items"][0]["retrieved_text_sha256"]


def test_generation_memory_evidence_rejects_modified_excerpt():
    excerpt = "retrieved excerpt"
    item = {
        "id": "memory-1",
        "content": excerpt,
        "content_sha256": "a" * 64,
        "retrieved_content_sha256": "b" * 64,
        "memory_type": "long_term",
        "version": 4,
        "policy_version": 2,
        "classification": "internal",
    }

    with pytest.raises(ValueError, match="memory_context_item_integrity_invalid"):
        _build_memory_context_evidence([item], "query")

def test_generation_worker_resolves_secret_key_and_hardens_every_http_client(monkeypatch):
    import ast
    from pathlib import Path

    monkeypatch.setenv("SUPABASE_URL", "https://project.supabase.co")
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "canonical-server-secret")
    assert _database() == ("https://project.supabase.co", "canonical-server-secret")

    source_path = (
        Path(__file__).resolve().parents[1]
        / "src" / "allpha_api" / "generation_job_worker.py"
    )
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    clients = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "AsyncClient"
    ]
    assert clients
    for client in clients:
        options = {keyword.arg: keyword.value for keyword in client.keywords}
        assert isinstance(options.get("trust_env"), ast.Constant)
        assert options["trust_env"].value is False
        assert isinstance(options.get("follow_redirects"), ast.Constant)
        assert options["follow_redirects"].value is False

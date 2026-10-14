from pathlib import Path
import uuid
import pytest
from fastapi import Request
from fastapi.testclient import TestClient
from allpha_api.auth import current_user
from allpha_api.main import app
from allpha_api.knowledge import _chunk, _extract, _scan

client = TestClient(app)
AGENT = "00000000-0000-0000-0000-000000000101"
SOURCE = "00000000-0000-0000-0000-000000000102"

def auth_as(user_id="owner-a"):
    async def fake_current_user(request: Request):
        request.state.supabase_access_token = f"token-{user_id}"
        return {"id": user_id, "email": f"{user_id}@example.invalid"}
    return fake_current_user

def test_knowledge_routes_require_authentication():
    assert client.get(f"/v1/agents/{AGENT}/knowledge/sources").status_code == 401
    assert client.post(f"/v1/agents/{AGENT}/knowledge/sources/{SOURCE}/process").status_code == 401
    assert client.delete(f"/v1/agents/{AGENT}/knowledge/sources/{SOURCE}").status_code == 401

def test_chunk_preserves_source_location_and_bounded_chunks():
    chunks = _chunk([{"location": {"kind": "page", "index": 4}, "text": "x" * 4000}])
    assert len(chunks) == 3
    assert [len(item["content"]) for item in chunks] == [1800, 1800, 400]
    assert chunks[1]["source_location"] == {"kind": "page", "index": 4, "offset": 1800}

def test_text_extract_requires_utf8():
    assert _extract("notes.txt", b"hello")[0]["text"] == "hello"
    with pytest.raises(ValueError, match="INVALID_TEXT_ENCODING"):
        _extract("notes.txt", b"\xff")

def test_scanner_fails_closed_when_unconfigured(monkeypatch):
    monkeypatch.delenv("ALLPHA_DOCUMENT_SCANNER_URL", raising=False)
    import asyncio
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as error:
        asyncio.run(_scan(b"private", "a.txt", "text/plain"))
    assert error.value.status_code == 503
    assert error.value.detail["code"] == "SCANNER_NOT_CONFIGURED"

def test_foreign_agent_sources_are_hidden(monkeypatch):
    calls = []
    async def fake_db(method, path, token, **kwargs):
        calls.append((method, path))
        return []
    monkeypatch.setattr("allpha_api.knowledge.user_db_request", fake_db)
    app.dependency_overrides[current_user] = auth_as("owner-b")
    try:
        response = client.get(f"/v1/agents/{AGENT}/knowledge/sources", headers={"Authorization": "Bearer test"})
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 404
    assert calls == [("GET", "agent_ownerships")]

def test_eng_p07_migration_has_private_storage_and_owner_rls():
    migration = Path(__file__).parents[1] / "supabase" / "migrations" / "20261014170000_eng_p07_knowledge_ingestion.sql"
    sql = migration.read_text(encoding="utf-8").lower()
    assert "create table if not exists public.agent_knowledge_sources" in sql
    assert "create table if not exists public.agent_knowledge_jobs" in sql
    assert "create table if not exists public.agent_knowledge_chunks" in sql
    assert "enable row level security" in sql
    assert "agent_knowledge_storage_owner_select" in sql
    assert "public=false" in sql
    assert "sha256" in sql and "source_location" in sql
    assert "references public.ai_agents(id) on delete cascade" in sql

def test_eng_p07_full_text_index_and_embedding_handoff_contract():
    migrations = Path(__file__).parents[1] / "supabase" / "migrations"
    fulltext = (migrations / "20261014173000_eng_p07_knowledge_fulltext_index.sql").read_text(encoding="utf-8").lower()
    api = (Path(__file__).parents[1] / "src" / "allpha_api" / "knowledge.py").read_text(encoding="utf-8")
    assert "generated always as (to_tsvector" in fulltext
    assert "using gin(search_vector)" in fulltext
    assert '"stage":"embedding_indexing"' in api
    assert '"status":"queued"' in api
    assert '"retrieval_ready":false' in api
    assert "ENG-P09 Model Router worker" in api

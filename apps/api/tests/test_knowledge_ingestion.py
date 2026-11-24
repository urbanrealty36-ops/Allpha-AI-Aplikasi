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
    from fastapi import HTTPException

    assert _extract("notes.txt", b"hello")[0]["text"] == "hello"
    with pytest.raises(HTTPException) as error:
        _extract("notes.txt", b"\xff")
    assert error.value.status_code == 422
    assert error.value.detail["code"] == "DOCUMENT_PARSE_FAILED"

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
    worker = (Path(__file__).parents[1] / "src" / "allpha_api" / "knowledge_worker.py").read_text(encoding="utf-8")
    pipeline = (Path(__file__).parents[1] / "supabase" / "migrations" / "20261124110000_eng_p07_knowledge_document_worker_pipeline.sql").read_text(encoding="utf-8")
    assert "generated always as (to_tsvector" in fulltext
    assert "using gin(search_vector)" in fulltext
    assert "rpc/enqueue_agent_knowledge_document_job" in api
    assert '"retrieval_ready":False' in api
    assert "complete_agent_knowledge_document_parse" in worker
    assert "'embedding_indexing'" in pipeline

def test_knowledge_mutations_are_api_only_and_storage_paths_are_scoped():
    migration = Path(__file__).parents[1] / "supabase" / "migrations" / "20261014170000_eng_p07_knowledge_ingestion.sql"
    sql = migration.read_text(encoding="utf-8").lower()
    api = (Path(__file__).parents[1] / "src" / "allpha_api" / "knowledge.py").read_text(encoding="utf-8")
    assert "grant select on public.agent_knowledge_sources,public.agent_knowledge_jobs,public.agent_knowledge_chunks to authenticated" in sql
    assert "s.storage_path=storage.objects.name and s.status='quarantined'" in sql
    lockdown = (Path(__file__).parents[1] / "supabase" / "migrations" / "20261124120000_eng_p07_knowledge_api_only_writes.sql").read_text(encoding="utf-8").lower()
    assert "revoke insert,update,delete on public.agent_knowledge_sources,public.agent_knowledge_jobs,public.agent_knowledge_chunks" in lockdown
    assert "drop policy if exists agent_knowledge_storage_owner_insert" in lockdown
    assert "SUPABASE_SERVICE_ROLE_KEY" in api
    assert "_admin_db_request" in api
    assert "urllib.parse import quote" in api


def test_document_processing_is_queued_through_service_rpc(monkeypatch):
    from allpha_api.knowledge import process_source
    calls=[]
    async def fake_owned(agent_id, request, user):
        return "owner-token"
    async def fake_source(agent_id, source_id, token, user):
        return {"id":str(source_id),"agent_id":str(agent_id),"owner_id":user["id"],
                "status":"quarantined","source_version":1,
                "sensitivity":"internal","provenance":{"sensitivity":"internal"}}
    async def fake_admin(method,path,access_token=None,**kwargs):
        calls.append((method,path,kwargs))
        return {"id":"job-1","status":"queued","stage":"awaiting_malware_scan","attempt":0,"progress":0}
    async def forbidden_scan(*args,**kwargs):
        raise AssertionError("HTTP request must only enqueue; scanner/parser execute in worker")
    monkeypatch.setattr("allpha_api.knowledge._owned",fake_owned)
    monkeypatch.setattr("allpha_api.knowledge._source",fake_source)
    monkeypatch.setattr("allpha_api.knowledge._admin_db_request",fake_admin)
    monkeypatch.setattr("allpha_api.knowledge._scan",forbidden_scan)
    app.dependency_overrides[current_user]=auth_as("owner-a")
    try:
        response=client.post(f"/v1/agents/{AGENT}/knowledge/sources/{SOURCE}/process",headers={"Authorization":"Bearer test"})
    finally:
        app.dependency_overrides.clear()
    assert response.status_code==202
    assert response.json()["status"]=="queued"
    assert response.json()["job"]["id"]=="job-1"
    assert calls[0][0:2]==("POST","rpc/enqueue_agent_knowledge_document_job")
    assert calls[0][2]["body"]=={"p_source_id":SOURCE,"p_agent_id":AGENT,"p_owner_id":"owner-a","p_reason":None}


def test_knowledge_storage_requires_server_side_key(monkeypatch):
    from fastapi import HTTPException
    from allpha_api.knowledge import _storage_config
    monkeypatch.setenv("SUPABASE_URL","https://example.supabase.co")
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY",raising=False)
    monkeypatch.delenv("SUPABASE_SECRET_KEY",raising=False)
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY","public-key")
    with pytest.raises(HTTPException) as error:
        _storage_config()
    assert error.value.status_code==503
    assert error.value.detail["code"]=="STORAGE_NOT_CONFIGURED"

from pathlib import Path
import uuid
import pytest
from fastapi import Request
from fastapi.testclient import TestClient
from allpha_api.auth import current_user
from allpha_api.main import app
from allpha_api.knowledge import _chunk, _extract, _scan
from allpha_api import knowledge

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
    pipeline = (Path(__file__).parents[1] / "supabase" / "migrations" / "20261124044949_eng_p07_knowledge_document_worker_pipeline.sql").read_text(encoding="utf-8")
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
    lockdown = (Path(__file__).parents[1] / "supabase" / "migrations" / "20261124045041_eng_p07_knowledge_api_only_writes.sql").read_text(encoding="utf-8").lower()
    assert "revoke insert,update,delete on public.agent_knowledge_sources,public.agent_knowledge_jobs,public.agent_knowledge_chunks" in lockdown
    assert "drop policy if exists agent_knowledge_storage_owner_insert" in lockdown
    assert "SUPABASE_SERVICE_ROLE_KEY" in api
    assert "_admin_db_request" in api
    assert "urllib.parse import quote" in api



async def _allow_processing():
    return None

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
    monkeypatch.setattr("allpha_api.knowledge._authorize_source_processing",lambda **kwargs: _allow_processing())
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



def test_document_processing_does_not_enqueue_without_authoritative_policy_provider(monkeypatch):
    calls=[]
    async def fake_owned(agent_id, request, user): return "owner-token"
    async def fake_source(agent_id, source_id, token, user):
        return {"id":str(source_id),"agent_id":str(agent_id),"owner_id":user["id"],"status":"quarantined","source_version":1,"sensitivity":"internal","provenance":{"sensitivity":"internal"}}
    async def fake_admin(method,path,access_token=None,**kwargs):
        calls.append((method,path)); return {"id":"must-not-enqueue"}
    monkeypatch.setattr("allpha_api.knowledge._owned",fake_owned)
    monkeypatch.setattr("allpha_api.knowledge._source",fake_source)
    monkeypatch.setattr("allpha_api.knowledge._admin_db_request",fake_admin)
    monkeypatch.setattr("allpha_api.knowledge.load_policy_resolver_from_environment",lambda:None)
    app.dependency_overrides[current_user]=auth_as("owner-a")
    try: response=client.post(f"/v1/agents/{AGENT}/knowledge/sources/{SOURCE}/process",headers={"Authorization":"Bearer test"})
    finally: app.dependency_overrides.clear()
    assert response.status_code==503
    assert response.json()["error"]["code"]=="KNOWLEDGE_POLICY_UNAVAILABLE"
    assert calls==[]

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


def test_delete_source_fences_jobs_before_idempotent_storage_and_database_cleanup(monkeypatch):
    from allpha_api.knowledge import delete_source
    calls=[]
    async def fake_owned(agent_id,request,user):
        return "owner-token"
    async def fake_admin(method,path,access_token=None,**kwargs):
        calls.append(("db",method,path,kwargs))
        if path=="rpc/begin_agent_knowledge_source_delete":
            return {"already_deleted":False,"storage_path":f"owner-a/{AGENT}/{SOURCE}/notes.txt","cancelled_jobs":2}
        return None
    async def fake_storage(method,path,*args,**kwargs):
        calls.append(("storage",method,path))
        return None
    monkeypatch.setattr("allpha_api.knowledge._owned",fake_owned)
    monkeypatch.setattr("allpha_api.knowledge._admin_db_request",fake_admin)
    monkeypatch.setattr("allpha_api.knowledge._storage",fake_storage)
    app.dependency_overrides[current_user]=auth_as("owner-a")
    try:
        response=client.delete(f"/v1/agents/{AGENT}/knowledge/sources/{SOURCE}",headers={"Authorization":"Bearer test"})
    finally:
        app.dependency_overrides.clear()
    assert response.status_code==204
    assert calls[0][0:3]==("db","POST","rpc/begin_agent_knowledge_source_delete")
    assert calls[0][3]["body"]=={"p_source_id":SOURCE,"p_agent_id":AGENT,"p_owner_id":"owner-a"}
    assert calls[1]==("storage","DELETE",f"agent-knowledge/owner-a/{AGENT}/{SOURCE}/notes.txt")
    assert calls[2][0:3]==("db","DELETE","agent_knowledge_sources")
    assert calls[2][3]["params"]["status"]=="eq.deleting"


def test_delete_source_returns_success_when_source_is_already_deleted(monkeypatch):
    from allpha_api.knowledge import delete_source
    calls=[]
    async def fake_owned(agent_id,request,user):
        return "owner-token"
    async def fake_admin(method,path,access_token=None,**kwargs):
        calls.append((method,path))
        return {"already_deleted":True}
    async def forbidden_storage(*args,**kwargs):
        raise AssertionError("Storage must not be touched for an already-deleted source")
    monkeypatch.setattr("allpha_api.knowledge._owned",fake_owned)
    monkeypatch.setattr("allpha_api.knowledge._admin_db_request",fake_admin)
    monkeypatch.setattr("allpha_api.knowledge._storage",forbidden_storage)
    app.dependency_overrides[current_user]=auth_as("owner-a")
    try:
        response=client.delete(f"/v1/agents/{AGENT}/knowledge/sources/{SOURCE}",headers={"Authorization":"Bearer test"})
    finally:
        app.dependency_overrides.clear()
    assert response.status_code==204
    assert calls==[("POST","rpc/begin_agent_knowledge_source_delete")]


def test_clamd_scanner_accepts_only_clean_local_verdicts(monkeypatch):
    import asyncio
    from allpha_api.knowledge import _scan
    monkeypatch.delenv("ALLPHA_DOCUMENT_SCANNER_URL",raising=False)
    monkeypatch.setenv("ALLPHA_DOCUMENT_SCANNER_MODE","clamd")
    calls=[]
    class Process:
        returncode=0
        def __init__(self, output):
            self.output = output
        async def communicate(self):
            return self.output,b""
    async def fake_exec(*args,**kwargs):
        calls.append(args)
        assert args[0]=="clamdscan"
        assert "--fdpass" not in args
        if "--version" in args:
            return Process(b"ClamAV 1.4.6/123/2026-11-24")
        assert "--no-summary" in args
        with open(args[-1],"rb") as source:
            assert source.read()==b"private document"
        return Process(b"allpha-knowledge.txt: OK")
    monkeypatch.setattr("allpha_api.knowledge.asyncio.create_subprocess_exec",fake_exec)
    asyncio.run(_scan(b"private document","notes.txt","text/plain"))
    assert len(calls)==2


def test_clamd_scanner_rejects_infected_document(monkeypatch):
    import asyncio
    from fastapi import HTTPException
    from allpha_api.knowledge import _scan
    monkeypatch.delenv("ALLPHA_DOCUMENT_SCANNER_URL",raising=False)
    monkeypatch.setenv("ALLPHA_DOCUMENT_SCANNER_MODE","clamd")
    class Process:
        returncode=1
        async def communicate(self):
            return b"notes.txt: Eicar-Test-Signature FOUND",b""
    async def fake_exec(*args,**kwargs):
        return Process()
    monkeypatch.setattr("allpha_api.knowledge.asyncio.create_subprocess_exec",fake_exec)
    with pytest.raises(HTTPException) as error:
        asyncio.run(_scan(b"infected","notes.txt","text/plain"))
    assert error.value.status_code==422
    assert error.value.detail["code"]=="MALWARE_SCAN_REJECTED"


def test_clamd_scanner_fails_closed_when_daemon_unavailable(monkeypatch):
    import asyncio
    from fastapi import HTTPException
    from allpha_api.knowledge import _scan
    monkeypatch.delenv("ALLPHA_DOCUMENT_SCANNER_URL",raising=False)
    monkeypatch.setenv("ALLPHA_DOCUMENT_SCANNER_MODE","clamd")
    class Process:
        returncode=2
        async def communicate(self):
            return b"",b"Could not connect to clamd"
    async def fake_exec(*args,**kwargs):
        return Process()
    monkeypatch.setattr("allpha_api.knowledge.asyncio.create_subprocess_exec",fake_exec)
    with pytest.raises(HTTPException) as error:
        asyncio.run(_scan(b"private","notes.txt","text/plain"))
    assert error.value.status_code==503
    assert error.value.detail["code"]=="SCANNER_UNAVAILABLE"


def test_public_source_projection_hides_storage_path_and_internal_provenance():
    source = {
        "id": "s", "filename": "a.txt", "sha256": "a" * 64, "status": "processing",
        "storage_path": "owner/agent/source/a.txt",
        "provenance": {
            "kind": "user_upload", "sensitivity": "internal", "sensitivity_set_by": "owner-id",
            "internal_note": "x",
            "malware_scan": {"scanner_id": "sc", "engine_version": "1", "signature_version": "2",
                             "sha256": "a" * 64, "contract_version": "c", "receipt_id": "r", "raw": "secret"},
        },
    }
    public = knowledge._public_source(source)
    assert "storage_path" not in public
    assert public["provenance"] == {
        "kind": "user_upload", "sensitivity": "internal",
        "malware_scan": {"scanner_id": "sc", "engine_version": "1", "signature_version": "2",
                         "sha256": "a" * 64, "contract_version": "c", "receipt_id": "r"},
    }
    assert knowledge._public_source({"id": "s", "provenance": None})["provenance"] == {}


def test_public_job_projection_drops_lease_fields():
    job = {"id": "j", "status": "queued", "stage": "awaiting_malware_scan", "lease_token": "t", "locked_by": "w", "attempt": 1}
    assert knowledge._public_job(job) == {"id": "j", "status": "queued", "stage": "awaiting_malware_scan", "attempt": 1}
    assert knowledge._public_job(None) is None

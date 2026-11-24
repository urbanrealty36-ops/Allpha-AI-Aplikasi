import pytest
from pydantic import ValidationError
from fastapi import Request
from fastapi.testclient import TestClient

from allpha_api.auth import current_user
from allpha_api.main import AgentCreate, AgentUpdate, app

client = TestClient(app)


def test_agent_routes_require_authentication():
    assert client.get("/v1/agents").status_code == 401
    assert client.post("/v1/agents", json={"handle": "helper_01", "display_name": "Helper"}).status_code == 401
    assert client.patch("/v1/agents/00000000-0000-0000-0000-000000000001", json={"status": "active"}).status_code == 401


def test_http_errors_use_stable_envelope_and_request_id():
    response = client.get("/v1/agents")
    body = response.json()
    assert response.status_code == 401
    assert body["error"]["code"] == "AUTH_REQUIRED"
    assert body["error"]["message"] == "Bearer token diperlukan."
    assert body["error"]["request_id"]
    assert response.headers["x-request-id"] == body["error"]["request_id"]


def test_agent_request_validation_uses_safe_stable_error_envelope():
    async def fake_current_user(request: Request):
        request.state.supabase_access_token = "human-session-token"
        return {"id": "human-123", "email": "human@example.invalid"}

    app.dependency_overrides[current_user] = fake_current_user
    try:
        response = client.patch(
            "/v1/agents/00000000-0000-0000-0000-000000000001",
            headers={"Authorization": "Bearer test"},
            json={"display_name": "A"},
        )
    finally:
        app.dependency_overrides.clear()

    body = response.json()
    assert response.status_code == 422
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["message"] == "Permintaan tidak valid."
    assert body["error"]["request_id"] == response.headers["x-request-id"]
    assert body["error"]["fields"]
    assert "input" not in body["error"]


def test_agent_identity_is_not_a_human_profile_payload():
    with pytest.raises(ValidationError):
        AgentCreate.model_validate({"handle": "agent_01", "display_name": "Agent One", "owner_user_id": "spoofed"})
    with pytest.raises(ValidationError):
        AgentCreate.model_validate({"handle": "Agent One", "display_name": "Agent One"})
    with pytest.raises(ValidationError):
        AgentCreate.model_validate({"handle": "agent_01", "display_name": "A"})


def test_agent_payload_validates_visibility_persona_and_status():
    value = AgentCreate.model_validate({
        "handle": "research_bot",
        "display_name": "Research Bot",
        "description": "Research assistant",
        "persona": {"tone": "concise"},
        "disclosure": "AI generated responses",
        "boundaries": {"private_owner_data": "owner_only"},
        "visibility": "private",
    })
    assert value.persona == {"tone": "concise"}
    assert value.disclosure == "AI generated responses"
    assert value.boundaries == {"private_owner_data": "owner_only"}
    assert value.visibility == "private"
    with pytest.raises(ValidationError):
        AgentCreate.model_validate({"handle": "research_bot", "display_name": "Research Bot", "persona": ["not", "an", "object"]})
    with pytest.raises(ValidationError):
        AgentCreate.model_validate({"handle": "research_bot", "display_name": "Research Bot", "visibility": "secret"})
    with pytest.raises(ValidationError):
        AgentCreate.model_validate({"handle": "research_bot", "display_name": "Research Bot", "boundaries": ["not", "an", "object"]})


def test_agent_configuration_rejects_oversized_json():
    with pytest.raises(ValidationError):
        AgentCreate.model_validate({
            "handle": "research_bot",
            "display_name": "Research Bot",
            "persona": {"prompt": "x" * (16 * 1024)},
        })


def test_agent_configuration_rejects_excessive_nesting():
    deeply_nested = {}
    cursor = deeply_nested
    for _ in range(8):
        cursor["level"] = {}
        cursor = cursor["level"]
    cursor["too_deep"] = True
    with pytest.raises(ValidationError):
        AgentCreate.model_validate({
            "handle": "research_bot",
            "display_name": "Research Bot",
            "boundaries": deeply_nested,
        })


def test_agent_update_configuration_has_same_size_limits():
    with pytest.raises(ValidationError):
        AgentUpdate.model_validate({"boundaries": {"prompt": "x" * (16 * 1024)}})


def test_agent_update_rejects_ownership_and_authority_fields():
    with pytest.raises(ValidationError):
        AgentUpdate.model_validate({"owner_user_id": "another-human"})
    with pytest.raises(ValidationError):
        AgentUpdate.model_validate({"created_by": "another-human"})
    with pytest.raises(ValidationError):
        AgentUpdate.model_validate({"status": "published"})


def test_agent_update_accepts_bounded_profile_fields():
    value = AgentUpdate.model_validate({"display_name": "Research Agent", "visibility": "public", "status": "active", "public_owner_attribution": True})
    assert value.display_name == "Research Agent"
    assert value.visibility == "public"
    assert value.status == "active"
    assert value.public_owner_attribution is True



def test_create_agent_uses_atomic_rpc_and_server_derived_owner(monkeypatch):
    calls = []

    async def fake_user_db_request(method, path, access_token, **kwargs):
        calls.append((method, path, access_token, kwargs))
        return [{
            "id": "agent-1",
            "handle": "research_bot",
            "display_name": "Research Bot",
            "created_by": "human-123",
            "visibility": "private",
            "status": "draft",
        }]

    async def fake_current_user(request: Request):
        request.state.supabase_access_token = "human-session-token"
        return {"id": "human-123", "email": "human@example.invalid"}

    monkeypatch.setattr("allpha_api.main.user_db_request", fake_user_db_request)
    app.dependency_overrides[current_user] = fake_current_user
    try:
        response = client.post("/v1/agents", headers={"Authorization": "Bearer test"}, json={
            "handle": "research_bot",
            "display_name": "Research Bot",
            "persona": {"tone": "concise"},
            "disclosure": "AI-generated responses",
            "boundaries": {"private_owner_data": "owner_only"},
        })
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201
    assert calls[0][0:3] == ("POST", "rpc/create_ai_agent", "human-session-token")
    assert calls[0][3]["body"]["p_disclosure"] == "AI-generated responses"
    assert calls[0][3]["body"]["p_boundaries"] == {"private_owner_data": "owner_only"}
    assert "owner_user_id" not in calls[0][3]["body"]
    assert response.json()["ownership"]["owner_user_id"] == "human-123"



def test_public_passport_returns_only_public_projection(monkeypatch):
    calls = []

    async def fake_user_db_request(method, path, access_token, **kwargs):
        calls.append((method, path, access_token, kwargs))
        if path == "ai_agents":
            return [{
                "id": "agent-1",
                "handle": "research_bot",
                "display_name": "Research Bot",
                "description": "Public description",
                "disclosure": "AI-generated responses",
                "visibility": "public",
                "status": "active",
            }]
        if path == "agent_skill_publications":
            return [{"id": "skill-1", "slug": "summary", "name": "Summary", "version": 2, "status": "published"}]
        if path == "agent_capabilities":
            return [{"id": "cap-1", "capability_key": "calendar.read", "status": "approved"}]
        raise AssertionError(path)

    monkeypatch.setattr("allpha_api.main.user_db_request", fake_user_db_request)
    response = client.get("/v1/agent-passports/research_bot")

    assert response.status_code == 200
    assert response.json()["passport"]["handle"] == "research_bot"
    assert response.json()["skills"][0]["version"] == 2
    assert response.json()["capabilities"][0]["status"] == "approved"
    assert "persona" not in response.json()["passport"]
    assert "boundaries" not in response.json()["passport"]
    assert "owner_user_id" not in response.json()["passport"]
    assert "persona" not in calls[0][3]["params"]["select"]
    assert calls[0][0:3] == ("GET", "ai_agents", None)
    assert calls[1][1] == "agent_skill_publications"
    assert calls[1][3]["params"]["select"] == "id,slug,name,description,category,version,status,publication_terms,created_at,updated_at"
    assert calls[2][1] == "agent_capabilities"
    assert "required_permission_scopes" not in calls[2][3]["params"]["select"]



def test_list_agents_is_scoped_to_current_active_owner(monkeypatch):
    calls = []

    async def fake_user_db_request(method, path, access_token, **kwargs):
        calls.append((method, path, access_token, kwargs))
        return [{
            "agent_id": "agent-owned-by-me",
            "ownership_role": "owner",
            "status": "active",
            "created_at": "2026-10-13T00:00:00Z",
            "agent": {"id": "agent-owned-by-me", "handle": "my_agent", "display_name": "My Agent"},
        }]

    async def fake_current_user(request: Request):
        request.state.supabase_access_token = "human-a-token"
        return {"id": "human-a", "email": "human-a@example.invalid"}

    monkeypatch.setattr("allpha_api.main.user_db_request", fake_user_db_request)
    app.dependency_overrides[current_user] = fake_current_user
    try:
        response = client.get("/v1/agents", headers={"Authorization": "Bearer test"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["items"][0]["ownership"]["owner_user_id"] == "human-a"
    assert calls[0][3]["params"]["owner_user_id"] == "eq.human-a"
    assert calls[0][3]["params"]["ownership_role"] == "eq.owner"
    assert calls[0][3]["params"]["status"] == "eq.active"


def test_get_agent_returns_only_current_active_owner_record(monkeypatch):
    calls = []

    async def fake_user_db_request(method, path, access_token, **kwargs):
        calls.append((method, path, access_token, kwargs))
        if path == "agent_ownerships":
            return [{"agent_id": "agent-owned-by-a", "ownership_role": "owner", "status": "active", "created_at": "2026-10-13T00:00:00Z"}]
        return [{"id": "agent-owned-by-a", "handle": "owner_agent", "display_name": "Owner Agent", "visibility": "private", "status": "draft"}]

    async def fake_current_user(request: Request):
        request.state.supabase_access_token = "human-a-token"
        return {"id": "human-a", "email": "human-a@example.invalid"}

    monkeypatch.setattr("allpha_api.main.user_db_request", fake_user_db_request)
    app.dependency_overrides[current_user] = fake_current_user
    try:
        response = client.get("/v1/agents/00000000-0000-0000-0000-000000000001", headers={"Authorization": "Bearer test"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["agent"]["handle"] == "owner_agent"
    assert response.json()["ownership"]["owner_user_id"] == "human-a"
    assert calls[0][1] == "agent_ownerships"
    assert calls[0][3]["params"]["owner_user_id"] == "eq.human-a"
    assert calls[1][1] == "ai_agents"
    assert calls[1][3]["params"]["id"] == "eq.00000000-0000-0000-0000-000000000001"


def test_patch_agent_uses_atomic_owner_and_version_checked_rpc(monkeypatch):
    calls = []

    async def fake_user_db_request(method, path, access_token, **kwargs):
        calls.append((method, path, access_token, kwargs))
        if path == "ai_agents":
            return [{"id": "00000000-0000-0000-0000-000000000001", "version": 4}]
        if path == "rpc/update_my_ai_agent":
            return [{"id": "00000000-0000-0000-0000-000000000001", "display_name": "Updated Agent", "visibility": "public", "status": "active", "version": 5}]
        raise AssertionError(path)

    async def fake_current_user(request: Request):
        request.state.supabase_access_token = "human-a-token"
        return {"id": "human-a", "email": "human-a@example.invalid"}

    monkeypatch.setattr("allpha_api.main.user_db_request", fake_user_db_request)
    app.dependency_overrides[current_user] = fake_current_user
    try:
        response = client.patch(
            "/v1/agents/00000000-0000-0000-0000-000000000001",
            headers={"Authorization": "Bearer test"},
            json={"display_name": "Updated Agent", "visibility": "public", "status": "active"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["agent"]["display_name"] == "Updated Agent"
    assert [call[1] for call in calls] == ["ai_agents", "rpc/update_my_ai_agent"]
    assert calls[1][0:3] == ("POST", "rpc/update_my_ai_agent", "human-a-token")
    assert calls[1][3]["body"]["p_expected_version"] == 4
    assert calls[1][3]["body"]["p_changes"] == {"display_name": "Updated Agent", "visibility": "public", "status": "active"}


def test_patch_agent_does_not_update_when_caller_is_not_owner(monkeypatch):
    calls = []

    async def fake_user_db_request(method, path, access_token, **kwargs):
        calls.append((method, path, access_token, kwargs))
        return []

    async def fake_current_user(request: Request):
        request.state.supabase_access_token = "human-b-token"
        return {"id": "human-b", "email": "human-b@example.invalid"}

    monkeypatch.setattr("allpha_api.main.user_db_request", fake_user_db_request)
    app.dependency_overrides[current_user] = fake_current_user
    try:
        response = client.patch(
            "/v1/agents/00000000-0000-0000-0000-000000000001",
            headers={"Authorization": "Bearer test"},
            json={"display_name": "Attempted takeover"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert len(calls) == 1
    assert calls[0][1] == "ai_agents"



def test_public_passport_hides_private_draft_or_revoked_agent(monkeypatch):
    calls = []

    async def fake_user_db_request(method, path, access_token, **kwargs):
        calls.append((method, path, access_token, kwargs))
        return []

    monkeypatch.setattr("allpha_api.main.user_db_request", fake_user_db_request)
    response = client.get("/v1/agent-passports/revoked_agent")

    assert response.status_code == 404
    assert calls[0][0:3] == ("GET", "ai_agents", None)
    assert calls[0][3]["params"]["visibility"] == "eq.public"
    assert calls[0][3]["params"]["status"] == "eq.active"

def test_agent_schema_and_rpc_migration_match_api_contract():
    from pathlib import Path

    migrations = Path(__file__).resolve().parents[1] / "supabase" / "migrations"
    baseline = migrations / "20261013054429_eng_p04_ai_agent_identity.sql"
    forward = migrations / "20261014072435_eng_p05_agent_contract_reconciliation.sql"
    assert baseline.is_file(), "canonical Agent identity baseline migration must be present"
    assert forward.is_file(), "forward Agent contract reconciliation migration must be present"

    baseline_sql = baseline.read_text(encoding="utf-8")
    forward_sql = forward.read_text(encoding="utf-8")
    assert "create table if not exists public.ai_agents" in baseline_sql.lower()
    assert "create table if not exists public.agent_ownerships" in baseline_sql.lower()
    assert "add column if not exists disclosure" in forward_sql.lower()
    assert "add column if not exists boundaries" in forward_sql.lower()
    assert "p_disclosure text" in forward_sql.lower()
    assert "p_boundaries jsonb" in forward_sql.lower()
    assert "grant execute on function public.create_ai_agent(text, text, text, text, jsonb, text, text, jsonb) to authenticated" in forward_sql.lower()


def test_publish_agent_uses_owner_scoped_versioned_rpc(monkeypatch):
    calls=[]
    async def fake_user_db_request(method,path,access_token,**kwargs):
        calls.append((method,path,access_token,kwargs))
        return [{"id":"agent-1","status":"active","visibility":"public","version":6,"public_owner_attribution":True}]
    async def fake_current_user(request: Request):
        request.state.supabase_access_token="owner-token"
        return {"id":"owner-1","email":"owner@example.invalid"}
    monkeypatch.setattr("allpha_api.main.user_db_request",fake_user_db_request)
    app.dependency_overrides[current_user]=fake_current_user
    try:
        response=client.post("/v1/agents/00000000-0000-0000-0000-000000000001/publish",
            headers={"Authorization":"Bearer test"},json={"expected_version":5,"public_owner_attribution":True})
    finally:
        app.dependency_overrides.clear()
    assert response.status_code==200
    assert calls[0][0:3]==("POST","rpc/publish_my_ai_agent","owner-token")
    assert calls[0][3]["body"]=={"p_agent_id":"00000000-0000-0000-0000-000000000001","p_expected_version":5,"p_public_owner_attribution":True}


def test_revoke_agent_publication_uses_owner_scoped_versioned_rpc(monkeypatch):
    calls=[]
    async def fake_user_db_request(method,path,access_token,**kwargs):
        calls.append((method,path,access_token,kwargs))
        return [{"id":"agent-1","status":"draft","visibility":"private","version":7,"public_owner_attribution":False}]
    async def fake_current_user(request: Request):
        request.state.supabase_access_token="owner-token"
        return {"id":"owner-1","email":"owner@example.invalid"}
    monkeypatch.setattr("allpha_api.main.user_db_request",fake_user_db_request)
    app.dependency_overrides[current_user]=fake_current_user
    try:
        response=client.post("/v1/agents/00000000-0000-0000-0000-000000000001/revoke-publication",
            headers={"Authorization":"Bearer test"},json={"expected_version":6})
    finally:
        app.dependency_overrides.clear()
    assert response.status_code==200
    assert calls[0][1]=="rpc/revoke_my_ai_agent_publication"
    assert calls[0][3]["body"]["p_expected_version"]==6


def test_agent_identity_versions_are_owner_scoped(monkeypatch):
    calls=[]
    async def fake_user_db_request(method,path,access_token,**kwargs):
        calls.append((method,path,access_token,kwargs))
        if path=="ai_agents":
            return [{"id":"agent-1","version":3}]
        if path=="agent_identity_versions":
            return [{"version":3,"event_type":"updated","snapshot":{"display_name":"Agent"},"snapshot_sha256":"a"*64}]
        raise AssertionError(path)
    async def fake_current_user(request: Request):
        request.state.supabase_access_token="owner-token"
        return {"id":"owner-1","email":"owner@example.invalid"}
    monkeypatch.setattr("allpha_api.main.user_db_request",fake_user_db_request)
    app.dependency_overrides[current_user]=fake_current_user
    try:
        response=client.get("/v1/agents/00000000-0000-0000-0000-000000000001/versions",
            headers={"Authorization":"Bearer test"})
    finally:
        app.dependency_overrides.clear()
    assert response.status_code==200
    assert response.json()["current_version"]==3
    assert response.json()["items"][0]["event_type"]=="updated"
    assert calls[1][3]["params"]["limit"]=="50"


def test_public_passport_owner_attribution_requires_explicit_consent(monkeypatch):
    calls=[]
    async def fake_user_db_request(method,path,access_token,**kwargs):
        calls.append((method,path,access_token,kwargs))
        if path=="ai_agents":
            return [{"id":"agent-1","handle":"public_agent","display_name":"Public Agent","disclosure":"AI-generated responses","visibility":"public","status":"active","public_owner_attribution":True,"version":3,"published_at":"2026-11-24T00:00:00Z"}]
        if path=="agent_skill_publications" or path=="agent_capabilities":
            return []
        if path=="rpc/get_public_agent_owner_attribution":
            return [{"username":"human-owner","display_name":"Human Owner","avatar_url":"https://cdn.example.invalid/avatar.png"}]
        raise AssertionError(path)
    monkeypatch.setattr("allpha_api.main.user_db_request",fake_user_db_request)
    response=client.get("/v1/agent-passports/public_agent")
    assert response.status_code==200
    assert response.json()["owner_attribution"]["username"]=="human-owner"
    assert "owner_user_id" not in response.json()["owner_attribution"]
    assert calls[-1][1]=="rpc/get_public_agent_owner_attribution"


def test_agent_identity_history_and_publication_migration_is_forward_only():
    from pathlib import Path
    migrations=Path(__file__).resolve().parents[1]/"supabase"/"migrations"
    migration=migrations/"20261124031340_eng_p05_agent_identity_versions_and_passport_attribution.sql"
    assert migration.is_file()
    sql=migration.read_text(encoding="utf-8").lower()
    assert "create table if not exists public.agent_identity_versions" in sql
    assert "create trigger ai_agents_capture_identity_version" in sql
    assert "public_owner_attribution" in sql
    assert "public.publish_my_ai_agent" in sql
    assert "public.revoke_my_ai_agent_publication" in sql
    assert "public.get_public_agent_owner_attribution" in sql
    assert "agent_identity_versions" in sql and "owned_agents" in sql

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
    deeply_nested = {"level": {"level": {"level": {"level": {"level": {"level": {"level": {"level": {"too_deep": True}}}}}}}}
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
    value = AgentUpdate.model_validate({"display_name": "Research Agent", "visibility": "public", "status": "active"})
    assert value.display_name == "Research Agent"
    assert value.visibility == "public"
    assert value.status == "active"



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
        return [{
            "id": "agent-1",
            "handle": "research_bot",
            "display_name": "Research Bot",
            "description": "Public description",
            "disclosure": "AI-generated responses",
            "visibility": "public",
            "status": "active",
        }]

    monkeypatch.setattr("allpha_api.main.user_db_request", fake_user_db_request)
    response = client.get("/v1/agent-passports/research_bot")

    assert response.status_code == 200
    assert response.json()["passport"]["handle"] == "research_bot"
    assert "persona" not in response.json()["passport"]
    assert "boundaries" not in response.json()["passport"]
    assert "owner_user_id" not in response.json()["passport"]
    assert "persona" not in calls[0][3]["params"]["select"]
    assert calls[0][0:3] == ("GET", "ai_agents", None)



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


def test_patch_agent_updates_only_after_active_owner_check(monkeypatch):
    calls = []

    async def fake_user_db_request(method, path, access_token, **kwargs):
        calls.append((method, path, access_token, kwargs))
        if path == "agent_ownerships":
            return [{"agent_id": "00000000-0000-0000-0000-000000000001", "ownership_role": "owner", "status": "active"}]
        return [{"id": "00000000-0000-0000-0000-000000000001", "display_name": "Updated Agent", "visibility": "public", "status": "active"}]

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
    assert [call[1] for call in calls] == ["agent_ownerships", "ai_agents"]
    assert calls[1][0] == "PATCH"
    assert calls[1][2] == "human-a-token"
    assert calls[1][3]["body"] == {"display_name": "Updated Agent", "visibility": "public", "status": "active"}
    assert calls[1][3]["prefer"] == "return=representation"


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
    assert calls[0][1] == "agent_ownerships"
    assert calls[0][3]["params"]["owner_user_id"] == "eq.human-b"



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

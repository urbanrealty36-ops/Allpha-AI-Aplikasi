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

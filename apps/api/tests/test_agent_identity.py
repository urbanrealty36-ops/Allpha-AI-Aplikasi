import pytest
from pydantic import ValidationError
from fastapi.testclient import TestClient

from allpha_api.main import AgentCreate, AgentUpdate, app

client = TestClient(app)


def test_agent_routes_require_authentication():
    assert client.get("/v1/agents").status_code == 401
    assert client.get("/v1/agent-passports/research_bot").status_code == 401
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

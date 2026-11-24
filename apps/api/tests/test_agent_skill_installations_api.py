from fastapi import Request
from fastapi.testclient import TestClient

from allpha_api.auth import current_user
from allpha_api.main import app

client = TestClient(app)
AGENT = "11111111-1111-4111-8111-111111111111"
SOURCE_AGENT = "22222222-2222-4222-8222-222222222222"
SOURCE_SKILL = "33333333-3333-4333-8333-333333333333"
INSTALLATION = "44444444-4444-4444-8444-444444444444"


def auth_as(user_id="owner-a"):
    async def fake_current_user(request: Request):
        request.state.supabase_access_token = "token-" + user_id
        return {"id": user_id, "email": user_id + "@example.invalid"}
    return fake_current_user


def test_public_skill_publication_catalog_is_anonymous_and_paged(monkeypatch):
    calls = []
    async def fake_db(method, path, token, **kwargs):
        calls.append((method, path, token, kwargs))
        return [{"id": SOURCE_SKILL, "agent_id": SOURCE_AGENT, "version": 3, "publication_terms": {"license": "owner"}}]
    monkeypatch.setattr("allpha_api.main.privileged_rest_request", fake_db)
    response = client.get("/v1/agent-skills/publications?agent_id=" + SOURCE_AGENT + "&limit=200&offset=-2")
    assert response.status_code == 200
    assert response.json()["items"][0]["id"] == SOURCE_SKILL
    assert calls[0][0:2] == ("GET", "agent_skill_publications")
    assert calls[0][3]["params"]["limit"] == "100"
    assert calls[0][3]["params"]["offset"] == "0"


def test_agent_skill_installation_list_requires_auth_and_uses_owner_scoped_table(monkeypatch):
    assert client.get(f"/v1/agents/{AGENT}/skill-installations").status_code == 401
    calls = []
    service_calls = []
    async def fake_db(method, path, token, **kwargs):
        calls.append((method, path, token, kwargs))
        return [{"id": INSTALLATION, "agent_id": AGENT, "status": "active"}]
    async def fake_service(function_name, *, body):
        service_calls.append((function_name, body))
        return 0
    monkeypatch.setattr("allpha_api.main.user_db_request", fake_db)
    monkeypatch.setattr("allpha_api.main.service_db_request", fake_service)
    app.dependency_overrides[current_user] = auth_as("owner-a")
    try:
        response = client.get(f"/v1/agents/{AGENT}/skill-installations", headers={"Authorization": "Bearer test"})
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()["items"][0]["id"] == INSTALLATION
    assert service_calls == [("expire_agent_skill_installations", {"p_agent_id": AGENT, "p_actor_user_id": "owner-a"})]
    assert len(calls) == 1
    assert calls[0][0:3] == ("GET", "agent_skill_installations", "token-owner-a")
    assert calls[0][3]["params"]["agent_id"] == "eq." + AGENT


def test_skill_installation_requires_explicit_license_acceptance(monkeypatch):
    calls = []
    async def fake_db(method, path, token, **kwargs):
        calls.append((method, path, token, kwargs))
        return []
    monkeypatch.setattr("allpha_api.main.user_db_request", fake_db)
    app.dependency_overrides[current_user] = auth_as()
    try:
        response = client.post(f"/v1/agents/{AGENT}/skills/install",
            headers={"Authorization": "Bearer test"},
            json={"source_agent_id": SOURCE_AGENT, "source_skill_id": SOURCE_SKILL, "source_version": 3,
                  "accept_license": False, "idempotency_key": "install-key-0001"})
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "SKILL_LICENSE_ACCEPTANCE_REQUIRED"
    assert calls == []


def test_skill_installation_uses_canonical_transactional_rpc(monkeypatch):
    calls = []
    async def fake_service(function_name, *, body):
        calls.append((function_name, body))
        return {"installation": {"id": INSTALLATION, "status": "active"}, "installed_skill_id": "55555555-5555-4555-8555-555555555555", "idempotent_replay": False}
    monkeypatch.setattr("allpha_api.main.service_db_request", fake_service)
    app.dependency_overrides[current_user] = auth_as("owner-a")
    try:
        response = client.post(f"/v1/agents/{AGENT}/skills/install",
            headers={"Authorization": "Bearer test"},
            json={"source_agent_id": SOURCE_AGENT, "source_skill_id": SOURCE_SKILL, "source_version": 3,
                  "accept_license": True, "idempotency_key": "install-key-0001"})
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 201
    assert calls[0][0] == "install_agent_skill"
    assert calls[0][1] == {
        "p_agent_id": AGENT, "p_source_agent_id": SOURCE_AGENT, "p_source_skill_id": SOURCE_SKILL,
        "p_source_version": 3, "p_accept_license": True, "p_idempotency_key": "install-key-0001",
        "p_actor_user_id": "owner-a",
    }


def test_skill_installation_revoke_requires_owner_reason_and_calls_rpc(monkeypatch):
    calls = []
    async def fake_service(function_name, *, body):
        calls.append((function_name, body))
        return {"installation": {"id": INSTALLATION, "status": "revoked"}, "runtime_authorized": False}
    monkeypatch.setattr("allpha_api.main.service_db_request", fake_service)
    app.dependency_overrides[current_user] = auth_as("owner-a")
    try:
        response = client.post(f"/v1/agents/{AGENT}/skill-installations/{INSTALLATION}/revoke",
            headers={"Authorization": "Bearer test"}, json={"reason": "License terms no longer accepted"})
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    assert calls[0][0] == "revoke_agent_skill_installation"
    assert calls[0][1] == {
        "p_agent_id": AGENT, "p_installation_id": INSTALLATION,
        "p_reason": "License terms no longer accepted", "p_actor_user_id": "owner-a",
    }


def test_skill_installation_revocation_requires_authentication():
    response = client.post(f"/v1/agents/{AGENT}/skill-installations/{INSTALLATION}/revoke",
        json={"reason": "License terms no longer accepted"})
    assert response.status_code == 401

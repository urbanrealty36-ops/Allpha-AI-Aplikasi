from fastapi import Request
from fastapi.testclient import TestClient

from allpha_api.auth import current_user
from allpha_api.main import app

client = TestClient(app)



def test_interest_signal_read_is_owner_scoped(monkeypatch):
    calls = []

    async def fake_user_db_request(method, path, token, **kwargs):
        calls.append((method, path, token, kwargs))
        if path == "user_interest_graph_signals":
            return [{"interest_key": "spatial_3d", "signal_type": "passion", "strength": 1}]
        return [{"interest_key": "spatial_3d", "signal_type": "passion", "action": "set"}]

    async def fake_current_user(request: Request):
        request.state.supabase_access_token = "interest-graph-token"
        return {"id": "interest-graph-owner", "email": "owner@example.invalid"}

    monkeypatch.setattr("allpha_api.interest_graph_api.user_db_request", fake_user_db_request)
    app.dependency_overrides[current_user] = fake_current_user
    try:
        response = client.get("/v1/me/interest-signals", headers={"Authorization": "Bearer interest-graph-token"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["items"][0]["interest_key"] == "spatial_3d"
    assert len(calls) == 2
    assert all(call[2] == "interest-graph-token" for call in calls)
    assert all(call[3]["params"]["user_id"] == "eq.interest-graph-owner" for call in calls)


def test_interest_signal_write_uses_service_rpc_and_authenticated_actor(monkeypatch):
    calls = []

    async def fake_service_db_request(function_name, *, body):
        calls.append((function_name, body))
        return [{
            "user_id": "interest-graph-owner", "interest_key": "spatial_3d",
            "signal_type": "passion", "strength": 1, "signal_source": "user_selected",
            "consent_version": "interest-graph-v1",
        }]

    async def fake_current_user(request: Request):
        request.state.supabase_access_token = "interest-graph-token"
        return {"id": "interest-graph-owner", "email": "owner@example.invalid"}

    monkeypatch.setattr("allpha_api.interest_graph_api.service_db_request", fake_service_db_request)
    app.dependency_overrides[current_user] = fake_current_user
    try:
        response = client.put(
            "/v1/me/interest-signals",
            headers={"Authorization": "Bearer interest-graph-token"},
            json={
                "interest_key": "spatial_3d", "signal_type": "passion", "strength": 1,
                "signal_source": "user_selected", "consent_version": "interest-graph-v1",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert calls == [("set_user_interest_graph_signal_for_actor", {
        "p_actor_user_id": "interest-graph-owner", "p_interest_key": "spatial_3d",
        "p_signal_type": "passion", "p_strength": 1.0, "p_signal_source": "user_selected",
        "p_consent_version": "interest-graph-v1",
    })]


def test_interest_signal_delete_is_server_scoped(monkeypatch):
    calls = []

    async def fake_service_db_request(function_name, *, body):
        calls.append((function_name, body))
        return [{"interest_key": "spatial_3d", "signal_type": "habit"}]

    async def fake_current_user(request: Request):
        request.state.supabase_access_token = "interest-graph-token"
        return {"id": "interest-graph-owner", "email": "owner@example.invalid"}

    monkeypatch.setattr("allpha_api.interest_graph_api.service_db_request", fake_service_db_request)
    app.dependency_overrides[current_user] = fake_current_user
    try:
        response = client.delete(
            "/v1/me/interest-signals/habit/spatial_3d",
            headers={"Authorization": "Bearer interest-graph-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert calls == [("delete_user_interest_graph_signal_for_actor", {
        "p_actor_user_id": "interest-graph-owner", "p_interest_key": "spatial_3d", "p_signal_type": "habit",
    })]


def test_interest_signal_reset_requires_explicit_integer_confirmation(monkeypatch):
    async def fake_service_db_request(function_name, *, body):
        assert function_name == "clear_user_interest_graph_signals_for_actor"
        assert body == {"p_actor_user_id": "interest-graph-owner"}
        return False

    async def fake_current_user(request: Request):
        request.state.supabase_access_token = "interest-graph-token"
        return {"id": "interest-graph-owner", "email": "owner@example.invalid"}

    monkeypatch.setattr("allpha_api.interest_graph_api.service_db_request", fake_service_db_request)
    app.dependency_overrides[current_user] = fake_current_user
    try:
        response = client.delete("/v1/me/interest-signals", headers={"Authorization": "Bearer interest-graph-token"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INTEREST_SIGNAL_RESET_UNCONFIRMED"



def test_interest_signal_write_can_target_only_an_owned_agent(monkeypatch):
    calls = []

    async def fake_service_db_request(function_name, *, body):
        calls.append((function_name, body))
        return [{"user_id": "interest-graph-owner", "agent_id": "owned-agent", "interest_key": "technology"}]

    async def fake_current_user(request: Request):
        request.state.supabase_access_token = "interest-graph-token"
        return {"id": "interest-graph-owner", "email": "owner@example.invalid"}

    monkeypatch.setattr("allpha_api.interest_graph_api.service_db_request", fake_service_db_request)
    app.dependency_overrides[current_user] = fake_current_user
    try:
        response = client.put(
            "/v1/me/interest-signals",
            headers={"Authorization": "Bearer interest-graph-token"},
            json={
                "interest_key": "technology", "signal_type": "passion", "strength": 0.8,
                "signal_source": "user_selected", "agent_id": "11111111-1111-4111-8111-111111111111",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert calls[0][1]["p_actor_user_id"] == "interest-graph-owner"
    assert calls[0][1]["p_agent_id"] == "11111111-1111-4111-8111-111111111111"
    assert calls[0][1]["p_consent_version"] == "interest-graph-v1"


def test_interest_signal_rejects_client_supplied_consent_version():
    response = client.put(
        "/v1/me/interest-signals",
        json={
            "interest_key": "technology", "signal_type": "habit", "strength": 0.5,
            "signal_source": "observed_interaction", "consent_version": "client-forged-version",
        },
    )
    assert response.status_code == 422



def test_interest_catalog_and_taxonomy_relationships_are_server_read_only(monkeypatch):
    calls = []

    async def fake_user_db_request(method, path, token, **kwargs):
        calls.append((method, path, token, kwargs))
        if path == "interest_catalog":
            return [{"interest_key": "technology", "label": "IT & Teknologi", "sensitivity": "standard"}]
        if path == "interest_taxonomy_edges":
            return [{"source_interest_key": "technology", "target_interest_key": "spatial_3d", "relation_type": "parent_of"}]
        raise AssertionError(path)

    async def fake_current_user(request: Request):
        request.state.supabase_access_token = "interest-graph-token"
        return {"id": "interest-graph-owner", "email": "owner@example.invalid"}

    monkeypatch.setattr("allpha_api.interest_graph_api.user_db_request", fake_user_db_request)
    app.dependency_overrides[current_user] = fake_current_user
    try:
        response = client.get("/v1/interests/catalog", headers={"Authorization": "Bearer interest-graph-token"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["items"][0]["interest_key"] == "technology"
    assert response.json()["relationships"][0]["relation_type"] == "parent_of"
    assert [call[1] for call in calls] == ["interest_catalog", "interest_taxonomy_edges"]

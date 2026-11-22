from __future__ import annotations

from fastapi import Request
from fastapi.testclient import TestClient

from allpha_api.auth import current_user
from allpha_api.main import app
from allpha_api import social_graph_api


OWNER = "00000000-0000-4000-8000-000000000101"
OTHER_OWNER = "00000000-0000-4000-8000-000000000102"
AGENT_A = "00000000-0000-4000-8000-000000000201"
AGENT_B = "00000000-0000-4000-8000-000000000202"
HUMAN_B = "00000000-0000-4000-8000-000000000302"


def _user(request: Request):
    request.state.supabase_access_token = "isolated-eng-p04-token"
    request.state.user_id = OWNER
    return {"id": OWNER, "email": "owner@example.invalid"}


def _install(monkeypatch, *, actor_role="owner", replay=None):
    calls = []

    async def fake_rows(method, path, token, *, params=None, body=None, prefer=None):
        params = params or {}
        calls.append((method, path, params, body, prefer))
        if path == "agent_ownerships":
            agent_id = params.get("agent_id", "").removeprefix("eq.")
            owner_id = params.get("owner_user_id", "").removeprefix("eq.")
            role = actor_role if agent_id == AGENT_A else "owner"
            if owner_id == OWNER:
                return [{"agent_id": agent_id, "owner_user_id": owner_id, "ownership_role": role, "status": "active"}]
            return [{"agent_id": agent_id, "owner_user_id": OTHER_OWNER, "ownership_role": "owner", "status": "active"}]
        if path == "ai_agents":
            agent_id = params.get("id", "").removeprefix("eq.")
            return [{"id": agent_id, "created_by": OWNER if agent_id == AGENT_A else OTHER_OWNER,
                     "status": "active", "visibility": "public", "handle": "agent", "display_name": "Agent"}]
        if path == "profiles":
            return [{"id": HUMAN_B, "visibility": "public", "account_status": "active"}]
        if path == "social_edges" and method == "GET":
            if replay and params.get("idempotency_key") == "eq.retry-key-001":
                return [replay]
            return []
        if path == "social_edges" and method == "POST":
            row = {"id": "00000000-0000-4000-8000-000000000999", **body,
                   "status": "active", "created_at": "2026-11-22T00:00:00Z"}
            return [row]
        raise AssertionError((method, path, params, body))

    async def fake_server_db(method, table, *, params=None, body=None, prefer=None):
        params = params or {}
        if table == "profiles":
            profile_id = params.get("id", "").removeprefix("eq.")
            if profile_id == HUMAN_B:
                return [{"id": HUMAN_B, "visibility": "public", "account_status": "active"}]
            if profile_id == OTHER_OWNER:
                return [{"id": OTHER_OWNER, "account_status": "active"}]
            return []
        if table == "ai_agents":
            agent_id = params.get("id", "").removeprefix("eq.")
            return [{"id": agent_id, "created_by": OTHER_OWNER, "status": "active",
                     "visibility": "public", "handle": "target-agent", "display_name": "Target Agent"}]
        if table == "agent_ownerships":
            return [{"agent_id": AGENT_B, "owner_user_id": OTHER_OWNER, "ownership_role": "owner", "status": "active"}]
        return []

    monkeypatch.setattr(social_graph_api, "_rows", fake_rows)
    monkeypatch.setattr(social_graph_api, "_server_db", fake_server_db)
    app.dependency_overrides[current_user] = _user
    return calls


def test_human_to_human_relationship_uses_typed_human_nodes(monkeypatch):
    calls = _install(monkeypatch)
    try:
        response = TestClient(app).post("/v1/social/relationships", json={
            "target_type": "human", "target_id": HUMAN_B, "edge_type": "follow"
        })
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 201, response.text
    body = next(call[3] for call in calls if call[0] == "POST")
    assert body["actor_node_type"] == "human" and body["target_node_type"] == "human"
    assert body["actor_agent_id"] is None and body["target_agent_id"] is None


def test_human_to_agent_relationship_resolves_agent_owner_and_target_type(monkeypatch):
    calls = _install(monkeypatch)
    try:
        response = TestClient(app).post("/v1/social/relationships", json={
            "target_type": "agent", "target_id": AGENT_B, "edge_type": "follow"
        })
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 201, response.text
    body = next(call[3] for call in calls if call[0] == "POST")
    assert body["actor_node_type"] == "human" and body["target_node_type"] == "agent"
    assert body["target_agent_id"] == AGENT_B and body["target_user_id"] == OTHER_OWNER


def test_agent_to_human_relationship_requires_owner_and_uses_agent_actor_node(monkeypatch):
    calls = _install(monkeypatch)
    try:
        response = TestClient(app).post("/v1/social/relationships", json={
            "target_type": "human", "target_id": HUMAN_B, "edge_type": "follow", "actor_agent_id": AGENT_A
        })
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 201, response.text
    body = next(call[3] for call in calls if call[0] == "POST")
    assert body["actor_node_type"] == "agent" and body["target_node_type"] == "human"
    assert body["actor_agent_id"] == AGENT_A and body["actor_user_id"] == OWNER


def test_agent_to_agent_relationship_is_a_single_typed_graph_edge(monkeypatch):
    calls = _install(monkeypatch)
    try:
        response = TestClient(app).post("/v1/social/relationships", json={
            "target_type": "agent", "target_id": AGENT_B, "edge_type": "follow", "actor_agent_id": AGENT_A
        })
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 201, response.text
    body = next(call[3] for call in calls if call[0] == "POST")
    assert body["actor_node_type"] == "agent" and body["target_node_type"] == "agent"
    assert body["actor_agent_id"] == AGENT_A and body["target_agent_id"] == AGENT_B


def test_agent_operator_cannot_block_without_owner_authority(monkeypatch):
    _install(monkeypatch, actor_role="operator")
    try:
        response = TestClient(app).post("/v1/social/relationships", json={
            "target_type": "human", "target_id": HUMAN_B, "edge_type": "block", "actor_agent_id": AGENT_A
        })
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "SOCIAL_AGENT_OWNER_REQUIRED"


def test_idempotency_key_is_persisted_and_replay_returns_existing_edge(monkeypatch):
    existing = {"id": "00000000-0000-4000-8000-000000000999", "actor_user_id": OWNER,
                "target_user_id": OTHER_OWNER, "actor_node_type": "human", "target_node_type": "agent",
                "actor_agent_id": None, "target_agent_id": AGENT_B, "edge_type": "follow",
                "status": "active", "idempotency_key": "retry-key-001"}
    calls = _install(monkeypatch, replay=existing)
    try:
        response = TestClient(app).post("/v1/social/relationships", headers={"Idempotency-Key": "retry-key-001"},
            json={"target_type": "agent", "target_id": AGENT_B, "edge_type": "follow"})
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200, response.text
    assert response.json()["idempotent_replay"] is True
    assert not any(call[0] == "POST" for call in calls)

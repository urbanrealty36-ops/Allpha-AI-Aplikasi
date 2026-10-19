from __future__ import annotations

import uuid
from fastapi import Request
from fastapi.testclient import TestClient
from allpha_api import community_api
from allpha_api.auth import current_user
from allpha_api.main import app


def _user(request: Request):
    request.state.user_id = "community-test-user"
    return {"id": "community-test-user", "email": "community@example.invalid"}


def test_community_api_requires_auth():
    response = TestClient(app).get("/v1/communities")
    assert response.status_code == 401


def test_create_community_creates_owner_membership(monkeypatch):
    community_id = str(uuid.uuid4())
    calls = []
    async def db(method, table, *, params=None, body=None, prefer=None):
        calls.append((method, table, body))
        if method == "POST" and table == "rpc/create_community_with_owner":
            return [{"id": community_id, "name": body["p_name"], "slug": body["p_slug"], "visibility": body["p_visibility"]}]
        raise AssertionError((method, table))
    monkeypatch.setattr(community_api, "_db", db)
    app.dependency_overrides[current_user] = _user
    try:
        response = TestClient(app).post("/v1/communities", json={"name":"Builders","slug":"allpha-builders","description":"Build together","visibility":"private"})
        assert response.status_code == 201
        assert response.json()["membership_role"] == "owner"
        creation = next(call for call in calls if call[1] == "rpc/create_community_with_owner")
        assert creation[2]["p_created_by"] == "community-test-user"
    finally:
        app.dependency_overrides.clear()


def test_private_community_is_not_disclosed_to_non_member(monkeypatch):
    community_id = uuid.uuid4()
    async def db(method, table, *, params=None, body=None, prefer=None):
        if table == "communities":
            return [{"id": str(community_id), "visibility":"private", "status":"active"}]
        if table == "community_memberships":
            return []
        raise AssertionError((method, table))
    monkeypatch.setattr(community_api, "_db", db)
    app.dependency_overrides[current_user] = _user
    try:
        response = TestClient(app).get(f"/v1/communities/{community_id}")
        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_workspace_document_version_conflict_is_rejected(monkeypatch):
    workspace_id, document_id = uuid.uuid4(), uuid.uuid4()
    async def access(workspace_id, user_id, write=False):
        return {"workspace":{"id":str(workspace_id)}, "membership":{"role":"owner"}}
    async def db(method, table, *, params=None, body=None, prefer=None):
        if method == "GET" and table == "workspace_documents":
            return [{"id":str(document_id), "workspace_id":str(workspace_id), "version":3, "status":"active"}]
        raise AssertionError("A stale document update must not write a new version")
    monkeypatch.setattr(community_api, "_require_workspace", access)
    monkeypatch.setattr(community_api, "_db", db)
    app.dependency_overrides[current_user] = _user
    try:
        response = TestClient(app).put(f"/v1/workspaces/{workspace_id}/documents/{document_id}", json={"title":"Doc","body":"stale","expected_version":2})
        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "DOCUMENT_VERSION_CONFLICT"
    finally:
        app.dependency_overrides.clear()


def test_mission_progress_uses_atomic_idempotent_rpc(monkeypatch):
    community_id, mission_id = uuid.uuid4(), uuid.uuid4()
    async def member(*args, **kwargs): return {"role":"member"}
    async def db(method, table, *, params=None, body=None, prefer=None):
        assert method == "POST" and table == "rpc/record_community_mission_progress"
        assert body["p_community_id"] == str(community_id)
        assert body["p_mission_id"] == str(mission_id)
        assert body["p_user_id"] == "community-test-user"
        assert body["p_increment"] == 50
        assert uuid.UUID(body["p_idempotency_key"])
        return [{"progress_count":2,"status":"completed","mission_id":str(mission_id)}]
    monkeypatch.setattr(community_api, "_require_member", member)
    monkeypatch.setattr(community_api, "_db", db)
    app.dependency_overrides[current_user] = _user
    try:
        response=TestClient(app).post("/v1/communities/"+str(community_id)+"/missions/"+str(mission_id)+"/progress?increment=50",headers={"Idempotency-Key":str(uuid.uuid4())})
        assert response.status_code == 200
        assert response.json()["progress"]["progress_count"] == 2
        assert response.json()["reward_status"] == "not_configured"
    finally:
        app.dependency_overrides.clear()


def test_agent_grant_requires_active_agent_and_explicit_resource_approval(monkeypatch):
    agent_id, community_id, grant_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    calls = []
    async def db(method, table, *, params=None, body=None, prefer=None):
        calls.append((method, table, params, body))
        if table == "ai_agents" and method == "GET":
            return [{"id": str(agent_id), "status": "active"}]
        if table == "agent_ownerships" and method == "GET":
            return [{"agent_id": str(agent_id), "owner_user_id": "community-test-user"}]
        if table == "communities" and method == "GET":
            return [{"id": str(community_id), "status": "active", "visibility": "public"}]
        if table == "community_memberships" and method == "GET":
            return [{"community_id": str(community_id), "user_id": "community-test-user", "role": "owner", "status": "active"}]
        if table == "agent_resource_grants" and method == "POST":
            return [{"id": str(grant_id), **body}]
        if table == "agent_resource_grant_audit" and method == "POST":
            return None
        raise AssertionError((method, table, params, body))
    monkeypatch.setattr(community_api, "_db", db)
    app.dependency_overrides[current_user] = _user
    try:
        response = TestClient(app).post(
            f"/v1/agents/{agent_id}/resource-grants",
            json={"resource_type":"community","resource_id":str(community_id),"scopes":["read_published_content","comment"]},
        )
        assert response.status_code == 201, response.text
        assert response.json()["participation_enabled"] is False
        assert response.json()["grant"]["scopes"] == ["comment", "read_published_content"]
        assert any(call[1] == "agent_resource_grant_audit" for call in calls)
    finally:
        app.dependency_overrides.clear()


def test_agent_grant_fails_closed_without_resource_approver(monkeypatch):
    agent_id, community_id = uuid.uuid4(), uuid.uuid4()
    async def db(method, table, *, params=None, body=None, prefer=None):
        if table == "ai_agents":
            return [{"id": str(agent_id), "status": "active"}]
        if table == "agent_ownerships":
            return [{"agent_id": str(agent_id), "owner_user_id": "community-test-user"}]
        if table == "communities":
            return [{"id": str(community_id), "status": "active", "visibility": "public"}]
        if table == "community_memberships":
            return []
        raise AssertionError((method, table))
    monkeypatch.setattr(community_api, "_db", db)
    app.dependency_overrides[current_user] = _user
    try:
        response = TestClient(app).post(
            f"/v1/agents/{agent_id}/resource-grants",
            json={"resource_type":"community","resource_id":str(community_id),"scopes":["read_published_content"]},
        )
        assert response.status_code == 403
        assert response.json()["detail"]["code"] == "RESOURCE_GRANT_APPROVER_REQUIRED"
    finally:
        app.dependency_overrides.clear()


def test_agent_grant_rejects_scope_not_allowed_for_resource(monkeypatch):
    agent_id, workspace_id = uuid.uuid4(), uuid.uuid4()
    async def db(method, table, *, params=None, body=None, prefer=None):
        if table == "ai_agents":
            return [{"id": str(agent_id), "status": "active"}]
        if table == "agent_ownerships":
            return [{"agent_id": str(agent_id), "owner_user_id": "community-test-user"}]
        if table == "workspaces":
            return [{"id": str(workspace_id), "status": "active"}]
        if table == "workspace_memberships":
            return [{"workspace_id": str(workspace_id), "user_id": "community-test-user", "role": "owner", "status": "active"}]
        raise AssertionError((method, table))
    monkeypatch.setattr(community_api, "_db", db)
    app.dependency_overrides[current_user] = _user
    try:
        response = TestClient(app).post(
            f"/v1/agents/{agent_id}/resource-grants",
            json={"resource_type":"workspace","resource_id":str(workspace_id),"scopes":["create_agent_post"]},
        )
        assert response.status_code == 422
        assert response.json()["detail"]["code"] == "AGENT_GRANT_SCOPE_NOT_ALLOWED"
    finally:
        app.dependency_overrides.clear()

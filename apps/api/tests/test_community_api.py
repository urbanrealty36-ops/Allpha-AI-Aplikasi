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
        if method == "GET" and table == "communities":
            return []
        if method == "POST" and table == "communities":
            return [{"id": community_id, "name": body["name"], "slug": body["slug"], "visibility": body["visibility"]}]
        if method == "POST" and table == "community_memberships":
            return None
        raise AssertionError((method, table))
    monkeypatch.setattr(community_api, "_db", db)
    app.dependency_overrides[current_user] = _user
    try:
        response = TestClient(app).post("/v1/communities", json={"name":"Builders","slug":"allpha-builders","description":"Build together","visibility":"private"})
        assert response.status_code == 201
        assert response.json()["membership_role"] == "owner"
        membership = next(call for call in calls if call[1] == "community_memberships")
        assert membership[2]["user_id"] == "community-test-user"
        assert membership[2]["role"] == "owner"
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


def test_mission_progress_cannot_exceed_target(monkeypatch):
    community_id, mission_id = uuid.uuid4(), uuid.uuid4()
    async def member(*args, **kwargs): return {"role":"member"}
    async def db(method, table, *, params=None, body=None, prefer=None):
        if method == "GET" and table == "community_missions":
            return [{"id":str(mission_id),"community_id":str(community_id),"target_count":2,"status":"active"}]
        if method == "GET" and table == "community_mission_progress":
            return [{"progress_count":1}]
        if method == "POST" and table == "community_mission_progress":
            assert body["progress_count"] == 2
            assert body["status"] == "completed"
            return [body]
        raise AssertionError((method, table))
    monkeypatch.setattr(community_api, "_require_member", member)
    monkeypatch.setattr(community_api, "_db", db)
    app.dependency_overrides[current_user] = _user
    try:
        response = TestClient(app).post(f"/v1/communities/{community_id}/missions/{mission_id}/progress?increment=50")
        assert response.status_code == 200
        assert response.json()["progress"]["progress_count"] == 2
        assert response.json()["reward_status"] == "not_configured"
    finally:
        app.dependency_overrides.clear()

from __future__ import annotations

from fastapi import Request
from fastapi.testclient import TestClient

from allpha_api.auth import current_user
from allpha_api.main import app


ACTOR_ID = "11111111-1111-4111-8111-111111111111"
TARGET_ID = "22222222-2222-4222-8222-222222222222"
client = TestClient(app)


def _social_user(request: Request):
    request.state.supabase_access_token = "isolated-eng-p04-token"
    return {"id": ACTOR_ID, "email": "social-actor@example.invalid"}


def _override_user():
    app.dependency_overrides[current_user] = _social_user


def test_follow_rejects_inactive_or_unprovisioned_target(monkeypatch):
    calls = []

    async def fake_user_db_request(method, path, token, **kwargs):
        calls.append((method, path, kwargs))
        if path == "profiles":
            return [{"id": TARGET_ID, "visibility": "public", "account_status": "suspended"}]
        raise AssertionError(f"social write should not proceed: {method} {path}")

    monkeypatch.setattr("allpha_api.main.user_db_request", fake_user_db_request)
    _override_user()
    try:
        response = client.post(
            "/v1/me/social-edges",
            json={"target_user_id": TARGET_ID, "edge_type": "follow"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "SOCIAL_TARGET_NOT_FOUND"
    assert len(calls) == 1
    assert calls[0][1] == "profiles"


def test_follow_rejects_mutual_block_with_stable_policy_error(monkeypatch):
    calls = []

    async def fake_user_db_request(method, path, token, **kwargs):
        params = kwargs.get("params") or {}
        calls.append((method, path, params))
        if path == "profiles":
            return [{"id": TARGET_ID, "visibility": "public", "account_status": "active"}]
        if path == "social_edges" and params.get("edge_type") == "eq.block":
            if params.get("actor_user_id") == f"eq.{TARGET_ID}":
                return [{"id": "33333333-3333-4333-8333-333333333333"}]
            return []
        raise AssertionError(f"follow write should not proceed: {method} {path} {params}")

    monkeypatch.setattr("allpha_api.main.user_db_request", fake_user_db_request)
    _override_user()
    try:
        response = client.post(
            "/v1/me/social-edges",
            json={"target_user_id": TARGET_ID, "edge_type": "follow"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "SOCIAL_EDGE_BLOCKED"
    assert all(not (method == "POST" and path == "social_edges") for method, path, _ in calls)


def test_follow_request_uses_authenticated_actor_and_preserves_private_request_state(monkeypatch):
    calls = []

    async def fake_user_db_request(method, path, token, **kwargs):
        params = kwargs.get("params") or {}
        body = kwargs.get("body") or {}
        calls.append((method, path, params, body, token))
        if path == "profiles":
            return [{"id": TARGET_ID, "visibility": "private", "account_status": "active"}]
        if path == "social_edges" and params.get("edge_type") == "eq.block":
            return []
        if path == "social_edges" and method == "GET":
            return []
        if path == "social_edges" and method == "POST":
            return [{
                "id": "44444444-4444-4444-8444-444444444444",
                "actor_user_id": ACTOR_ID,
                "target_user_id": TARGET_ID,
                "edge_type": "follow",
                "status": "requested",
                "created_at": "2026-10-27T00:00:00+00:00",
            }]
        raise AssertionError(f"unexpected request: {method} {path} {params}")

    monkeypatch.setattr("allpha_api.main.user_db_request", fake_user_db_request)
    _override_user()
    try:
        response = client.post(
            "/v1/me/social-edges",
            json={"target_user_id": TARGET_ID, "edge_type": "follow"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201
    assert response.json()["edge"]["status"] == "requested"
    assert response.json()["outcome"] == "follow_request_created"
    write = next(call for call in calls if call[0] == "POST" and call[1] == "social_edges")
    assert write[3]["actor_user_id"] == ACTOR_ID
    assert write[3]["target_user_id"] == TARGET_ID
    assert write[4] == "isolated-eng-p04-token"

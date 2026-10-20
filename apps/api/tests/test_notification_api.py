from __future__ import annotations

from fastapi import Request
from fastapi.testclient import TestClient

from allpha_api import notification_api
from allpha_api.auth import current_user
from allpha_api.main import app


USER_ID = "11111111-1111-4111-8111-111111111111"
OTHER_USER_ID = "22222222-2222-4222-8222-222222222222"


def _user(request: Request):
    request.state.user_id = USER_ID
    return {"id": USER_ID, "email": "notification-test@example.invalid"}


def test_notification_inbox_requires_auth():
    response = TestClient(app).get("/v1/notifications")
    assert response.status_code == 401


def test_notification_list_is_owner_scoped_and_returns_unread_count(monkeypatch):
    calls = []

    async def fake_request(method, table, *, params, body=None, prefer=None):
        calls.append((method, table, params))
        if len(calls) == 1:
            return [{"id": "n-1", "user_id": USER_ID, "title": "Hello", "read_at": None}]
        return [{"id": "n-1"}, {"id": "n-2"}]

    monkeypatch.setattr(notification_api, "_request", fake_request)
    app.dependency_overrides[current_user] = _user
    try:
        response = TestClient(app).get("/v1/notifications?limit=10&unread_only=true")
        assert response.status_code == 200
        body = response.json()
        assert body["unread_count"] == 2
        assert body["items"][0]["id"] == "n-1"
        assert calls[0][2]["user_id"] == f"eq.{USER_ID}"
        assert calls[0][2]["read_at"] == "is.null"
        assert calls[1][2]["user_id"] == f"eq.{USER_ID}"
    finally:
        app.dependency_overrides.clear()


def test_mark_notification_read_scopes_update_to_authenticated_owner(monkeypatch):
    calls = []

    async def fake_request(method, table, *, params, body=None, prefer=None):
        calls.append((method, table, params, body, prefer))
        return [{"id": "n-1", "read_at": "2026-10-20T00:00:00+00:00"}]

    monkeypatch.setattr(notification_api, "_request", fake_request)
    app.dependency_overrides[current_user] = _user
    try:
        response = TestClient(app).patch(
            "/v1/notifications/11111111-1111-4111-8111-111111111111/read",
            json={},
        )
        assert response.status_code == 200
        assert response.json()["already_read"] is False
        assert calls[0][0] == "PATCH"
        assert calls[0][2]["user_id"] == f"eq.{USER_ID}"
        assert calls[0][2]["read_at"] == "is.null"
        assert calls[0][3]["read_at"]
        assert calls[0][4] == "return=representation"
    finally:
        app.dependency_overrides.clear()


def test_mark_read_returns_not_found_for_other_users_notification(monkeypatch):
    async def fake_request(method, table, *, params, body=None, prefer=None):
        if method == "PATCH":
            return []
        assert params["user_id"] == f"eq.{USER_ID}"
        return []

    monkeypatch.setattr(notification_api, "_request", fake_request)
    app.dependency_overrides[current_user] = _user
    try:
        response = TestClient(app).patch(
            "/v1/notifications/33333333-3333-4333-8333-333333333333/read",
            json={},
        )
        assert response.status_code == 404
        payload = response.json()
        error = payload.get("detail", payload.get("error", {}))
        assert error["code"] == "NOTIFICATION_NOT_FOUND"
    finally:
        app.dependency_overrides.clear()


def test_mark_all_read_updates_only_authenticated_owner(monkeypatch):
    calls = []

    async def fake_request(method, table, *, params, body=None, prefer=None):
        calls.append((method, params, body))
        return [{"id": "n-1"}, {"id": "n-2"}]

    monkeypatch.setattr(notification_api, "_request", fake_request)
    app.dependency_overrides[current_user] = _user
    try:
        response = TestClient(app).post("/v1/notifications/read-all", json={})
        assert response.status_code == 200
        assert response.json() == {"updated_count": 2}
        assert calls[0][0] == "PATCH"
        assert calls[0][1]["user_id"] == f"eq.{USER_ID}"
        assert calls[0][1]["read_at"] == "is.null"
    finally:
        app.dependency_overrides.clear()


def test_notification_storage_failure_is_fail_closed(monkeypatch):
    from fastapi import HTTPException

    def no_config():
        raise HTTPException(status_code=503, detail={"code": "NOTIFICATIONS_NOT_CONFIGURED"})

    monkeypatch.setattr(notification_api, "_config", no_config)

    async def call_request():
        return await notification_api._request("GET", "notifications", params={"limit": "1"})

    import asyncio
    try:
        asyncio.run(call_request())
        assert False, "expected a fail-closed 503"
    except HTTPException as exc:
        assert exc.status_code == 503
        assert exc.detail["code"] == "NOTIFICATIONS_NOT_CONFIGURED"

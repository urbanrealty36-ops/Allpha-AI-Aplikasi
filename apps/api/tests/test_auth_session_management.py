"""ENG-P02 self-service session API contract regression tests."""
from fastapi import Request
from fastapi.testclient import TestClient

from allpha_api.auth import current_session_user, current_user
from allpha_api.main import app


USER = {"id": "11111111-1111-4111-8111-111111111111"}
CURRENT = "22222222-2222-4222-8222-222222222222"
OTHER = "33333333-3333-4333-8333-333333333333"


async def _session_user(request: Request):
    request.state.auth_session_id = CURRENT
    request.state.supabase_access_token = "verified-test-session"
    return USER


async def _active_user(request: Request):
    request.state.auth_session_id = CURRENT
    request.state.supabase_access_token = "verified-test-session"
    return USER


def _client(monkeypatch, dependency, resolver, db):
    monkeypatch.setattr("allpha_api.main.user_db_request", db)
    app.dependency_overrides[dependency] = resolver
    return TestClient(app)


def test_list_sessions_is_self_scoped_and_marks_current(monkeypatch):
    expected = [{
        "id": CURRENT,
        "created_at": "2026-11-22T10:00:00Z",
        "updated_at": "2026-11-22T10:10:00Z",
        "refreshed_at": "2026-11-22T10:10:00Z",
        "not_after": None,
        "aal": "aal1",
        "user_agent": "Allpha Android",
        "ip": "192.0.2.10",
        "is_current": True,
    }]
    calls = []

    async def db(method, path, token, **kwargs):
        calls.append((method, path, token, kwargs))
        return expected

    client = _client(monkeypatch, current_user, _active_user, db)
    try:
        response = client.get("/v1/me/sessions", headers={"Authorization": "Bearer test"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"items": expected, "current_session_id": CURRENT}
    assert calls == [("POST", "rpc/list_my_auth_sessions", "verified-test-session", {"body": {"p_current_session_id": CURRENT}})]


def test_revoke_other_sessions_preserves_current_session(monkeypatch):
    calls = []

    async def db(method, path, token, **kwargs):
        calls.append((method, path, token, kwargs))
        return 2

    client = _client(monkeypatch, current_session_user, _session_user, db)
    try:
        response = client.post("/v1/me/sessions/revoke-others", headers={"Authorization": "Bearer test"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"revoked_count": 2}
    assert calls == [("POST", "rpc/revoke_my_other_auth_sessions", "verified-test-session", {"body": {"p_current_session_id": CURRENT}})]


def test_revoke_selected_session_uses_owner_scoped_rpc(monkeypatch):
    calls = []

    async def db(method, path, token, **kwargs):
        calls.append((method, path, token, kwargs))
        return True

    client = _client(monkeypatch, current_session_user, _session_user, db)
    try:
        response = client.post(f"/v1/me/sessions/{OTHER}/revoke", headers={"Authorization": "Bearer test"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"revoked": True}
    assert calls == [("POST", "rpc/revoke_my_auth_session", "verified-test-session", {"body": {"p_session_id": OTHER}})]


def test_revoke_selected_session_does_not_disclose_foreign_session(monkeypatch):
    async def db(method, path, token, **kwargs):
        return False

    client = _client(monkeypatch, current_session_user, _session_user, db)
    try:
        response = client.post(f"/v1/me/sessions/{OTHER}/revoke", headers={"Authorization": "Bearer test"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "SESSION_NOT_FOUND"

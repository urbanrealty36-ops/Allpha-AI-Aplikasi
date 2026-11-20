import uuid

from fastapi import HTTPException
from fastapi.testclient import TestClient

from allpha_api import live_api
from allpha_api.auth import current_user
from allpha_api.main import app

OWNER = "11111111-1111-4111-8111-111111111111"
SESSION = "22222222-2222-4222-8222-222222222222"


def _auth():
    return {"id": OWNER, "email": "live-host@example.invalid"}


def test_live_session_create_is_provider_neutral_and_idempotent(monkeypatch):
    captured = {}

    async def fake_rpc(name, payload):
        captured["name"] = name
        captured["payload"] = payload
        return {
            "outcome": "created",
            "session": {
                "id": SESSION, "host_user_id": OWNER, "title": "Stage",
                "status": "planned", "version": 1, "provider_key": None,
                "provider_session_ref": None,
            },
        }

    monkeypatch.setattr(live_api, "_rpc", fake_rpc)
    app.dependency_overrides[current_user] = lambda: _auth()
    try:
        response = TestClient(app).post("/v1/live/sessions", json={
            "title": "Stage", "visibility": "public", "idempotency_key": "live-create-001",
        })
    finally:
        app.dependency_overrides.pop(current_user, None)

    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["session"]["status"] == "planned"
    assert payload["media_plane"]["status"] == "not_configured"
    assert payload["media_plane"]["publish_subscribe_tokens_available"] is False
    assert payload["recording_provider_enabled"] is False
    assert captured["name"] == "create_live_session"
    assert captured["payload"]["p_host_user_id"] == OWNER


def test_live_transition_to_live_fails_closed_without_approved_media_provider(monkeypatch):
    async def fake_db(method, path, *, params=None, payload=None, prefer=None):
        if method == "GET" and path == "live_sessions":
            return [{
                "id": SESSION, "host_user_id": OWNER, "conversation_id": "33333333-3333-4333-8333-333333333333",
                "title": "Stage", "status": "preparing", "version": 2,
            }]
        if method == "GET" and path == "live_participants":
            return []
        raise AssertionError((method, path, params, payload))

    async def blocked_rpc(name, payload):
        assert name == "transition_live_session"
        assert payload["p_next_status"] == "live"
        raise HTTPException(409, detail={
            "code": "LIVE_MEDIA_PROVIDER_NOT_APPROVED",
            "message": "Provider approval required",
        })

    monkeypatch.setattr(live_api, "_db", fake_db)
    monkeypatch.setattr(live_api, "_rpc", blocked_rpc)
    app.dependency_overrides[current_user] = lambda: _auth()
    try:
        response = TestClient(app).post(f"/v1/live/sessions/{SESSION}/transition", json={
            "expected_version": 2, "next_status": "live", "reason": "host_start",
        })
    finally:
        app.dependency_overrides.pop(current_user, None)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "LIVE_MEDIA_PROVIDER_NOT_APPROVED"

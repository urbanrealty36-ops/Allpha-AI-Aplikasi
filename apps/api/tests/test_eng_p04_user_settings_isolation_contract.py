from fastapi import Request
from fastapi.testclient import TestClient

from allpha_api.auth import current_user
from allpha_api.main import app


def test_settings_reads_are_scoped_to_each_authenticated_identity_and_forward_its_jwt(monkeypatch):
    user_by_token = {
        "token-user-a": "00000000-0000-0000-0000-0000000000a1",
        "token-user-b": "00000000-0000-0000-0000-0000000000b2",
    }
    calls = []

    async def fake_current_user(request: Request):
        token = request.headers["Authorization"].removeprefix("Bearer ")
        request.state.supabase_access_token = token
        return {"id": user_by_token[token], "email": token + "@example.invalid"}

    async def fake_user_db_request(method, path, access_token, **kwargs):
        calls.append((method, path, access_token, kwargs))
        expected_user_id = user_by_token[access_token]
        assert method == "GET"
        assert path == "user_settings"
        assert kwargs["params"]["user_id"] == "eq." + expected_user_id
        return [{
            "user_id": expected_user_id,
            "theme": "system",
            "notification_preferences": {"security_alerts": True},
            "privacy_settings": {"discoverable_by_username": False},
            "updated_at": "2026-10-27T00:00:00Z",
        }]

    monkeypatch.setattr("allpha_api.main.user_db_request", fake_user_db_request)
    app.dependency_overrides[current_user] = fake_current_user
    client = TestClient(app)
    try:
        response_a = client.get("/v1/me/settings", headers={"Authorization": "Bearer token-user-a"})
        response_b = client.get("/v1/me/settings", headers={"Authorization": "Bearer token-user-b"})
    finally:
        app.dependency_overrides.clear()

    assert response_a.status_code == 200, response_a.text
    assert response_b.status_code == 200, response_b.text
    user_a = user_by_token["token-user-a"]
    user_b = user_by_token["token-user-b"]
    assert response_a.json()["settings"]["user_id"] == user_a
    assert response_b.json()["settings"]["user_id"] == user_b
    assert response_a.json()["settings"]["user_id"] != response_b.json()["settings"]["user_id"]
    assert [(call[0], call[1], call[2]) for call in calls] == [
        ("GET", "user_settings", "token-user-a"),
        ("GET", "user_settings", "token-user-b"),
    ]

import pytest
from pydantic import ValidationError
from fastapi.testclient import TestClient

from allpha_api.main import ProfileUpdate, UserSettingsUpdate, app

client = TestClient(app)


def test_identity_settings_endpoints_require_authentication():
    for path in ("/v1/me/settings", "/v1/me/consents"):
        response = client.get(path)
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "AUTH_REQUIRED"
    response = client.patch("/v1/me/settings", json={"theme": "dark"})
    assert response.status_code == 401
    response = client.post(
        "/v1/me/consents",
        json={"consent_type": "privacy_policy", "policy_version": "v1", "granted": True},
    )
    assert response.status_code == 401


def test_profile_update_cannot_change_authority_fields():
    with pytest.raises(ValidationError):
        ProfileUpdate.model_validate({"account_status": "active"})
    with pytest.raises(ValidationError):
        ProfileUpdate.model_validate({"role": "super_admin"})


def test_settings_payload_is_strict_and_typed():
    with pytest.raises(ValidationError):
        UserSettingsUpdate.model_validate({"theme": "neon"})
    with pytest.raises(ValidationError):
        UserSettingsUpdate.model_validate({"notification_preferences": {"security_alerts": "yes"}})
    with pytest.raises(ValidationError):
        UserSettingsUpdate.model_validate({"user_id": "another-user"})


def test_valid_settings_payload():
    value = UserSettingsUpdate.model_validate({
        "theme": "dark",
        "notification_preferences": {
            "product_updates": False,
            "security_alerts": True,
            "social_activity": False,
        },
        "privacy_settings": {"discoverable_by_username": False},
    })
    assert value.theme == "dark"
    assert value.notification_preferences.security_alerts is True
    assert value.privacy_settings.discoverable_by_username is False

def test_deactivation_uses_scoped_rpc_instead_of_direct_profile_update(monkeypatch):
    from fastapi import Request
    from allpha_api.auth import current_user

    calls = []

    async def fake_user_db_request(method, path, access_token, **kwargs):
        calls.append((method, path, access_token, kwargs))
        return [{
            "id": "human-123",
            "account_status": "deactivation_requested",
            "updated_at": "2026-10-14T00:00:00Z",
        }]

    async def fake_current_user(request: Request):
        request.state.supabase_access_token = "human-session-token"
        return {"id": "human-123", "email": "human@example.invalid"}

    monkeypatch.setattr("allpha_api.main.user_db_request", fake_user_db_request)
    app.dependency_overrides[current_user] = fake_current_user
    try:
        response = client.post("/v1/me/deactivation-request", headers={"Authorization": "Bearer test"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert calls[0][0:3] == ("POST", "rpc/request_account_deactivation", "human-session-token")
    assert calls[0][3]["body"] == {}
    assert response.json()["profile"]["id"] == "human-123"



def test_consent_payload_rejects_client_owned_identity_and_invalid_types():
    from allpha_api.main import ConsentCreate

    with pytest.raises(ValidationError):
        ConsentCreate.model_validate({
            "user_id": "another-user",
            "consent_type": "privacy_policy",
            "policy_version": "v1",
            "granted": True,
        })
    with pytest.raises(ValidationError):
        ConsentCreate.model_validate({
            "consent_type": "admin_override",
            "policy_version": "v1",
            "granted": True,
        })


def test_consent_record_is_bound_to_authenticated_user_and_immutable_insert(monkeypatch):
    from fastapi import Request
    from allpha_api.auth import current_user

    calls = []

    async def fake_user_db_request(method, path, access_token, **kwargs):
        calls.append((method, path, access_token, kwargs))
        return [{
            "consent_type": "privacy_policy",
            "policy_version": "v1.2",
            "granted": True,
            "recorded_at": "2026-10-14T00:00:00Z",
        }]

    async def fake_current_user(request: Request):
        request.state.supabase_access_token = "consent-session-token"
        return {"id": "human-123", "email": "human@example.invalid"}

    monkeypatch.setattr("allpha_api.main.user_db_request", fake_user_db_request)
    app.dependency_overrides[current_user] = fake_current_user
    try:
        response = client.post(
            "/v1/me/consents",
            headers={"Authorization": "Bearer test"},
            json={"consent_type": "privacy_policy", "policy_version": "v1.2", "granted": True},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201
    assert calls[0][0:3] == ("POST", "user_consents", "consent-session-token")
    assert calls[0][3]["body"] == {
        "user_id": "human-123",
        "consent_type": "privacy_policy",
        "policy_version": "v1.2",
        "granted": True,
    }
    assert calls[0][3]["prefer"] == "return=representation"



def test_social_graph_endpoints_require_authentication():
    assert client.get("/v1/me/social-graph").status_code == 401
    assert client.get("/v1/me/interests").status_code == 401
    assert client.post(
        "/v1/me/social-edges",
        json={"target_user_id": "00000000-0000-0000-0000-000000000002", "edge_type": "follow"},
    ).status_code == 401
    assert client.put(
        "/v1/me/interests",
        json={"interest_key": "ai", "preference": "interested"},
    ).status_code == 401


def test_social_edge_payload_is_strict_and_supported_types_only():
    from allpha_api.main import SocialEdgeCreate

    with pytest.raises(ValidationError):
        SocialEdgeCreate.model_validate({
            "target_user_id": "00000000-0000-0000-0000-000000000002",
            "edge_type": "friend",
        })
    with pytest.raises(ValidationError):
        SocialEdgeCreate.model_validate({
            "target_user_id": "00000000-0000-0000-0000-000000000002",
            "edge_type": "follow",
            "actor_user_id": "00000000-0000-0000-0000-000000000003",
        })


def test_social_edge_uses_authenticated_actor_and_validated_target(monkeypatch):
    from fastapi import Request
    from allpha_api.auth import current_user

    calls = []

    async def fake_user_db_request(method, path, access_token, **kwargs):
        calls.append((method, path, access_token, kwargs))
        return [{
            "id": "edge-123",
            "target_user_id": "00000000-0000-0000-0000-000000000002",
            "edge_type": "follow",
            "status": "active",
            "created_at": "2026-10-14T00:00:00Z",
        }]

    async def fake_current_user(request: Request):
        request.state.supabase_access_token = "social-session-token"
        return {"id": "human-123", "email": "human@example.invalid"}

    monkeypatch.setattr("allpha_api.main.user_db_request", fake_user_db_request)
    app.dependency_overrides[current_user] = fake_current_user
    try:
        response = client.post(
            "/v1/me/social-edges",
            headers={"Authorization": "Bearer test"},
            json={"target_user_id": "00000000-0000-0000-0000-000000000002", "edge_type": "follow"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201
    assert calls[0][0:3] == ("POST", "social_edges", "social-session-token")
    assert calls[0][3]["body"] == {
        "actor_user_id": "human-123",
        "target_user_id": "00000000-0000-0000-0000-000000000002",
        "edge_type": "follow",
    }


def test_social_edge_rejects_self_target(monkeypatch):
    from fastapi import Request
    from allpha_api.auth import current_user

    async def fake_current_user(request: Request):
        request.state.supabase_access_token = "social-session-token"
        return {"id": "00000000-0000-0000-0000-000000000001"}

    app.dependency_overrides[current_user] = fake_current_user
    try:
        response = client.post(
            "/v1/me/social-edges",
            headers={"Authorization": "Bearer test"},
            json={"target_user_id": "00000000-0000-0000-0000-000000000001", "edge_type": "block"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "SOCIAL_EDGE_SELF_TARGET"


def test_interest_preference_is_bound_to_authenticated_user(monkeypatch):
    from fastapi import Request
    from allpha_api.auth import current_user

    calls = []

    async def fake_user_db_request(method, path, access_token, **kwargs):
        calls.append((method, path, access_token, kwargs))
        return [{
            "interest_key": "ai.social",
            "preference": "not_interested",
            "created_at": "2026-10-14T00:00:00Z",
            "updated_at": "2026-10-14T00:00:00Z",
        }]

    async def fake_current_user(request: Request):
        request.state.supabase_access_token = "interest-session-token"
        return {"id": "human-123"}

    monkeypatch.setattr("allpha_api.main.user_db_request", fake_user_db_request)
    app.dependency_overrides[current_user] = fake_current_user
    try:
        response = client.put(
            "/v1/me/interests",
            headers={"Authorization": "Bearer test"},
            json={"interest_key": "ai.social", "preference": "not_interested"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert calls[0][0:3] == ("POST", "user_interests", "interest-session-token")
    assert calls[0][3]["body"] == {
        "user_id": "human-123",
        "interest_key": "ai.social",
        "preference": "not_interested",
    }
    assert calls[0][3]["prefer"] == "resolution=merge-duplicates,return=representation"



def test_follow_request_accept_is_scoped_to_authenticated_target(monkeypatch):
    from fastapi import Request
    from allpha_api.auth import current_user

    calls = []

    async def fake_user_db_request(method, path, access_token, **kwargs):
        calls.append((method, path, access_token, kwargs))
        return [{
            "id": "edge-123",
            "actor_user_id": "human-sender",
            "target_user_id": "human-recipient",
            "edge_type": "follow",
            "status": "active",
            "created_at": "2026-10-14T00:00:00Z",
        }]

    async def fake_current_user(request: Request):
        request.state.supabase_access_token = "recipient-session-token"
        return {"id": "human-recipient"}

    monkeypatch.setattr("allpha_api.main.user_db_request", fake_user_db_request)
    app.dependency_overrides[current_user] = fake_current_user
    try:
        response = client.post(
            "/v1/me/follow-requests/00000000-0000-0000-0000-000000000123/accept",
            headers={"Authorization": "Bearer test"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert calls[0][0:3] == ("PATCH", "social_edges", "recipient-session-token")
    assert calls[0][3]["params"]["target_user_id"] == "eq.human-recipient"
    assert calls[0][3]["params"]["status"] == "eq.requested"
    assert calls[0][3]["body"] == {"status": "active"}

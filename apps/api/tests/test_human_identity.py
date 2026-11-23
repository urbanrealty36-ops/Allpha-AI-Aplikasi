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


def test_consent_record_uses_service_only_append_only_rpc_and_verified_actor(monkeypatch):
    from fastapi import Request
    from allpha_api.auth import current_user

    monkeypatch.setenv("ALLPHA_POLICY_VERSION_PRIVACY_POLICY", "v1.2")
    calls = []

    async def fake_service_db_request(function_name, *, body):
        calls.append((function_name, body))
        return [{
            "id": "consent-event-1",
            "user_id": "human-123",
            "consent_type": "privacy_policy",
            "policy_version": "v1.2",
            "decision": "granted",
            "source": "account_settings",
            "idempotency_key": "consent-test-0001",
            "recorded_at": "2026-10-14T00:00:00Z",
        }]

    async def fake_current_user(request: Request):
        request.state.supabase_access_token = "consent-session-token"
        return {"id": "human-123", "email": "human@example.invalid"}

    monkeypatch.setattr("allpha_api.main.service_db_request", fake_service_db_request)
    app.dependency_overrides[current_user] = fake_current_user
    try:
        response = client.post(
            "/v1/me/consents",
            headers={"Authorization": "Bearer test", "Idempotency-Key": "consent-test-0001"},
            json={"consent_type": "privacy_policy", "policy_version": "v1.2", "granted": True},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201
    assert calls[0][0] == "record_account_consent_event_for_actor"
    assert calls[0][1] == {
        "p_actor_user_id": "human-123",
        "p_consent_type": "privacy_policy",
        "p_policy_version": "v1.2",
        "p_decision": "granted",
        "p_source": "account_settings",
        "p_idempotency_key": "consent-test-0001",
    }


def test_consent_history_reads_owner_events_and_server_policy_versions(monkeypatch):
    from fastapi import Request
    from allpha_api.auth import current_user

    monkeypatch.setenv("ALLPHA_POLICY_VERSION_TERMS_OF_SERVICE", "tos-2026-11")
    monkeypatch.setenv("ALLPHA_POLICY_VERSION_PRIVACY_POLICY", "privacy-2026-11")
    monkeypatch.delenv("ALLPHA_POLICY_VERSION_PRODUCT_UPDATES", raising=False)
    calls = []

    async def fake_user_db_request(method, path, access_token, **kwargs):
        calls.append((method, path, access_token, kwargs))
        return [{
            "id": "event-1",
            "consent_type": "product_updates",
            "policy_version": "v2",
            "decision": "revoked",
            "source": "account_settings",
            "idempotency_key": "event-idempotency-1",
            "recorded_at": "2026-11-23T00:00:00Z",
        }]

    async def fake_current_user(request: Request):
        request.state.supabase_access_token = "consent-session-token"
        return {"id": "human-123", "email": "human@example.invalid"}

    monkeypatch.setattr("allpha_api.main.user_db_request", fake_user_db_request)
    app.dependency_overrides[current_user] = fake_current_user
    try:
        response = client.get("/v1/me/consents", headers={"Authorization": "Bearer test"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert calls[0][0:3] == ("GET", "user_consent_events", "consent-session-token")
    assert calls[0][3]["params"]["user_id"] == "eq.human-123"
    assert response.json()["items"][0]["decision"] == "revoked"
    assert response.json()["current_policy_versions"] == {
        "terms_of_service": "tos-2026-11",
        "privacy_policy": "privacy-2026-11",
        "product_updates": None,
    }


def test_consent_rejects_client_invented_policy_version_without_database_write(monkeypatch):
    from fastapi import Request
    from allpha_api.auth import current_user

    monkeypatch.delenv("ALLPHA_POLICY_VERSION_PRIVACY_POLICY", raising=False)
    calls = []

    async def fake_service_db_request(function_name, *, body):
        calls.append((function_name, body))
        raise AssertionError("consent must fail closed before database write")

    async def fake_current_user(request: Request):
        request.state.supabase_access_token = "consent-session-token"
        return {"id": "human-123", "email": "human@example.invalid"}

    monkeypatch.setattr("allpha_api.main.service_db_request", fake_service_db_request)
    app.dependency_overrides[current_user] = fake_current_user
    try:
        response = client.post(
            "/v1/me/consents",
            headers={"Authorization": "Bearer test"},
            json={"consent_type": "privacy_policy", "policy_version": "v99-client-invented", "granted": True},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "CONSENT_POLICY_NOT_CONFIGURED"
    assert calls == []


def test_required_policy_consent_cannot_be_revoked_through_optional_controls(monkeypatch):
    from fastapi import Request
    from allpha_api.auth import current_user

    monkeypatch.setenv("ALLPHA_POLICY_VERSION_PRIVACY_POLICY", "v1.2")
    calls = []

    async def fake_service_db_request(function_name, *, body):
        calls.append((function_name, body))
        raise AssertionError("required policy withdrawal must fail before persistence")

    async def fake_current_user(request: Request):
        request.state.supabase_access_token = "consent-session-token"
        return {"id": "human-123", "email": "human@example.invalid"}

    monkeypatch.setattr("allpha_api.main.service_db_request", fake_service_db_request)
    app.dependency_overrides[current_user] = fake_current_user
    try:
        response = client.post(
            "/v1/me/consents",
            headers={"Authorization": "Bearer test"},
            json={"consent_type": "privacy_policy", "policy_version": "v1.2", "granted": False},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "REQUIRED_POLICY_WITHDRAWAL_NOT_SUPPORTED"
    assert calls == []


def test_product_updates_consent_can_be_revoked_with_append_only_event(monkeypatch):
    from fastapi import Request
    from allpha_api.auth import current_user

    monkeypatch.setenv("ALLPHA_POLICY_VERSION_PRODUCT_UPDATES", "v2.0")
    calls = []

    async def fake_service_db_request(function_name, *, body):
        calls.append((function_name, body))
        return [{"decision": "revoked", "consent_type": "product_updates", "policy_version": "v2.0"}]

    async def fake_current_user(request: Request):
        request.state.supabase_access_token = "consent-session-token"
        return {"id": "human-123", "email": "human@example.invalid"}

    monkeypatch.setattr("allpha_api.main.service_db_request", fake_service_db_request)
    app.dependency_overrides[current_user] = fake_current_user
    try:
        response = client.post(
            "/v1/me/consents",
            headers={"Authorization": "Bearer test", "Idempotency-Key": "consent-revoke-0001"},
            json={"consent_type": "product_updates", "policy_version": "v2.0", "granted": False},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201
    assert calls[0][1]["p_decision"] == "revoked"
    assert calls[0][1]["p_actor_user_id"] == "human-123"


def test_consent_rejects_stale_policy_version_without_database_write(monkeypatch):
    from fastapi import Request
    from allpha_api.auth import current_user

    monkeypatch.setenv("ALLPHA_POLICY_VERSION_PRIVACY_POLICY", "v1.3")
    calls = []

    async def fake_service_db_request(function_name, *, body):
        calls.append((function_name, body))
        raise AssertionError("stale consent must fail before database write")

    async def fake_current_user(request: Request):
        request.state.supabase_access_token = "consent-session-token"
        return {"id": "human-123", "email": "human@example.invalid"}

    monkeypatch.setattr("allpha_api.main.service_db_request", fake_service_db_request)
    app.dependency_overrides[current_user] = fake_current_user
    try:
        response = client.post(
            "/v1/me/consents",
            headers={"Authorization": "Bearer test"},
            json={"consent_type": "privacy_policy", "policy_version": "v1.2", "granted": True},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "CONSENT_POLICY_VERSION_MISMATCH"
    assert calls == []



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

    reads = []
    service_calls = []
    target_id = "00000000-0000-0000-0000-000000000002"

    async def fake_user_db_request(method, path, access_token, **kwargs):
        reads.append((method, path, access_token, kwargs))
        if method == "GET" and path == "social_edges":
            return []
        if method == "GET" and path == "profiles":
            return [{"id": target_id, "visibility": "public", "account_status": "active"}]
        raise AssertionError(f"unexpected read: {method} {path}")

    async def fake_service_db_request(function_name, *, body):
        service_calls.append((function_name, body))
        return [{
            "id": "edge-123", "actor_user_id": body["p_actor_user_id"],
            "target_user_id": target_id, "edge_type": "follow", "status": "active",
            "created_at": "2026-10-14T00:00:00Z",
        }]

    async def fake_current_user(request: Request):
        request.state.supabase_access_token = "social-session-token"
        return {"id": "human-123", "email": "human@example.invalid"}

    monkeypatch.setattr("allpha_api.main.user_db_request", fake_user_db_request)
    monkeypatch.setattr("allpha_api.main.service_db_request", fake_service_db_request)
    app.dependency_overrides[current_user] = fake_current_user
    try:
        response = client.post(
            "/v1/me/social-edges",
            headers={"Authorization": "Bearer test"},
            json={"target_user_id": target_id, "edge_type": "follow"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201
    assert response.json()["edge"]["target_user_id"] == target_id
    assert response.json()["idempotent_replay"] is False
    assert all(call[0] == "GET" for call in reads)
    assert service_calls[0][0] == "create_social_edge_for_actor"
    assert service_calls[0][1]["p_actor_user_id"] == "human-123"
    assert service_calls[0][1]["p_target_user_id"] == target_id


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


def test_interest_preference_uses_authenticated_actor_and_server_only_catalog_rpc(monkeypatch):
    from fastapi import Request
    from allpha_api.auth import current_user

    calls = []

    async def fake_service_db_request(function_name, *, body):
        calls.append((function_name, body))
        return [{
            "interest_key": "technology",
            "preference": "not_interested",
            "created_at": "2026-10-14T00:00:00Z",
            "updated_at": "2026-10-14T00:00:00Z",
        }]

    async def fake_current_user(request: Request):
        request.state.supabase_access_token = "interest-session-token"
        return {"id": "human-123"}

    monkeypatch.setattr("allpha_api.interest_graph_api.service_db_request", fake_service_db_request)
    app.dependency_overrides[current_user] = fake_current_user
    try:
        response = client.put(
            "/v1/me/interests",
            headers={"Authorization": "Bearer test"},
            json={"interest_key": "IT & Teknologi", "preference": "not_interested"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert calls == [(
        "set_my_interest_preference_for_actor",
        {
            "p_actor_user_id": "human-123",
            "p_interest_key": "IT & Teknologi",
            "p_preference": "not_interested",
        },
    )]
    assert response.json()["item"]["interest_key"] == "technology"



def test_interest_catalog_is_served_from_canonical_database(monkeypatch):
    calls = []

    async def fake_user_db_request(method, path, access_token, **kwargs):
        calls.append((method, path, access_token, kwargs))
        if path == "interest_catalog":
            return [{"interest_key": "health", "label": "Kesehatan", "label_key": "auth.interest.health", "category": "wellbeing"}]
        if path == "interest_taxonomy_edges":
            return []
        raise AssertionError(path)

    monkeypatch.setattr("allpha_api.interest_graph_api.user_db_request", fake_user_db_request)
    response = client.get("/v1/interests/catalog")

    assert response.status_code == 200
    assert calls[0][0:3] == ("GET", "interest_catalog", None)
    assert response.json()["items"][0]["interest_key"] == "health"
    assert response.json()["relationships"] == []


def test_interest_delete_uses_server_only_actor_rpc(monkeypatch):
    from fastapi import Request
    from allpha_api.auth import current_user

    calls = []

    async def fake_service_db_request(function_name, *, body):
        calls.append((function_name, body))
        return [{"interest_key": "technology"}]

    async def fake_current_user(request: Request):
        request.state.supabase_access_token = "interest-session-token"
        return {"id": "human-123"}

    monkeypatch.setattr("allpha_api.interest_graph_api.service_db_request", fake_service_db_request)
    app.dependency_overrides[current_user] = fake_current_user
    try:
        response = client.delete("/v1/me/interests/technology", headers={"Authorization": "Bearer test"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert calls == [("delete_my_interest_for_actor", {
        "p_actor_user_id": "human-123",
        "p_interest_key": "technology",
    })]


def test_privacy_patch_preserves_existing_interest_matching_flag(monkeypatch):
    from fastapi import Request
    from allpha_api.auth import current_user

    calls = []

    async def fake_user_db_request(method, path, access_token, **kwargs):
        calls.append((method, path, kwargs))
        if method == "GET":
            return [{"privacy_settings": {"discoverable_by_username": True, "allow_interest_matching": True}}]
        return [{"user_id": "human-123", "privacy_settings": kwargs["body"]["privacy_settings"]}]

    async def fake_current_user(request: Request):
        request.state.supabase_access_token = "settings-session-token"
        return {"id": "human-123"}

    monkeypatch.setattr("allpha_api.main.user_db_request", fake_user_db_request)
    app.dependency_overrides[current_user] = fake_current_user
    try:
        response = client.patch(
            "/v1/me/settings",
            headers={"Authorization": "Bearer test"},
            json={"privacy_settings": {"allow_interest_matching": False}},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    patch_call = next(call for call in calls if call[0] == "PATCH")
    assert patch_call[2]["body"]["privacy_settings"] == {
        "discoverable_by_username": True,
        "allow_interest_matching": False,
    }


def test_interest_matching_requires_public_discovery_permission(monkeypatch):
    from fastapi import Request
    from allpha_api.auth import current_user

    async def fake_user_db_request(method, path, access_token, **kwargs):
        return [{"privacy_settings": {"discoverable_by_username": False, "allow_interest_matching": False}}]

    async def fake_current_user(request: Request):
        request.state.supabase_access_token = "settings-session-token"
        return {"id": "human-123"}

    monkeypatch.setattr("allpha_api.main.user_db_request", fake_user_db_request)
    app.dependency_overrides[current_user] = fake_current_user
    try:
        response = client.patch(
            "/v1/me/settings",
            headers={"Authorization": "Bearer test"},
            json={"privacy_settings": {"allow_interest_matching": True}},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INTEREST_MATCHING_REQUIRES_DISCOVERABILITY"


def test_interest_matching_requires_active_public_profile(monkeypatch):
    from fastapi import Request
    from allpha_api.auth import current_user

    calls = []

    async def fake_user_db_request(method, path, access_token, **kwargs):
        calls.append((method, path, kwargs))
        if path == "user_settings":
            return [{"privacy_settings": {"discoverable_by_username": True, "allow_interest_matching": False}}]
        if path == "profiles":
            return [{"visibility": "private", "account_status": "active"}]
        raise AssertionError((method, path, kwargs))

    async def fake_current_user(request: Request):
        request.state.supabase_access_token = "settings-session-token"
        return {"id": "human-123"}

    monkeypatch.setattr("allpha_api.main.user_db_request", fake_user_db_request)
    app.dependency_overrides[current_user] = fake_current_user
    try:
        response = client.patch(
            "/v1/me/settings",
            headers={"Authorization": "Bearer test"},
            json={"privacy_settings": {"allow_interest_matching": True}},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INTEREST_MATCHING_REQUIRES_PUBLIC_PROFILE"
    assert not any(call[0] == "PATCH" for call in calls)


def test_follow_request_accept_is_scoped_to_authenticated_target(monkeypatch):
    from fastapi import Request
    from allpha_api.auth import current_user

    service_calls = []
    edge_id = "00000000-0000-0000-0000-000000000303"

    async def fake_service_db_request(function_name, *, body):
        service_calls.append((function_name, body))
        return [{"id": edge_id, "actor_user_id": "requester", "target_user_id": "human-123",
                 "edge_type": "follow", "status": "active"}]

    async def fake_current_user(request: Request):
        request.state.supabase_access_token = "social-session-token"
        return {"id": "human-123", "email": "human@example.invalid"}

    monkeypatch.setattr("allpha_api.main.service_db_request", fake_service_db_request)
    app.dependency_overrides[current_user] = fake_current_user
    try:
        response = client.post(
            f"/v1/me/follow-requests/{edge_id}/accept",
            headers={"Authorization": "Bearer test"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert service_calls == [("accept_social_follow_for_actor", {"p_actor_user_id": "human-123", "p_edge_id": edge_id})]



def test_first_authenticated_profile_read_provisions_profile_before_account_guard(monkeypatch):
    """A verified new Supabase session must be able to create its own profile."""
    from fastapi import Request
    from allpha_api.auth import current_session_user

    calls = []
    profile = {
        "id": "human-new",
        "username": "new-human",
        "display_name": "New Human",
        "avatar_url": None,
        "bio": "",
        "visibility": "public",
        "locale": "id-ID",
        "account_status": "active",
    }

    async def fake_session_user(request: Request):
        request.state.supabase_access_token = "verified-new-session"
        return {
            "id": "human-new",
            "email": "new-human@example.invalid",
            "user_metadata": {"display_name": "New Human", "locale": "id-ID"},
        }

    async def fake_user_db_request(method, path, access_token, **kwargs):
        calls.append((method, path, access_token, kwargs))
        if method == "GET" and path == "profiles":
            return []
        if method == "POST" and path == "profiles":
            return [profile]
        raise AssertionError(f"unexpected database operation: {method} {path}")

    monkeypatch.setattr("allpha_api.main.user_db_request", fake_user_db_request)
    app.dependency_overrides[current_session_user] = fake_session_user
    try:
        response = client.get("/v1/me", headers={"Authorization": "Bearer verified-new-session"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["profile"]["id"] == "human-new"
    assert [call[:3] for call in calls] == [
        ("GET", "profiles", "verified-new-session"),
        ("POST", "profiles", "verified-new-session"),
    ]
    assert calls[1][3]["body"] == {
        "id": "human-new",
        "display_name": "New Human",
        "locale": "id-ID",
    }

import pytest
from pydantic import ValidationError
from fastapi import HTTPException, Request
from fastapi.testclient import TestClient

from allpha_api.auth import current_session_user, current_user, user_db_request
from allpha_api.main import OrganizationCreate, ProfileUpdate, app

client = TestClient(app)


def test_authenticated_routes_reject_missing_bearer_token():
    for path in ("/v1/me", "/v1/organizations", "/v1/organizations/00000000-0000-4000-8000-000000000001/memberships"):
        response = client.get(path)
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "AUTH_REQUIRED"


def test_ready_reports_supabase_configuration_without_exposing_secrets(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_PUBLISHABLE_KEY", raising=False)
    response = client.get("/readyz")
    assert response.status_code == 503
    payload = response.json()
    assert payload["status"] == "not_ready"
    assert payload["dependencies"]["database"]["status"] == "not_configured"
    assert "SUPABASE" not in response.text


def test_ready_requires_live_supabase_auth_and_postgrest(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://staging-example.supabase.co")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "sb_publishable_test_only")

    class FakeResponse:
        def __init__(self, status_code):
            self.status_code = status_code

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            self.calls = []

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url, **kwargs):
            self.calls.append(url)
            if url.endswith("/auth/v1/health"):
                return FakeResponse(200)
            if url.endswith("/rest/v1/agent_ownerships?select=agent_id&limit=0"):
                return FakeResponse(503)
            raise AssertionError(f"Unexpected readiness probe URL: {url}")

    monkeypatch.setattr("allpha_api.main.httpx.AsyncClient", FakeAsyncClient)
    response = client.get("/readyz")

    assert response.status_code == 503
    payload = response.json()
    assert payload["status"] == "not_ready"
    assert payload["dependencies"]["authentication"]["status"] == "reachable"
    assert payload["dependencies"]["database"]["status"] == "unavailable"
    assert "staging-example" not in response.text
    assert "sb_publishable_test_only" not in response.text


def test_ready_returns_ready_only_when_auth_and_postgrest_respond(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://staging-example.supabase.co")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "sb_publishable_test_only")

    class FakeResponse:
        status_code = 200

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url, **kwargs):
            assert url.endswith(("/auth/v1/health", "/rest/v1/agent_ownerships?select=agent_id&limit=0"))
            assert kwargs["headers"] == {"apikey": "sb_publishable_test_only"}
            return FakeResponse()

    monkeypatch.setattr("allpha_api.main.httpx.AsyncClient", FakeAsyncClient)
    response = client.get("/readyz")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ready"
    assert payload["dependencies"]["authentication"]["status"] == "reachable"
    assert payload["dependencies"]["database"]["status"] == "reachable"
    assert payload["dependencies"]["object_storage"]["status"] == "not_checked"
    assert payload["dependencies"]["ai_gateway"]["status"] == "not_checked"


def test_profile_payload_rejects_authority_fields():
    with pytest.raises(ValidationError):
        ProfileUpdate.model_validate({"role": "super_admin"})


def test_create_organization_uses_authenticated_identity(monkeypatch):
    calls = []

    async def fake_service_db_request(function_name, *, body):
        calls.append((function_name, body))
        return [{"id": "org-1", "name": "Test Org", "slug": "test-org", "owner_id": "user-123"}]

    async def fake_current_user(request: Request):
        request.state.supabase_access_token = "test-token"
        return {"id": "user-123", "email": "test@example.invalid"}

    monkeypatch.setattr("allpha_api.main.service_db_request", fake_service_db_request)
    app.dependency_overrides[current_user] = fake_current_user
    try:
        response = client.post(
            "/v1/organizations",
            headers={"Authorization": "Bearer test-token"},
            json={"name": "Test Org", "slug": "test-org"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201
    assert calls == [("create_organization_for_user", {"p_actor_user_id": "user-123", "p_name": "Test Org", "p_slug": "test-org"})]
    assert "owner_id" not in response.request.content.decode()


def test_profile_update_schema_rejects_invalid_visibility():
    with pytest.raises(ValidationError):
        ProfileUpdate.model_validate({"visibility": "world"})



def test_organization_create_rejects_client_authority_fields():
    with pytest.raises(ValidationError):
        OrganizationCreate.model_validate({
            "name": "Tenant Test",
            "slug": "tenant-test",
            "owner_id": "00000000-0000-4000-8000-000000000001",
        })
    with pytest.raises(ValidationError):
        OrganizationCreate.model_validate({
            "name": "Tenant Test",
            "slug": "tenant-test",
            "tenant_id": "00000000-0000-4000-8000-000000000001",
        })

def test_invalid_supabase_bearer_token_is_rejected(monkeypatch):
    class FakeResponse:
        status_code = 401

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, *args, **kwargs):
            return FakeResponse()

    monkeypatch.setenv("SUPABASE_URL", "https://staging-example.supabase.co")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "sb_publishable_test_only")
    monkeypatch.setattr("allpha_api.auth.httpx.AsyncClient", FakeAsyncClient)

    response = client.get("/v1/me", headers={"Authorization": "Bearer definitely-invalid"})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_TOKEN"
    assert "definitely-invalid" not in response.text

def test_expired_supabase_bearer_token_is_rejected(monkeypatch):
    class FakeResponse:
        status_code = 403

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, *args, **kwargs):
            return FakeResponse()

    monkeypatch.setenv("SUPABASE_URL", "https://staging-example.supabase.co")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "sb_publishable_test_only")
    monkeypatch.setattr("allpha_api.auth.httpx.AsyncClient", FakeAsyncClient)

    response = client.get("/v1/organizations", headers={"Authorization": "Bearer expired-token-fixture"})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_TOKEN"
    assert "expired-token-fixture" not in response.text


def test_membership_lookup_with_manipulated_cross_tenant_id_returns_not_found(monkeypatch):
    from fastapi import Request
    from allpha_api.auth import current_user
    import uuid

    foreign_organization_id = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    calls = []

    async def fake_user_db_request(method, path, access_token, **kwargs):
        calls.append((method, path, access_token, kwargs))
        return []

    async def fake_current_user(request: Request):
        request.state.supabase_access_token = "tenant-b-token"
        request.state.user_id = "tenant-b-user"
        return {"id": "tenant-b-user", "email": "tenant-b@example.invalid"}

    monkeypatch.setattr("allpha_api.auth.user_db_request", fake_user_db_request)
    app.dependency_overrides[current_user] = fake_current_user
    try:
        response = client.get(
            f"/v1/organizations/{foreign_organization_id}/memberships",
            headers={"Authorization": "Bearer tenant-b-session"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ORGANIZATION_NOT_FOUND"
    assert len(calls) == 1
    assert calls[0][0:3] == ("GET", "organization_memberships", "tenant-b-token")
    assert calls[0][3]["params"]["organization_id"] == f"eq.{foreign_organization_id}"
    assert calls[0][3]["params"]["user_id"] == "eq.tenant-b-user"

def test_profile_update_is_self_scoped_and_rejects_server_owned_fields(monkeypatch):
    calls = []

    async def fake_user_db_request(method, path, access_token, **kwargs):
        calls.append((method, path, access_token, kwargs))
        return [{"id": "authenticated-user", "display_name": "Updated"}]

    async def fake_current_user(request: Request):
        request.state.supabase_access_token = "scoped-test-token"
        return {"id": "authenticated-user", "email": "user@example.invalid"}

    monkeypatch.setattr("allpha_api.main.user_db_request", fake_user_db_request)
    app.dependency_overrides[current_user] = fake_current_user
    try:
        response = client.patch(
            "/v1/me/profile",
            headers={"Authorization": "Bearer scoped-test-token"},
            json={"display_name": "Updated", "id": "another-user", "account_status": "active"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
    assert calls == []

def test_profile_update_query_is_scoped_to_authenticated_user(monkeypatch):
    calls = []

    async def fake_user_db_request(method, path, access_token, **kwargs):
        calls.append((method, path, access_token, kwargs))
        return [{"id": "authenticated-user", "display_name": "My profile"}]

    async def fake_current_user(request: Request):
        request.state.supabase_access_token = "scoped-test-token"
        return {"id": "authenticated-user", "email": "user@example.invalid"}

    monkeypatch.setattr("allpha_api.main.user_db_request", fake_user_db_request)
    app.dependency_overrides[current_user] = fake_current_user
    try:
        response = client.patch(
            "/v1/me/profile",
            headers={"Authorization": "Bearer scoped-test-token"},
            json={"display_name": "My profile"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert calls == [(
        "PATCH",
        "profiles",
        "scoped-test-token",
        {
            "params": {
                "id": "eq.authenticated-user",
                "select": "id,username,display_name,avatar_url,bio,visibility,locale,created_at,updated_at",
            },
            "body": {"display_name": "My profile"},
            "prefer": "return=representation",
        },
    )]


def test_social_graph_includes_incoming_follow_requests_scoped_to_authenticated_user(monkeypatch):
    calls = []

    async def fake_user_db_request(method, path, access_token, **kwargs):
        calls.append((method, path, access_token, kwargs))
        if path == "social_edges" and kwargs.get("params", {}).get("status") == "eq.requested":
            return [{"id": "request-1", "actor_user_id": "follower-1", "edge_type": "follow", "status": "requested"}]
        return []

    async def fake_current_user(request: Request):
        request.state.supabase_access_token = "social-test-token"
        return {"id": "recipient-user", "email": "recipient@example.invalid"}

    monkeypatch.setattr("allpha_api.main.user_db_request", fake_user_db_request)
    app.dependency_overrides[current_user] = fake_current_user
    try:
        response = client.get(
            "/v1/me/social-graph",
            headers={"Authorization": "Bearer social-test-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["incoming_requests"] == [
        {"id": "request-1", "actor_user_id": "follower-1", "edge_type": "follow", "status": "requested"}
    ]
    request_call = next(call for call in calls if call[1] == "social_edges" and call[3]["params"].get("status") == "eq.requested")
    assert request_call[0] == "GET"
    assert request_call[2] == "social-test-token"
    assert request_call[3]["params"]["target_user_id"] == "eq.recipient-user"
    assert request_call[3]["params"]["edge_type"] == "eq.follow"
    assert request_call[3]["params"]["status"] == "eq.requested"


def test_social_graph_requires_authentication():
    response = client.get("/v1/me/social-graph")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH_REQUIRED"


def test_social_graph_reads_are_scoped_to_authenticated_identity(monkeypatch):
    calls = []

    async def fake_user_db_request(method, path, access_token, **kwargs):
        calls.append((method, path, access_token, kwargs))
        return []

    async def fake_current_user(request: Request):
        request.state.supabase_access_token = "social-scope-token"
        return {"id": "authenticated-social-user", "email": "social@example.invalid"}

    monkeypatch.setattr("allpha_api.main.user_db_request", fake_user_db_request)
    app.dependency_overrides[current_user] = fake_current_user
    try:
        response = client.get(
            "/v1/me/social-graph",
            headers={"Authorization": "Bearer social-scope-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert len(calls) == 5
    assert all(call[2] == "social-scope-token" for call in calls)
    assert calls[0][1] == "social_edges"
    assert calls[0][3]["params"]["actor_user_id"] == "eq.authenticated-social-user"
    assert calls[1][3]["params"]["target_user_id"] == "eq.authenticated-social-user"
    assert calls[1][3]["params"]["edge_type"] == "eq.follow"
    assert calls[1][3]["params"]["status"] == "eq.active"
    assert calls[2][3]["params"]["target_user_id"] == "eq.authenticated-social-user"
    assert calls[2][3]["params"]["edge_type"] == "eq.block"
    assert calls[3][3]["params"]["target_user_id"] == "eq.authenticated-social-user"
    assert calls[3][3]["params"]["edge_type"] == "eq.follow"
    assert calls[3][3]["params"]["status"] == "eq.requested"
    assert calls[4][1] == "user_interests"
    assert calls[4][3]["params"]["user_id"] == "eq.authenticated-social-user"


def test_membership_lookup_for_authorized_user_uses_session_token_and_org_scope(monkeypatch):
    organization_id = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
    membership = {
        "organization_id": organization_id,
        "user_id": "tenant-a-user",
        "role": "owner",
        "invited_by": "tenant-a-user",
        "created_at": "2026-10-14T00:00:00Z",
    }
    calls = []

    async def fake_user_db_request(method, path, access_token, **kwargs):
        calls.append((method, path, access_token, kwargs))
        assert path == "organization_memberships"
        return [membership]

    async def fake_current_user(request: Request):
        request.state.supabase_access_token = "tenant-a-session-token"
        request.state.user_id = "tenant-a-user"
        return {"id": "tenant-a-user", "email": "tenant-a@example.invalid"}

    monkeypatch.setattr("allpha_api.auth.user_db_request", fake_user_db_request)
    monkeypatch.setattr("allpha_api.main.user_db_request", fake_user_db_request)
    app.dependency_overrides[current_user] = fake_current_user
    try:
        response = client.get(
            f"/v1/organizations/{organization_id}/memberships",
            headers={"Authorization": "Bearer tenant-a-session-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"items": [membership]}
    assert len(calls) == 2
    method, path, access_token, kwargs = calls[0]
    assert (method, path, access_token) == (
        "GET",
        "organization_memberships",
        "tenant-a-session-token",
    )
    assert kwargs["params"]["organization_id"] == f"eq.{organization_id}"
    assert kwargs["params"]["user_id"] == "eq.tenant-a-user"
    assert calls[1][1] == "organization_memberships"
    assert calls[1][3]["params"]["select"] == "organization_id,user_id,role,invited_by,created_at"
    assert kwargs["params"]["select"] == "organization_id,user_id,role"
    # This mock regression proves the caller token is forwarded to PostgREST.
    # It does not prove live RLS enforcement; that requires an isolated non-production DB.



def test_record_consent_uses_authenticated_user_and_caller_session(monkeypatch):
    calls = []

    async def fake_user_db_request(method, path, access_token, **kwargs):
        calls.append((method, path, access_token, kwargs))
        return [{
            "consent_type": "privacy_policy",
            "policy_version": "policy-test-v1",
            "granted": True,
            "recorded_at": "2026-10-14T00:00:00Z",
        }]

    async def fake_current_user(request: Request):
        request.state.supabase_access_token = "consent-session-token"
        return {"id": "authenticated-consent-user", "email": "consent@example.invalid"}

    monkeypatch.setattr("allpha_api.main.user_db_request", fake_user_db_request)
    app.dependency_overrides[current_user] = fake_current_user
    try:
        response = client.post(
            "/v1/me/consents",
            headers={"Authorization": "Bearer consent-session-token"},
            json={"consent_type": "privacy_policy", "policy_version": "policy-test-v1", "granted": True},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201
    assert response.json()["consent"]["consent_type"] == "privacy_policy"
    assert len(calls) == 1
    method, path, token, kwargs = calls[0]
    assert (method, path, token) == ("POST", "user_consents", "consent-session-token")
    assert kwargs["body"] == {
        "user_id": "authenticated-consent-user",
        "consent_type": "privacy_policy",
        "policy_version": "policy-test-v1",
        "granted": True,
    }


def test_record_consent_rejects_forged_identity_fields_before_database_write(monkeypatch):
    calls = []

    async def fake_user_db_request(method, path, access_token, **kwargs):
        calls.append((method, path, access_token, kwargs))
        return []

    async def fake_current_user(request: Request):
        request.state.supabase_access_token = "consent-session-token"
        return {"id": "authenticated-consent-user", "email": "consent@example.invalid"}

    monkeypatch.setattr("allpha_api.main.user_db_request", fake_user_db_request)
    app.dependency_overrides[current_user] = fake_current_user
    try:
        response = client.post(
            "/v1/me/consents",
            headers={"Authorization": "Bearer consent-session-token"},
            json={
                "user_id": "another-user",
                "consent_type": "privacy_policy",
                "policy_version": "policy-test-v1",
                "granted": True,
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert calls == []


def test_record_consent_requires_authentication():
    response = client.post(
        "/v1/me/consents",
        json={"consent_type": "privacy_policy", "policy_version": "policy-test-v1", "granted": True},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH_REQUIRED"


def test_get_consents_is_scoped_to_authenticated_user(monkeypatch):
    calls = []

    async def fake_user_db_request(method, path, access_token, **kwargs):
        calls.append((method, path, access_token, kwargs))
        return [{"consent_type": "terms_of_service", "policy_version": "terms-test-v1", "granted": True, "recorded_at": "2026-10-14T00:00:00Z"}]

    async def fake_current_user(request: Request):
        request.state.supabase_access_token = "consent-read-token"
        return {"id": "consent-owner", "email": "owner@example.invalid"}

    monkeypatch.setattr("allpha_api.main.user_db_request", fake_user_db_request)
    app.dependency_overrides[current_user] = fake_current_user
    try:
        response = client.get("/v1/me/consents", headers={"Authorization": "Bearer consent-read-token"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["items"][0]["consent_type"] == "terms_of_service"
    assert calls == [(
        "GET",
        "user_consents",
        "consent-read-token",
        {"params": {
            "select": "consent_type,policy_version,granted,recorded_at",
            "user_id": "eq.consent-owner",
            "order": "recorded_at.desc",
            "limit": "100",
        }},
    )]

def test_social_edge_create_uses_authenticated_actor_and_caller_token(monkeypatch):
    reads = []
    service_calls = []
    target_user_id = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"

    async def fake_user_db_request(method, path, access_token, **kwargs):
        reads.append((method, path, access_token, kwargs))
        if method == "GET" and path == "social_edges":
            return []
        if method == "GET" and path == "profiles":
            return [{"id": target_user_id, "visibility": "public", "account_status": "active"}]
        raise AssertionError(f"unexpected read: {method} {path}")

    async def fake_service_db_request(function_name, *, body):
        service_calls.append((function_name, body))
        assert function_name == "create_social_edge_for_actor"
        return [{
            "id": "edge-1", "actor_user_id": body["p_actor_user_id"],
            "target_user_id": body["p_target_user_id"], "edge_type": "follow",
            "status": "active", "created_at": "2026-10-14T00:00:00Z",
        }]

    async def fake_current_user(request: Request):
        request.state.supabase_access_token = "social-write-session-token"
        return {"id": "authenticated-social-actor", "email": "actor@example.invalid"}

    monkeypatch.setattr("allpha_api.main.user_db_request", fake_user_db_request)
    monkeypatch.setattr("allpha_api.main.service_db_request", fake_service_db_request)
    app.dependency_overrides[current_user] = fake_current_user
    try:
        response = client.post(
            "/v1/me/social-edges",
            headers={"Authorization": "Bearer social-write-session-token"},
            json={"target_user_id": target_user_id, "edge_type": "follow"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201
    assert response.json()["edge"]["target_user_id"] == target_user_id
    assert response.json()["idempotent_replay"] is False
    assert all(call[0] == "GET" for call in reads)
    assert service_calls[0][0] == "create_social_edge_for_actor"
    assert service_calls[0][1] == {
        "p_actor_user_id": "authenticated-social-actor",
        "p_target_user_id": target_user_id,
        "p_actor_node_type": "human",
        "p_target_node_type": "human",
        "p_actor_agent_id": None,
        "p_target_agent_id": None,
        "p_edge_type": "follow",
        "p_idempotency_key": None,
    }


def test_social_edge_rejects_self_target_before_database_write(monkeypatch):
    calls = []

    async def fake_user_db_request(method, path, access_token, **kwargs):
        calls.append((method, path, access_token, kwargs))
        return []

    async def fake_current_user(request: Request):
        request.state.supabase_access_token = "social-self-target-token"
        return {"id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa", "email": "self@example.invalid"}

    monkeypatch.setattr("allpha_api.main.user_db_request", fake_user_db_request)
    app.dependency_overrides[current_user] = fake_current_user
    try:
        response = client.post(
            "/v1/me/social-edges",
            headers={"Authorization": "Bearer social-self-target-token"},
            json={
                "target_user_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
                "edge_type": "follow",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "SOCIAL_EDGE_SELF_TARGET"
    assert calls == []

def test_follow_request_accept_is_scoped_to_authenticated_recipient(monkeypatch):
    service_calls = []
    edge_id = "dddddddd-dddd-4ddd-8ddd-dddddddddddd"

    async def fake_service_db_request(function_name, *, body):
        service_calls.append((function_name, body))
        return [{"id": edge_id, "actor_user_id": "requester", "target_user_id": "recipient", "edge_type": "follow", "status": "active"}]

    async def fake_current_user(request: Request):
        request.state.supabase_access_token = "recipient-token"
        return {"id": "recipient", "email": "recipient@example.invalid"}

    monkeypatch.setattr("allpha_api.main.service_db_request", fake_service_db_request)
    app.dependency_overrides[current_user] = fake_current_user
    try:
        response = client.post(
            f"/v1/me/follow-requests/{edge_id}/accept",
            headers={"Authorization": "Bearer recipient-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert service_calls == [("accept_social_follow_for_actor", {"p_actor_user_id": "recipient", "p_edge_id": edge_id})]


def test_follow_request_accept_returns_safe_not_found_when_not_owned_or_pending(monkeypatch):
    async def fake_service_db_request(function_name, *, body):
        assert function_name == "accept_social_follow_for_actor"
        return []

    async def fake_current_user(request: Request):
        request.state.supabase_access_token = "recipient-token"
        return {"id": "recipient", "email": "recipient@example.invalid"}

    monkeypatch.setattr("allpha_api.main.service_db_request", fake_service_db_request)
    app.dependency_overrides[current_user] = fake_current_user
    try:
        response = client.post(
            "/v1/me/follow-requests/dddddddd-dddd-4ddd-8ddd-dddddddddddd/accept",
            headers={"Authorization": "Bearer recipient-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "FOLLOW_REQUEST_NOT_FOUND"


def test_interest_upsert_and_delete_are_scoped_to_authenticated_user(monkeypatch):
    calls = []

    async def fake_user_db_request(method, path, access_token, **kwargs):
        calls.append((method, path, access_token, kwargs))
        if method == "POST":
            return [{"interest_key": "desain.3d", "preference": "interested"}]
        return [{"interest_key": "desain.3d"}]

    async def fake_current_user(request: Request):
        request.state.supabase_access_token = "interest-session-token"
        return {"id": "interest-owner", "email": "owner@example.invalid"}

    monkeypatch.setattr("allpha_api.main.user_db_request", fake_user_db_request)
    app.dependency_overrides[current_user] = fake_current_user
    try:
        put_response = client.put(
            "/v1/me/interests",
            headers={"Authorization": "Bearer interest-session-token"},
            json={"interest_key": "desain.3d", "preference": "interested"},
        )
        delete_response = client.delete(
            "/v1/me/interests/desain.3d",
            headers={"Authorization": "Bearer interest-session-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert put_response.status_code == 200
    assert delete_response.status_code == 200
    assert len(calls) == 2
    assert calls[0][0:3] == ("POST", "user_interests", "interest-session-token")
    assert calls[0][3]["body"]["user_id"] == "interest-owner"
    assert calls[0][3]["params"]["on_conflict"] == "user_id,interest_key"
    assert calls[1][0:3] == ("DELETE", "user_interests", "interest-session-token")
    assert calls[1][3]["params"]["user_id"] == "eq.interest-owner"
    assert calls[1][3]["params"]["interest_key"] == "eq.desain.3d"


def test_social_edge_delete_returns_not_found_and_never_deletes_another_actor_edge(monkeypatch):
    calls = []

    async def fake_user_db_request(method, path, access_token, **kwargs):
        calls.append((method, path, access_token, kwargs))
        return []

    async def fake_current_user(request: Request):
        request.state.supabase_access_token = "social-delete-token"
        return {"id": "authenticated-actor", "email": "actor@example.invalid"}

    monkeypatch.setattr("allpha_api.main.user_db_request", fake_user_db_request)
    app.dependency_overrides[current_user] = fake_current_user
    try:
        response = client.delete(
            "/v1/me/social-edges/eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee/follow",
            headers={"Authorization": "Bearer social-delete-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "SOCIAL_EDGE_NOT_FOUND"
    assert calls[0][3]["params"]["actor_user_id"] == "eq.authenticated-actor"



def test_protected_api_rejects_revoked_supabase_session(monkeypatch):
    import time
    import uuid
    import jwt

    session_id = str(uuid.uuid4())
    token = jwt.encode(
        {"sub": "authenticated-user", "session_id": session_id, "exp": int(time.time()) + 3600},
        "test-only-signing-key",
        algorithm="HS256",
    )

    class FakeResponse:
        status_code = 200
        def json(self):
            return {"id": "authenticated-user", "email_confirmed_at": "2026-11-22T00:00:00Z"}

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *args): return False
        async def get(self, *args, **kwargs): return FakeResponse()

    monkeypatch.setenv("SUPABASE_URL", "https://auth-session-test.supabase.co")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "sb_publishable_test_only")
    monkeypatch.setattr("allpha_api.auth.httpx.AsyncClient", FakeAsyncClient)

    async def revoked_session(method, path, access_token, **kwargs):
        assert method == "POST"
        assert path == "rpc/is_auth_session_active"
        assert access_token == token
        assert kwargs["body"]["p_session_id"] == session_id
        return False

    monkeypatch.setattr("allpha_api.auth.user_db_request", revoked_session)
    request = Request({"type": "http", "method": "GET", "path": "/v1/me", "headers": [], "query_string": b"", "server": ("test", 80), "client": ("test", 1234), "scheme": "http"})
    from fastapi.security import HTTPAuthorizationCredentials
    with pytest.raises(Exception) as caught:
        import asyncio
        session_user = asyncio.run(current_session_user(request, HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)))
        asyncio.run(current_user(request, session_user))
    assert getattr(caught.value, "status_code", None) == 401
    assert getattr(caught.value, "detail", {}).get("code") == "SESSION_REVOKED"


def test_session_revocation_endpoint_is_scoped_to_verified_current_session(monkeypatch):
    calls = []
    async def fake_user_db_request(method, path, access_token, **kwargs):
        calls.append((method, path, access_token, kwargs))
        return True
    async def fake_current_user(request: Request):
        request.state.supabase_access_token = "verified-session-token"
        request.state.auth_session_id = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
        return {"id": "authenticated-user"}
    monkeypatch.setattr("allpha_api.main.user_db_request", fake_user_db_request)
    app.dependency_overrides[current_session_user] = fake_current_user
    try:
        response = client.post("/v1/auth/revoke", headers={"Authorization": "Bearer verified-session-token"})
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json() == {"revoked": True}
    assert calls == [("POST", "rpc/revoke_my_auth_session", "verified-session-token", {
        "body": {"p_session_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"}
    })]


@pytest.mark.parametrize("upstream_status", [400, 408, 429, 500, 502, 503])
def test_supabase_auth_upstream_failures_do_not_invalidate_local_session(monkeypatch, upstream_status):
    class FakeResponse:
        status_code = upstream_status

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, *args, **kwargs):
            return FakeResponse()

    monkeypatch.setenv("SUPABASE_URL", "https://staging-example.supabase.co")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "sb_publishable_test_only")
    monkeypatch.setattr("allpha_api.auth.httpx.AsyncClient", FakeAsyncClient)

    response = client.get("/v1/me", headers={"Authorization": "Bearer potentially-valid-session"})

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "AUTH_UNAVAILABLE"
    assert "potentially-valid-session" not in response.text


def test_session_inventory_uses_owner_scoped_rpc_and_marks_current_session(monkeypatch):
    calls = []

    async def fake_user_db_request(method, path, access_token, **kwargs):
        calls.append((method, path, access_token, kwargs))
        return [{"id": "session-current", "is_current": True, "user_agent": "Web"}]

    async def fake_current_user(request: Request):
        request.state.supabase_access_token = "owner-session-token"
        request.state.auth_session_id = "session-current"
        return {"id": "authenticated-user"}

    monkeypatch.setattr("allpha_api.main.user_db_request", fake_user_db_request)
    app.dependency_overrides[current_user] = fake_current_user
    try:
        response = client.get("/v1/me/sessions", headers={"Authorization": "Bearer owner-session-token"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"items": [{"id": "session-current", "is_current": True, "user_agent": "Web"}], "current_session_id": "session-current"}
    assert calls == [("POST", "rpc/list_my_auth_sessions", "owner-session-token", {"body": {"p_current_session_id": "session-current"}})]


def test_revoke_other_sessions_uses_verified_current_session_context(monkeypatch):
    calls = []

    async def fake_user_db_request(method, path, access_token, **kwargs):
        calls.append((method, path, access_token, kwargs))
        return 3

    async def fake_current_session_user(request: Request):
        request.state.supabase_access_token = "owner-session-token"
        request.state.auth_session_id = "session-current"
        return {"id": "authenticated-user"}

    monkeypatch.setattr("allpha_api.main.user_db_request", fake_user_db_request)
    app.dependency_overrides[current_session_user] = fake_current_session_user
    try:
        response = client.post("/v1/me/sessions/revoke-others", headers={"Authorization": "Bearer owner-session-token"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"revoked_count": 3}
    assert calls == [("POST", "rpc/revoke_my_other_auth_sessions", "owner-session-token", {"body": {"p_current_session_id": "session-current"}})]


def test_selected_session_revocation_is_uuid_validated_and_owner_scoped(monkeypatch):
    calls = []

    async def fake_user_db_request(method, path, access_token, **kwargs):
        calls.append((method, path, access_token, kwargs))
        return True

    async def fake_current_session_user(request: Request):
        request.state.supabase_access_token = "owner-session-token"
        request.state.auth_session_id = "session-current"
        return {"id": "authenticated-user"}

    monkeypatch.setattr("allpha_api.main.user_db_request", fake_user_db_request)
    app.dependency_overrides[current_session_user] = fake_current_session_user
    try:
        response = client.post(
            "/v1/me/sessions/aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa/revoke",
            headers={"Authorization": "Bearer owner-session-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"revoked": True}
    assert calls == [("POST", "rpc/revoke_my_auth_session", "owner-session-token", {
        "body": {"p_session_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"}
    })]


def test_missing_postgrest_rpc_is_reported_as_schema_unavailable(monkeypatch):
    import asyncio
    from fastapi import HTTPException

    class FakeResponse:
        status_code = 404
        content = b'{"code":"PGRST202","message":"function not found"}'
        def json(self):
            return {"code": "PGRST202", "message": "function not found"}

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *args): return False
        async def request(self, *args, **kwargs): return FakeResponse()

    monkeypatch.setenv("SUPABASE_URL", "https://schema-test.supabase.co")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "sb_publishable_test_only")
    monkeypatch.setattr("allpha_api.auth.httpx.AsyncClient", FakeAsyncClient)

    with pytest.raises(HTTPException) as caught:
        asyncio.run(user_db_request("POST", "rpc/list_my_auth_sessions", "owner-token", body={"p_current_session_id": "session-id"}))

    assert caught.value.status_code == 503
    assert caught.value.detail["code"] == "DATABASE_SCHEMA_UNAVAILABLE"
    assert "PGRST202" not in str(caught.value.detail)
    assert "owner-token" not in str(caught.value.detail)


def test_missing_postgrest_table_is_reported_as_schema_unavailable(monkeypatch):
    class FakeResponse:
        status_code = 404
        content = b'{"code":"PGRST205"}'
        def json(self):
            return {"code": "PGRST205"}

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            return False
        async def request(self, *args, **kwargs):
            return FakeResponse()

    monkeypatch.setenv("SUPABASE_URL", "https://schema-missing.example.supabase.co")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "sb_publishable_test_only")
    monkeypatch.setattr("allpha_api.auth.httpx.AsyncClient", FakeAsyncClient)

    with pytest.raises(HTTPException) as exc:
        import asyncio
        asyncio.run(user_db_request("GET", "organizations", "verified-test-token"))

    assert exc.value.status_code == 503
    assert exc.value.detail["code"] == "DATABASE_SCHEMA_UNAVAILABLE"

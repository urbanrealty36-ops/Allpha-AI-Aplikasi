import pytest
from pydantic import ValidationError
from fastapi import Request
from fastapi.testclient import TestClient

from allpha_api.auth import current_user
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
    assert payload["dependencies"]["database"] == "not_configured"
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
            if url.endswith("/rest/v1/"):
                return FakeResponse(503)
            raise AssertionError(f"Unexpected readiness probe URL: {url}")

    monkeypatch.setattr("allpha_api.main.httpx.AsyncClient", FakeAsyncClient)
    response = client.get("/readyz")

    assert response.status_code == 503
    payload = response.json()
    assert payload["status"] == "not_ready"
    assert payload["dependencies"]["authentication"] == "reachable"
    assert payload["dependencies"]["database"] == "unavailable"
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
            assert url.endswith(("/auth/v1/health", "/rest/v1/"))
            assert kwargs["headers"] == {"apikey": "sb_publishable_test_only"}
            return FakeResponse()

    monkeypatch.setattr("allpha_api.main.httpx.AsyncClient", FakeAsyncClient)
    response = client.get("/readyz")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ready"
    assert payload["dependencies"]["authentication"] == "reachable"
    assert payload["dependencies"]["database"] == "reachable"
    assert payload["dependencies"]["object_storage"] == "not_configured"
    assert payload["dependencies"]["ai_gateway"] == "not_configured"


def test_profile_payload_rejects_authority_fields():
    with pytest.raises(ValidationError):
        ProfileUpdate.model_validate({"role": "super_admin"})


def test_create_organization_uses_authenticated_identity(monkeypatch):
    calls = []

    async def fake_user_db_request(method, path, access_token, **kwargs):
        calls.append((method, path, access_token, kwargs))
        return [{"id": "org-1", "name": "Test Org", "slug": "test-org", "owner_id": "user-123"}]

    async def fake_current_user(request: Request):
        request.state.supabase_access_token = "test-token"
        return {"id": "user-123", "email": "test@example.invalid"}

    monkeypatch.setattr("allpha_api.main.user_db_request", fake_user_db_request)
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
    assert calls[0][0:3] == ("POST", "organizations", "test-token")
    assert calls[0][3]["body"]["owner_id"] == "user-123"
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
        return {"id": "tenant-b-user", "email": "tenant-b@example.invalid"}

    monkeypatch.setattr("allpha_api.main.user_db_request", fake_user_db_request)
    app.dependency_overrides[current_user] = fake_current_user
    try:
        response = client.get(
            f"/v1/organizations/{foreign_organization_id}/memberships",
            headers={"Authorization": "Bearer tenant-b-session"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"
    assert calls[0][1] == "organization_memberships"
    assert calls[0][3]["params"]["organization_id"] == f"eq.{foreign_organization_id}"
    assert calls[1][1] == "organizations"
    assert calls[1][3]["params"]["id"] == f"eq.{foreign_organization_id}"
    assert all(call[2] == "tenant-b-token" for call in calls)

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
                "select": "id,username,display_name,avatar_url,bio,visibility,created_at,updated_at",
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
    assert len(calls) == 4
    assert all(call[2] == "social-scope-token" for call in calls)
    assert calls[0][1] == "social_edges"
    assert calls[0][3]["params"]["actor_user_id"] == "eq.authenticated-social-user"
    assert calls[1][3]["params"]["target_user_id"] == "eq.authenticated-social-user"
    assert calls[1][3]["params"]["edge_type"] == "eq.block"
    assert calls[2][3]["params"]["target_user_id"] == "eq.authenticated-social-user"
    assert calls[2][3]["params"]["edge_type"] == "eq.follow"
    assert calls[2][3]["params"]["status"] == "eq.requested"
    assert calls[3][1] == "user_interests"
    assert calls[3][3]["params"]["user_id"] == "eq.authenticated-social-user"

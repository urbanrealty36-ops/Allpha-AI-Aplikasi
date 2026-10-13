import pytest
from pydantic import ValidationError
from fastapi.testclient import TestClient

from allpha_api.auth import current_user
from allpha_api.main import ProfileUpdate, app

client = TestClient(app)


def test_authenticated_routes_reject_missing_bearer_token():
    for path in ("/v1/me", "/v1/organizations"):
        response = client.get(path)
        assert response.status_code == 401
        assert response.json()["detail"]["code"] == "AUTH_REQUIRED"


def test_ready_reports_supabase_configuration_without_exposing_secrets(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_PUBLISHABLE_KEY", raising=False)
    response = client.get("/readyz")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ready"
    assert payload["dependencies"]["database"] == "not_configured"
    assert "SUPABASE" not in response.text


def test_profile_payload_rejects_authority_fields():
    with pytest.raises(ValidationError):
        ProfileUpdate.model_validate({"role": "super_admin"})


def test_create_organization_uses_authenticated_identity(monkeypatch):
    calls = []

    async def fake_user_db_request(method, path, access_token, **kwargs):
        calls.append((method, path, access_token, kwargs))
        return [{"id": "org-1", "name": "Test Org", "slug": "test-org", "owner_id": "user-123"}]

    async def fake_current_user():
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

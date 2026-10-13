from fastapi.testclient import TestClient

from allpha_api.main import app

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
    assert payload["status"] == "degraded"
    assert payload["dependencies"]["database"] == "not_configured"
    assert "SUPABASE" not in response.text


def test_profile_payload_rejects_authority_fields():
    response = client.patch(
        "/v1/me/profile",
        headers={"Authorization": "Bearer invalid"},
        json={"role": "super_admin"},
    )
    assert response.status_code == 422

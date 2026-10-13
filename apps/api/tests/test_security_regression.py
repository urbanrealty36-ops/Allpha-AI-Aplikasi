from fastapi.testclient import TestClient

from allpha_api.main import app

client = TestClient(app)


def test_identity_endpoint_rejects_requests_without_bearer_token() -> None:
    response = client.get("/v1/me")
    assert response.status_code == 401
    body = response.json()
    assert body["error"]["code"] == "AUTH_REQUIRED"
    assert "request_id" in body["error"]
    assert "Authorization" not in response.text
    assert "SUPABASE_PUBLISHABLE_KEY" not in response.text


def test_auth_error_envelope_does_not_expose_backend_details() -> None:
    response = client.get("/v1/me", headers={"Authorization": "Basic not-a-bearer"})
    assert response.status_code == 401
    body = response.json()
    assert body["error"]["code"] == "AUTH_REQUIRED"
    assert "traceback" not in response.text.lower()
    assert "postgres" not in response.text.lower()
    assert "service_role" not in response.text.lower()

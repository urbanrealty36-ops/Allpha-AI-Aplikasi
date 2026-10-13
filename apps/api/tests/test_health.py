from fastapi.testclient import TestClient

from allpha_api.main import app

client = TestClient(app)


def test_healthz_reports_process_liveness() -> None:
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "allpha-api"}
    assert response.headers.get("x-request-id")


def test_readiness_does_not_claim_unconfigured_dependencies() -> None:
    response = client.get("/readyz")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["dependencies"]["database"] == "not_configured"
    assert body["dependencies"]["object_storage"] == "not_configured"
    assert body["dependencies"]["ai_gateway"] == "not_configured"


def test_request_id_is_preserved() -> None:
    response = client.get("/healthz", headers={"x-request-id": "test-request-123"})
    assert response.headers["x-request-id"] == "test-request-123"


def test_system_status_reports_version_and_capabilities() -> None:
    response = client.get("/v1/system/status")
    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "allpha-api"
    assert body["capabilities"]["database"] is False
    assert body["capabilities"]["authentication"] is False

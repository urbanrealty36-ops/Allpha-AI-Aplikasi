from fastapi.testclient import TestClient

from allpha_api.main import app

client = TestClient(app)


def test_healthz_reports_process_liveness() -> None:
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "allpha-api"}
    assert response.headers.get("x-request-id")


def test_readiness_fails_closed_when_core_dependencies_are_unconfigured(monkeypatch) -> None:
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_PUBLISHABLE_KEY", raising=False)
    response = client.get("/readyz")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "not_ready"
    assert body["dependencies"]["database"]["status"] == "not_configured"
    assert body["dependencies"]["authentication"]["status"] == "not_configured"
    assert body["dependencies"]["object_storage"]["status"] == "not_checked"
    assert body["dependencies"]["ai_gateway"] == "not_configured"


def test_readiness_passes_when_core_supabase_configuration_exists(monkeypatch) -> None:
    class HealthyResponse:
        status_code = 200

    class HealthySupabaseClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return False

        async def get(self, url: str, headers: dict[str, str]):
            assert url in {
                "https://example.supabase.co/auth/v1/health",
                "https://example.supabase.co/rest/v1/",
            }
            assert headers == {"apikey": "test-publishable-key"}
            return HealthyResponse()

    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "test-publishable-key")
    monkeypatch.setattr("allpha_api.main.httpx.AsyncClient", lambda **kwargs: HealthySupabaseClient())
    response = client.get("/readyz")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["dependencies"]["database"]["status"] == "reachable"
    assert body["dependencies"]["authentication"]["status"] == "reachable"


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


def test_cors_allows_configured_local_web_origin() -> None:
    response = client.options(
        "/v1/me",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization",
        },
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"
    assert "authorization" in response.headers.get("access-control-allow-headers", "").lower()


def test_cors_does_not_reflect_untrusted_origins() -> None:
    response = client.get("/healthz", headers={"Origin": "https://untrusted.example"})
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") is None

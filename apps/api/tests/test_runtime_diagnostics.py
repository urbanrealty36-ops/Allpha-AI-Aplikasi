from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import httpx

from allpha_api import main
from allpha_api.model_router import TextGenerationRouterUnavailable


def test_readyz_probes_auth_and_postgrest_independently(monkeypatch):
    calls: list[str] = []

    class FakeResponse:
        def __init__(self, status_code: int):
            self.status_code = status_code

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, url: str, headers=None):
            calls.append(url)
            if url.endswith("/auth/v1/health"):
                raise httpx.TimeoutException("synthetic isolated test timeout")
            return FakeResponse(200)

    monkeypatch.setenv("SUPABASE_URL", "https://supabase.example")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "test-publishable-key")
    monkeypatch.setattr(main.httpx, "AsyncClient", lambda *args, **kwargs: FakeClient())

    response = asyncio.run(main.readyz())
    payload = json.loads(response.body)

    assert response.status_code == 503
    assert payload["dependencies"]["authentication"]["status"] == "timeout"
    assert payload["dependencies"]["database"]["status"] == "reachable"
    assert set(calls) == {
        "https://supabase.example/auth/v1/health",
        "https://supabase.example/rest/v1/",
    }


def test_runtime_preflight_returns_safe_active_tariff_category():
    class FakeRouter:
        async def preflight(self, sensitivity: str):
            assert sensitivity == "private"
            raise TextGenerationRouterUnavailable(
                "internal exception must not be returned",
                category="active_tariff",
            )

    request = SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(text_generation_router=FakeRouter())),
        state=SimpleNamespace(request_id="request-test"),
    )
    response = asyncio.run(main.runtime_preflight(request, {"id": "verified-owner"}))
    payload = json.loads(response.body)

    assert response.status_code == 503
    assert payload["failure_category"] == "active_tariff"
    assert payload["dependencies"]["active_tariff"] == "not_verified"
    assert payload["request_id"] == "request-test"
    assert "internal exception" not in response.body.decode()


def test_runtime_preflight_reports_missing_router_without_sensitive_detail():
    request = SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(text_generation_router=None)),
        state=SimpleNamespace(request_id="request-test"),
    )
    response = asyncio.run(main.runtime_preflight(request, {"id": "verified-owner"}))
    payload = json.loads(response.body)

    assert response.status_code == 503
    assert payload["failure_category"] == "provider_route"
    assert payload["dependencies"]["provider_route"] == "not_configured"

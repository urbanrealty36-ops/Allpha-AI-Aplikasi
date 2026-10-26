from fastapi import Request
from fastapi.testclient import TestClient
from allpha_api.auth import current_user
from allpha_api.main import app


def _authenticated_user(request: Request):
    request.state.user_id = "spatial-test-user"
    return {"id": "spatial-test-user"}




def _get_authenticated(path: str):
    app.dependency_overrides[current_user] = _authenticated_user
    try:
        return TestClient(app).get(path)
    finally:
        app.dependency_overrides.pop(current_user, None)


def test_spatial_navigation_requires_server_catalog_configuration(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    response = _get_authenticated("/v1/spatial/navigation/nodes")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "SPATIAL_NAVIGATION_UNAVAILABLE"


def test_spatial_navigation_rejects_unknown_level_before_database_access(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-role-test")
    response = _get_authenticated("/v1/spatial/navigation/nodes?level=moon")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "SPATIAL_LEVEL_INVALID"


def test_spatial_navigation_rejects_malformed_cursor_before_database_access(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-role-test")
    response = _get_authenticated("/v1/spatial/navigation/nodes?cursor=not-a-valid-cursor")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "SPATIAL_CURSOR_INVALID"


def test_spatial_asset_catalog_rejects_noncanonical_category(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-role-test")
    response = _get_authenticated("/v1/spatial/assets?category=not-a-category")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "SPATIAL_CATEGORY_INVALID"


def test_spatial_asset_catalog_fails_closed_without_database_config(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    response = _get_authenticated("/v1/spatial/assets")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "SPATIAL_NAVIGATION_UNAVAILABLE"


def test_spatial_catalog_rejects_anonymous_requests():
    response = TestClient(app).get("/v1/spatial/navigation/nodes")
    assert response.status_code == 401

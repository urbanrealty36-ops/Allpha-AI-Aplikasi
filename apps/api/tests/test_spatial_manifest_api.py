from fastapi import Request
from fastapi.testclient import TestClient

from allpha_api.auth import current_user
from allpha_api.main import app


def _authenticated_user(request: Request):
    request.state.user_id = "spatial-test-user"
    return {"id": "spatial-test-user"}




def _get_authenticated(path: str, **kwargs):
    app.dependency_overrides[current_user] = _authenticated_user
    try:
        return TestClient(app).get(path, **kwargs)
    finally:
        app.dependency_overrides.pop(current_user, None)


def test_public_scene_manifest_fails_closed_when_server_catalog_is_unconfigured(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    response = _get_authenticated("/v1/spatial/scenes/known-scene/manifest")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "SPATIAL_MANIFEST_UNAVAILABLE"


def test_public_scene_manifest_rejects_invalid_scene_key_before_storage_access():
    response = _get_authenticated("/v1/spatial/scenes/Invalid%20Key/manifest")
    assert response.status_code == 422



def test_test_only_scene_manifest_is_not_discoverable_without_test_secret(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-role-test")
    monkeypatch.setenv("ALLPHA_SPATIAL_TEST_ACCESS_KEY", "t" * 40)
    response = TestClient(app).get("/v1/spatial/test/scenes/internal-test/manifest")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "SPATIAL_TEST_SCENE_NOT_FOUND"


def test_test_only_scene_manifest_fails_closed_when_test_secret_is_not_configured(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-role-test")
    monkeypatch.delenv("ALLPHA_SPATIAL_TEST_ACCESS_KEY", raising=False)
    response = TestClient(app).get(
        "/v1/spatial/test/scenes/internal-test/manifest",
        headers={"X-Allpha-Spatial-Test-Key": "t" * 40},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "SPATIAL_TEST_SCENE_NOT_FOUND"


def test_published_scene_manifest_rejects_anonymous_requests():
    response = TestClient(app).get("/v1/spatial/scenes/known-scene/manifest")
    assert response.status_code == 401

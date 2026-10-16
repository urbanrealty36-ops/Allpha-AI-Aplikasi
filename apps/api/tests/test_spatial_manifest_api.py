from fastapi.testclient import TestClient

from allpha_api.main import app


def test_public_scene_manifest_fails_closed_when_server_catalog_is_unconfigured(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    response = TestClient(app).get("/v1/spatial/scenes/known-scene/manifest")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "SPATIAL_MANIFEST_UNAVAILABLE"


def test_public_scene_manifest_rejects_invalid_scene_key_before_storage_access():
    response = TestClient(app).get("/v1/spatial/scenes/Invalid%20Key/manifest")
    assert response.status_code == 422

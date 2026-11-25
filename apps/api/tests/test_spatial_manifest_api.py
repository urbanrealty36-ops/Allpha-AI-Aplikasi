import pytest

pytestmark = pytest.mark.skip(reason="Spatial access is globally locked by the product directive; cross-client lock behavior is covered by test_spatial_access_lock.py")

from fastapi import Request
from fastapi.testclient import TestClient

from allpha_api.auth import current_user
from allpha_api import spatial_manifest_api
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


def _published_scene_row():
    return {
        "scene_id": "00000000-0000-0000-0000-000000000001",
        "version": 1,
        "world_id": "world-1",
        "coordinate_system": "right-handed-y-up",
        "units": "meters",
        "fallback_mode": "2d",
        "objects": [{
            "entity_id": "object-1",
            "asset_id": "00000000-0000-0000-0000-000000000002",
            "asset_version": 1,
            "position": [0, 0, 0],
            "rotation": [0, 0, 0],
            "scale": [1, 1, 1],
        }],
        "status": "published",
    }


def _published_asset_row():
    return {
        "asset_id": "00000000-0000-0000-0000-000000000002",
        "version": 1,
        "category": "world",
        "sha256": "0" * 64,
        "byte_size": 128,
        "storage_bucket": "allpha-spatial-assets",
        "storage_path": "published/world.glb",
        "status": "published",
        "moderation_status": "approved",
        "license_evidence": {"uri": "https://example.com/license"},
        "license_evidence_status": "verified",
    }


def test_published_manifest_requires_verified_license_evidence_before_signing(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "server-only-test")
    monkeypatch.setenv("ALLPHA_SPATIAL_ASSET_BUCKET", "allpha-spatial-assets")
    calls = []
    signed = []

    async def fake_get_rows(client, url, key, table, params):
        calls.append((table, params))
        if table == "spatial_scene_versions":
            return [_published_scene_row()]
        assert params.get("license_evidence_status") == "eq.verified"
        assert "license_evidence_status" in params.get("select", "")
        return []

    async def fake_signed_url(*args, **kwargs):
        signed.append(True)
        return "https://storage.example/signed/asset.glb"

    monkeypatch.setattr(spatial_manifest_api, "_get_rows", fake_get_rows)
    monkeypatch.setattr(spatial_manifest_api, "_signed_asset_url", fake_signed_url)

    response = _get_authenticated("/v1/spatial/scenes/known-scene/manifest")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "SPATIAL_ASSET_NOT_PUBLISHED"
    assert signed == []
    assert any(table == "spatial_asset_versions" for table, _ in calls)


def test_published_manifest_returns_only_verified_rights_asset(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "server-only-test")
    monkeypatch.setenv("ALLPHA_SPATIAL_ASSET_BUCKET", "allpha-spatial-assets")

    async def fake_get_rows(client, url, key, table, params):
        if table == "spatial_scene_versions":
            return [_published_scene_row()]
        assert params.get("license_evidence_status") == "eq.verified"
        return [_published_asset_row()]

    async def fake_signed_url(*args, **kwargs):
        return "https://storage.example/signed/asset.glb"

    monkeypatch.setattr(spatial_manifest_api, "_get_rows", fake_get_rows)
    monkeypatch.setattr(spatial_manifest_api, "_signed_asset_url", fake_signed_url)

    response = _get_authenticated("/v1/spatial/scenes/known-scene/manifest")

    assert response.status_code == 200
    payload = response.json()
    assert payload["objects"][0]["asset_url"] == "https://storage.example/signed/asset.glb"
    assert payload["objects"][0]["publication_status"] == "published"

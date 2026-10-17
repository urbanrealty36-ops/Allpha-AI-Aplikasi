from fastapi.testclient import TestClient

from allpha_api.main import app


def test_test_ingest_is_not_discoverable_without_server_secret(monkeypatch):
    monkeypatch.setenv("ALLPHA_SPATIAL_TEST_ACCESS_KEY", "x" * 40)
    response = TestClient(app).post(
        "/v1/spatial/test/assets/ingest",
        headers={"X-Allpha-Spatial-Test-Key": "wrong"},
        data={"metadata": "{}"},
        files={"file": ("fixture.glb", b"not-glb", "model/gltf-binary")},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "SPATIAL_TEST_INGEST_NOT_FOUND"


def test_test_ingest_fails_closed_when_secret_missing(monkeypatch):
    monkeypatch.delenv("ALLPHA_SPATIAL_TEST_ACCESS_KEY", raising=False)
    response = TestClient(app).post(
        "/v1/spatial/test/assets/ingest",
        headers={"X-Allpha-Spatial-Test-Key": "x" * 40},
        data={"metadata": "{}"},
        files={"file": ("fixture.glb", b"not-glb", "model/gltf-binary")},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "SPATIAL_TEST_INGEST_NOT_FOUND"


def test_test_ingest_rejects_non_glb_before_storage_access(monkeypatch):
    monkeypatch.setenv("ALLPHA_SPATIAL_TEST_ACCESS_KEY", "x" * 40)
    response = TestClient(app).post(
        "/v1/spatial/test/assets/ingest",
        headers={"X-Allpha-Spatial-Test-Key": "x" * 40},
        data={"metadata": '{"asset_key":"test.fixture","scene_key":"test.scene","category":"agent-character","source_url":"https://example.invalid/model.glb","source_repo":"fixture","source_path":"fixture.glb","display_name":"Test fixture"}'},
        files={"file": ("fixture.glb", b"not-glb", "model/gltf-binary")},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "SPATIAL_GLB_INVALID"


def test_test_ingest_rejects_noncanonical_category_before_storage_access(monkeypatch):
    monkeypatch.setenv("ALLPHA_SPATIAL_TEST_ACCESS_KEY", "x" * 40)
    response = TestClient(app).post(
        "/v1/spatial/test/assets/ingest",
        headers={"X-Allpha-Spatial-Test-Key": "x" * 40},
        data={"metadata": '{"asset_key":"test.fixture","scene_key":"test.scene","category":"misc","source_url":"https://example.invalid/model.glb","source_repo":"fixture","source_path":"fixture.glb","display_name":"Test fixture"}'},
        files={"file": ("fixture.glb", b"not-glb", "model/gltf-binary")},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "SPATIAL_INGEST_METADATA_INVALID"

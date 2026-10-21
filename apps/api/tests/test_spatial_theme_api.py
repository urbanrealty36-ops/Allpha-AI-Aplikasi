import asyncio
import hashlib
import json

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from allpha_api.main import app
from allpha_api.spatial_theme_api import (
    CATEGORIES,
    ThemeManifestDraft,
    ThemeSlot,
    Transform,
    _canonical_digest,
    _validate_assets,
)


def test_theme_manifest_is_declarative_and_rejects_unknown_fields():
    manifest = ThemeManifestDraft.model_validate({
        "schema_version": "1.0",
        "theme_key": "crystal-city",
        "display_name": "Crystal City",
        "slots": [{
            "slot_key": "city-district",
            "category": "district",
            "asset_key": "district-crystal",
            "asset_version": 1,
            "transform": {"position": [0, 0, 0], "rotation": [0, 0, 0], "scale": [1, 1, 1]},
        }],
    })
    assert manifest.theme_key == "crystal-city"
    assert len(CATEGORIES) == 14
    assert len(_canonical_digest(manifest)) == 64
    with pytest.raises(ValueError):
        ThemeManifestDraft.model_validate({
            "theme_key": "crystal-city", "display_name": "Crystal City",
            "arbitrary_code": "run()", "slots": [],
        })


def test_theme_manifest_rejects_duplicate_slots_and_invalid_scale():
    with pytest.raises(ValueError):
        ThemeManifestDraft.model_validate({
            "theme_key": "crystal-city", "display_name": "Crystal City",
            "slots": [
                {"slot_key": "district-slot", "category": "district", "asset_key": "district-one", "asset_version": 1},
                {"slot_key": "district-slot", "category": "district", "asset_key": "district-two", "asset_version": 1},
            ],
        })
    with pytest.raises(ValueError):
        Transform.model_validate({"scale": [1, 0, 1]})


def test_theme_public_manifest_fails_closed_when_theme_schema_is_unavailable(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-role-test")
    import allpha_api.spatial_theme_api as theme_api

    async def fail_catalog(*args, **kwargs):
        raise HTTPException(status_code=503, detail={"code": "SPATIAL_CATALOG_NOT_READY", "message": "not ready"})

    monkeypatch.setattr(theme_api, "_get_rows", fail_catalog)
    response = TestClient(app).get("/v1/spatial/themes/crystal-city/manifest")
    assert response.status_code == 503


def test_theme_publish_validation_requires_published_rights_verified_assets(monkeypatch):
    import allpha_api.spatial_theme_api as theme_api

    async def fake_asset(asset_key, version):
        return {
            "asset_id": "00000000-0000-0000-0000-000000000001",
            "asset_key": asset_key, "version": version, "category": "district",
            "status": "test_only", "moderation_status": "pending",
            "license_evidence": {"status": "unverified"},
            "sha256": "a" * 64, "byte_size": 128,
            "storage_bucket": "private", "storage_path": "asset.glb",
        }

    monkeypatch.setattr(theme_api, "_get_asset", fake_asset)
    manifest = ThemeManifestDraft.model_validate({
        "theme_key": "crystal-city", "display_name": "Crystal City",
        "slots": [{"slot_key": "city-district", "category": "district",
                   "asset_key": "district-crystal", "asset_version": 1}],
    })
    result = asyncio.run(theme_api._validate_assets(manifest, for_publish=True))
    assert result["valid"] is False
    assert any(error["code"] == "ASSET_NOT_PUBLICATION_READY" for error in result["errors"])
    assert any(error["code"] == "THEME_CATEGORY_COVERAGE_INCOMPLETE" for error in result["errors"])


def test_theme_public_manifest_route_rejects_invalid_key():
    response = TestClient(app).get("/v1/spatial/themes/Invalid%20Key/manifest")
    assert response.status_code == 422

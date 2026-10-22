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



def test_complete_theme_requires_all_fourteen_canonical_categories(monkeypatch):
    import allpha_api.spatial_theme_api as theme_api

    async def approved_asset(asset_key, version):
        slot = next(item for item in slots if item.asset_key == asset_key)
        return {
            "asset_id": f"00000000-0000-0000-0000-{version:012d}",
            "asset_key": asset_key, "version": version, "category": slot.category,
            "status": "published", "moderation_status": "approved",
            "license_evidence": {"status": "verified"},
            "sha256": "a" * 64, "byte_size": 1024,
            "storage_bucket": "private", "storage_path": asset_key + ".glb",
        }

    slots = [
        ThemeSlot(slot_key="slot-" + category, category=category, asset_key="asset-" + category, asset_version=1)
        for category in CATEGORIES
    ]
    monkeypatch.setattr(theme_api, "_get_asset", approved_asset)
    manifest = ThemeManifestDraft(theme_key="complete-theme", display_name="Complete Theme", slots=slots)
    result = asyncio.run(theme_api._validate_assets(manifest, for_publish=True))
    assert result["valid"] is True
    assert len(result["resolved"]) == 14
    assert all(result["category_coverage"][category] == 1 for category in CATEGORIES)


def test_theme_manifest_hash_is_canonical_and_content_sensitive():
    first = ThemeManifestDraft.model_validate({
        "theme_key": "crystal-city", "display_name": "Crystal City",
        "slots": [{"slot_key": "district-slot", "category": "district", "asset_key": "district-one", "asset_version": 1}],
    })
    same = ThemeManifestDraft.model_validate(json.loads(json.dumps(first.model_dump(mode="json"))))
    changed = ThemeManifestDraft.model_validate({
        "theme_key": "crystal-city", "display_name": "Crystal City",
        "slots": [{"slot_key": "district-slot", "category": "district", "asset_key": "district-one", "asset_version": 2}],
    })
    assert _canonical_digest(first) == _canonical_digest(same)
    assert _canonical_digest(first) != _canonical_digest(changed)


def test_theme_migration_declares_server_only_access_and_immutable_versions():
    from pathlib import Path

    migration = Path(__file__).resolve().parents[1] / "supabase" / "migrations" / "20261021100000_eng_p22_theme_builder_registry.sql"
    source = migration.read_text(encoding="utf-8")
    assert "create table if not exists public.spatial_themes" in source
    assert "create table if not exists public.spatial_theme_versions" in source
    assert "spatial_theme_version_immutable_guard" in source
    assert "revoke all on public.spatial_themes from anon, authenticated" in source
    assert "revoke all on public.spatial_theme_versions from anon, authenticated" in source



def test_theme_preview_and_publish_both_block_moderation_rejected_assets(monkeypatch):
    import allpha_api.spatial_theme_api as theme_api

    async def rejected_asset(asset_key, version):
        return {
            "asset_id": "00000000-0000-0000-0000-000000000001",
            "asset_key": asset_key, "version": version, "category": "district",
            "status": "test_only", "moderation_status": "rejected",
            "license_evidence": {"status": "unverified"},
            "sha256": "a" * 64, "byte_size": 128,
            "storage_bucket": "private", "storage_path": "asset.glb",
        }

    monkeypatch.setattr(theme_api, "_get_asset", rejected_asset)
    manifest = ThemeManifestDraft.model_validate({
        "theme_key": "crystal-city", "display_name": "Crystal City",
        "slots": [{"slot_key": "district-slot", "category": "district",
                   "asset_key": "district-rejected", "asset_version": 1}],
    })
    preview = asyncio.run(theme_api._validate_assets(manifest, for_publish=False))
    publish = asyncio.run(theme_api._validate_assets(manifest, for_publish=True))
    assert preview["valid"] is False
    assert publish["valid"] is False
    assert any(error["code"] == "ASSET_MODERATION_REJECTED" for error in preview["errors"])



def test_optional_missing_asset_is_warning_not_blocking_required_slot(monkeypatch):
    import allpha_api.spatial_theme_api as theme_api

    async def missing_asset(asset_key, version):
        return None

    monkeypatch.setattr(theme_api, "_get_asset", missing_asset)
    manifest = ThemeManifestDraft.model_validate({
        "theme_key": "optional-theme", "display_name": "Optional Theme",
        "slots": [{
            "slot_key": "optional-booth", "category": "booth",
            "asset_key": "missing-booth", "asset_version": 1, "required": False,
        }],
    })
    result = asyncio.run(theme_api._validate_assets(manifest))
    assert result["valid"] is True
    assert not any(error["code"] == "ASSET_VERSION_NOT_FOUND" for error in result["errors"])
    assert any(warning["code"] == "ASSET_VERSION_NOT_FOUND" for warning in result["warnings"])


def test_category_coverage_reports_all_fourteen_categories_from_canonical_registry(monkeypatch):
    import allpha_api.spatial_theme_api as theme_api

    async def fake_store(method, table, *, params=None, body=None, prefer=None):
        assert method == "GET"
        assert params["limit"] == "1000"
        if table == "spatial_asset_versions":
            return [
                {"asset_key": "agent-one", "version": 1, "category": "agent-character", "status": "test_only", "moderation_status": "pending", "license_evidence_status": "unverified", "sha256": "a" * 64, "byte_size": 100},
                {"asset_key": "agent-two", "version": 1, "category": "agent-character", "status": "published", "moderation_status": "approved", "license_evidence_status": "verified", "sha256": "b" * 64, "byte_size": 200},
                {"asset_key": "unknown-one", "version": 1, "category": "unknown", "status": "test_only", "moderation_status": "pending", "license_evidence_status": "unverified", "sha256": "c" * 64, "byte_size": 300},
            ]
        if table == "spatial_asset_ingest_receipts":
            return [
                {"asset_key": "agent-one", "display_name": "Agent one", "category_candidate": "agent-character", "category_mapping_status": "mapped", "lifecycle_status": "test_only", "sha256": "a" * 64, "byte_size": 100},
                {"asset_key": "unregistered", "display_name": "Quarantined asset", "category_candidate": None, "category_mapping_status": "unmapped", "lifecycle_status": "quarantined", "sha256": "d" * 64, "byte_size": 400, "source_repo": "example/repo", "source_path": "asset.glb", "source_url": "https://example.org/asset.glb", "source_license_claim": "unknown", "review_state": "quarantined"},
            ]
        pytest.fail("unexpected registry table: " + table)

    monkeypatch.setattr(theme_api, "privileged_rest_request", fake_store)
    result = asyncio.run(theme_api.get_theme_builder_category_coverage({"id": "operator"}))
    assert result["registry"] == "spatial_asset_versions"
    assert result["receipt_registry"] == "spatial_asset_ingest_receipts"
    assert result["total_asset_versions"] == 3
    assert result["total_ingest_receipts"] == 2
    assert len(result["categories"]) == 14
    avatar = next(row for row in result["categories"] if row["category"] == "agent-character")
    assert avatar["asset_versions"] == 2
    assert avatar["ingest_receipts"] == 1
    assert avatar["publication_ready"] == 1
    assert result["unmapped_or_noncanonical"] == 1
    assert len(result["unregistered_receipts"]) == 1
    assert result["unregistered_receipts"][0]["asset_key"] == "unregistered"
    assert result["integrity_mismatches"] == []
    assert result["category_mismatches"] == []
    assert result["receipt_mapping_status_counts"] == {"mapped": 1, "unmapped": 1}
    assert result["truncated"] is False


def test_public_theme_manifest_rejects_asset_category_mismatch(monkeypatch):
    import allpha_api.spatial_theme_api as theme_api

    manifest = ThemeManifestDraft.model_validate({
        "theme_key": "crystal-city", "display_name": "Crystal City",
        "slots": [{
            "slot_key": "district-slot", "category": "district",
            "asset_key": "wrong-category-asset", "asset_version": 1,
        }],
    })
    digest = _canonical_digest(manifest)

    async def fake_rows(client, url, key, table, params):
        if table == "spatial_themes":
            return [{"theme_key": "crystal-city", "display_name": "Crystal City", "status": "published", "active_version": 1}]
        if table == "spatial_theme_versions":
            return [{"theme_key": "crystal-city", "version": 1, "manifest": manifest.model_dump(mode="json"), "manifest_sha256": digest, "status": "published"}]
        if table == "spatial_asset_versions":
            return [{
                "asset_id": "00000000-0000-0000-0000-000000000001",
                "asset_key": "wrong-category-asset", "version": 1, "category": "booth",
                "sha256": "a" * 64, "byte_size": 1024, "storage_bucket": "private",
                "storage_path": "wrong-category-asset.glb", "status": "published",
                "moderation_status": "approved", "license_evidence": {"status": "verified"},
            }]
        pytest.fail("unexpected canonical registry table: " + table)

    monkeypatch.setattr(theme_api, "_service_config", lambda: ("https://example.supabase.co", "service-role-test"))
    monkeypatch.setattr(theme_api, "_get_rows", fake_rows)
    monkeypatch.setattr(theme_api, "_signed_asset_url", lambda *args, **kwargs: "https://example.supabase.co/signed.glb")
    response = TestClient(app).get("/v1/spatial/themes/crystal-city/manifest")
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "SPATIAL_ASSET_CATEGORY_MISMATCH"

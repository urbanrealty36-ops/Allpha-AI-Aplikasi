import pytest
from pydantic import ValidationError

from allpha_api.spatial_scene_contract import CANONICAL_ASSET_CATEGORIES, SceneManifestV1


def valid_manifest():
    return {
        "schema_version": "1.0",
        "scene_id": "scene-test-only",
        "scene_version": 1,
        "world_id": "world-test-only",
        "coordinate_system": "right-handed-y-up",
        "units": "meters",
        "fallback_mode": "2d",
        "objects": [{
            "entity_id": "entity-test-only",
            "asset_id": "asset-test-only",
            "asset_version": 1,
            "category": "world",
            "asset_url": "https://assets.example.invalid/test.glb",
            "sha256": "a" * 64,
            "byte_size": 1024,
            "position": [0, 0, 0],
            "rotation": [0, 0, 0],
            "scale": [1, 1, 1],
            "publication_status": "approved",
        }],
    }


def test_scene_manifest_accepts_valid_authorized_contract_shape():
    parsed = SceneManifestV1.model_validate(valid_manifest())
    assert parsed.schema_version == "1.0"
    assert parsed.objects[0].category == "world"
    assert len(CANONICAL_ASSET_CATEGORIES) == 14


@pytest.mark.parametrize("status", ["draft", "review", "rejected", "revoked", "uploaded"])
def test_scene_manifest_rejects_non_publication_status(status):
    data = valid_manifest()
    data["objects"][0]["publication_status"] = status
    with pytest.raises(ValidationError):
        SceneManifestV1.model_validate(data)


def test_scene_manifest_rejects_unknown_category_and_http_url():
    data = valid_manifest()
    data["objects"][0]["category"] = "district-city"
    with pytest.raises(ValidationError):
        SceneManifestV1.model_validate(data)
    data = valid_manifest()
    data["objects"][0]["asset_url"] = "http://assets.example.invalid/test.glb"
    with pytest.raises(ValidationError):
        SceneManifestV1.model_validate(data)


def test_scene_manifest_rejects_invalid_digest_and_duplicate_entity_ids():
    data = valid_manifest()
    data["objects"][0]["sha256"] = "not-a-digest"
    with pytest.raises(ValidationError):
        SceneManifestV1.model_validate(data)
    data = valid_manifest()
    duplicate = dict(data["objects"][0])
    duplicate["asset_id"] = "another-test-asset"
    data["objects"].append(duplicate)
    with pytest.raises(ValidationError):
        SceneManifestV1.model_validate(data)


def test_scene_manifest_rejects_non_finite_coordinates_and_zero_scale():
    data = valid_manifest()
    data["objects"][0]["position"] = [float("nan"), 0, 0]
    with pytest.raises(ValidationError):
        SceneManifestV1.model_validate(data)
    data = valid_manifest()
    data["objects"][0]["scale"] = [0, 1, 1]
    with pytest.raises(ValidationError):
        SceneManifestV1.model_validate(data)

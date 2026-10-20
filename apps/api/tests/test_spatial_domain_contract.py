import pytest
from pydantic import ValidationError

from allpha_api.spatial_domain_contract import (
    SpatialCoordinatesV1,
    SpatialNavigationNodeV1,
    SpatialNavigationPageV1,
)


def node(**overrides):
    value = {
        "node_id": "universe-main",
        "parent_id": None,
        "level": "universe",
        "slug": "universe-main",
        "display_name": "Universe",
        "coordinates": {"x": 0, "y": 0, "z": 0},
        "landmarks": [{
            "landmark_id": "universe-entry",
            "kind": "entry",
            "label": "Entry",
            "coordinates": {"x": 0, "y": 0, "z": 0},
        }],
        "child_count": 0,
        "navigation_enabled": True,
    }
    value.update(overrides)
    return value


def test_spatial_navigation_contract_accepts_root_and_coordinate_frame():
    parsed = SpatialNavigationNodeV1.model_validate(node())
    assert parsed.contract_version == "1.0"
    assert parsed.level == "universe"
    assert parsed.coordinates.system == "right-handed-y-up"
    assert parsed.coordinates.units == "meters"


@pytest.mark.parametrize("level", ["galaxy", "world", "district", "zone", "booth", "poi", "scene_object"])
def test_non_root_spatial_node_requires_parent(level):
    with pytest.raises(ValidationError):
        SpatialNavigationNodeV1.model_validate(node(level=level))


def test_universe_root_rejects_parent_and_duplicate_landmarks():
    with pytest.raises(ValidationError):
        SpatialNavigationNodeV1.model_validate(node(parent_id="parent-root"))
    value = node()
    value["landmarks"] = [value["landmarks"][0], value["landmarks"][0]]
    with pytest.raises(ValidationError):
        SpatialNavigationNodeV1.model_validate(value)


def test_spatial_coordinates_reject_non_finite_values():
    with pytest.raises(ValidationError):
        SpatialCoordinatesV1(x=float("nan"), y=0, z=0)


def test_spatial_navigation_page_is_bounded_and_versioned():
    parsed = SpatialNavigationPageV1.model_validate({"items": [node()], "next_cursor": None})
    assert parsed.contract_version == "1.0"
    assert len(parsed.items) == 1

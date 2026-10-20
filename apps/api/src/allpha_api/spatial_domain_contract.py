"""Versioned spatial-domain identity, hierarchy and navigation contracts.

These schemas describe navigation metadata only. They do not grant access to a scene,
asset, or private location; authorization and publication remain API-owned.
"""
from __future__ import annotations

import math
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


SpatialLevel = Literal[
    "universe", "galaxy", "world", "district", "zone", "booth", "poi", "scene_object"
]
CoordinateSystem = Literal["right-handed-y-up"]
LandmarkKind = Literal["entry", "exit", "portal", "spawn", "poi", "waypoint"]


class SpatialDomainModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class SpatialCoordinatesV1(SpatialDomainModel):
    system: CoordinateSystem = "right-handed-y-up"
    units: Literal["meters"] = "meters"
    x: float
    y: float
    z: float

    @model_validator(mode="after")
    def coordinates_are_finite(self) -> "SpatialCoordinatesV1":
        if not all(math.isfinite(value) for value in (self.x, self.y, self.z)):
            raise ValueError("coordinates must be finite")
        return self


class SpatialLandmarkV1(SpatialDomainModel):
    landmark_id: str = Field(min_length=3, max_length=128, pattern=r"^[a-z0-9][a-z0-9._-]{2,127}$")
    kind: LandmarkKind
    label: str = Field(min_length=1, max_length=120)
    coordinates: SpatialCoordinatesV1


class SpatialNavigationNodeV1(SpatialDomainModel):
    contract_version: Literal["1.0"] = "1.0"
    node_id: str = Field(min_length=3, max_length=128, pattern=r"^[a-z0-9][a-z0-9._-]{2,127}$")
    parent_id: str | None = Field(default=None, min_length=3, max_length=128)
    level: SpatialLevel
    slug: str = Field(min_length=3, max_length=128, pattern=r"^[a-z0-9][a-z0-9._-]{2,127}$")
    display_name: str = Field(min_length=1, max_length=160)
    coordinates: SpatialCoordinatesV1 | None = None
    landmarks: tuple[SpatialLandmarkV1, ...] = Field(default=(), max_length=250)
    child_count: int = Field(ge=0, le=1000000)
    navigation_enabled: bool = True

    @field_validator("parent_id")
    @classmethod
    def parent_id_format(cls, value: str | None) -> str | None:
        if value is not None and not re.fullmatch(r"[a-z0-9][a-z0-9._-]{2,127}", value):
            raise ValueError("parent_id format is invalid")
        return value

    @model_validator(mode="after")
    def hierarchy_root_has_no_parent(self) -> "SpatialNavigationNodeV1":
        if self.level == "universe" and self.parent_id is not None:
            raise ValueError("universe root cannot have a parent")
        if self.level != "universe" and self.parent_id is None:
            raise ValueError("non-root spatial nodes require a parent")
        ids = [landmark.landmark_id for landmark in self.landmarks]
        if len(ids) != len(set(ids)):
            raise ValueError("landmark IDs must be unique within a node")
        return self


class SpatialNavigationPageV1(SpatialDomainModel):
    contract_version: Literal["1.0"] = "1.0"
    items: tuple[SpatialNavigationNodeV1, ...] = Field(max_length=100)
    next_cursor: str | None = Field(default=None, max_length=512)

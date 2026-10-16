"""Canonical, fail-closed schema for authorized spatial scene manifests.

This module validates API responses before they can be passed to a client renderer.
It is not an asset registry and does not grant publication rights by itself.
"""
from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator

CANONICAL_ASSET_CATEGORIES = (
    "universe", "galaxy", "world", "orbit", "capsule", "district", "booth",
    "content-feed", "agent-character", "live-stage", "human-live",
    "sticker-social", "animation", "navigation-fx",
)


class StrictSpatialModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class SceneObjectV1(StrictSpatialModel):
    entity_id: str = Field(min_length=1, max_length=128)
    asset_id: str = Field(min_length=1, max_length=128)
    asset_version: int = Field(ge=1)
    category: Literal[
        "universe", "galaxy", "world", "orbit", "capsule", "district", "booth",
        "content-feed", "agent-character", "live-stage", "human-live",
        "sticker-social", "animation", "navigation-fx",
    ]
    asset_url: HttpUrl
    sha256: str
    byte_size: int = Field(gt=0, le=536870912)
    position: tuple[float, float, float]
    rotation: tuple[float, float, float]
    scale: tuple[float, float, float]
    publication_status: Literal["approved", "published"]

    @field_validator("asset_url")
    @classmethod
    def require_https(cls, value: HttpUrl) -> HttpUrl:
        if value.scheme != "https":
            raise ValueError("asset_url must use HTTPS")
        return value

    @field_validator("sha256")
    @classmethod
    def require_sha256(cls, value: str) -> str:
        if not re.fullmatch(r"[a-fA-F0-9]{64}", value):
            raise ValueError("sha256 must be a 64-character hexadecimal digest")
        return value.lower()

    @field_validator("position", "rotation", "scale")
    @classmethod
    def require_finite_coordinates(cls, value: tuple[float, float, float]) -> tuple[float, float, float]:
        import math
        if not all(math.isfinite(component) for component in value):
            raise ValueError("coordinates must be finite numbers")
        return value

    @field_validator("scale")
    @classmethod
    def require_nonzero_scale(cls, value: tuple[float, float, float]) -> tuple[float, float, float]:
        if any(component <= 0 or component > 10000 for component in value):
            raise ValueError("scale components must be positive and bounded")
        return value


class SceneManifestV1(StrictSpatialModel):
    schema_version: Literal["1.0"]
    scene_id: str = Field(min_length=1, max_length=128)
    scene_version: int = Field(ge=1)
    world_id: str = Field(min_length=1, max_length=128)
    coordinate_system: Literal["right-handed-y-up"]
    units: Literal["meters"]
    fallback_mode: Literal["2d", "low_detail"] = "2d"
    objects: tuple[SceneObjectV1, ...] = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def unique_entity_ids(self) -> "SceneManifestV1":
        ids = [item.entity_id for item in self.objects]
        if len(ids) != len(set(ids)):
            raise ValueError("entity_id values must be unique within a scene")
        return self

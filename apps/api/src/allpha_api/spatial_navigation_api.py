"""Read-only public spatial hierarchy and published GLB catalog API.

Only explicitly published, public nodes and assets are exposed. Ingest receipts and
TEST_ONLY/quarantined/draft rows remain private and are never auto-published here.
"""
from __future__ import annotations

import base64
import json
import os
import re
from typing import Literal

import httpx
from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field

router = APIRouter(tags=["spatial-navigation"])
_TIMEOUT = httpx.Timeout(12.0, connect=3.0)
_LEVELS = {"universe", "galaxy", "world", "district", "zone", "booth", "poi", "scene_object"}
_CATEGORIES = {
    "universe", "galaxy", "world", "orbit", "capsule", "district", "booth",
    "content-feed", "agent-character", "live-stage", "human-live", "sticker-social",
    "animation", "navigation-fx",
}


class NavigationNode(BaseModel):
    model_config = ConfigDict(extra="forbid")
    contract_version: Literal["1.0"] = "1.0"
    node_id: str
    parent_id: str | None
    level: str
    slug: str
    display_name: str
    coordinates: dict | None = None
    landmarks: list[dict] = Field(default_factory=list)
    scene_key: str | None = None
    child_count: int = Field(ge=0)
    version: int = Field(ge=1)


class NavigationPage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    contract_version: Literal["1.0"] = "1.0"
    items: list[NavigationNode]
    next_cursor: str | None = None


class PublishedAsset(BaseModel):
    model_config = ConfigDict(extra="forbid")
    asset_id: str
    asset_version: int
    asset_key: str
    display_name: str
    category: str
    sha256: str
    byte_size: int
    published_at: str | None = None


class PublishedAssetPage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    contract_version: Literal["1.0"] = "1.0"
    items: list[PublishedAsset]
    next_cursor: str | None = None


def _config() -> tuple[str, str]:
    url = os.getenv("SUPABASE_URL", "").rstrip("/")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not key:
        raise HTTPException(status_code=503, detail={
            "code": "SPATIAL_NAVIGATION_UNAVAILABLE",
            "message": "Layanan navigasi spasial belum dikonfigurasi.",
        })
    return url, key


def _cursor_decode(cursor: str | None) -> int:
    if not cursor:
        return 0
    try:
        raw = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)).decode("ascii")
        offset = int(raw)
        if offset < 0 or offset > 1_000_000:
            raise ValueError
        return offset
    except (ValueError, UnicodeDecodeError, base64.binascii.Error) as exc:
        raise HTTPException(status_code=422, detail={
            "code": "SPATIAL_CURSOR_INVALID",
            "message": "Cursor navigasi tidak valid.",
        }) from exc


def _cursor_encode(offset: int) -> str:
    return base64.urlsafe_b64encode(str(offset).encode("ascii")).decode("ascii").rstrip("=")


async def _get_rows(client: httpx.AsyncClient, url: str, key: str, table: str, params: dict[str, str]) -> list[dict]:
    try:
        response = await client.get(
            f"{url}/rest/v1/{table}",
            headers={"apikey": key, "Authorization": f"Bearer {key}", "Accept": "application/json"},
            params=params,
        )
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=503, detail={
            "code": "SPATIAL_CATALOG_UNAVAILABLE",
            "message": "Katalog spasial sementara tidak tersedia.",
        }) from exc
    if response.status_code >= 500:
        raise HTTPException(status_code=503, detail={
            "code": "SPATIAL_CATALOG_UNAVAILABLE",
            "message": "Katalog spasial sementara tidak tersedia.",
        })
    if response.status_code >= 400:
        raise HTTPException(status_code=503, detail={
            "code": "SPATIAL_CATALOG_NOT_READY",
            "message": "Skema katalog navigasi belum tersedia.",
        })
    rows = response.json()
    if not isinstance(rows, list):
        raise HTTPException(status_code=503, detail={
            "code": "SPATIAL_CATALOG_INVALID",
            "message": "Respons katalog spasial tidak valid.",
        })
    return rows


@router.get("/v1/spatial/navigation/nodes", response_model=NavigationPage)
async def list_navigation_nodes(
    response: Response,
    parent_key: str | None = Query(default=None, min_length=3, max_length=128, pattern=r"^[a-z0-9][a-z0-9._-]{2,127}$"),
    level: str | None = Query(default=None),
    cursor: str | None = Query(default=None, max_length=64),
    limit: int = Query(default=50, ge=1, le=100),
) -> NavigationPage:
    """List only published public nodes; omit parent_key to list Universe roots."""
    response.headers["Cache-Control"] = "public, max-age=30, stale-while-revalidate=60"
    offset = _cursor_decode(cursor)
    if level is not None and level not in _LEVELS:
        raise HTTPException(status_code=422, detail={"code": "SPATIAL_LEVEL_INVALID", "message": "Level spasial tidak dikenal."})
    url, key = _config()
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        parent_id = None
        if parent_key:
            parents = await _get_rows(client, url, key, "spatial_public_navigation_nodes", {
                "select": "id,node_key", "node_key": f"eq.{parent_key}", "limit": "1",
            })
            if not parents:
                raise HTTPException(status_code=404, detail={"code": "SPATIAL_NODE_NOT_FOUND", "message": "Node spasial publik tidak ditemukan."})
            parent_id = parents[0]["id"]
        params = {
            "select": "id,node_key,parent_id,level,slug,display_name,coordinates,landmarks,scene_key,child_count,version",
            "order": "created_at.asc,id.asc",
            "limit": str(limit + 1),
            "offset": str(offset),
        }
        params["parent_id"] = f"eq.{parent_id}" if parent_id else "is.null"
        if level:
            params["level"] = f"eq.{level}"
        rows = await _get_rows(client, url, key, "spatial_public_navigation_nodes", params)
    has_more = len(rows) > limit
    rows = rows[:limit]
    items = [NavigationNode(
        node_id=str(row["node_key"]), parent_id=str(row["parent_id"]) if row.get("parent_id") else None,
        level=row["level"], slug=row["slug"], display_name=row["display_name"],
        coordinates=row.get("coordinates"), landmarks=row.get("landmarks") or [],
        scene_key=row.get("scene_key"), child_count=int(row.get("child_count") or 0),
        version=int(row.get("version") or 1),
    ) for row in rows]
    return NavigationPage(items=items, next_cursor=_cursor_encode(offset + limit) if has_more else None)


@router.get("/v1/spatial/assets", response_model=PublishedAssetPage)
async def list_published_spatial_assets(
    response: Response,
    category: str | None = Query(default=None),
    cursor: str | None = Query(default=None, max_length=64),
    limit: int = Query(default=50, ge=1, le=100),
) -> PublishedAssetPage:
    """Browse only published GLB versions. Intake receipts and TEST_ONLY rows are never exposed."""
    response.headers["Cache-Control"] = "public, max-age=30, stale-while-revalidate=60"
    if category is not None and category not in _CATEGORIES:
        raise HTTPException(status_code=422, detail={"code": "SPATIAL_CATEGORY_INVALID", "message": "Kategori aset tidak termasuk 14 kategori kanonis."})
    offset = _cursor_decode(cursor)
    url, key = _config()
    params = {
        "select": "asset_id,version,asset_key,display_name,category,sha256,byte_size,published_at",
        "status": "eq.published", "moderation_status": "eq.approved",
        "order": "published_at.asc,asset_key.asc,version.asc",
        "limit": str(limit + 1), "offset": str(offset),
    }
    if category:
        params["category"] = f"eq.{category}"
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        rows = await _get_rows(client, url, key, "spatial_asset_versions", params)
    has_more = len(rows) > limit
    rows = rows[:limit]
    items = [PublishedAsset(
        asset_id=str(row["asset_id"]), asset_version=int(row["version"]),
        asset_key=row["asset_key"], display_name=row["display_name"], category=row["category"],
        sha256=row["sha256"], byte_size=int(row["byte_size"]), published_at=row.get("published_at"),
    ) for row in rows]
    return PublishedAssetPage(items=items, next_cursor=_cursor_encode(offset + limit) if has_more else None)

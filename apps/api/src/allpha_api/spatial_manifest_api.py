"""Public, fail-closed scene manifest endpoint backed by the canonical spatial registry."""
from __future__ import annotations

import os
import secrets
from urllib.parse import quote

import httpx
from fastapi import APIRouter, Header, HTTPException, Path, Response

from allpha_api.spatial_scene_contract import SceneManifestV1

router = APIRouter(tags=["spatial-renderer"])
_SIGNED_URL_TTL_SECONDS = 300
_TIMEOUT = httpx.Timeout(12.0, connect=3.0)


def _service_config() -> tuple[str, str]:
    url = os.getenv("SUPABASE_URL", "").rstrip("/")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not key:
        raise HTTPException(status_code=503, detail={
            "code": "SPATIAL_MANIFEST_UNAVAILABLE",
            "message": "Layanan manifest spasial belum dikonfigurasi.",
        })
    return url, key


async def _get_rows(client: httpx.AsyncClient, url: str, key: str, table: str, params: dict[str, str]) -> list[dict]:
    response = await client.get(
        f"{url}/rest/v1/{table}",
        headers={"apikey": key, "Authorization": f"Bearer {key}"},
        params=params,
    )
    if response.status_code >= 500:
        raise HTTPException(status_code=503, detail={
            "code": "SPATIAL_CATALOG_UNAVAILABLE",
            "message": "Katalog aset spasial sementara tidak tersedia.",
        })
    if response.status_code >= 400:
        # Do not leak Postgres/PostgREST internals; a missing source-only migration is a blocked integration.
        raise HTTPException(status_code=503, detail={
            "code": "SPATIAL_CATALOG_NOT_READY",
            "message": "Skema katalog spasial belum tersedia pada lingkungan ini.",
        })
    rows = response.json()
    if not isinstance(rows, list):
        raise HTTPException(status_code=503, detail={
            "code": "SPATIAL_CATALOG_INVALID",
            "message": "Respons katalog spasial tidak valid.",
        })
    return rows


async def _signed_asset_url(client: httpx.AsyncClient, url: str, key: str, bucket: str, path: str) -> str:
    allowed_bucket = os.getenv("ALLPHA_SPATIAL_ASSET_BUCKET", "")
    if not allowed_bucket or bucket != allowed_bucket:
        raise HTTPException(status_code=503, detail={
            "code": "SPATIAL_STORAGE_BUCKET_NOT_CONFIGURED",
            "message": "Bucket aset spasial kanonis belum dikonfigurasi.",
        })
    if not bucket or not path or path.startswith("/") or ".." in path.split("/"):
        raise HTTPException(status_code=409, detail={
            "code": "SPATIAL_ASSET_STORAGE_REFERENCE_INVALID",
            "message": "Referensi penyimpanan aset tidak valid.",
        })
    endpoint = f"{url}/storage/v1/object/sign/{quote(bucket, safe='')}/{quote(path, safe='/')}"
    response = await client.post(
        endpoint,
        headers={"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={"expiresIn": _SIGNED_URL_TTL_SECONDS},
    )
    if response.status_code >= 400:
        raise HTTPException(status_code=503, detail={
            "code": "SPATIAL_ASSET_URL_UNAVAILABLE",
            "message": "URL aset yang terotorisasi tidak dapat diterbitkan.",
        })
    signed_path = response.json().get("signedURL")
    if not isinstance(signed_path, str) or not signed_path:
        raise HTTPException(status_code=503, detail={
            "code": "SPATIAL_ASSET_URL_INVALID",
            "message": "Layanan penyimpanan mengembalikan URL aset yang tidak valid.",
        })
    if signed_path.startswith("https://"):
        return signed_path
    return f"{url}/storage/v1{signed_path if signed_path.startswith('/') else '/' + signed_path}"


@router.get("/v1/spatial/test/scenes/{scene_key}/manifest")
async def get_test_only_scene_manifest(
    response: Response,
    scene_key: str = Path(min_length=3, max_length=120, pattern=r"^[a-z0-9][a-z0-9._-]{2,119}$"),
    test_key: str | None = Header(default=None, alias="X-Allpha-Spatial-Test-Key"),
) -> dict:
    """Return an isolated TEST_ONLY scene only to callers holding a dedicated test secret.

    This endpoint never changes lifecycle state and never makes assets publicly published.
    Do not place the test key in browser/mobile bundles; use it only in trusted test runners.
    """
    response.headers["Cache-Control"] = "no-store, private"
    response.headers["Vary"] = "X-Allpha-Spatial-Test-Key"
    expected = os.getenv("ALLPHA_SPATIAL_TEST_ACCESS_KEY", "")
    if len(expected) < 32 or not test_key or not secrets.compare_digest(test_key, expected):
        raise HTTPException(status_code=404, detail={
            "code": "SPATIAL_TEST_SCENE_NOT_FOUND",
            "message": "Scene pengujian tidak ditemukan.",
        })
    url, key = _service_config()
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            scenes = await _get_rows(client, url, key, "spatial_scene_versions", {
                "select": "scene_id,version,world_id,coordinate_system,units,fallback_mode,objects,status",
                "scene_key": f"eq.{scene_key}",
                "status": "eq.test_only",
                "order": "version.desc",
                "limit": "1",
            })
            if not scenes:
                raise HTTPException(status_code=404, detail={
                    "code": "SPATIAL_TEST_SCENE_NOT_FOUND",
                    "message": "Scene pengujian tidak ditemukan.",
                })
            scene = scenes[0]
            placements = scene.get("objects")
            if not isinstance(placements, list) or not placements:
                raise HTTPException(status_code=409, detail={
                    "code": "SPATIAL_TEST_SCENE_INVALID",
                    "message": "Scene pengujian tidak memiliki penempatan aset yang valid.",
                })
            objects = []
            for placement in placements:
                if not isinstance(placement, dict):
                    raise HTTPException(status_code=409, detail={
                        "code": "SPATIAL_TEST_SCENE_INVALID",
                        "message": "Penempatan aset pengujian tidak valid.",
                    })
                asset_id, asset_version = placement.get("asset_id"), placement.get("asset_version")
                if not isinstance(asset_id, str) or not isinstance(asset_version, int):
                    raise HTTPException(status_code=409, detail={
                        "code": "SPATIAL_TEST_SCENE_INVALID",
                        "message": "Referensi versi aset pengujian tidak valid.",
                    })
                assets = await _get_rows(client, url, key, "spatial_asset_versions", {
                    "select": "asset_id,version,category,sha256,byte_size,storage_bucket,storage_path,status",
                    "asset_id": f"eq.{asset_id}",
                    "version": f"eq.{asset_version}",
                    "status": "eq.test_only",
                    "limit": "1",
                })
                if not assets:
                    raise HTTPException(status_code=409, detail={
                        "code": "SPATIAL_TEST_ASSET_NOT_ALLOWED",
                        "message": "Scene pengujian hanya boleh merujuk aset TEST_ONLY.",
                    })
                asset = assets[0]
                signed_url = await _signed_asset_url(
                    client, url, key, asset.get("storage_bucket", ""), asset.get("storage_path", "")
                )
                objects.append({
                    "entity_id": placement.get("entity_id"),
                    "asset_id": asset["asset_id"],
                    "asset_version": asset["version"],
                    "category": asset["category"],
                    "asset_url": signed_url,
                    "sha256": asset["sha256"],
                    "byte_size": asset["byte_size"],
                    "position": placement.get("position", [0, 0, 0]),
                    "rotation": placement.get("rotation", [0, 0, 0]),
                    "scale": placement.get("scale", [1, 1, 1]),
                    "publication_status": "test_only",
                })
            return {
                "schema_version": "1.0",
                "scene_id": str(scene["scene_id"]),
                "scene_version": scene["version"],
                "world_id": scene["world_id"],
                "coordinate_system": scene["coordinate_system"],
                "units": scene["units"],
                "fallback_mode": scene["fallback_mode"],
                "lifecycle": "test_only",
                "objects": objects,
            }
    except HTTPException:
        raise
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=503, detail={
            "code": "SPATIAL_CATALOG_UNAVAILABLE",
            "message": "Katalog pengujian spasial sementara tidak dapat diakses.",
        }) from exc


@router.get("/v1/spatial/scenes/{scene_key}/manifest", response_model=SceneManifestV1)
async def get_published_scene_manifest(
    response: Response,
    scene_key: str = Path(min_length=3, max_length=120, pattern=r"^[a-z0-9][a-z0-9._-]{2,119}$"),
) -> SceneManifestV1:
    """Return only a published scene and published, approved asset versions."""
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["Vary"] = "Authorization"
    url, key = _service_config()
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            scenes = await _get_rows(client, url, key, "spatial_scene_versions", {
                "select": "scene_id,version,world_id,coordinate_system,units,fallback_mode,objects,status",
                "scene_key": f"eq.{scene_key}",
                "status": "eq.published",
                "order": "version.desc",
                "limit": "1",
            })
            if not scenes:
                raise HTTPException(status_code=404, detail={
                    "code": "SPATIAL_SCENE_NOT_FOUND",
                    "message": "Scene yang dipublikasikan tidak ditemukan.",
                })
            scene = scenes[0]
            raw_objects = scene.get("objects")
            if not isinstance(raw_objects, list) or not raw_objects:
                raise HTTPException(status_code=409, detail={
                    "code": "SPATIAL_SCENE_INVALID",
                    "message": "Scene yang dipublikasikan tidak memiliki penempatan aset yang valid.",
                })

            objects = []
            for placement in raw_objects:
                if not isinstance(placement, dict):
                    raise HTTPException(status_code=409, detail={
                        "code": "SPATIAL_SCENE_INVALID",
                        "message": "Penempatan aset pada scene tidak valid.",
                    })
                asset_id = placement.get("asset_id")
                asset_version = placement.get("asset_version")
                if not isinstance(asset_id, str) or not isinstance(asset_version, int):
                    raise HTTPException(status_code=409, detail={
                        "code": "SPATIAL_SCENE_INVALID",
                        "message": "Referensi versi aset pada scene tidak valid.",
                    })
                assets = await _get_rows(client, url, key, "spatial_asset_versions", {
                    "select": "asset_id,version,category,sha256,byte_size,storage_bucket,storage_path,status,moderation_status,license_evidence",
                    "asset_id": f"eq.{asset_id}",
                    "version": f"eq.{asset_version}",
                    "status": "eq.published",
                    "moderation_status": "eq.approved",
                    "limit": "1",
                })
                if not assets:
                    raise HTTPException(status_code=409, detail={
                        "code": "SPATIAL_ASSET_NOT_PUBLISHED",
                        "message": "Scene merujuk aset yang belum dipublikasikan atau tidak disetujui.",
                    })
                asset = assets[0]
                if not asset.get("license_evidence") or asset.get("license_evidence") == {}:
                    raise HTTPException(status_code=409, detail={
                        "code": "SPATIAL_ASSET_RIGHTS_UNVERIFIED",
                        "message": "Bukti lisensi aset belum tersedia.",
                    })
                signed_url = await _signed_asset_url(
                    client, url, key, asset.get("storage_bucket", ""), asset.get("storage_path", "")
                )
                objects.append({
                    "entity_id": placement.get("entity_id"),
                    "asset_id": asset["asset_id"],
                    "asset_version": asset["version"],
                    "category": asset["category"],
                    "asset_url": signed_url,
                    "sha256": asset["sha256"],
                    "byte_size": asset["byte_size"],
                    "position": placement.get("position", [0, 0, 0]),
                    "rotation": placement.get("rotation", [0, 0, 0]),
                    "scale": placement.get("scale", [1, 1, 1]),
                    "publication_status": "published",
                })
            manifest = SceneManifestV1.model_validate({
                "schema_version": "1.0",
                "scene_id": str(scene["scene_id"]),
                "scene_version": scene["version"],
                "world_id": scene["world_id"],
                "coordinate_system": scene["coordinate_system"],
                "units": scene["units"],
                "fallback_mode": scene["fallback_mode"],
                "objects": objects,
            })
            return manifest
    except HTTPException:
        raise
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=503, detail={
            "code": "SPATIAL_CATALOG_UNAVAILABLE",
            "message": "Katalog aset spasial sementara tidak dapat diakses.",
        }) from exc

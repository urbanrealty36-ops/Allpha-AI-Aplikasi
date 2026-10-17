"""Trusted TEST_ONLY GLB ingest for exercising the canonical private-storage/manifest path.

This route is intended for trusted automation only. It never approves or publishes assets.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import uuid
from urllib.parse import quote

import httpx
from fastapi import APIRouter, File, Form, Header, HTTPException, UploadFile

from allpha_api.spatial_test_auth import is_authorized_spatial_test_request

router = APIRouter(tags=["spatial-ingest"])
MAX_BYTES = 536_870_912
CATEGORIES = {
    "universe", "galaxy", "world", "orbit", "capsule", "district", "booth",
    "content-feed", "agent-character", "live-stage", "human-live",
    "sticker-social", "animation", "navigation-fx",
}
_TIMEOUT = httpx.Timeout(30.0, connect=5.0)


def _error(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code, "message": message})


def _config() -> tuple[str, str, str]:
    url = os.getenv("SUPABASE_URL", "").rstrip("/")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    bucket = os.getenv("ALLPHA_SPATIAL_ASSET_BUCKET", "")
    if not url or not key or not bucket:
        raise _error(503, "SPATIAL_INGEST_UNAVAILABLE", "Layanan ingest spasial belum dikonfigurasi.")
    return url, key, bucket


def _check_glb(data: bytes) -> None:
    # Validate the GLB v2 container and the first JSON chunk before storage.
    if len(data) < 20 or data[:4] != b"glTF":
        raise _error(422, "SPATIAL_GLB_INVALID", "File bukan container GLB yang valid.")
    version = int.from_bytes(data[4:8], "little")
    declared = int.from_bytes(data[8:12], "little")
    chunk_length = int.from_bytes(data[12:16], "little")
    chunk_type = data[16:20]
    if version != 2 or declared != len(data) or chunk_type != b"JSON" or chunk_length < 2 or 20 + chunk_length > len(data):
        raise _error(422, "SPATIAL_GLB_INVALID", "Header atau JSON chunk GLB tidak valid.")
    try:
        document = json.loads(data[20:20 + chunk_length].decode("utf-8").rstrip(" \\t\\r\\n\\0"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise _error(422, "SPATIAL_GLB_INVALID", "JSON chunk GLB tidak dapat dibaca.") from exc
    if not isinstance(document, dict) or not isinstance(document.get("asset"), dict) or document["asset"].get("version") != "2.0":
        raise _error(422, "SPATIAL_GLB_INVALID", "Dokumen GLB tidak menyatakan glTF 2.0.")


async def _rows(client: httpx.AsyncClient, url: str, key: str, table: str, params: dict[str, str]) -> list[dict]:
    response = await client.get(
        f"{url}/rest/v1/{table}",
        headers={"apikey": key, "Authorization": f"Bearer {key}"},
        params=params,
    )
    if response.status_code >= 400:
        raise _error(503, "SPATIAL_CATALOG_UNAVAILABLE", "Katalog spasial belum dapat diakses.")
    value = response.json()
    if not isinstance(value, list):
        raise _error(503, "SPATIAL_CATALOG_INVALID", "Respons katalog spasial tidak valid.")
    return value


async def _insert(client: httpx.AsyncClient, url: str, key: str, table: str, body: dict) -> dict:
    response = await client.post(
        f"{url}/rest/v1/{table}",
        headers={
            "apikey": key, "Authorization": f"Bearer {key}",
            "Content-Type": "application/json", "Prefer": "return=representation",
        },
        json=body,
    )
    if response.status_code >= 400:
        raise _error(503, "SPATIAL_CATALOG_WRITE_FAILED", "Katalog spasial gagal mencatat ingest TEST_ONLY.")
    rows = response.json()
    if not isinstance(rows, list) or not rows:
        raise _error(503, "SPATIAL_CATALOG_WRITE_FAILED", "Katalog spasial tidak mengembalikan hasil ingest.")
    return rows[0]


@router.post("/v1/spatial/test/assets/ingest", status_code=201)
async def ingest_test_only_glb(
    file: UploadFile = File(...),
    metadata: str = Form(...),
    test_key: str | None = Header(default=None, alias="X-Allpha-Spatial-Test-Key"),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict:
    """Upload a verified GLB into private storage; register only evidence-mapped TEST_ONLY assets."""
    if not is_authorized_spatial_test_request(test_key, authorization):
        raise _error(404, "SPATIAL_TEST_INGEST_NOT_FOUND", "Endpoint ingest pengujian tidak ditemukan.")

    try:
        meta = json.loads(metadata)
    except json.JSONDecodeError as exc:
        raise _error(422, "SPATIAL_INGEST_METADATA_INVALID", "Metadata ingest harus berupa JSON valid.") from exc
    if not isinstance(meta, dict):
        raise _error(422, "SPATIAL_INGEST_METADATA_INVALID", "Metadata ingest harus berupa objek JSON.")

    asset_key = meta.get("asset_key")
    scene_key = meta.get("scene_key")
    category = meta.get("category")
    source_url = meta.get("source_url")
    source_repo = meta.get("source_repo")
    source_path = meta.get("source_path")
    display_name = meta.get("display_name")
    if not isinstance(asset_key, str) or not re.fullmatch(r"[a-z0-9][a-z0-9._-]{2,120}", asset_key):
        raise _error(422, "SPATIAL_INGEST_METADATA_INVALID", "asset_key tidak valid.")
    if not isinstance(scene_key, str) or not re.fullmatch(r"[a-z0-9][a-z0-9._-]{2,120}", scene_key):
        raise _error(422, "SPATIAL_INGEST_METADATA_INVALID", "scene_key tidak valid.")
    if category in ("", "unmapped"):
        category = None
    if category is not None and category not in CATEGORIES:
        raise _error(422, "SPATIAL_INGEST_METADATA_INVALID", "category bukan salah satu dari 14 kategori kanonis.")
    if not isinstance(source_url, str) or not source_url.startswith(("https://", "http://")) or len(source_url) > 2048:
        raise _error(422, "SPATIAL_INGEST_METADATA_INVALID", "source_url harus berupa URL HTTP(S).")
    if not isinstance(display_name, str) or not 2 <= len(display_name) <= 160:
        raise _error(422, "SPATIAL_INGEST_METADATA_INVALID", "display_name tidak valid.")
    if not isinstance(source_repo, str) or not isinstance(source_path, str):
        raise _error(422, "SPATIAL_INGEST_METADATA_INVALID", "source_repo dan source_path wajib dicatat.")

    data = await file.read(MAX_BYTES + 1)
    if not data or len(data) > MAX_BYTES:
        raise _error(413, "SPATIAL_GLB_SIZE_INVALID", "Ukuran GLB harus antara 1 byte dan 512 MiB.")
    _check_glb(data)
    digest = hashlib.sha256(data).hexdigest()
    asset_id, scene_id = str(uuid.uuid4()), str(uuid.uuid4())
    bucket_config = os.getenv("ALLPHA_SPATIAL_ASSET_BUCKET", "")
    url, key, bucket = _config()
    if bucket != bucket_config:
        raise _error(503, "SPATIAL_STORAGE_BUCKET_NOT_CONFIGURED", "Bucket spasial tidak cocok dengan konfigurasi kanonis.")
    object_path = f"test-only/{asset_key}/{digest}.glb" if category else f"test-only-unmapped/{asset_key}/{digest}.glb"
    headers = {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "model/gltf-binary", "x-upsert": "true"}

    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        # Idempotent retry: reuse only the exact same asset bytes; never overwrite a different version.
        existing = await _rows(client, url, key, "spatial_asset_versions", {
            "select": "asset_id,version,sha256,storage_bucket,storage_path,status",
            "asset_key": f"eq.{asset_key}", "version": "eq.1", "limit": "1",
        })
        if existing:
            row = existing[0]
            if row.get("sha256") != digest or row.get("status") != "test_only":
                raise _error(409, "SPATIAL_INGEST_CONFLICT", "asset_key versi 1 sudah dipakai oleh aset berbeda.")
            asset_id = row["asset_id"]
            object_path = row["storage_path"]
        else:
            upload = await client.post(
                f"{url}/storage/v1/object/{quote(bucket, safe='')}/{quote(object_path, safe='/')}",
                headers=headers, content=data,
            )
            if upload.status_code >= 400:
                raise _error(503, "SPATIAL_STORAGE_UPLOAD_FAILED", "Upload ke private Storage gagal.")
            receipt_body = {
                "asset_key": asset_key, "display_name": display_name, "source_url": source_url,
                "source_repo": source_repo, "source_path": source_path,
                "source_license_claim": str(meta.get("license") or "unknown")[:256],
                "review_state": str(meta.get("review") or "unreviewed")[:256],
                "category_candidate": category,
                "category_mapping_status": "mapped" if category else "unmapped",
                "sha256": digest, "byte_size": len(data), "storage_bucket": bucket,
                "storage_path": object_path,
                "lifecycle_status": "test_only" if category else "quarantined",
            }
            receipt = await client.post(
                f"{url}/rest/v1/spatial_asset_ingest_receipts?on_conflict=asset_key",
                headers={"apikey": key, "Authorization": f"Bearer {key}",
                         "Content-Type": "application/json", "Prefer": "resolution=merge-duplicates,return=representation"},
                json=receipt_body,
            )
            if receipt.status_code >= 400:
                raise _error(503, "SPATIAL_INGEST_RECEIPT_FAILED", "Bukti provenance ingest tidak dapat dicatat.")
            if not category:
                return {
                    "lifecycle": "quarantined", "registry_status": "unmapped",
                    "storage_bucket": bucket, "storage_path": object_path,
                    "sha256": digest, "byte_size": len(data),
                    "source_repo": source_repo, "source_path": source_path,
                    "rights_status": "unverified", "moderation_status": "pending",
                }
            await _insert(client, url, key, "spatial_asset_versions", {
                "asset_id": asset_id, "version": 1, "asset_key": asset_key,
                "display_name": display_name, "category": category, "source_url": source_url,
                "provenance": {"source_repository": source_repo, "source_path": source_path,
                               "source_license_claim": str(meta.get("license") or "unknown"),
                               "source_review_state": str(meta.get("review") or "unreviewed"),
                               "ingest_mode": "trusted_test_only", "sha256": digest},
                "license_evidence": {"status": "unverified", "note": "TEST_ONLY; no public rights approval"},
                "sha256": digest, "byte_size": len(data), "mime_type": "model/gltf-binary",
                "storage_bucket": bucket, "storage_path": object_path,
                "dimensions": {}, "material_metadata": {}, "capabilities": {"glb_container": "valid"},
                "compatibility": {"native_renderer_acceptance": "pending"},
                "moderation_status": "pending", "status": "test_only",
            })

        scene = await _rows(client, url, key, "spatial_scene_versions", {
            "select": "scene_id,version,objects,status", "scene_key": f"eq.{scene_key}",
            "version": "eq.1", "limit": "1",
        })
        if scene:
            objects = scene[0].get("objects")
            if scene[0].get("status") != "test_only" or not isinstance(objects, list):
                raise _error(409, "SPATIAL_SCENE_INGEST_CONFLICT", "scene_key versi 1 sudah dipakai oleh scene lain.")
            same_asset = any(
                isinstance(item, dict)
                and item.get("asset_id") == asset_id
                and item.get("asset_version") == 1
                for item in objects
            )
            if not same_asset:
                raise _error(409, "SPATIAL_SCENE_INGEST_CONFLICT", "scene_key sudah menunjuk aset TEST_ONLY yang berbeda.")
            scene_id = scene[0]["scene_id"]
        else:
            await _insert(client, url, key, "spatial_scene_versions", {
                "scene_id": scene_id, "version": 1, "scene_key": scene_key,
                "world_id": str(meta.get("world_id") or "test-world"),
                "coordinate_system": "right-handed-y-up", "units": "meters",
                "fallback_mode": "2d",
                "objects": [{
                    "entity_id": str(meta.get("entity_id") or "test-asset"),
                    "asset_id": asset_id, "asset_version": 1,
                    "position": [0, 0, 0], "rotation": [0, 0, 0], "scale": [1, 1, 1],
                }],
                "status": "test_only",
            })

    return {
        "lifecycle": "test_only", "asset_id": asset_id, "asset_version": 1,
        "scene_key": scene_key, "scene_version": 1, "storage_bucket": bucket,
        "storage_path": object_path, "sha256": digest, "byte_size": len(data),
        "rights_status": "unverified", "moderation_status": "pending",
        "next": f"/v1/spatial/test/scenes/{scene_key}/manifest",
    }

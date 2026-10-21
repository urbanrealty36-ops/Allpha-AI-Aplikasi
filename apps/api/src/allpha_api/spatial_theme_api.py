"""Canonical Theme Builder and versioned spatial asset manifest API for ENG-P22.

Theme definitions are declarative JSON only. Published manifests resolve immutable asset
versions through the existing spatial asset registry; this module does not create a
second asset registry or renderer.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any, Literal

import httpx
from fastapi import APIRouter, Depends, HTTPException, Path, Request, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from allpha_api.operator_security import privileged_rest_request, require_operator_scope, write_operator_audit
from allpha_api.spatial_manifest_api import _get_rows, _service_config, _signed_asset_url

router = APIRouter(tags=["spatial-themes"])
CATEGORIES = (
    "universe", "galaxy", "world", "orbit", "capsule", "district", "booth",
    "content-feed", "agent-character", "live-stage", "human-live",
    "sticker-social", "animation", "navigation-fx",
)
_KEY = re.compile(r"^[a-z0-9][a-z0-9._-]{2,119}$")
_TIMEOUT = httpx.Timeout(12.0, connect=3.0)


def _fail(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code, "message": message})


class Transform(BaseModel):
    model_config = ConfigDict(extra="forbid")
    position: tuple[float, float, float] = (0.0, 0.0, 0.0)
    rotation: tuple[float, float, float] = (0.0, 0.0, 0.0)
    scale: tuple[float, float, float] = (1.0, 1.0, 1.0)

    @model_validator(mode="after")
    def finite_transform(self):
        for vector in (self.position, self.rotation, self.scale):
            if any(not abs(value) < float("inf") for value in vector):
                raise ValueError("Transform harus berisi angka finite.")
        if any(value <= 0 for value in self.scale):
            raise ValueError("Skala transform harus positif.")
        return self


class ThemeSlot(BaseModel):
    model_config = ConfigDict(extra="forbid")
    slot_key: str = Field(min_length=3, max_length=120, pattern=r"^[a-z0-9][a-z0-9._-]{2,119}$")
    category: Literal[
        "universe", "galaxy", "world", "orbit", "capsule", "district", "booth",
        "content-feed", "agent-character", "live-stage", "human-live",
        "sticker-social", "animation", "navigation-fx",
    ]
    asset_key: str = Field(min_length=3, max_length=120, pattern=r"^[a-z0-9][a-z0-9._-]{2,119}$")
    asset_version: int = Field(ge=1)
    transform: Transform = Field(default_factory=Transform)
    required: bool = True


class ThemeManifestDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["1.0"] = "1.0"
    theme_key: str = Field(min_length=3, max_length=120, pattern=r"^[a-z0-9][a-z0-9._-]{2,119}$")
    display_name: str = Field(min_length=2, max_length=160)
    description: str = Field(default="", max_length=2000)
    fallback_mode: Literal["2d", "low_detail"] = "low_detail"
    slots: list[ThemeSlot] = Field(default_factory=list, max_length=350)

    @model_validator(mode="after")
    def unique_slots(self):
        keys = [slot.slot_key for slot in self.slots]
        if len(keys) != len(set(keys)):
            raise ValueError("slot_key tidak boleh duplikat.")
        return self


class ThemeCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    theme_key: str = Field(min_length=3, max_length=120, pattern=r"^[a-z0-9][a-z0-9._-]{2,119}$")
    display_name: str = Field(min_length=2, max_length=160)
    description: str = Field(default="", max_length=2000)


class ThemeVersionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    manifest: ThemeManifestDraft


async def _get_asset(asset_key: str, version: int) -> dict[str, Any] | None:
    rows = await privileged_rest_request("GET", "spatial_asset_versions", params={
        "select": "asset_id,asset_key,version,category,status,moderation_status,license_evidence,sha256,byte_size,storage_bucket,storage_path,capabilities,compatibility",
        "asset_key": f"eq.{asset_key}", "version": f"eq.{version}", "limit": "1",
    })
    return rows[0] if isinstance(rows, list) and rows else None


async def _validate_assets(manifest: ThemeManifestDraft, *, for_publish: bool = False) -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    resolved: list[dict[str, Any]] = []
    for slot in manifest.slots:
        asset = await _get_asset(slot.asset_key, slot.asset_version)
        if not asset:
            errors.append({"slot_key": slot.slot_key, "code": "ASSET_VERSION_NOT_FOUND"})
            continue
        if asset.get("category") != slot.category:
            errors.append({"slot_key": slot.slot_key, "code": "CATEGORY_MISMATCH"})
            continue
        if asset.get("status") in {"rejected", "revoked", "retired", "blocked", "failed"}:
            errors.append({"slot_key": slot.slot_key, "code": "ASSET_LIFECYCLE_BLOCKED"})
            continue
        license_evidence = asset.get("license_evidence")
        rights_verified = isinstance(license_evidence, dict) and license_evidence.get("status") == "verified"
        is_published = asset.get("status") == "published" and asset.get("moderation_status") == "approved" and rights_verified
        if for_publish and not is_published:
            errors.append({"slot_key": slot.slot_key, "code": "ASSET_NOT_PUBLICATION_READY"})
            continue
        if not is_published:
            warnings.append({"slot_key": slot.slot_key, "code": "ASSET_NOT_PUBLIC"})
        resolved.append({"slot": slot.model_dump(mode="json"), "asset": asset, "publication_ready": is_published})
    missing_categories = sorted(set(CATEGORIES) - {slot.category for slot in manifest.slots})
    if missing_categories:
        warnings.append({"code": "THEME_CATEGORY_COVERAGE_INCOMPLETE", "categories": ",".join(missing_categories)})
        if for_publish:
            errors.append({"code": "THEME_CATEGORY_COVERAGE_INCOMPLETE", "categories": ",".join(missing_categories)})
    return {"valid": not errors, "errors": errors, "warnings": warnings, "resolved": resolved,
            "category_coverage": {category: sum(1 for slot in manifest.slots if slot.category == category) for category in CATEGORIES}}


def _canonical_digest(manifest: ThemeManifestDraft) -> str:
    canonical = json.dumps(manifest.model_dump(mode="json"), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


async def _build_render_manifest(theme: dict[str, Any], version: dict[str, Any], *, public: bool) -> dict[str, Any]:
    try:
        draft = ThemeManifestDraft.model_validate(version.get("manifest"))
    except Exception as exc:
        raise _fail(409, "SPATIAL_THEME_MANIFEST_INVALID", "Definisi Theme tersimpan tidak lolos validasi schema.") from exc
    if draft.theme_key != theme.get("theme_key"):
        raise _fail(409, "SPATIAL_THEME_KEY_MISMATCH", "Theme key pada versi tidak sesuai.")
    validation = await _validate_assets(draft, for_publish=public)
    if not validation["valid"]:
        raise _fail(409, "SPATIAL_THEME_ASSET_NOT_READY", "Manifest Theme memiliki referensi aset yang belum siap.")
    url, key = _service_config()
    objects = []
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            for item in validation["resolved"]:
                slot, asset = item["slot"], item["asset"]
                signed_url = await _signed_asset_url(client, url, key, asset.get("storage_bucket", ""), asset.get("storage_path", ""))
                transform = slot["transform"]
                objects.append({
                    "entity_id": slot["slot_key"], "asset_id": asset["asset_id"],
                    "asset_version": asset["version"], "category": asset["category"],
                    "asset_url": signed_url, "sha256": asset["sha256"], "byte_size": asset["byte_size"],
                    "position": transform["position"], "rotation": transform["rotation"], "scale": transform["scale"],
                    "publication_status": "published" if public else "approved",
                })
    except HTTPException:
        raise
    except httpx.HTTPError as exc:
        raise _fail(503, "SPATIAL_THEME_ASSET_URL_UNAVAILABLE", "URL aset Theme tidak dapat diterbitkan.") from exc
    return {
        "schema_version": "1.0", "scene_id": f"theme:{theme['theme_key']}",
        "scene_version": version["version"], "world_id": theme["theme_key"],
        "coordinate_system": "right-handed-y-up", "units": "meters",
        "fallback_mode": draft.fallback_mode, "theme_key": theme["theme_key"],
        "theme_version": version["version"], "theme_name": draft.display_name,
        "manifest_sha256": version["manifest_sha256"], "objects": objects,
    }


@router.get("/v1/admin/spatial/themes")
async def list_themes(
    limit: int = 50, offset: int = 0,
    operator: dict[str, Any] = Depends(require_operator_scope("platform:content.moderate")),
) -> dict[str, Any]:
    if not 1 <= limit <= 100 or offset < 0:
        raise _fail(422, "SPATIAL_THEME_PAGINATION_INVALID", "Pagination Theme tidak valid.")
    rows = await privileged_rest_request("GET", "spatial_themes", params={
        "select": "theme_key,display_name,description,status,active_version,created_at,updated_at",
        "order": "updated_at.desc", "limit": str(limit), "offset": str(offset),
    })
    return {"items": rows or [], "limit": limit, "offset": offset}


@router.post("/v1/admin/spatial/themes", status_code=201)
async def create_theme(
    payload: ThemeCreate, request: Request,
    operator: dict[str, Any] = Depends(require_operator_scope("platform:content.moderate")),
) -> dict[str, Any]:
    existing = await privileged_rest_request("GET", "spatial_themes", params={
        "select": "theme_key", "theme_key": f"eq.{payload.theme_key}", "limit": "1",
    })
    if existing:
        raise _fail(409, "SPATIAL_THEME_ALREADY_EXISTS", "Theme key sudah digunakan.")
    await write_operator_audit(request, actor_user_id=operator["id"], action="spatial.theme.create",
        outcome="attempted", resource_type="spatial_theme", resource_id=payload.theme_key,
        metadata={"display_name": payload.display_name})
    rows = await privileged_rest_request("POST", "spatial_themes", body={
        **payload.model_dump(), "status": "draft", "active_version": None,
        "created_by": operator["id"], "updated_at": datetime.now(timezone.utc).isoformat(),
    }, prefer="return=representation")
    if not isinstance(rows, list) or not rows:
        raise _fail(503, "SPATIAL_THEME_CREATE_FAILED", "Theme tidak dapat disimpan.")
    await write_operator_audit(request, actor_user_id=operator["id"], action="spatial.theme.create",
        outcome="allowed", resource_type="spatial_theme", resource_id=payload.theme_key)
    return {"item": rows[0]}


@router.post("/v1/admin/spatial/themes/{theme_key}/versions", status_code=201)
async def create_theme_version(
    payload: ThemeVersionCreate, request: Request,
    theme_key: str = Path(min_length=3, max_length=120, pattern=r"^[a-z0-9][a-z0-9._-]{2,119}$"),
    operator: dict[str, Any] = Depends(require_operator_scope("platform:content.moderate")),
) -> dict[str, Any]:
    if payload.manifest.theme_key != theme_key:
        raise _fail(422, "SPATIAL_THEME_KEY_MISMATCH", "Manifest harus menggunakan theme_key pada URL.")
    themes = await privileged_rest_request("GET", "spatial_themes", params={
        "select": "theme_key,status", "theme_key": f"eq.{theme_key}", "limit": "1",
    })
    if not themes:
        raise _fail(404, "SPATIAL_THEME_NOT_FOUND", "Theme tidak ditemukan.")
    versions = await privileged_rest_request("GET", "spatial_theme_versions", params={
        "select": "version", "theme_key": f"eq.{theme_key}", "order": "version.desc", "limit": "1",
    })
    version = int(versions[0]["version"]) + 1 if versions else 1
    validation = await _validate_assets(payload.manifest)
    digest = _canonical_digest(payload.manifest)
    await write_operator_audit(request, actor_user_id=operator["id"], action="spatial.theme.version.create",
        outcome="attempted", resource_type="spatial_theme_version", resource_id=f"{theme_key}:{version}",
        metadata={"manifest_sha256": digest, "slot_count": len(payload.manifest.slots), "validation_errors": len(validation["errors"])})
    rows = await privileged_rest_request("POST", "spatial_theme_versions", body={
        "theme_key": theme_key, "version": version, "schema_version": "1.0",
        "manifest": payload.manifest.model_dump(mode="json"), "manifest_sha256": digest,
        "status": "draft", "created_by": operator["id"],
    }, prefer="return=representation")
    if not isinstance(rows, list) or not rows:
        raise _fail(503, "SPATIAL_THEME_VERSION_CREATE_FAILED", "Versi Theme tidak dapat disimpan.")
    await write_operator_audit(request, actor_user_id=operator["id"], action="spatial.theme.version.create",
        outcome="allowed", resource_type="spatial_theme_version", resource_id=f"{theme_key}:{version}",
        metadata={"manifest_sha256": digest})
    return {"item": rows[0], "validation": {k: v for k, v in validation.items() if k != "resolved"}}


@router.post("/v1/admin/spatial/themes/{theme_key}/versions/{version}/validate")
async def validate_theme_version(
    theme_key: str, version: int, request: Request,
    operator: dict[str, Any] = Depends(require_operator_scope("platform:content.moderate")),
) -> dict[str, Any]:
    if not 1 <= version <= 100000:
        raise _fail(422, "SPATIAL_THEME_VERSION_INVALID", "Versi Theme tidak valid.")
    rows = await privileged_rest_request("GET", "spatial_theme_versions", params={
        "select": "theme_key,version,manifest,manifest_sha256,status",
        "theme_key": f"eq.{theme_key}", "version": f"eq.{version}", "limit": "1",
    })
    if not rows:
        raise _fail(404, "SPATIAL_THEME_VERSION_NOT_FOUND", "Versi Theme tidak ditemukan.")
    item = rows[0]
    draft = ThemeManifestDraft.model_validate(item["manifest"])
    digest = _canonical_digest(draft)
    validation = await _validate_assets(draft)
    validation["manifest_sha256"] = digest
    validation["stored_hash_matches"] = digest == item.get("manifest_sha256")
    if not validation["stored_hash_matches"]:
        validation["valid"] = False
        validation["errors"].append({"code": "THEME_MANIFEST_HASH_MISMATCH"})
    await write_operator_audit(request, actor_user_id=operator["id"], action="spatial.theme.version.validate",
        outcome="allowed" if validation["valid"] else "denied", resource_type="spatial_theme_version",
        resource_id=f"{theme_key}:{version}", metadata={"valid": validation["valid"], "error_count": len(validation["errors"])})
    validation.pop("resolved", None)
    return validation


@router.post("/v1/admin/spatial/themes/{theme_key}/versions/{version}/publish")
async def publish_theme_version(
    theme_key: str, version: int, request: Request,
    operator: dict[str, Any] = Depends(require_operator_scope("platform:content.moderate")),
) -> dict[str, Any]:
    rows = await privileged_rest_request("GET", "spatial_theme_versions", params={
        "select": "theme_key,version,manifest,manifest_sha256,status",
        "theme_key": f"eq.{theme_key}", "version": f"eq.{version}", "limit": "1",
    })
    if not rows:
        raise _fail(404, "SPATIAL_THEME_VERSION_NOT_FOUND", "Versi Theme tidak ditemukan.")
    item = rows[0]
    if item.get("status") not in {"draft", "review", "approved"}:
        raise _fail(409, "SPATIAL_THEME_TRANSITION_INVALID", "Hanya versi draft/review/approved yang dapat dipublikasikan.")
    draft = ThemeManifestDraft.model_validate(item["manifest"])
    if _canonical_digest(draft) != item.get("manifest_sha256"):
        raise _fail(409, "THEME_MANIFEST_HASH_MISMATCH", "Hash manifest tidak cocok.")
    validation = await _validate_assets(draft, for_publish=True)
    if not validation["valid"]:
        validation.pop("resolved", None)
        raise _fail(409, "SPATIAL_THEME_NOT_READY", "Publikasi diblokir karena aset belum memenuhi syarat.")
    await write_operator_audit(request, actor_user_id=operator["id"], action="spatial.theme.version.publish",
        outcome="attempted", resource_type="spatial_theme_version", resource_id=f"{theme_key}:{version}",
        metadata={"manifest_sha256": item["manifest_sha256"], "slot_count": len(draft.slots)})
    now = datetime.now(timezone.utc).isoformat()
    updated = await privileged_rest_request("PATCH", "spatial_theme_versions", params={
        "theme_key": f"eq.{theme_key}", "version": f"eq.{version}", "status": f"in.(draft,review,approved)",
    }, body={"status": "published", "published_at": now}, prefer="return=representation")
    if not isinstance(updated, list) or not updated:
        raise _fail(409, "SPATIAL_THEME_TRANSITION_CONFLICT", "Versi Theme berubah; muat ulang sebelum publikasi.")
    await privileged_rest_request("PATCH", "spatial_themes", params={"theme_key": f"eq.{theme_key}"}, body={
        "status": "published", "active_version": version, "updated_at": now,
    }, prefer="return=minimal")
    await write_operator_audit(request, actor_user_id=operator["id"], action="spatial.theme.version.publish",
        outcome="allowed", resource_type="spatial_theme_version", resource_id=f"{theme_key}:{version}",
        metadata={"manifest_sha256": item["manifest_sha256"]})
    return {"theme_key": theme_key, "version": version, "status": "published", "manifest_sha256": item["manifest_sha256"]}




@router.get("/v1/admin/spatial/themes/{theme_key}/versions/{version}/preview")
async def preview_theme_version(
    theme_key: str, version: int, request: Request,
    operator: dict[str, Any] = Depends(require_operator_scope("platform:content.moderate")),
) -> dict[str, Any]:
    """Operator-only preview; signed URLs never make draft assets public."""
    rows = await privileged_rest_request("GET", "spatial_theme_versions", params={
        "select": "theme_key,version,manifest,manifest_sha256,status",
        "theme_key": f"eq.{theme_key}", "version": f"eq.{version}", "limit": "1",
    })
    themes = await privileged_rest_request("GET", "spatial_themes", params={
        "select": "theme_key,display_name,status", "theme_key": f"eq.{theme_key}", "limit": "1",
    })
    if not rows or not themes:
        raise _fail(404, "SPATIAL_THEME_VERSION_NOT_FOUND", "Versi Theme tidak ditemukan.")
    item = rows[0]
    if item.get("status") not in {"draft", "review", "approved"}:
        raise _fail(409, "SPATIAL_THEME_PREVIEW_STATE_INVALID", "Preview operator hanya tersedia untuk versi nonpublik yang dapat ditinjau.")
    draft = ThemeManifestDraft.model_validate(item.get("manifest"))
    if _canonical_digest(draft) != item.get("manifest_sha256"):
        raise _fail(409, "THEME_MANIFEST_HASH_MISMATCH", "Hash manifest tidak cocok.")
    rendered = await _build_render_manifest(themes[0], item, public=False)
    await write_operator_audit(request, actor_user_id=operator["id"], action="spatial.theme.version.preview",
        outcome="allowed", resource_type="spatial_theme_version", resource_id=f"{theme_key}:{version}",
        metadata={"manifest_sha256": item["manifest_sha256"], "object_count": len(rendered["objects"])})
    return rendered


@router.get("/v1/spatial/themes/{theme_key}/manifest")
async def get_published_theme_manifest(
    response: Response,
    theme_key: str = Path(min_length=3, max_length=120, pattern=r"^[a-z0-9][a-z0-9._-]{2,119}$"),
) -> dict[str, Any]:
    """Renderer contract: published Theme + immutable published asset versions only."""
    if response is not None:
        response.headers["Cache-Control"] = "private, no-store"
        response.headers["Vary"] = "Authorization"
    url, key = _service_config()
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            themes = await _get_rows(client, url, key, "spatial_themes", {
                "select": "theme_key,display_name,status,active_version",
                "theme_key": f"eq.{theme_key}", "status": "eq.published", "limit": "1",
            })
            if not themes or not themes[0].get("active_version"):
                raise _fail(404, "SPATIAL_THEME_NOT_FOUND", "Theme publik tidak ditemukan.")
            theme = themes[0]
            versions = await _get_rows(client, url, key, "spatial_theme_versions", {
                "select": "theme_key,version,manifest,manifest_sha256,status",
                "theme_key": f"eq.{theme_key}", "version": f"eq.{theme['active_version']}",
                "status": "eq.published", "limit": "1",
            })
            if not versions:
                raise _fail(404, "SPATIAL_THEME_VERSION_NOT_FOUND", "Versi Theme publik tidak ditemukan.")
            draft = ThemeManifestDraft.model_validate(versions[0].get("manifest"))
            digest = _canonical_digest(draft)
            if digest != versions[0].get("manifest_sha256"):
                raise _fail(409, "THEME_MANIFEST_HASH_MISMATCH", "Hash manifest publik tidak cocok.")
            # Resolve using the same canonical asset registry and lifecycle gate.
            objects = []
            for slot in draft.slots:
                assets = await _get_rows(client, url, key, "spatial_asset_versions", {
                    "select": "asset_id,asset_key,version,category,sha256,byte_size,storage_bucket,storage_path,status,moderation_status,license_evidence",
                    "asset_key": f"eq.{slot.asset_key}", "version": f"eq.{slot.asset_version}",
                    "status": "eq.published", "moderation_status": "eq.approved", "limit": "1",
                })
                if not assets:
                    raise _fail(409, "SPATIAL_ASSET_NOT_PUBLISHED", "Theme merujuk aset yang belum dipublikasikan.")
                asset = assets[0]
                evidence = asset.get("license_evidence")
                if not isinstance(evidence, dict) or evidence.get("status") != "verified":
                    raise _fail(409, "SPATIAL_ASSET_RIGHTS_UNVERIFIED", "Aset Theme tidak memiliki bukti hak yang terverifikasi.")
                signed_url = await _signed_asset_url(client, url, key, asset.get("storage_bucket", ""), asset.get("storage_path", ""))
                transform = slot.transform.model_dump(mode="json")
                objects.append({
                    "entity_id": slot.slot_key, "asset_id": asset["asset_id"], "asset_version": asset["version"],
                    "category": asset["category"], "asset_url": signed_url, "sha256": asset["sha256"],
                    "byte_size": asset["byte_size"], "position": transform["position"],
                    "rotation": transform["rotation"], "scale": transform["scale"], "publication_status": "published",
                })
            return {
                "schema_version": "1.0", "scene_id": f"theme:{theme_key}",
                "scene_version": versions[0]["version"], "world_id": theme_key,
                "coordinate_system": "right-handed-y-up", "units": "meters",
                "fallback_mode": draft.fallback_mode, "theme_key": theme_key,
                "theme_version": versions[0]["version"], "theme_name": draft.display_name,
                "manifest_sha256": digest, "objects": objects,
            }
    except HTTPException:
        raise
    except httpx.HTTPError as exc:
        raise _fail(503, "SPATIAL_THEME_CATALOG_UNAVAILABLE", "Katalog Theme sementara tidak tersedia.") from exc

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
            target = errors if slot.required else warnings
            target.append({"slot_key": slot.slot_key, "code": "ASSET_VERSION_NOT_FOUND"})
            continue
        if asset.get("category") != slot.category:
            target = errors if slot.required else warnings
            target.append({"slot_key": slot.slot_key, "code": "CATEGORY_MISMATCH"})
            continue
        if asset.get("status") in {"rejected", "revoked", "retired", "blocked", "failed"}:
            target = errors if slot.required else warnings
            target.append({"slot_key": slot.slot_key, "code": "ASSET_LIFECYCLE_BLOCKED"})
            continue
        if asset.get("moderation_status") == "rejected":
            target = errors if slot.required else warnings
            target.append({"slot_key": slot.slot_key, "code": "ASSET_MODERATION_REJECTED"})
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
    resolved_categories = {item["slot"]["category"] for item in resolved}
    missing_categories = sorted(set(CATEGORIES) - resolved_categories)
    # A zero-asset 2D fallback Theme is a valid public shell while spatial GLBs are being
    # onboarded. It publishes no GLB and cannot accidentally expose quarantined assets.
    fallback_shell = not manifest.slots and manifest.fallback_mode == "2d"
    if missing_categories and not fallback_shell:
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



@router.get("/v1/admin/spatial/assets/category-coverage")
async def get_theme_builder_category_coverage(
    operator: dict[str, Any] = Depends(require_operator_scope("platform:content.moderate")),
) -> dict[str, Any]:
    """Read-only, evidence-backed coverage for the canonical 14-category asset registry."""
    rows = await privileged_rest_request("GET", "spatial_asset_versions", params={
        "select": "asset_key,version,category,status,moderation_status,license_evidence_status,sha256,byte_size",
        "order": "asset_key.asc,version.asc", "limit": "1000",
    })
    receipts = await privileged_rest_request("GET", "spatial_asset_ingest_receipts", params={
        "select": "receipt_id,asset_key,display_name,category_candidate,category_mapping_status,lifecycle_status,sha256,byte_size,source_repo,source_path,source_url,source_license_claim,review_state",
        "order": "asset_key.asc", "limit": "1000",
    })
    records = rows or []
    receipt_records = receipts or []
    categories: list[dict[str, Any]] = []
    for category in CATEGORIES:
        matching = [row for row in records if row.get("category") == category]
        receipt_matching = [row for row in receipt_records if row.get("category_candidate") == category]
        categories.append({
            "category": category,
            "asset_versions": len(matching),
            "ingest_receipts": len(receipt_matching),
            "published": sum(1 for row in matching if row.get("status") == "published"),
            "approved": sum(1 for row in matching if row.get("moderation_status") == "approved"),
            "rights_verified": sum(1 for row in matching if row.get("license_evidence_status") == "verified"),
            "publication_ready": sum(1 for row in matching if row.get("status") == "published"
                                     and row.get("moderation_status") == "approved"
                                     and row.get("license_evidence_status") == "verified"),
        })
    by_key: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        by_key.setdefault(str(record.get("asset_key")), []).append(record)
    unregistered = []
    integrity_mismatches = []
    category_mismatches = []
    for receipt in receipt_records:
        matching_assets = by_key.get(str(receipt.get("asset_key")), [])
        if not matching_assets:
            unregistered.append({
                key: receipt.get(key) for key in (
                    "receipt_id", "asset_key", "display_name", "category_candidate", "category_mapping_status",
                    "lifecycle_status", "sha256", "byte_size", "source_repo", "source_path",
                    "source_url", "source_license_claim", "review_state",
                )
            })
            continue
        asset = next((row for row in matching_assets if row.get("sha256") == receipt.get("sha256")), matching_assets[0])
        if asset.get("sha256") != receipt.get("sha256") or asset.get("byte_size") != receipt.get("byte_size"):
            integrity_mismatches.append({
                "asset_key": receipt.get("asset_key"),
                "receipt_sha256": receipt.get("sha256"),
                "asset_sha256": asset.get("sha256"),
                "receipt_byte_size": receipt.get("byte_size"),
                "asset_byte_size": asset.get("byte_size"),
            })
        if receipt.get("category_mapping_status") == "mapped" and receipt.get("category_candidate") != asset.get("category"):
            category_mismatches.append({
                "asset_key": receipt.get("asset_key"),
                "receipt_category": receipt.get("category_candidate"),
                "asset_category": asset.get("category"),
            })
    mapping_status_counts: dict[str, int] = {}
    for receipt in receipt_records:
        status = str(receipt.get("category_mapping_status") or "unknown")
        mapping_status_counts[status] = mapping_status_counts.get(status, 0) + 1
    return {
        "registry": "spatial_asset_versions",
        "receipt_registry": "spatial_asset_ingest_receipts",
        "total_asset_versions": len(records),
        "total_ingest_receipts": len(receipt_records),
        "categories": categories,
        "unmapped_or_noncanonical": sum(1 for row in records if row.get("category") not in CATEGORIES),
        "receipt_mapping_status_counts": mapping_status_counts,
        "unregistered_receipts": unregistered,
        "integrity_mismatches": integrity_mismatches,
        "category_mismatches": category_mismatches,
        "notes": [
            "Receipt category candidates and mapped flags are ingest metadata, not independent semantic/visual category approval.",
            "A receipt without a canonical asset version remains quarantined and is never auto-registered by this read-only report.",
            "Only published, moderation-approved, rights-verified asset versions are eligible for public manifests.",
        ],
        "truncated": len(records) >= 1000 or len(receipt_records) >= 1000,
    }


@router.get("/v1/admin/spatial/assets")
async def list_theme_builder_assets(
    category: str | None = None, status: str | None = None,
    limit: int = 100, offset: int = 0,
    operator: dict[str, Any] = Depends(require_operator_scope("platform:content.moderate")),
) -> dict[str, Any]:
    """Operator asset library backed by the one canonical spatial asset registry."""
    if not 1 <= limit <= 100 or offset < 0:
        raise _fail(422, "SPATIAL_ASSET_PAGINATION_INVALID", "Pagination aset tidak valid.")
    if category is not None and category not in CATEGORIES:
        raise _fail(422, "SPATIAL_ASSET_CATEGORY_INVALID", "Kategori aset tidak termasuk taxonomy kanonis.")
    allowed_statuses = {"draft", "uploaded", "quarantined", "validating", "review", "approved", "test_only", "published", "deprecated", "retired", "rejected", "failed", "blocked", "revoked"}
    if status is not None and status not in allowed_statuses:
        raise _fail(422, "SPATIAL_ASSET_STATUS_INVALID", "Status aset tidak valid.")
    params = {
        "select": "asset_key,version,display_name,category,status,moderation_status,license_evidence,sha256,byte_size,capabilities,compatibility,created_at",
        "order": "created_at.desc,asset_key.asc,version.desc",
        "limit": str(limit), "offset": str(offset),
    }
    if category:
        params["category"] = f"eq.{category}"
    if status:
        params["status"] = f"eq.{status}"
    rows = await privileged_rest_request("GET", "spatial_asset_versions", params=params)
    return {"items": rows or [], "limit": limit, "offset": offset, "category": category, "status": status}


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
    if themes[0].get("status") == "retired":
        raise _fail(409, "SPATIAL_THEME_RETIRED", "Theme retired tidak dapat menerima versi baru.")
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


@router.post("/v1/admin/spatial/themes/{theme_key}/versions/{version}/approve")
async def approve_theme_version(
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
    if item.get("status") not in {"draft", "review"}:
        raise _fail(409, "SPATIAL_THEME_TRANSITION_INVALID", "Hanya versi draft/review yang dapat disetujui.")
    draft = ThemeManifestDraft.model_validate(item["manifest"])
    if _canonical_digest(draft) != item.get("manifest_sha256"):
        raise _fail(409, "THEME_MANIFEST_HASH_MISMATCH", "Hash manifest tidak cocok.")
    validation = await _validate_assets(draft, for_publish=True)
    if not validation["valid"]:
        validation.pop("resolved", None)
        return {"status": "blocked", "validation": validation}
    await write_operator_audit(request, actor_user_id=operator["id"], action="spatial.theme.version.approve",
        outcome="attempted", resource_type="spatial_theme_version", resource_id=f"{theme_key}:{version}",
        metadata={"manifest_sha256": item["manifest_sha256"], "slot_count": len(draft.slots)})
    updated = await privileged_rest_request("PATCH", "spatial_theme_versions", params={
        "theme_key": f"eq.{theme_key}", "version": f"eq.{version}", "status": "in.(draft,review)",
    }, body={"status": "approved"}, prefer="return=representation")
    if not isinstance(updated, list) or not updated:
        raise _fail(409, "SPATIAL_THEME_TRANSITION_CONFLICT", "Versi Theme berubah; muat ulang sebelum persetujuan.")
    await write_operator_audit(request, actor_user_id=operator["id"], action="spatial.theme.version.approve",
        outcome="allowed", resource_type="spatial_theme_version", resource_id=f"{theme_key}:{version}",
        metadata={"manifest_sha256": item["manifest_sha256"]})
    return {"theme_key": theme_key, "version": version, "status": "approved", "manifest_sha256": item["manifest_sha256"]}


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
    if item.get("status") != "approved":
        raise _fail(409, "SPATIAL_THEME_TRANSITION_INVALID", "Versi Theme harus disetujui sebelum publikasi.")
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
        "theme_key": f"eq.{theme_key}", "version": f"eq.{version}", "status": "eq.approved",
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



@router.get("/v1/spatial/themes")
async def list_published_themes(
    limit: int = 50, offset: int = 0,
) -> dict[str, Any]:
    """Public directory contains only themes with an active published version."""
    if not 1 <= limit <= 100 or offset < 0:
        raise _fail(422, "SPATIAL_THEME_PAGINATION_INVALID", "Pagination Theme tidak valid.")
    url, key = _service_config()
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            rows = await _get_rows(client, url, key, "spatial_themes", {
                "select": "theme_key,display_name,description,status,active_version,updated_at",
                "status": "eq.published", "active_version": "not.is.null",
                "order": "updated_at.desc", "limit": str(limit), "offset": str(offset),
            })
            if not rows:
                return {"items": [], "limit": limit, "offset": offset}
            theme_keys = ",".join(theme["theme_key"] for theme in rows)
            version_rows = await _get_rows(client, url, key, "spatial_theme_versions", {
                "select": "theme_key,version", "theme_key": f"in.({theme_keys})",
                "status": "eq.published", "limit": str(limit),
            })
            published_versions = {(row.get("theme_key"), row.get("version")) for row in version_rows}
            items = [theme for theme in rows if (theme["theme_key"], theme["active_version"]) in published_versions]
            return {"items": items, "limit": limit, "offset": offset}
    except HTTPException:
        raise
    except httpx.HTTPError as exc:
        raise _fail(503, "SPATIAL_THEME_CATALOG_UNAVAILABLE", "Katalog Theme sementara tidak tersedia.") from exc


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
                if asset.get("category") != slot.category:
                    raise _fail(409, "SPATIAL_ASSET_CATEGORY_MISMATCH", "Kategori aset tidak cocok dengan slot Theme.")
                if not isinstance(asset.get("sha256"), str) or not re.fullmatch(r"[a-f0-9]{64}", asset["sha256"]):
                    raise _fail(409, "SPATIAL_ASSET_CHECKSUM_INVALID", "Checksum aset tidak valid.")
                if not isinstance(asset.get("byte_size"), int) or asset["byte_size"] <= 0:
                    raise _fail(409, "SPATIAL_ASSET_SIZE_INVALID", "Ukuran aset tidak valid.")
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


class OrphanReceiptRegistration(BaseModel):
    """Operator-reviewed category assignment; never grants rights or publication approval."""
    model_config = ConfigDict(extra="forbid")
    category: Literal[
        "universe", "galaxy", "world", "orbit", "capsule", "district", "booth",
        "content-feed", "agent-character", "live-stage", "human-live",
        "sticker-social", "animation", "navigation-fx",
    ]
    rationale: str = Field(min_length=12, max_length=1000)
    evidence_uri: str = Field(min_length=8, max_length=2048, pattern=r"^https://")


@router.post("/v1/admin/spatial/assets/receipts/{receipt_id}/register", status_code=201)
async def register_orphan_asset_receipt(
    payload: OrphanReceiptRegistration,
    request: Request,
    receipt_id: str = Path(min_length=36, max_length=36),
    operator: dict[str, Any] = Depends(require_operator_scope("platform:content.moderate")),
) -> dict[str, Any]:
    """Register an orphan receipt as quarantined after an operator records category evidence.

    This action repairs registry linkage only. It deliberately leaves license evidence
    unverified, moderation pending, and lifecycle quarantined; it cannot publish an asset.
    """
    receipts = await privileged_rest_request("GET", "spatial_asset_ingest_receipts", params={
        "select": "receipt_id,asset_key,display_name,source_url,source_repo,source_path,source_license_claim,review_state,category_candidate,category_mapping_status,sha256,byte_size,storage_bucket,storage_path,lifecycle_status",
        "receipt_id": f"eq.{receipt_id}", "limit": "1",
    })
    if not receipts:
        raise _fail(404, "SPATIAL_ASSET_RECEIPT_NOT_FOUND", "Receipt aset tidak ditemukan.")
    receipt = receipts[0]
    existing = await privileged_rest_request("GET", "spatial_asset_versions", params={
        "select": "asset_key,version,category,sha256,byte_size,status",
        "asset_key": f"eq.{receipt['asset_key']}", "limit": "2",
    })
    if existing:
        if any(row.get("sha256") == receipt.get("sha256") and row.get("byte_size") == receipt.get("byte_size") for row in existing):
            raise _fail(409, "SPATIAL_ASSET_RECEIPT_ALREADY_REGISTERED", "Receipt sudah memiliki versi aset kanonis; jalankan rekonsiliasi, bukan registrasi ulang.")
        raise _fail(409, "SPATIAL_ASSET_KEY_CONFLICT", "Asset key sudah digunakan oleh konten dengan checksum berbeda.")
    if receipt.get("lifecycle_status") != "quarantined":
        raise _fail(409, "SPATIAL_ASSET_RECEIPT_NOT_QUARANTINED", "Endpoint ini hanya menerima receipt orphan yang masih dikarantina.")
    if receipt.get("category_mapping_status") == "mapped" and receipt.get("category_candidate") != payload.category:
        raise _fail(409, "SPATIAL_ASSET_CATEGORY_REVIEW_CONFLICT", "Receipt sudah memiliki kategori kandidat yang berbeda; selesaikan konflik melalui review terpisah.")
    provenance = {
        "ingest_receipt_id": receipt["receipt_id"],
        "source_repo": receipt["source_repo"],
        "source_path": receipt["source_path"],
        "category_review": {
            "reviewed_by": operator["id"],
            "rationale": payload.rationale.strip(),
            "evidence_uri": payload.evidence_uri,
            "reviewed_at": datetime.now(timezone.utc).isoformat(),
        },
    }
    license_evidence = {
        "status": "unverified",
        "reason": "Registrasi receipt tidak membuktikan lisensi atau hak karya turunan.",
        "source_license_claim": receipt.get("source_license_claim") or "unknown",
    }
    await write_operator_audit(request, actor_user_id=operator["id"], action="spatial.asset.receipt.register",
        outcome="attempted", resource_type="spatial_asset_receipt", resource_id=receipt_id,
        metadata={"asset_key": receipt["asset_key"], "category": payload.category, "sha256": receipt["sha256"]})
    created = await privileged_rest_request("POST", "spatial_asset_versions", body={
        "asset_key": receipt["asset_key"],
        "version": 1,
        "display_name": receipt["display_name"],
        "category": payload.category,
        "source_url": receipt["source_url"],
        "provenance": provenance,
        "license_evidence": license_evidence,
        "sha256": receipt["sha256"],
        "byte_size": receipt["byte_size"],
        "mime_type": "model/gltf-binary",
        "storage_bucket": receipt["storage_bucket"],
        "storage_path": receipt["storage_path"],
        "moderation_status": "pending",
        "status": "quarantined",
        "license_evidence_uri": None,
        "license_evidence_status": "unverified",
        "internal_preview_enabled": False,
    }, prefer="return=representation")
    if not isinstance(created, list) or not created:
        raise _fail(503, "SPATIAL_ASSET_RECEIPT_REGISTER_FAILED", "Versi aset karantina tidak berhasil dibuat.")
    updated_receipt = await privileged_rest_request("PATCH", "spatial_asset_ingest_receipts", params={
        "receipt_id": f"eq.{receipt_id}",
    }, body={
        "category_candidate": payload.category,
        "category_mapping_status": "mapped",
        "review_state": "CATEGORY_MAPPED_RIGHTS_QUARANTINED",
        "lifecycle_status": "quarantined",
    }, prefer="return=representation")
    if not isinstance(updated_receipt, list) or not updated_receipt:
        await write_operator_audit(request, actor_user_id=operator["id"], action="spatial.asset.receipt.register",
            outcome="partial_failure", resource_type="spatial_asset_receipt", resource_id=receipt_id,
            metadata={"asset_key": receipt["asset_key"], "reason": "receipt_update_failed"})
        raise _fail(503, "SPATIAL_ASSET_RECEIPT_RECONCILIATION_PARTIAL", "Aset sudah terdaftar dalam status karantina, tetapi receipt belum tersinkron. Jalankan rekonsiliasi idempoten.")
    await write_operator_audit(request, actor_user_id=operator["id"], action="spatial.asset.receipt.register",
        outcome="allowed", resource_type="spatial_asset_receipt", resource_id=receipt_id,
        metadata={"asset_key": receipt["asset_key"], "category": payload.category, "status": "quarantined"})
    return {
        "item": created[0],
        "receipt": updated_receipt[0],
        "publication": {
            "status": "blocked",
            "reason": "Hak penggunaan masih belum terverifikasi dan moderasi belum disetujui.",
        },
    }


@router.post("/v1/admin/spatial/assets/reconcile")
async def reconcile_spatial_assets(
    request: Request,
    limit: int = 1000,
    operator: dict[str, Any] = Depends(require_operator_scope("platform:content.moderate")),
) -> dict[str, Any]:
    """Idempotent evidence-based reconciliation report for canonical assets and ingest receipts.

    Safe to repeat. This classifies every receipt without inventing rights/moderation decisions
    or publishing assets; unresolved receipts do not block independent eligible assets.
    """
    if not 1 <= limit <= 1000:
        raise _fail(422, "SPATIAL_RECONCILE_LIMIT_INVALID", "Limit rekonsiliasi harus 1 sampai 1000.")
    assets = await privileged_rest_request("GET", "spatial_asset_versions", params={
        "select": "asset_key,version,category,status,moderation_status,license_evidence,license_evidence_status,sha256,byte_size",
        "order": "asset_key.asc,version.asc", "limit": str(limit),
    })
    receipts = await privileged_rest_request("GET", "spatial_asset_ingest_receipts", params={
        "select": "receipt_id,asset_key,display_name,category_candidate,category_mapping_status,lifecycle_status,sha256,byte_size,source_license_claim,review_state",
        "order": "asset_key.asc,receipt_id.asc", "limit": str(limit),
    })
    asset_rows = assets if isinstance(assets, list) else []
    receipt_rows = receipts if isinstance(receipts, list) else []
    by_key: dict[str, list[dict[str, Any]]] = {}
    for asset in asset_rows:
        by_key.setdefault(str(asset.get("asset_key") or ""), []).append(asset)
    outcomes: list[dict[str, Any]] = []
    counts = {"ready_for_existing_publish_flow": 0, "needs_evidence_or_review": 0,
              "rejected_or_blocked": 0, "conflict": 0, "unregistered": 0}
    for receipt in receipt_rows:
        key = str(receipt.get("asset_key") or "")
        candidates = by_key.get(key, [])
        matched = None
        if not candidates:
            outcome, reasons = "unregistered", ["CANONICAL_ASSET_VERSION_MISSING"]
        else:
            exact = [row for row in candidates if row.get("sha256") == receipt.get("sha256")
                     and row.get("byte_size") == receipt.get("byte_size")]
            if not exact:
                outcome, reasons = "conflict", ["CHECKSUM_OR_SIZE_MISMATCH"]
            else:
                matched = exact[0]
                if (matched.get("status") in {"rejected", "revoked", "retired", "blocked", "failed"}
                        or matched.get("moderation_status") == "rejected"):
                    outcome, reasons = "rejected_or_blocked", ["ASSET_LIFECYCLE_OR_MODERATION_BLOCKED"]
                else:
                    license = matched.get("license_evidence")
                    rights_verified = isinstance(license, dict) and license.get("status") == "verified"
                    if matched.get("license_evidence_status") != "verified" or not rights_verified:
                        outcome, reasons = "needs_evidence_or_review", ["LICENSE_RIGHTS_NOT_VERIFIED"]
                    elif matched.get("moderation_status") != "approved":
                        outcome, reasons = "needs_evidence_or_review", ["MODERATION_NOT_APPROVED"]
                    else:
                        outcome, reasons = "ready_for_existing_publish_flow", [
                            "ASSET_ALREADY_PUBLICATION_READY" if matched.get("status") == "published"
                            else "RIGHTS_AND_MODERATION_VERIFIED_BUT_ASSET_NOT_PUBLISHED"
                        ]
                    if (receipt.get("category_mapping_status") == "mapped"
                            and receipt.get("category_candidate") != matched.get("category")):
                        outcome, reasons = "conflict", ["CATEGORY_MAPPING_CONFLICT"]
        counts[outcome] += 1
        outcomes.append({
            "receipt_id": receipt.get("receipt_id"), "asset_key": key,
            "display_name": receipt.get("display_name"), "outcome": outcome,
            "reason_codes": reasons, "matched_version": matched.get("version") if matched else None,
            "canonical_category": matched.get("category") if matched else None,
            "receipt_category": receipt.get("category_candidate"),
            "sha256": receipt.get("sha256"), "byte_size": receipt.get("byte_size"),
            "next_action": (
                "Continue through existing canonical asset publish flow" if outcome == "ready_for_existing_publish_flow" else
                "Collect and verify rights evidence, then complete moderation review" if outcome == "needs_evidence_or_review" else
                "Keep excluded from public manifests; investigate or resolve conflict" if outcome in {"conflict", "rejected_or_blocked"} else
                "Register through the existing quarantined receipt workflow after category evidence review"
            ),
        })
    await write_operator_audit(
        request, actor_user_id=operator["id"], action="spatial.asset.reconcile",
        outcome="allowed", resource_type="spatial_asset_registry", resource_id="batch",
        metadata={"asset_count": len(asset_rows), "receipt_count": len(receipt_rows),
                  "counts": counts, "truncated": len(asset_rows) >= limit or len(receipt_rows) >= limit},
    )
    return {
        "operation": "spatial_asset_reconciliation", "idempotent": True,
        "mutated_asset_lifecycle": False, "public_manifest_mutation": False,
        "counts": counts, "assets_examined": len(asset_rows), "receipts_examined": len(receipt_rows),
        "truncated": len(asset_rows) >= limit or len(receipt_rows) >= limit, "items": outcomes,
        "policy": {
            "eligible": "Rights and moderation must already be verified; proceed through existing publish flow.",
            "pending": "Missing evidence/review stays pending and does not block other receipts.",
            "excluded": "Rejected or conflicting assets remain excluded from public manifests.",
            "theme": "Only the canonical Theme version publish flow can create a public manifest.",
        },
    }


@router.get("/v1/admin/spatial/assets/publication-candidates")
async def list_spatial_publication_candidates(
    category: str | None = None,
    limit: int = 100,
    offset: int = 0,
    operator: dict[str, Any] = Depends(require_operator_scope("platform:content.moderate")),
) -> dict[str, Any]:
    """List only canonical GLB versions that can be referenced by a public Theme manifest.

    This is a compact actionable registry view, not an approval bypass: it never mutates
    asset state and deliberately excludes pending, rejected, rights-unverified, or test-only rows.
    """
    if not 1 <= limit <= 100 or offset < 0:
        raise _fail(422, "SPATIAL_ASSET_PAGINATION_INVALID", "Pagination aset tidak valid.")
    if category is not None and category not in CATEGORIES:
        raise _fail(422, "SPATIAL_ASSET_CATEGORY_INVALID", "Kategori aset tidak termasuk taxonomy kanonis.")
    params: dict[str, str] = {
        "select": "asset_id,asset_key,version,display_name,category,status,moderation_status,license_evidence,license_evidence_status,sha256,byte_size,storage_bucket,storage_path,capabilities,compatibility",
        "status": "eq.published", "moderation_status": "eq.approved",
        "license_evidence_status": "eq.verified",
        "order": "category.asc,asset_key.asc,version.desc",
        "limit": str(limit), "offset": str(offset),
    }
    if category:
        params["category"] = f"eq.{category}"
    rows = await privileged_rest_request("GET", "spatial_asset_versions", params=params)
    eligible = []
    for row in rows if isinstance(rows, list) else []:
        evidence = row.get("license_evidence")
        if not (isinstance(evidence, dict) and evidence.get("status") == "verified"):
            continue
        if not re.fullmatch(r"[a-f0-9]{64}", str(row.get("sha256") or "")):
            continue
        if not isinstance(row.get("byte_size"), int) or row["byte_size"] <= 0:
            continue
        if not row.get("storage_bucket") or not row.get("storage_path"):
            continue
        eligible.append({
            "asset_key": row["asset_key"], "asset_version": row["version"],
            "asset_id": row["asset_id"], "display_name": row.get("display_name"),
            "category": row["category"], "sha256": row["sha256"],
            "byte_size": row["byte_size"], "capabilities": row.get("capabilities") or [],
            "compatibility": row.get("compatibility") or {},
            "eligible_for_theme_slot": True,
        })
    return {
        "items": eligible, "count": len(eligible), "limit": limit, "offset": offset,
        "filters": {"category": category, "status": "published", "moderation_status": "approved",
                    "license_evidence_status": "verified"},
        "next_action": "Create Theme slots from these exact asset_key/version pairs; never infer eligibility from file presence alone.",
    }


@router.post("/v1/admin/spatial/themes/{theme_key}/versions/from-publication-candidates", status_code=201)
async def create_theme_version_from_publication_candidates(
    request: Request,
    theme_key: str = Path(min_length=3, max_length=120, pattern=r"^[a-z0-9][a-z0-9._-]{2,119}$"),
    limit: int = 100,
    operator: dict[str, Any] = Depends(require_operator_scope("platform:content.moderate")),
) -> dict[str, Any]:
    """Create a draft Theme from exact, already-publication-ready canonical GLB versions."""
    if not 1 <= limit <= 350:
        raise _fail(422, "SPATIAL_THEME_CANDIDATE_LIMIT_INVALID", "Limit harus 1 sampai 350.")
    themes = await privileged_rest_request("GET", "spatial_themes", params={
        "select": "theme_key,status", "theme_key": f"eq.{theme_key}", "limit": "1",
    })
    if not themes:
        raise _fail(404, "SPATIAL_THEME_NOT_FOUND", "Theme tidak ditemukan.")
    if themes[0].get("status") == "retired":
        raise _fail(409, "SPATIAL_THEME_RETIRED", "Theme retired tidak dapat menerima versi baru.")
    candidates = await privileged_rest_request("GET", "spatial_asset_versions", params={
        "select": "asset_id,asset_key,version,display_name,category,status,moderation_status,license_evidence,license_evidence_status,sha256,byte_size,storage_bucket,storage_path",
        "status": "eq.published", "moderation_status": "eq.approved",
        "license_evidence_status": "eq.verified",
        "order": "category.asc,asset_key.asc,version.desc", "limit": str(limit),
    })
    chosen: dict[str, dict[str, Any]] = {}
    for asset in candidates if isinstance(candidates, list) else []:
        evidence = asset.get("license_evidence")
        if (asset.get("category") not in CATEGORIES or not isinstance(evidence, dict)
                or evidence.get("status") != "verified"
                or not re.fullmatch(r"[a-f0-9]{64}", str(asset.get("sha256") or ""))
                or not isinstance(asset.get("byte_size"), int) or asset["byte_size"] <= 0
                or not asset.get("storage_bucket") or not asset.get("storage_path")):
            continue
        chosen.setdefault(asset["category"], asset)
    if not chosen:
        raise _fail(409, "SPATIAL_THEME_NO_PUBLICATION_CANDIDATES",
                    "Belum ada GLB yang memenuhi status publikasi, moderasi, hak, checksum, dan Storage.")
    versions = await privileged_rest_request("GET", "spatial_theme_versions", params={
        "select": "version", "theme_key": f"eq.{theme_key}", "order": "version.desc", "limit": "1",
    })
    version = int(versions[0]["version"]) + 1 if versions else 1
    import math
    slots = []
    for index, category in enumerate(CATEGORIES):
        asset = chosen.get(category)
        if not asset:
            continue
        angle = (2 * math.pi * index) / len(CATEGORIES)
        radius = 4.0 if category in {"universe", "world", "district"} else 2.0
        slots.append({
            "slot_key": f"{category}-main", "category": category,
            "asset_key": asset["asset_key"], "asset_version": asset["version"],
            "transform": {"position": [round(radius * math.cos(angle), 4), 0.0, round(radius * math.sin(angle), 4)],
                          "rotation": [0.0, round(-angle, 4), 0.0], "scale": [1.0, 1.0, 1.0]},
            "required": True,
        })
    manifest = ThemeManifestDraft(
        theme_key=theme_key,
        display_name=theme_key.replace("-", " ").replace("_", " ").title(),
        description="Generated from exact publication-ready canonical GLB versions; review before publishing.",
        fallback_mode="2d", slots=slots,
    )
    validation = await _validate_assets(manifest)
    digest = _canonical_digest(manifest)
    rows = await privileged_rest_request("POST", "spatial_theme_versions", body={
        "theme_key": theme_key, "version": version, "schema_version": "1.0",
        "manifest": manifest.model_dump(mode="json"), "manifest_sha256": digest,
        "status": "draft", "created_by": operator["id"],
    }, prefer="return=representation")
    if not isinstance(rows, list) or not rows:
        raise _fail(503, "SPATIAL_THEME_VERSION_CREATE_FAILED", "Versi Theme tidak dapat disimpan.")
    await write_operator_audit(request, actor_user_id=operator["id"], action="spatial.theme.version.from_candidates",
        outcome="allowed", resource_type="spatial_theme_version", resource_id=f"{theme_key}:{version}",
        metadata={"manifest_sha256": digest, "slot_count": len(slots), "categories": [slot["category"] for slot in slots]})
    return {"item": rows[0], "status": "draft", "publication_requires_normal_lifecycle": True,
            "candidate_count": len(slots), "missing_categories": sorted(set(CATEGORIES) - set(chosen)),
            "validation": {key: value for key, value in validation.items() if key != "resolved"},
            "next_steps": ["validate", "approve", "publish"]}


@router.get("/v1/admin/spatial/agents/character-skill-mapping-candidates")
async def list_agent_character_skill_mapping_candidates(
    request: Request,
    limit: int = 100,
    offset: int = 0,
    operator: dict[str, Any] = Depends(require_operator_scope("platform:content.moderate")),
) -> dict[str, Any]:
    """Resolve bot/archetype/asset/immutable skill-version links without auto-activating bots."""
    if not 1 <= limit <= 500 or offset < 0:
        raise _fail(422, "SPATIAL_AGENT_MAPPING_PAGINATION_INVALID", "Pagination mapping tidak valid.")
    bots = await privileged_rest_request("GET", "official_agent_bots", params={
        "select": "id,display_name,character_archetype_key,character_asset_key,agent_id,status,skill_version_id,skill_version_number,skill_version_digest,asset_validation_status",
        "order": "character_archetype_key.asc,id.asc", "limit": str(limit), "offset": str(offset),
    })
    assets = await privileged_rest_request("GET", "spatial_asset_versions", params={
        "select": "asset_id,asset_key,version,category,status,moderation_status,license_evidence,license_evidence_status,sha256,byte_size,storage_bucket,storage_path,capabilities,compatibility",
        "category": "eq.agent-character", "order": "asset_key.asc,version.desc", "limit": "1000",
    })
    skill_versions = await privileged_rest_request("GET", "agent_skill_versions", params={
        "select": "id,skill_id,agent_id,version,snapshot,created_at", "order": "agent_id.asc,version.desc", "limit": "1000",
    })
    skill_by_agent: dict[str, list[dict[str, Any]]] = {}
    for skill_version in skill_versions if isinstance(skill_versions, list) else []:
        if skill_version.get("agent_id"):
            skill_by_agent.setdefault(str(skill_version["agent_id"]), []).append(skill_version)
    asset_rows = assets if isinstance(assets, list) else []
    output = []
    counts = {"fully_linked": 0, "missing_character_asset": 0, "missing_skill_version": 0,
              "asset_not_publication_ready": 0, "archetype_mismatch": 0}
    for bot in bots if isinstance(bots, list) else []:
        archetype = str(bot.get("character_archetype_key") or "")
        exact_key = next((asset for asset in asset_rows if asset.get("asset_key") == bot.get("character_asset_key")), None)
        compatible = []
        for asset in asset_rows:
            metadata = json.dumps({"capabilities": asset.get("capabilities") or [], "compatibility": asset.get("compatibility") or {}}, sort_keys=True)
            if archetype and archetype in metadata:
                compatible.append(asset)
        chosen = exact_key or (compatible[0] if len(compatible) == 1 else None)
        skill_match = next((sv for sv in skill_by_agent.get(str(bot.get("agent_id") or ""), [])
                            if bot.get("skill_version_id") and sv.get("id") == bot.get("skill_version_id")), None)
        if not chosen:
            reason = "missing_character_asset"
        elif (chosen.get("status") != "published" or chosen.get("moderation_status") != "approved"
              or chosen.get("license_evidence_status") != "verified"
              or not isinstance(chosen.get("license_evidence"), dict)
              or chosen["license_evidence"].get("status") != "verified"
              or not re.fullmatch(r"[a-f0-9]{64}", str(chosen.get("sha256") or ""))
              or not isinstance(chosen.get("byte_size"), int) or chosen["byte_size"] <= 0
              or not chosen.get("storage_bucket") or not chosen.get("storage_path")):
            reason = "asset_not_publication_ready"
        elif not skill_match or not bot.get("skill_version_digest") or not bot.get("skill_version_number"):
            reason = "missing_skill_version"
        elif skill_match.get("agent_id") != bot.get("agent_id") or skill_match.get("version") != bot.get("skill_version_number"):
            reason = "missing_skill_version"
        elif archetype not in json.dumps({"capabilities": chosen.get("capabilities") or [], "compatibility": chosen.get("compatibility") or {}}, sort_keys=True):
            reason = "archetype_mismatch"
        else:
            reason = "fully_linked"
        counts[reason] += 1
        output.append({
            "bot_id": bot.get("id"), "display_name": bot.get("display_name"),
            "character_archetype_key": archetype or None,
            "character_asset_key": chosen.get("asset_key") if chosen else bot.get("character_asset_key"),
            "asset_version": chosen.get("version") if chosen else None,
            "asset_publication_ready": reason == "fully_linked",
            "agent_id": bot.get("agent_id"), "skill_version_id": skill_match.get("id") if skill_match else bot.get("skill_version_id"),
            "skill_version_number": skill_match.get("version") if skill_match else bot.get("skill_version_number"),
            "skill_version_digest": bot.get("skill_version_digest"),
            "mapping_status": reason, "bot_status_unchanged": True,
        })
    await write_operator_audit(request, actor_user_id=operator["id"], action="spatial.agent.mapping.candidates",
        outcome="allowed", resource_type="official_agent_bots", resource_id="batch",
        metadata={"bot_count": len(output), "counts": counts})
    return {"source_of_truth": ["official_agent_bots", "spatial_asset_versions", "agent_skill_versions"],
            "counts": counts, "items": output, "limit": limit, "offset": offset,
            "activation_performed": False,
            "policy": "Only archetype-compatible published rights-verified character assets and the matching immutable Skill Version can be fully linked."}

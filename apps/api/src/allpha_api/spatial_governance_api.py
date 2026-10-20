"""ENG-P21 privileged spatial hierarchy and GLB governance lifecycle."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from allpha_api.operator_security import privileged_rest_request, require_operator_scope, write_operator_audit

router = APIRouter(prefix="/v1/admin/spatial", tags=["spatial-governance"])
LEVELS = ("universe", "galaxy", "world", "district", "zone", "booth", "poi", "scene_object")
PARENT_LEVELS = {
    "universe": (),
    "galaxy": ("universe",),
    "world": ("galaxy",),
    "district": ("world",),
    "zone": ("district",),
    "booth": ("district", "zone"),
    "poi": ("world", "district", "zone", "booth"),
    "scene_object": ("world", "district", "zone", "booth", "poi"),
}
CATEGORIES = ("universe", "galaxy", "world", "orbit", "capsule", "district", "booth", "content-feed", "agent-character", "live-stage", "human-live", "sticker-social", "animation", "navigation-fx")


def fail(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code, "message": message})


class NodeCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    node_key: str = Field(min_length=3, max_length=128, pattern=r"^[a-z0-9][a-z0-9._-]{2,127}$")
    parent_key: str | None = Field(default=None, min_length=3, max_length=128)
    level: Literal["universe", "galaxy", "world", "district", "zone", "booth", "poi", "scene_object"]
    slug: str = Field(min_length=3, max_length=128, pattern=r"^[a-z0-9][a-z0-9._-]{2,127}$")
    display_name: str = Field(min_length=1, max_length=160)
    coordinates: dict[str, Any] | None = None
    landmarks: list[dict[str, Any]] = Field(default_factory=list, max_length=250)
    scene_key: str | None = Field(default=None, max_length=120)
    access_policy: Literal["public", "authenticated", "owner_only"] = "public"

    @model_validator(mode="after")
    def root_parent_invariant(self):
        if (self.level == "universe") != (self.parent_key is None):
            raise ValueError("Universe wajib menjadi root; level lain wajib memiliki parent.")
        if self.coordinates is not None:
            if set(self.coordinates) - {"system", "units", "x", "y", "z"}:
                raise ValueError("Koordinat hanya menerima system, units, x, y, z.")
            if self.coordinates.get("system", "right-handed-y-up") != "right-handed-y-up" or self.coordinates.get("units", "meters") != "meters":
                raise ValueError("Sistem koordinat harus right-handed-y-up dalam meter.")
            for axis in ("x", "y", "z"):
                value = self.coordinates.get(axis)
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not abs(value) < float("inf"):
                    raise ValueError("Koordinat x/y/z harus angka finite.")
        return self


class NodeDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Literal["approved", "rejected"]
    reason: str = Field(min_length=8, max_length=500)


class AssetDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Literal["approved", "rejected"]
    reason: str = Field(min_length=8, max_length=500)
    category: str | None = None
    license_evidence_uri: str | None = Field(default=None, max_length=2048)

    @field_validator("license_evidence_uri")
    @classmethod
    def evidence_uri(cls, value):
        if value is not None and not value.startswith("https://"):
            raise ValueError("Bukti lisensi harus URL HTTPS.")
        return value


class AgentAssetMappingCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    agent_id: UUID
    asset_key: str = Field(min_length=3, max_length=120, pattern=r"^[a-z0-9][a-z0-9._-]{2,119}$")
    asset_version: int = Field(ge=1)
    evidence_type: Literal["authoritative_agent_profile", "owner_attestation", "source_manifest", "reviewed_visual_match"]
    evidence_uri: str = Field(min_length=12, max_length=2048)
    evidence_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    rationale: str = Field(min_length=12, max_length=1000)

    @field_validator("evidence_uri")
    @classmethod
    def evidence_https(cls, value):
        if not value.startswith("https://"):
            raise ValueError("Evidence harus URL HTTPS.")
        return value


@router.post("/nodes", status_code=201)
async def create_spatial_node(payload: NodeCreate, request: Request,
    operator: dict[str, Any] = Depends(require_operator_scope("platform:content.moderate"))) -> dict[str, Any]:
    parent_id = None
    if payload.parent_key:
        parents = await privileged_rest_request("GET", "spatial_navigation_nodes", params={
            "select": "id,node_key,level,status", "node_key": f"eq.{payload.parent_key}", "limit": "1"
        })
        if not parents:
            raise fail(422, "SPATIAL_PARENT_NOT_FOUND", "Parent node tidak ditemukan.")
        parent = parents[0]
        if parent["level"] not in PARENT_LEVELS[payload.level]:
            raise fail(422, "SPATIAL_HIERARCHY_INVALID", "Level parent tidak sesuai dengan aturan hierarki.")
        if parent["status"] not in ("approved", "published"):
            raise fail(409, "SPATIAL_PARENT_NOT_APPROVED", "Parent harus disetujui sebelum anak dibuat.")
        parent_id = parent["id"]
    body = {"node_key": payload.node_key, "parent_id": parent_id, "level": payload.level, "slug": payload.slug,
        "display_name": payload.display_name, "coordinates": payload.coordinates, "landmarks": payload.landmarks,
        "scene_key": payload.scene_key, "access_policy": payload.access_policy, "status": "draft", "version": 1}
    await write_operator_audit(request, actor_user_id=operator["id"], action="spatial.node.create", outcome="attempted", resource_type="spatial_navigation_node", resource_id=payload.node_key, metadata={"level": payload.level, "parent_key": payload.parent_key})
    try:
        rows = await privileged_rest_request("POST", "spatial_navigation_nodes", body=body, prefer="return=representation")
    except HTTPException as exc:
        if exc.status_code == 409:
            raise fail(409, "SPATIAL_NODE_CONFLICT", "node_key sudah digunakan.")
        raise
    row = rows[0] if isinstance(rows, list) and rows else {}
    await write_operator_audit(request, actor_user_id=operator["id"], action="spatial.node.create", outcome="allowed",
        resource_type="spatial_navigation_node", resource_id=str(row.get("id") or payload.node_key),
        metadata={"node_key": payload.node_key, "level": payload.level, "parent_key": payload.parent_key})
    return {"item": row}


@router.get("/nodes")
async def list_governed_nodes(status: str = "draft", limit: int = 100,
    operator: dict[str, Any] = Depends(require_operator_scope("platform:content.moderate"))) -> dict[str, Any]:
    if status not in {"draft", "review", "approved", "published", "rejected", "deprecated", "revoked"} or not 1 <= limit <= 100:
        raise fail(422, "SPATIAL_NODE_FILTER_INVALID", "Filter node tidak valid.")
    rows = await privileged_rest_request("GET", "spatial_navigation_nodes", params={
        "select": "id,node_key,parent_id,level,slug,display_name,coordinates,landmarks,scene_key,access_policy,status,version,created_at,updated_at,published_at",
        "status": f"eq.{status}", "order": "created_at.asc", "limit": str(limit)})
    return {"items": rows or [], "status": status, "limit": limit}


@router.post("/nodes/{node_key}/submit")
async def submit_spatial_node(node_key: str, request: Request,
    operator: dict[str, Any] = Depends(require_operator_scope("platform:content.moderate"))) -> dict[str, Any]:
    rows = await privileged_rest_request("GET", "spatial_navigation_nodes", params={"select":"id,node_key,level,parent_id,status","node_key":f"eq.{node_key}","limit":"1"})
    if not rows or rows[0]["status"] != "draft":
        raise fail(409, "SPATIAL_NODE_TRANSITION_INVALID", "Hanya node draft yang dapat diajukan untuk review.")
    row = rows[0]
    if row["level"] != "universe":
        parents = await privileged_rest_request("GET", "spatial_navigation_nodes", params={"select":"id,status","id":f"eq.{row['parent_id']}","limit":"1"})
        if not parents or parents[0]["status"] not in ("approved", "published"):
            raise fail(409, "SPATIAL_PARENT_NOT_APPROVED", "Parent harus approved atau published.")
    await write_operator_audit(request, actor_user_id=operator["id"], action="spatial.node.submit", outcome="attempted", resource_type="spatial_navigation_node", resource_id=node_key, metadata={})
    updated = await privileged_rest_request("PATCH", "spatial_navigation_nodes", params={"id":f"eq.{row['id']}","status":"eq.draft"}, body={"status":"review","updated_at":datetime.now(timezone.utc).isoformat(),"version":1}, prefer="return=representation")
    await write_operator_audit(request, actor_user_id=operator["id"], action="spatial.node.submit", outcome="allowed", resource_type="spatial_navigation_node", resource_id=node_key, metadata={})
    return {"item": updated[0] if updated else None}


@router.post("/nodes/{node_key}/review")
async def review_spatial_node(node_key: str, payload: NodeDecision, request: Request,
    operator: dict[str, Any] = Depends(require_operator_scope("platform:content.moderate"))) -> dict[str, Any]:
    rows = await privileged_rest_request("GET", "spatial_navigation_nodes", params={"select":"id,status,level,parent_id","node_key":f"eq.{node_key}","limit":"1"})
    if not rows or rows[0]["status"] != "review":
        raise fail(409, "SPATIAL_NODE_TRANSITION_INVALID", "Node harus berstatus review.")
    row = rows[0]
    if payload.decision == "approved" and row["level"] != "universe":
        parents = await privileged_rest_request("GET", "spatial_navigation_nodes", params={"select":"id,status","id":f"eq.{row['parent_id']}","limit":"1"})
        if not parents or parents[0]["status"] not in ("approved", "published"):
            raise fail(409, "SPATIAL_PARENT_NOT_APPROVED", "Parent belum approved/published.")
    status = payload.decision
    await write_operator_audit(request, actor_user_id=operator["id"], action=f"spatial.node.{status}", outcome="attempted", resource_type="spatial_navigation_node", resource_id=node_key, metadata={"reason": payload.reason})
    updated = await privileged_rest_request("PATCH", "spatial_navigation_nodes", params={"node_key":f"eq.{node_key}","status":"eq.review"},
        body={"status":status,"updated_at":datetime.now(timezone.utc).isoformat()}, prefer="return=representation")
    await write_operator_audit(request, actor_user_id=operator["id"], action=f"spatial.node.{status}", outcome="allowed",
        resource_type="spatial_navigation_node", resource_id=node_key, metadata={"reason":payload.reason})
    return {"item": updated[0] if updated else None}


@router.post("/nodes/{node_key}/publish")
async def publish_spatial_node(node_key: str, request: Request,
    operator: dict[str, Any] = Depends(require_operator_scope("platform:content.moderate"))) -> dict[str, Any]:
    rows = await privileged_rest_request("GET", "spatial_navigation_nodes", params={"select":"id,node_key,level,parent_id,status,access_policy","node_key":f"eq.{node_key}","limit":"1"})
    if not rows or rows[0]["status"] != "approved":
        raise fail(409, "SPATIAL_NODE_NOT_APPROVED", "Node harus approved sebelum publikasi.")
    row = rows[0]
    if row["level"] != "universe":
        parents = await privileged_rest_request("GET", "spatial_navigation_nodes", params={"select":"id,status","id":f"eq.{row['parent_id']}","limit":"1"})
        if not parents or parents[0]["status"] != "published":
            raise fail(409, "SPATIAL_PARENT_NOT_PUBLISHED", "Parent harus dipublikasikan lebih dahulu.")
    await write_operator_audit(request, actor_user_id=operator["id"], action="spatial.node.publish", outcome="attempted", resource_type="spatial_navigation_node", resource_id=node_key, metadata={"access_policy": row["access_policy"]})
    updated = await privileged_rest_request("PATCH", "spatial_navigation_nodes", params={"id":f"eq.{row['id']}","status":"eq.approved"},
        body={"status":"published","published_at":datetime.now(timezone.utc).isoformat(),"updated_at":datetime.now(timezone.utc).isoformat()}, prefer="return=representation")
    await write_operator_audit(request, actor_user_id=operator["id"], action="spatial.node.publish", outcome="allowed",
        resource_type="spatial_navigation_node", resource_id=node_key, metadata={"access_policy":row["access_policy"]})
    return {"item": updated[0] if updated else None}


@router.get("/assets/review")
async def list_assets_for_review(limit: int = 100,
    operator: dict[str, Any] = Depends(require_operator_scope("platform:content.moderate"))) -> dict[str, Any]:
    if not 1 <= limit <= 100:
        raise fail(422, "SPATIAL_ASSET_PAGINATION_INVALID", "Limit harus 1-100.")
    rows = await privileged_rest_request("GET", "spatial_asset_versions", params={
        "select":"asset_id,version,asset_key,display_name,category,sha256,byte_size,status,moderation_status,license_evidence_status,source_url,source_repo,source_path",
        "status":"eq.test_only","order":"created_at.asc","limit":str(limit)})
    return {"items":rows or [],"limit":limit,"note":"Tidak ada aset yang dipublikasikan otomatis."}


@router.post("/assets/{asset_key}/{version}/review")
async def review_spatial_asset(asset_key: str, version: int, payload: AssetDecision, request: Request,
    operator: dict[str, Any] = Depends(require_operator_scope("platform:content.moderate"))) -> dict[str, Any]:
    if payload.category is not None and payload.category not in CATEGORIES:
        raise fail(422, "SPATIAL_CATEGORY_INVALID", "Kategori bukan bagian dari taxonomy 14 kategori.")
    rows = await privileged_rest_request("GET", "spatial_asset_versions", params={
        "select":"asset_id,version,asset_key,status,moderation_status,sha256,source_url,license_evidence_status",
        "asset_key":f"eq.{asset_key}","version":f"eq.{version}","limit":"1"})
    if not rows or rows[0]["status"] not in ("test_only","quarantined"):
        raise fail(409, "SPATIAL_ASSET_REVIEW_INVALID", "Aset tidak tersedia untuk review pada lifecycle saat ini.")
    row=rows[0]
    if payload.decision == "approved" and not payload.license_evidence_uri:
        raise fail(422, "SPATIAL_LICENSE_EVIDENCE_REQUIRED", "Persetujuan membutuhkan URL bukti lisensi HTTPS.")
    body={"moderation_status":payload.decision,"moderation_reason":payload.reason,"reviewed_by":operator["id"],"reviewed_at":datetime.now(timezone.utc).isoformat()}
    if payload.license_evidence_uri:
        body["license_evidence_uri"]=payload.license_evidence_uri
        body["license_evidence_status"]="verified"
    if payload.category:
        body["category"]=payload.category
    await write_operator_audit(request, actor_user_id=operator["id"], action=f"spatial.asset.review.{payload.decision}", outcome="attempted", resource_type="spatial_asset_version", resource_id=f"{asset_key}:{version}", metadata={"reason": payload.reason, "sha256": row["sha256"]})
    updated=await privileged_rest_request("PATCH","spatial_asset_versions",params={"asset_key":f"eq.{asset_key}","version":f"eq.{version}","status":f"in.({row['status']})"},body=body,prefer="return=representation")
    await write_operator_audit(request,actor_user_id=operator["id"],action=f"spatial.asset.review.{payload.decision}",outcome="allowed",
        resource_type="spatial_asset_version",resource_id=f"{asset_key}:{version}",metadata={"reason":payload.reason,"category":payload.category,"license_evidence_supplied":bool(payload.license_evidence_uri),"sha256":row["sha256"]})
    return {"item":updated[0] if updated else None}


@router.post("/assets/{asset_key}/{version}/publish")
async def publish_spatial_asset(asset_key: str, version: int, request: Request,
    operator: dict[str, Any] = Depends(require_operator_scope("platform:content.moderate"))) -> dict[str, Any]:
    rows=await privileged_rest_request("GET","spatial_asset_versions",params={"select":"asset_id,version,asset_key,status,moderation_status,license_evidence_status,sha256,category","asset_key":f"eq.{asset_key}","version":f"eq.{version}","limit":"1"})
    if not rows:
        raise fail(404,"SPATIAL_ASSET_NOT_FOUND","Versi aset tidak ditemukan.")
    row=rows[0]
    if row.get("moderation_status")!="approved" or row.get("license_evidence_status")!="verified" or row.get("status") not in ("test_only","quarantined"):
        raise fail(409,"SPATIAL_ASSET_NOT_READY","Aset wajib approved, memiliki bukti lisensi verified, dan berada dalam lifecycle yang dapat dipublikasikan.")
    await write_operator_audit(request, actor_user_id=operator["id"], action="spatial.asset.publish", outcome="attempted", resource_type="spatial_asset_version", resource_id=f"{asset_key}:{version}", metadata={"sha256": row["sha256"], "category": row["category"]})
    updated=await privileged_rest_request("PATCH","spatial_asset_versions",params={"asset_key":f"eq.{asset_key}","version":f"eq.{version}","status":f"in.(test_only,quarantined)","moderation_status":"eq.approved","license_evidence_status":"eq.verified"},
        body={"status":"published","published_at":datetime.now(timezone.utc).isoformat()},prefer="return=representation")
    await write_operator_audit(request,actor_user_id=operator["id"],action="spatial.asset.publish",outcome="allowed",resource_type="spatial_asset_version",resource_id=f"{asset_key}:{version}",metadata={"sha256":row["sha256"],"category":row["category"]})
    return {"item":updated[0] if updated else None}


@router.get("/agent-asset-mappings")
async def list_agent_asset_mappings(status: str = "pending", limit: int = 100,
    operator: dict[str, Any] = Depends(require_operator_scope("platform:content.moderate"))) -> dict[str, Any]:
    if status not in {"pending", "approved", "rejected", "revoked"} or not 1 <= limit <= 100:
        raise fail(422, "SPATIAL_MAPPING_FILTER_INVALID", "Filter mapping tidak valid.")
    rows = await privileged_rest_request("GET", "spatial_agent_asset_mappings", params={
        "select": "id,agent_id,asset_key,asset_version,evidence_type,evidence_uri,evidence_sha256,rationale,status,created_by,created_at,reviewed_by,reviewed_at,review_reason",
        "status": f"eq.{status}", "order": "created_at.asc", "limit": str(limit)})
    return {"items": rows or [], "status": status, "limit": limit}


@router.post("/agent-asset-mappings", status_code=201)@router.post("/agent-asset-mappings", status_code=201)
async def propose_agent_asset_mapping(payload: AgentAssetMappingCreate, request: Request,
    operator: dict[str, Any] = Depends(require_operator_scope("platform:content.moderate"))) -> dict[str, Any]:
    assets=await privileged_rest_request("GET","spatial_asset_versions",params={"select":"asset_id,asset_key,version,status,moderation_status,sha256","asset_key":f"eq.{payload.asset_key}","version":f"eq.{payload.asset_version}","status":"eq.published","moderation_status":"eq.approved","limit":"1"})
    if not assets:
        raise fail(409,"SPATIAL_AGENT_ASSET_NOT_PUBLISHED","Pemetaan hanya dapat mengacu pada GLB published+approved.")
    body={"agent_id":str(payload.agent_id),"asset_key":payload.asset_key,"asset_version":payload.asset_version,
        "evidence_type":payload.evidence_type,"evidence_uri":payload.evidence_uri,"evidence_sha256":payload.evidence_sha256,
        "rationale":payload.rationale,"status":"pending","created_by":operator["id"]}
    await write_operator_audit(request, actor_user_id=operator["id"], action="spatial.agent_asset_mapping.propose", outcome="attempted", resource_type="spatial_agent_asset_mapping", resource_id=str(payload.agent_id), metadata={"asset_key": payload.asset_key, "asset_version": payload.asset_version})
    rows=await privileged_rest_request("POST","spatial_agent_asset_mappings",body=body,prefer="return=representation")
    row=rows[0] if isinstance(rows,list) and rows else {}
    await write_operator_audit(request,actor_user_id=operator["id"],action="spatial.agent_asset_mapping.propose",outcome="allowed",
        resource_type="spatial_agent_asset_mapping",resource_id=str(row.get("id") or payload.agent_id),
        metadata={"asset_key":payload.asset_key,"asset_version":payload.asset_version,"evidence_type":payload.evidence_type,"asset_sha256":assets[0]["sha256"]})
    return {"item":row}


@router.post("/agent-asset-mappings/{mapping_id}/review")
async def review_agent_asset_mapping(mapping_id: UUID, payload: NodeDecision, request: Request,
    operator: dict[str, Any] = Depends(require_operator_scope("platform:content.moderate"))) -> dict[str, Any]:
    rows=await privileged_rest_request("GET","spatial_agent_asset_mappings",params={"select":"id,agent_id,asset_key,asset_version,status,evidence_type,evidence_uri,evidence_sha256","id":f"eq.{mapping_id}","limit":"1"})
    if not rows or rows[0]["status"]!="pending":
        raise fail(409,"SPATIAL_MAPPING_TRANSITION_INVALID","Mapping harus pending untuk direview.")
    row=rows[0]
    if payload.decision=="approved":
        assets=await privileged_rest_request("GET","spatial_asset_versions",params={"select":"sha256,status,moderation_status","asset_key":f"eq.{row['asset_key']}","version":f"eq.{row['asset_version']}","limit":"1"})
        if not assets or assets[0]["status"]!="published" or assets[0]["moderation_status"]!="approved":
            raise fail(409,"SPATIAL_AGENT_ASSET_NOT_PUBLISHED","Aset tidak lagi memenuhi syarat publikasi.")
        if row.get("evidence_sha256") and row["evidence_sha256"] != assets[0]["sha256"]:
            raise fail(409,"SPATIAL_MAPPING_EVIDENCE_MISMATCH","Checksum bukti tidak cocok dengan GLB.")
    body={"status":payload.decision,"reviewed_by":operator["id"],"reviewed_at":datetime.now(timezone.utc).isoformat(),"review_reason":payload.reason}
    await write_operator_audit(request, actor_user_id=operator["id"], action=f"spatial.agent_asset_mapping.{payload.decision}", outcome="attempted", resource_type="spatial_agent_asset_mapping", resource_id=str(mapping_id), metadata={"reason": payload.reason, "asset_key": row["asset_key"]})
    updated=await privileged_rest_request("PATCH","spatial_agent_asset_mappings",params={"id":f"eq.{mapping_id}","status":"eq.pending"},body=body,prefer="return=representation")
    await write_operator_audit(request,actor_user_id=operator["id"],action=f"spatial.agent_asset_mapping.{payload.decision}",outcome="allowed",
        resource_type="spatial_agent_asset_mapping",resource_id=str(mapping_id),metadata={"reason":payload.reason,"asset_key":row["asset_key"]})
    return {"item":updated[0] if updated else None}

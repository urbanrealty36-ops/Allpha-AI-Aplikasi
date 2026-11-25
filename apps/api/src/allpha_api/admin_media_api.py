"""Read-only Super Admin media operations backed by canonical media/job registries."""
from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from allpha_api.media_api import _require_cloudinary_media_schema, media_item_response
from allpha_api.operator_security import privileged_rest_request, require_operator_scope, write_operator_audit

router = APIRouter(prefix="/v1/admin/operator/media", tags=["platform-operations"])

_MEDIA_STATUSES = {"uploading", "uploaded", "processing", "ready", "failed", "deleting", "deleted"}
_MEDIA_DOMAINS = {"content", "profile", "feed", "reels", "stories", "cinema", "live", "agent", "messaging", "community", "marketplace", "other"}


def _operator_media_projection(item: dict[str, Any]) -> dict[str, Any]:
    projected = media_item_response(item)
    projected.pop("sha256", None)
    return projected


def _job_projection(job: dict[str, Any]) -> dict[str, Any]:
    allowed = (
        "id", "media_id", "job_type", "status", "attempts", "max_attempts",
        "run_at", "last_error_code", "created_at", "updated_at", "completed_at",
    )
    return {key: job[key] for key in allowed if key in job}


@router.get("", name="list_operator_media")
async def list_operator_media(
    request: Request,
    status: str | None = Query(default=None),
    domain: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=10000),
    operator: dict[str, Any] = Depends(require_operator_scope("platform:operations.read")),
) -> dict[str, Any]:
    await _require_cloudinary_media_schema()
    if status is not None and status not in _MEDIA_STATUSES:
        raise HTTPException(422, detail={"code": "MEDIA_STATUS_FILTER_INVALID", "message": "Filter status media tidak valid."})
    if domain is not None and domain not in _MEDIA_DOMAINS:
        raise HTTPException(422, detail={"code": "MEDIA_DOMAIN_FILTER_INVALID", "message": "Filter domain media tidak valid."})

    params: dict[str, str] = {
        "select": "id,content_id,domain,purpose,resource_id,filename,media_type,size_bytes,sha256,status,scan_status,storage_provider,provider_resource_type,provider_delivery_type,provider_format,provider_version,provider_width,provider_height,provider_duration,provider_bytes,provider_delete_state,upload_expires_at,upload_completed_at,provider_deleted_at,provider_callback_verified_at,created_at,processed_at,updated_at",
        "order": "created_at.desc",
        "limit": str(limit),
        "offset": str(offset),
    }
    if status:
        params["status"] = f"eq.{status}"
    if domain:
        params["domain"] = f"eq.{domain}"
    rows = await privileged_rest_request("GET", "content_media", params=params)
    media_ids = [str(row["id"]) for row in (rows or []) if row.get("id")]
    jobs: list[dict[str, Any]] = []
    if media_ids:
        jobs = await privileged_rest_request(
            "GET", "content_lifecycle_jobs",
            params={
                "select": "id,media_id,job_type,status,attempts,max_attempts,run_at,last_error_code,created_at,updated_at,completed_at",
                "media_id": "in.(" + ",".join(media_ids) + ")",
                "order": "created_at.desc",
                "limit": str(min(500, max(50, limit * 5))),
            },
        ) or []
    await write_operator_audit(
        request, actor_user_id=operator["id"], action="media.operations.list",
        outcome="allowed", resource_type="content_media",
        metadata={"count": len(rows or []), "status_filter": status, "domain_filter": domain},
    )
    return {
        "items": [_operator_media_projection(row) for row in (rows or [])],
        "jobs": [_job_projection(job) for job in jobs],
        "limit": limit, "offset": offset,
    }


@router.get("/{media_id}", name="get_operator_media")
async def get_operator_media(
    media_id: UUID,
    request: Request,
    operator: dict[str, Any] = Depends(require_operator_scope("platform:operations.read")),
) -> dict[str, Any]:
    await _require_cloudinary_media_schema()
    rows = await privileged_rest_request(
        "GET", "content_media",
        params={
            "select": "id,content_id,domain,purpose,resource_id,filename,media_type,size_bytes,sha256,status,scan_status,storage_provider,provider_resource_type,provider_delivery_type,provider_format,provider_version,provider_width,provider_height,provider_duration,provider_bytes,provider_delete_state,upload_expires_at,upload_completed_at,provider_deleted_at,provider_callback_verified_at,created_at,processed_at,updated_at",
            "id": f"eq.{media_id}", "limit": "1",
        },
    )
    if not rows:
        raise HTTPException(404, detail={"code": "MEDIA_NOT_FOUND", "message": "Media tidak ditemukan."})
    jobs = await privileged_rest_request(
        "GET", "content_lifecycle_jobs",
        params={
            "select": "id,media_id,job_type,status,attempts,max_attempts,run_at,last_error_code,created_at,updated_at,completed_at",
            "media_id": f"eq.{media_id}",
            "order": "created_at.desc",
            "limit": "100",
        },
    ) or []
    item = rows[0]
    await write_operator_audit(
        request, actor_user_id=operator["id"], action="media.operations.read",
        outcome="allowed", resource_type="content_media", resource_id=str(media_id),
        metadata={"status": item.get("status"), "domain": item.get("domain"), "storage_provider": item.get("storage_provider")},
    )
    return {"item": _operator_media_projection(item), "jobs": [_job_projection(job) for job in jobs]}

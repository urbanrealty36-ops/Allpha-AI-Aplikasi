"""ENG-P16 Stories/Moments lifecycle built on the canonical content registry."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from allpha_api.auth import current_user, optional_current_user
from allpha_api.content_api import MEDIA_FIELDS, _server_db, _signed_media_preview_url, _storage
from allpha_api.feed_api import _edges

router = APIRouter(prefix="/v1/stories", tags=["stories"])
STORY_FIELDS = (
    "id,owner_id,content_type,body,visibility,status,moderation_status,version,"
    "created_at,updated_at,published_at,expires_at,provenance"
)
MAX_TTL_HOURS = 168


class StoryCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    body: str = Field(default="", max_length=2000)
    visibility: Literal["public", "followers", "private"] = "public"
    expires_after_hours: int = Field(default=24, ge=1, le=MAX_TTL_HOURS)


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _attach_media(items: list[dict[str, Any]], *, owner_id: str | None = None) -> list[dict[str, Any]]:
    if not items:
        return []
    ids = [str(item["id"]) for item in items]
    params: dict[str, str] = {
        "select": MEDIA_FIELDS,
        "content_id": f"in.({','.join(ids)})",
        "status": "in.(uploaded,ready)",
        "order": "created_at.asc",
        "limit": str(min(500, len(ids) * 10)),
    }
    if owner_id is not None:
        params["owner_id"] = f"eq.{owner_id}"
    media = await _server_db("GET", "content_media", params=params)
    by_content: dict[str, list[dict[str, Any]]] = {}
    allowed_ids = set(ids)
    for row in media or []:
        content_id = str(row.get("content_id"))
        if content_id not in allowed_ids:
            continue
        by_content.setdefault(content_id, []).append({
            **row,
            "preview_url": await _signed_media_preview_url(row["storage_path"], expires_in=300),
        })
    return [{**item, "media": by_content.get(str(item["id"]), [])} for item in items]


async def _cleanup_story_media(content_id: str, owner_id: str | None = None) -> int:
    """Delete expired/removed story binaries and then their metadata; retain failed items for retry."""
    params: dict[str, str] = {
        "select": "id,owner_id,storage_path,status",
        "content_id": f"eq.{content_id}",
        "status": "in.(uploaded,ready,processing,failed,deleting)",
        "limit": "100",
    }
    if owner_id is not None:
        params["owner_id"] = f"eq.{owner_id}"
    media = await _server_db("GET", "content_media", params=params)
    deleted = 0
    for item in media or []:
        marked = item
        if item.get("status") != "deleting":
            rows = await _server_db("PATCH", "content_media", params={
                "id": f"eq.{item['id']}", "owner_id": f"eq.{item['owner_id']}",
                "status": f"eq.{item['status']}", "select": "id,owner_id,storage_path,status",
            }, body={"status": "deleting"}, prefer="return=representation")
            if not rows:
                continue
            marked = rows[0]
        try:
            await _storage("DELETE", f"content-media/{marked['storage_path']}")
        except HTTPException:
            # Preserve deleting metadata so a subsequent cleanup attempt can retry.
            continue
        await _server_db("DELETE", "content_media", params={
            "id": f"eq.{marked['id']}", "owner_id": f"eq.{marked['owner_id']}",
            "status": "eq.deleting",
        })
        deleted += 1
    return deleted


async def _cleanup_pending_story_media() -> int:
    """Retry media cleanup left in deleting state by an earlier interrupted request."""
    pending = await _server_db("GET", "content_media", params={
        "select": "id,content_id,owner_id",
        "status": "eq.deleting",
        "limit": "100",
    })
    deleted = 0
    for item in pending or []:
        parent = await _server_db("GET", "content_items", params={
            "select": "id,content_type,status",
            "id": f"eq.{item['content_id']}",
            "content_type": "eq.story",
            "status": "in.(archived,deleted)",
            "limit": "1",
        })
        if parent:
            deleted += await _cleanup_story_media(str(item["content_id"]), str(item["owner_id"]))
    return deleted


async def _expire_due_stories() -> int:
    """Hide expired stories immediately at read time and archive their lifecycle state."""
    now = _now().isoformat()
    expired = await _server_db("GET", "content_items", params={
        "select": "id,version",
        "content_type": "eq.story",
        "status": "eq.published",
        "moderation_status": "eq.approved",
        "expires_at": f"lte.{now}",
        "limit": "200",
    })
    changed = 0
    for row in expired or []:
        rows = await _server_db("PATCH", "content_items", params={
            "id": f"eq.{row['id']}",
            "content_type": "eq.story",
            "status": "eq.published",
            "moderation_status": "eq.approved",
            "expires_at": f"lte.{now}",
            "version": f"eq.{row['version']}",
            "select": "id",
        }, body={
            "status": "archived",
            "version": int(row["version"]) + 1,
        }, prefer="return=representation")
        if rows:
            changed += len(rows)
            await _cleanup_story_media(str(row["id"]))
    await _cleanup_pending_story_media()
    return changed


@router.post("", status_code=201)
async def create_story(
    payload: StoryCreate,
    request: Request,
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    if not payload.body.strip():
        # Media-only stories are created with a minimal body so the existing content
        # and private-media lifecycle can be reused without a second registry.
        body = ""
    else:
        body = payload.body.strip()
    row = {
        "owner_id": str(user["id"]),
        "content_type": "story",
        "body": body,
        "visibility": payload.visibility,
        "status": "draft",
        "moderation_status": "not_submitted",
        "version": 1,
        "provenance": {
            "stories": {
                "expires_after_hours": payload.expires_after_hours,
                "created_via": "eng-p16",
            }
        },
    }
    created = await _server_db("POST", "content_items", body=row, prefer="return=representation")
    if not created:
        raise HTTPException(503, detail={"code": "STORY_CREATE_FAILED", "message": "Story belum dapat disimpan."})
    return {
        "item": created[0],
        "next_action": "Tambahkan media bila diperlukan, lalu kirim melalui /v1/content/{id}/publish untuk moderasi.",
    }


@router.get("")
async def list_active_stories(
    request: Request,
    limit: int = Query(default=30, ge=1, le=100),
    user: dict[str, Any] | None = Depends(optional_current_user),
) -> dict[str, Any]:
    now = _now()
    # Guest reads filter expires_at at query time; do not let anonymous traffic trigger cleanup writes.
    if user:
        await _expire_due_stories()
    rows = await _server_db("GET", "content_items", params={
        "select": STORY_FIELDS,
        "content_type": "eq.story",
        "status": "eq.published",
        "moderation_status": "eq.approved",
        "visibility": "eq.public" if user is None else "in.(public,followers)",
        "expires_at": f"gt.{now.isoformat()}",
        "published_at": f"lte.{now.isoformat()}",
        "order": "published_at.desc,id.desc",
        "limit": str(min(1000, limit * 20)),
    })
    owner_ids = sorted({str(item.get("owner_id")) for item in (rows or []) if item.get("owner_id")})
    profiles = await _server_db("GET", "profiles", params={
        "select": "id,username,display_name,avatar_url,visibility",
        "id": f"in.({','.join(owner_ids)})", "limit": str(min(1000, len(owner_ids))),
    }) if owner_ids else []
    profiles_by_id = {str(profile.get("id")): profile for profile in (profiles or [])}
    if user:
        followed, hidden = await _edges(str(user["id"]))
        visible = [
            item for item in (rows or [])
            if str(item.get("owner_id")) not in hidden
            and (
                (item.get("visibility") == "public" and (
                    profiles_by_id.get(str(item.get("owner_id")), {}).get("visibility") == "public"
                    or str(item.get("owner_id")) in followed
                ))
                or (item.get("visibility") == "followers" and str(item.get("owner_id")) in followed)
            )
        ][:limit]
    else:
        # Anonymous discovery is strictly public and public-profile-only.
        visible = [
            item for item in (rows or [])
            if item.get("visibility") == "public"
            and profiles_by_id.get(str(item.get("owner_id")), {}).get("visibility") == "public"
        ][:limit]
    items = await _attach_media(visible)
    for item in items:
        creator = profiles_by_id.get(str(item.get("owner_id")), {})
        item["creator"] = {
            "username": creator.get("username"),
            "display_name": creator.get("display_name") or creator.get("username") or "Kreator",
            "avatar_url": creator.get("avatar_url"),
        }
        item["discovery_group"] = (
            "following" if user and str(item.get("owner_id")) in followed
            else "suggested_public"
        )
    return {"items": items, "server_time": now.isoformat(), "media_preview_expires_in": 300}


@router.get("/mine")
async def list_my_stories(
    request: Request,
    limit: int = Query(default=50, ge=1, le=100),
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    now = _now()
    await _expire_due_stories()
    rows = await _server_db("GET", "content_items", params={
        "select": STORY_FIELDS,
        "owner_id": f"eq.{user['id']}",
        "content_type": "eq.story",
        "status": "in.(draft,review,published,failed,archived)",
        "order": "created_at.desc",
        "limit": str(limit),
    })
    items = await _attach_media(rows or [], owner_id=str(user["id"]))
    return {
        "items": items,
        "server_time": now.isoformat(),
        "media_preview_expires_in": 300,
    }


@router.delete("/{story_id}")
async def archive_my_story(
    story_id: uuid.UUID,
    request: Request,
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    rows = await _server_db("GET", "content_items", params={
        "select": STORY_FIELDS,
        "id": f"eq.{story_id}",
        "owner_id": f"eq.{user['id']}",
        "content_type": "eq.story",
        "status": "not.in.(archived,deleted)",
        "limit": "1",
    })
    if not rows:
        raise HTTPException(404, detail={"code": "STORY_NOT_FOUND", "message": "Story tidak ditemukan."})
    item = rows[0]
    updated = await _server_db("PATCH", "content_items", params={
        "id": f"eq.{story_id}",
        "owner_id": f"eq.{user['id']}",
        "content_type": "eq.story",
        "status": f"eq.{item['status']}",
        "version": f"eq.{item['version']}",
        "select": STORY_FIELDS,
    }, body={
        "status": "archived",
        "expires_at": _now().isoformat(),
        "version": int(item["version"]) + 1,
    }, prefer="return=representation")
    if not updated:
        raise HTTPException(409, detail={"code": "STORY_UPDATE_CONFLICT", "message": "Story berubah; muat ulang sebelum mencoba lagi."})
    await _cleanup_story_media(str(story_id), str(user["id"]))
    return {"item": updated[0], "message": "Story diarsipkan; media yang dapat dihapus telah dibersihkan."}

"""ENG-P20 authenticated notification inbox API.

Notification writes are server-owned; this router exposes only the authenticated
user's inbox and read-state mutations. Provider delivery is not implied by inbox
persistence and is handled by a separate configured worker.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any
import uuid

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from allpha_api.auth import current_user

router = APIRouter(prefix="/v1/notifications", tags=["notifications"])
_TIMEOUT = httpx.Timeout(10.0, connect=3.0)


def _config() -> tuple[str, str]:
    base = os.getenv("SUPABASE_URL", "").rstrip("/")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "") or os.getenv("SUPABASE_SECRET_KEY", "")
    if not base or not key:
        raise HTTPException(status_code=503, detail={
            "code": "NOTIFICATIONS_NOT_CONFIGURED",
            "message": "Layanan notifikasi belum dikonfigurasi.",
        })
    return base, key


async def _request(method: str, table: str, *, params: dict[str, str], body: Any = None,
                   prefer: str | None = None) -> list[dict[str, Any]]:
    base, key = _config()
    headers = {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    if prefer:
        headers["Prefer"] = prefer
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            response = await client.request(method, f"{base}/rest/v1/{table}", params=params,
                                            json=body, headers=headers)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=503, detail={
            "code": "NOTIFICATIONS_UNAVAILABLE",
            "message": "Kotak notifikasi sementara tidak tersedia.",
        }) from exc
    if response.status_code >= 400:
        raise HTTPException(status_code=503, detail={
            "code": "NOTIFICATIONS_STORAGE_ERROR",
            "message": "Perubahan notifikasi tidak dapat disimpan.",
        })
    data = response.json() if response.content else []
    return data if isinstance(data, list) else []


@router.get("")
async def list_notifications(
    limit: int = Query(default=30, ge=1, le=100),
    before: datetime | None = None,
    unread_only: bool = False,
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    user_id = str(user["id"])
    params = {
        "select": "id,category,event_key,title,body,payload,delivery_state,read_at,delivered_at,created_at,expires_at",
        "user_id": f"eq.{user_id}",
        "or": "(expires_at.is.null,expires_at.gt." + datetime.now(timezone.utc).isoformat() + ")",
        "order": "created_at.desc,id.desc",
        "limit": str(limit),
    }
    if before is not None:
        params["created_at"] = f"lt.{before.astimezone(timezone.utc).isoformat()}"
    if unread_only:
        params["read_at"] = "is.null"
    items = await _request("GET", "notifications", params=params)
    unread_rows = await _request("GET", "notifications", params={
        "select": "id", "user_id": f"eq.{user_id}", "read_at": "is.null",
        "or": "(expires_at.is.null,expires_at.gt." + datetime.now(timezone.utc).isoformat() + ")",
        "limit": "1000",
    })
    return {"items": items, "unread_count": len(unread_rows), "limit": limit}


@router.patch("/{notification_id}/read")
async def mark_notification_read(
    notification_id: uuid.UUID,
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    rows = await _request("PATCH", "notifications", params={
        "id": f"eq.{notification_id}", "user_id": f"eq.{user['id']}",
        "read_at": "is.null", "select": "id,read_at",
    }, body={"read_at": datetime.now(timezone.utc).isoformat(),
             "updated_at": datetime.now(timezone.utc).isoformat()},
       prefer="return=representation")
    if not rows:
        existing = await _request("GET", "notifications", params={
            "select": "id,read_at", "id": f"eq.{notification_id}",
            "user_id": f"eq.{user['id']}", "limit": "1",
        })
        if not existing:
            raise HTTPException(status_code=404, detail={
                "code": "NOTIFICATION_NOT_FOUND",
                "message": "Notifikasi tidak ditemukan.",
            })
        return {"notification": existing[0], "already_read": True}
    return {"notification": rows[0], "already_read": False}


@router.post("/read-all")
async def mark_all_notifications_read(
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, int]:
    now = datetime.now(timezone.utc).isoformat()
    rows = await _request("PATCH", "notifications", params={
        "user_id": f"eq.{user['id']}", "read_at": "is.null", "select": "id",
    }, body={"read_at": now, "updated_at": now}, prefer="return=representation")
    return {"updated_count": len(rows)}

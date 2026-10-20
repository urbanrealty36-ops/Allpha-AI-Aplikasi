"""ENG-P20 authenticated notification inbox API.

Notification writes are server-owned; this router exposes only the authenticated
user's inbox and read-state mutations. Provider delivery is not implied by inbox
persistence and is handled by a separate configured worker.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Literal
import uuid

from pydantic import BaseModel, ConfigDict, Field

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from allpha_api.auth import current_user

router = APIRouter(prefix="/v1/notifications", tags=["notifications"])
DEFAULT_PREFERENCES = {
    "social_activity": True,
    "community": True,
    "workspace": True,
    "product_updates": True,
    "security_alerts": True,
    "push_enabled": True,
}

def _public_preferences(stored: Any) -> dict[str, bool]:
    source = stored if isinstance(stored, dict) else {}
    return {
        key: source[key] if isinstance(source.get(key), bool) else default
        for key, default in DEFAULT_PREFERENCES.items()
    }
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
        "delivery_state": "neq.suppressed",
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
        "select": "id", "user_id": f"eq.{user_id}", "read_at": "is.null", "delivery_state": "neq.suppressed",
        "or": "(expires_at.is.null,expires_at.gt." + datetime.now(timezone.utc).isoformat() + ")",
        "limit": "1000",
    })
    return {"items": items, "unread_count": len(unread_rows), "limit": limit}


class NotificationPreferencesUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    social_activity: bool | None = None
    community: bool | None = None
    workspace: bool | None = None
    product_updates: bool | None = None
    security_alerts: bool | None = None
    push_enabled: bool | None = None


class ExpoDeviceRegistration(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expo_push_token: str = Field(min_length=20, max_length=220)
    platform: Literal["android", "ios"]
    device_id: str | None = Field(default=None, min_length=1, max_length=160)


@router.get("/preferences")
async def get_notification_preferences(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    rows = await _request("GET", "user_settings", params={
        "select": "notification_preferences",
        "user_id": f"eq.{user['id']}",
        "limit": "1",
    })
    stored = rows[0].get("notification_preferences") if rows else {}
    return {"preferences": _public_preferences(stored)}


@router.patch("/preferences")
async def update_notification_preferences(
    payload: NotificationPreferencesUpdate,
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    changes = {key: getattr(payload, key) for key in payload.model_fields_set}
    if not changes or any(value is None for value in changes.values()):
        raise HTTPException(status_code=422, detail={
            "code": "NOTIFICATION_PREFERENCES_EMPTY",
            "message": "Pilih minimal satu preferensi notifikasi yang valid.",
        })
    rows = await _request("GET", "user_settings", params={
        "select": "notification_preferences",
        "user_id": f"eq.{user['id']}",
        "limit": "1",
    })
    stored = rows[0].get("notification_preferences") if rows else {}
    preferences = {**DEFAULT_PREFERENCES, **(stored if isinstance(stored, dict) else {}), **changes}
    await _request(
        "POST", "user_settings",
        params={"on_conflict": "user_id"},
        body={
            "user_id": str(user["id"]),
            "notification_preferences": preferences,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        },
        prefer="resolution=merge-duplicates,return=minimal",
    )
    return {"preferences": _public_preferences(preferences)}


@router.post("/devices", status_code=201)
async def register_notification_device(
    payload: ExpoDeviceRegistration,
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    token = payload.expo_push_token.strip()
    if not (token.startswith("ExponentPushToken[") or token.startswith("ExpoPushToken[")) or not token.endswith("]"):
        raise HTTPException(status_code=422, detail={
            "code": "EXPO_PUSH_TOKEN_INVALID",
            "message": "Token push Expo tidak valid.",
        })
    owner_rows = await _request("GET", "notification_devices", params={
        "select": "id,user_id,enabled",
        "expo_push_token": f"eq.{token}",
        "limit": "1",
    })
    now = datetime.now(timezone.utc).isoformat()
    if owner_rows:
        existing = owner_rows[0]
        if str(existing.get("user_id")) != str(user["id"]):
            raise HTTPException(status_code=409, detail={
                "code": "EXPO_PUSH_TOKEN_IN_USE",
                "message": "Token perangkat tidak dapat didaftarkan untuk akun ini.",
            })
        rows = await _request("PATCH", "notification_devices", params={
            "id": f"eq.{existing['id']}", "user_id": f"eq.{user['id']}",
            "select": "id,platform,enabled,last_seen_at",
        }, body={
            "platform": payload.platform, "device_id": payload.device_id,
            "enabled": True, "last_seen_at": now, "updated_at": now,
        }, prefer="return=representation")
        if not rows:
            raise HTTPException(status_code=503, detail={
                "code": "NOTIFICATION_DEVICE_UPDATE_FAILED",
                "message": "Registrasi perangkat belum dapat disimpan.",
            })
        return {"device": rows[0], "registered": True}

    rows = await _request("POST", "notification_devices", params={
        "select": "id,platform,enabled,last_seen_at",
    }, body={
        "user_id": str(user["id"]), "expo_push_token": token,
        "platform": payload.platform, "device_id": payload.device_id,
        "enabled": True, "last_seen_at": now, "updated_at": now,
    }, prefer="return=representation")
    if not rows:
        raise HTTPException(status_code=503, detail={
            "code": "NOTIFICATION_DEVICE_CREATE_FAILED",
            "message": "Registrasi perangkat belum dapat disimpan.",
        })
    return {"device": rows[0], "registered": True}


@router.delete("/devices/{device_id}")
async def unregister_notification_device(
    device_id: uuid.UUID,
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, bool]:
    rows = await _request("PATCH", "notification_devices", params={
        "id": f"eq.{device_id}", "user_id": f"eq.{user['id']}", "enabled": "eq.true",
        "select": "id",
    }, body={"enabled": False, "updated_at": datetime.now(timezone.utc).isoformat()},
       prefer="return=representation")
    if not rows:
        raise HTTPException(status_code=404, detail={
            "code": "NOTIFICATION_DEVICE_NOT_FOUND",
            "message": "Perangkat notifikasi tidak ditemukan.",
        })
    return {"disabled": True}


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

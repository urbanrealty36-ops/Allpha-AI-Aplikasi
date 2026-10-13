"""Allpha API foundation and authenticated identity/tenant endpoints."""
from __future__ import annotations

import os
import time
import uuid
from typing import Any, Literal

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from allpha_api.auth import current_user, user_db_request

APP_NAME = "allpha-api"
APP_VERSION = os.getenv("ALLPHA_API_VERSION", "0.2.0")
STARTED_AT = time.time()

app = FastAPI(
    title="Allpha Platform API",
    version=APP_VERSION,
    description="Allpha API with Supabase-backed identity and tenant authorization.",
)


@app.middleware("http")
async def request_context(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


@app.exception_handler(Exception)
async def unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    request_id = getattr(request.state, "request_id", "unknown")
    return JSONResponse(
        status_code=500,
        content={"error": {"code": "INTERNAL_ERROR", "message": "An unexpected error occurred.", "request_id": request_id}},
        headers={"X-Request-ID": request_id},
    )


class ProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str | None = Field(default=None, min_length=3, max_length=30, pattern=r"^[a-z0-9_]+$")
    display_name: str | None = Field(default=None, max_length=80)
    avatar_url: str | None = Field(default=None, max_length=2048)
    bio: str | None = Field(default=None, max_length=500)
    visibility: Literal["public", "private"] | None = None
    locale: Literal["id-ID", "en-US"] | None = None


class NotificationPreferences(BaseModel):
    model_config = ConfigDict(extra="forbid")
    product_updates: bool
    security_alerts: bool
    social_activity: bool


class PrivacyPreferences(BaseModel):
    model_config = ConfigDict(extra="forbid")
    discoverable_by_username: bool


class UserSettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    theme: Literal["light", "dark", "system"] | None = None
    notification_preferences: NotificationPreferences | None = None
    privacy_settings: PrivacyPreferences | None = None


class OrganizationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=2, max_length=120)
    slug: str = Field(min_length=2, max_length=63, pattern=r"^[a-z0-9][a-z0-9-]{1,62}$")


@app.get("/healthz", tags=["system"])
async def healthz() -> dict[str, str]:
    return {"status": "ok", "service": APP_NAME}


@app.get("/readyz", tags=["system"])
async def readyz() -> dict[str, Any]:
    configured = bool(os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_PUBLISHABLE_KEY"))
    return {
        "status": "ready",
        "service": APP_NAME,
        "version": APP_VERSION,
        "dependencies": {
            "database": "configured" if configured else "not_configured",
            "authentication": "configured" if configured else "not_configured",
            "object_storage": "not_configured",
            "ai_gateway": "not_configured",
        },
    }


@app.get("/v1/system/status", tags=["system"])
async def system_status(request: Request) -> dict[str, Any]:
    configured = bool(os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_PUBLISHABLE_KEY"))
    return {
        "service": APP_NAME,
        "version": APP_VERSION,
        "uptime_seconds": max(0, int(time.time() - STARTED_AT)),
        "request_id": getattr(request.state, "request_id", "unknown"),
        "environment": os.getenv("ALLPHA_ENVIRONMENT", "development"),
        "capabilities": {
            "health_checks": True,
            "structured_error_contract": True,
            "database": configured,
            "authentication": configured,
            "tenant_authorization": configured,
        },
    }


@app.get("/v1/me", tags=["identity"])
async def get_me(user: dict[str, Any] = Depends(current_user), request: Request = None) -> dict[str, Any]:
    access_token = request.state.supabase_access_token
    rows = await user_db_request(
        "GET", "profiles",
        access_token,
        params={"select": "id,username,display_name,avatar_url,bio,visibility,locale,account_status,created_at,updated_at", "id": f"eq.{user['id']}", "limit": "1"},
    )
    if not rows:
        # Profile creation is self-scoped by RLS; no privileged service key is used.
        rows = await user_db_request(
            "POST", "profiles", access_token,
            body={"id": user["id"], "display_name": (user.get("user_metadata") or {}).get("display_name", "")[:80], "locale": (user.get("user_metadata") or {}).get("locale", "id-ID")},
            prefer="return=representation",
        )
    return {"user": {"id": user["id"], "email": user.get("email"), "email_confirmed_at": user.get("email_confirmed_at")}, "profile": rows[0] if rows else None}


@app.patch("/v1/me/profile", tags=["identity"])
async def update_my_profile(payload: ProfileUpdate, user: dict[str, Any] = Depends(current_user), request: Request = None) -> dict[str, Any]:
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=422, detail={"code": "EMPTY_UPDATE", "message": "Tidak ada perubahan profil."})
    result = await user_db_request(
        "PATCH", "profiles", request.state.supabase_access_token,
        params={"id": f"eq.{user['id']}", "select": "id,username,display_name,avatar_url,bio,visibility,created_at,updated_at"},
        body=changes, prefer="return=representation",
    )
    if not result:
        raise HTTPException(status_code=404, detail={"code": "PROFILE_NOT_FOUND", "message": "Profil tidak ditemukan."})
    return {"profile": result[0]}



@app.get("/v1/me/settings", tags=["identity"])
async def get_my_settings(request: Request, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    rows = await user_db_request(
        "GET", "user_settings", request.state.supabase_access_token,
        params={"select": "user_id,theme,notification_preferences,privacy_settings,updated_at", "user_id": f"eq.{user['id']}", "limit": "1"},
    )
    if not rows:
        rows = await user_db_request(
            "POST", "user_settings", request.state.supabase_access_token,
            body={"user_id": user["id"]}, prefer="return=representation",
        )
    return {"settings": rows[0] if rows else None}


@app.patch("/v1/me/settings", tags=["identity"])
async def update_my_settings(payload: UserSettingsUpdate, request: Request, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    changes = payload.model_dump(exclude_unset=True, exclude_none=True)
    if not changes:
        raise HTTPException(status_code=422, detail={"code": "EMPTY_UPDATE", "message": "Tidak ada pengaturan yang diubah."})
    if "notification_preferences" in changes and payload.notification_preferences:
        changes["notification_preferences"] = payload.notification_preferences.model_dump()
    if "privacy_settings" in changes and payload.privacy_settings:
        changes["privacy_settings"] = payload.privacy_settings.model_dump()
    token = request.state.supabase_access_token
    rows = await user_db_request(
        "PATCH", "user_settings", token,
        params={"user_id": f"eq.{user['id']}", "select": "user_id,theme,notification_preferences,privacy_settings,updated_at"},
        body=changes, prefer="return=representation",
    )
    if not rows:
        existing = await user_db_request(
            "GET", "user_settings", token,
            params={"select": "user_id", "user_id": f"eq.{user['id']}", "limit": "1"},
        )
        if not existing:
            rows = await user_db_request(
                "POST", "user_settings", token,
                body={"user_id": user["id"], **changes}, prefer="return=representation",
            )
    if not rows:
        raise HTTPException(status_code=404, detail={"code": "SETTINGS_NOT_FOUND", "message": "Pengaturan tidak dapat diperbarui."})
    return {"settings": rows[0]}


@app.get("/v1/me/consents", tags=["identity"])
async def get_my_consents(request: Request, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    rows = await user_db_request(
        "GET", "user_consents", request.state.supabase_access_token,
        params={"select": "consent_type,policy_version,granted,recorded_at", "user_id": f"eq.{user['id']}", "order": "recorded_at.desc", "limit": "100"},
    )
    return {"items": rows}


@app.post("/v1/me/deactivation-request", tags=["identity"])
async def request_account_deactivation(request: Request, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    rows = await user_db_request(
        "PATCH", "profiles", request.state.supabase_access_token,
        params={"id": f"eq.{user['id']}", "select": "id,account_status,updated_at"},
        body={"account_status": "deactivation_requested"},
        prefer="return=representation",
    )
    if not rows:
        raise HTTPException(status_code=404, detail={"code": "PROFILE_NOT_FOUND", "message": "Profil tidak ditemukan."})
    return {"profile": rows[0], "message": "Permintaan penonaktifan akun tercatat. Akun belum dihapus."}


@app.get("/v1/organizations", tags=["organizations"])
async def list_organizations(user: dict[str, Any] = Depends(current_user), request: Request = None) -> dict[str, Any]:
    rows = await user_db_request(
        "GET", "organizations", request.state.supabase_access_token,
        params={"select": "id,name,slug,owner_id,created_at,updated_at", "order": "created_at.desc", "limit": "100"},
    )
    return {"items": rows}


@app.post("/v1/organizations", status_code=201, tags=["organizations"])
async def create_organization(payload: OrganizationCreate, user: dict[str, Any] = Depends(current_user), request: Request = None) -> dict[str, Any]:
    # owner_id comes from the validated Supabase Auth identity, never the client payload.
    rows = await user_db_request(
        "POST", "organizations", request.state.supabase_access_token,
        body={"name": payload.name, "slug": payload.slug, "owner_id": user["id"]},
        params={"select": "id,name,slug,owner_id,created_at,updated_at"},
        prefer="return=representation",
    )
    if not rows:
        raise HTTPException(status_code=500, detail={"code": "CREATE_FAILED", "message": "Organisasi tidak dapat dibuat."})
    return {"organization": rows[0]}


@app.get("/v1/organizations/{organization_id}/memberships", tags=["organizations"])
async def list_organization_memberships(organization_id: uuid.UUID, user: dict[str, Any] = Depends(current_user), request: Request = None) -> dict[str, Any]:
    rows = await user_db_request(
        "GET", "organization_memberships", request.state.supabase_access_token,
        params={"select": "organization_id,user_id,role,invited_by,created_at", "organization_id": f"eq.{organization_id}", "order": "created_at.asc", "limit": "500"},
    )
    # RLS filters memberships; return 404 rather than disclose a private tenant's existence.
    if not rows:
        orgs = await user_db_request(
            "GET", "organizations", request.state.supabase_access_token,
            params={"select": "id", "id": f"eq.{organization_id}", "limit": "1"},
        )
        if not orgs:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Organisasi tidak ditemukan."})
    return {"items": rows}

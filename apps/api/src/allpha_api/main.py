"""Allpha API foundation and authenticated identity/tenant endpoints."""
from __future__ import annotations

import json
import re
import os
import time
import uuid
from typing import Any, Literal

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
import httpx
from pydantic import BaseModel, ConfigDict, Field, field_validator

from allpha_api.auth import current_user, user_db_request
from allpha_api.agent_runtime_api import router as agent_runtime_router
from allpha_api.workflow_api import router as workflow_router
from allpha_api.skill_challenge_api import router as skill_challenge_router
from allpha_api.supabase_credit_ledger_store import CreditLedgerPersistenceError, SupabaseCreditLedgerStore
from allpha_api.tool_registry import ToolInputError, UnknownToolError, execute_tool, list_tools, validate_tool_dependencies
from allpha_api.operator_security import router as operator_security_router
from allpha_api.knowledge import router as knowledge_router
from allpha_api.knowledge_retrieval import router as knowledge_retrieval_router
from allpha_api.skill_catalog import search_skill_catalog
from allpha_api.official_bots_api import router as official_bots_router

APP_NAME = "allpha-api"
APP_VERSION = os.getenv("ALLPHA_API_VERSION", "0.2.0")
STARTED_AT = time.time()

app = FastAPI(
    title="Allpha Platform API",
    version=APP_VERSION,
    description="Allpha API with Supabase-backed identity and tenant authorization.",
)

# Browser origins are explicit and configurable. The default includes the canonical
# production web/admin origins plus local development. Railway should set
# ALLPHA_CORS_ORIGINS explicitly to the same exact origin allowlist.
cors_origins = [
    origin.strip()
    for origin in os.getenv(
        "ALLPHA_CORS_ORIGINS",
        "https://allpha.web.id,https://adm.allpha.web.id,http://localhost:3000,http://localhost:3001,http://localhost:19006,http://localhost:8081",
    ).split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "X-Request-ID"],
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


@app.exception_handler(HTTPException)
async def http_error(request: Request, exc: HTTPException) -> JSONResponse:
    """Return a stable, non-sensitive error envelope for expected API failures."""
    request_id = getattr(request.state, "request_id", "unknown")
    detail = exc.detail if isinstance(exc.detail, dict) else {}
    code = detail.get("code") if isinstance(detail.get("code"), str) else "REQUEST_FAILED"
    message = detail.get("message") if isinstance(detail.get("message"), str) else "Permintaan tidak dapat diproses."
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": code, "message": message, "request_id": request_id}},
        headers={"X-Request-ID": request_id, **(exc.headers or {})},
    )


@app.exception_handler(RequestValidationError)
async def request_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Expose safe field/type hints without echoing submitted values or internals."""
    request_id = getattr(request.state, "request_id", "unknown")
    fields = []
    for item in exc.errors():
        location = [str(part) for part in item.get("loc", ()) if part not in ("body", "query", "path", "header")]
        fields.append({"field": ".".join(location), "reason": str(item.get("type", "invalid"))})
    return JSONResponse(
        status_code=422,
        content={"error": {
            "code": "VALIDATION_ERROR",
            "message": "Permintaan tidak valid.",
            "request_id": request_id,
            "fields": fields,
        }},
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


class ConsentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    consent_type: Literal["terms_of_service", "privacy_policy", "product_updates"]
    policy_version: str = Field(min_length=1, max_length=40)
    granted: bool


class SocialEdgeCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    target_user_id: uuid.UUID
    edge_type: Literal["follow", "block", "mute"]


class InterestPreferenceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    interest_key: str = Field(min_length=1, max_length=80, pattern=r"^[a-z0-9][a-z0-9._-]{0,79}$")
    preference: Literal["interested", "not_interested"] = "interested"


class OrganizationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=2, max_length=120)
    slug: str = Field(min_length=2, max_length=63, pattern=r"^[a-z0-9][a-z0-9-]{1,62}$")



@app.get("/v1/skill-catalog", tags=["agent-identity"])
async def get_skill_catalog(
    q: str = "",
    category: str = "",
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    """Public metadata catalog for Human Agent Identity and operator discovery.

    Catalog entries are non-executable blueprints. Runtime permission is granted
    only by canonical Agent Runtime policy/capability lifecycle.
    """
    if len(q) > 120 or len(category) > 80:
        raise HTTPException(status_code=422, detail={"code": "SKILL_CATALOG_QUERY_INVALID", "message": "Filter katalog terlalu panjang."})
    if limit < 1 or limit > 100 or offset < 0 or offset > 100_000:
        raise HTTPException(status_code=422, detail={"code": "SKILL_CATALOG_PAGINATION_INVALID", "message": "Batas pagination katalog tidak valid."})
    return search_skill_catalog(q=q, category=category, limit=limit, offset=offset)


@app.get("/v1/credits/balance", tags=["credits"])
async def get_credit_balance(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    """Return the authenticated user's server-derived AI Credit balance projection."""
    try:
        store = SupabaseCreditLedgerStore.from_environment()
        balance = await store.get_balance(owner_user_id=str(user["id"]))
    except ValueError as exc:
        raise HTTPException(
            status_code=503,
            detail={"code": "CREDIT_LEDGER_NOT_CONFIGURED", "message": "Layanan AI Credits belum dikonfigurasi."},
        ) from exc
    except CreditLedgerPersistenceError as exc:
        raise HTTPException(
            status_code=503,
            detail={"code": "CREDIT_LEDGER_UNAVAILABLE", "message": "Saldo AI Credits belum dapat dibaca."},
        ) from exc
    return {"account_id": user["id"], **balance}

@app.get("/healthz", tags=["system"])
async def healthz() -> dict[str, str]:
    return {"status": "ok", "service": APP_NAME}


@app.get("/readyz", tags=["system"])
async def readyz() -> JSONResponse:
    """Fail closed unless the canonical Supabase Auth and PostgREST APIs respond."""
    supabase_url = os.getenv("SUPABASE_URL", "").rstrip("/")
    publishable_key = os.getenv("SUPABASE_PUBLISHABLE_KEY", "")
    if not supabase_url or not publishable_key:
        dependencies = {
            "database": "not_configured",
            "authentication": "not_configured",
            "object_storage": "not_configured",
            "ai_gateway": "not_configured",
        }
        return JSONResponse(
            status_code=503,
            content={
                "status": "not_ready",
                "service": APP_NAME,
                "version": APP_VERSION,
                "dependencies": dependencies,
            },
        )

    headers = {"apikey": publishable_key}
    auth_status = "unavailable"
    database_status = "unavailable"
    try:
        # Bound probe time so readiness checks cannot tie up workers indefinitely.
        async with httpx.AsyncClient(timeout=httpx.Timeout(3.0, connect=1.0)) as client:
            auth_response = await client.get(f"{supabase_url}/auth/v1/health", headers=headers)
            database_response = await client.get(f"{supabase_url}/rest/v1/", headers=headers)
        auth_status = "reachable" if auth_response.status_code == 200 else "unavailable"
        database_status = "reachable" if database_response.status_code == 200 else "unavailable"
    except httpx.HTTPError:
        # Do not leak upstream URLs, response bodies, or credentials from readiness.
        pass

    ready = auth_status == "reachable" and database_status == "reachable"
    dependencies = {
        "database": database_status,
        "authentication": auth_status,
        "object_storage": "not_configured",
        "ai_gateway": "not_configured",
    }
    return JSONResponse(
        status_code=200 if ready else 503,
        content={
            "status": "ready" if ready else "not_ready",
            "service": APP_NAME,
            "version": APP_VERSION,
            "dependencies": dependencies,
        },
    )


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
    if "tool_dependencies" in changes:
        try:
            validate_tool_dependencies(changes["tool_dependencies"])
        except UnknownToolError as exc:
            raise HTTPException(status_code=422, detail={"code": "UNKNOWN_TOOL_DEPENDENCY", "message": f"Tool tidak terdaftar atau tidak memiliki handler: {exc}"}) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail={"code": "INVALID_TOOL_DEPENDENCIES", "message": str(exc)}) from exc
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


@app.post("/v1/me/consents", status_code=201, tags=["identity"])
async def record_my_consent(payload: ConsentCreate, request: Request, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    # Consent history is append-only: user_id is always derived from the authenticated identity.
    rows = await user_db_request(
        "POST", "user_consents", request.state.supabase_access_token,
        body={
            "user_id": user["id"],
            "consent_type": payload.consent_type,
            "policy_version": payload.policy_version,
            "granted": payload.granted,
        },
        params={"select": "consent_type,policy_version,granted,recorded_at"},
        prefer="return=representation",
    )
    if not rows:
        raise HTTPException(status_code=409, detail={"code": "CONSENT_NOT_RECORDED", "message": "Persetujuan tidak dapat dicatat. Periksa apakah versi kebijakan sudah pernah dicatat."})
    return {"consent": rows[0]}


@app.post("/v1/me/deactivation-request", tags=["identity"])
async def request_account_deactivation(request: Request, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    rows = await user_db_request(
        "POST", "rpc/request_account_deactivation", request.state.supabase_access_token,
        body={},
    )
    if not rows:
        raise HTTPException(status_code=404, detail={"code": "PROFILE_NOT_FOUND", "message": "Profil tidak ditemukan."})
    return {"profile": rows[0], "message": "Permintaan penonaktifan akun tercatat. Akun belum dihapus."}


@app.get("/v1/me/social-graph", tags=["social"])
async def get_my_social_graph(request: Request, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    token = request.state.supabase_access_token
    outgoing = await user_db_request(
        "GET", "social_edges", token,
        params={"select": "id,target_user_id,edge_type,status,created_at",
                "actor_user_id": f"eq.{user['id']}", "order": "created_at.desc", "limit": "500"},
    )
    incoming_blocks = await user_db_request(
        "GET", "social_edges", token,
        params={"select": "id,actor_user_id,edge_type,created_at",
                "target_user_id": f"eq.{user['id']}", "edge_type": "eq.block",
                "order": "created_at.desc", "limit": "500"},
    )
    incoming_requests = await user_db_request(
        "GET", "social_edges", token,
        params={"select": "id,actor_user_id,edge_type,status,created_at",
                "target_user_id": f"eq.{user['id']}", "edge_type": "eq.follow",
                "status": "eq.requested", "order": "created_at.desc", "limit": "500"},
    )
    interests = await user_db_request(
        "GET", "user_interests", token,
        params={"select": "interest_key,preference,created_at,updated_at",
                "user_id": f"eq.{user['id']}", "order": "interest_key.asc", "limit": "500"},
    )
    return {"outgoing": outgoing, "incoming_requests": incoming_requests, "blocked_by": incoming_blocks, "interests": interests}


@app.post("/v1/me/social-edges", status_code=201, tags=["social"])
async def create_my_social_edge(payload: SocialEdgeCreate, request: Request, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    if str(payload.target_user_id) == str(user["id"]):
        raise HTTPException(status_code=422, detail={"code": "SOCIAL_EDGE_SELF_TARGET", "message": "Relasi sosial tidak dapat ditujukan ke akun sendiri."})
    rows = await user_db_request(
        "POST", "social_edges", request.state.supabase_access_token,
        body={"actor_user_id": user["id"], "target_user_id": str(payload.target_user_id), "edge_type": payload.edge_type},
        params={"select": "id,target_user_id,edge_type,status,created_at"},
        prefer="return=representation",
    )
    if not rows:
        raise HTTPException(status_code=409, detail={"code": "SOCIAL_EDGE_NOT_RECORDED", "message": "Relasi sosial tidak dapat disimpan."})
    return {"edge": rows[0]}


@app.post("/v1/me/follow-requests/{edge_id}/accept", tags=["social"])
async def accept_my_follow_request(edge_id: uuid.UUID, request: Request, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    rows = await user_db_request(
        "PATCH", "social_edges", request.state.supabase_access_token,
        params={"id": f"eq.{edge_id}", "target_user_id": f"eq.{user['id']}",
                "edge_type": "eq.follow", "status": "eq.requested",
                "select": "id,actor_user_id,target_user_id,edge_type,status,created_at"},
        body={"status": "active"}, prefer="return=representation",
    )
    if not rows:
        raise HTTPException(status_code=404, detail={"code": "FOLLOW_REQUEST_NOT_FOUND", "message": "Permintaan mengikuti tidak ditemukan atau sudah diproses."})
    return {"edge": rows[0]}


@app.delete("/v1/me/follow-requests/{edge_id}", tags=["social"])
async def reject_my_follow_request(edge_id: uuid.UUID, request: Request, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    rows = await user_db_request(
        "DELETE", "social_edges", request.state.supabase_access_token,
        params={"id": f"eq.{edge_id}", "target_user_id": f"eq.{user['id']}",
                "edge_type": "eq.follow", "status": "eq.requested", "select": "id"},
        prefer="return=representation",
    )
    if not rows:
        raise HTTPException(status_code=404, detail={"code": "FOLLOW_REQUEST_NOT_FOUND", "message": "Permintaan mengikuti tidak ditemukan atau sudah diproses."})
    return {"removed": rows[0]}


@app.delete("/v1/me/social-edges/{target_user_id}/{edge_type}", tags=["social"])
async def delete_my_social_edge(target_user_id: uuid.UUID, edge_type: Literal["follow", "block", "mute"], request: Request, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    if str(target_user_id) == str(user["id"]):
        raise HTTPException(status_code=422, detail={"code": "SOCIAL_EDGE_SELF_TARGET", "message": "Relasi sosial tidak valid."})
    rows = await user_db_request(
        "DELETE", "social_edges", request.state.supabase_access_token,
        params={"actor_user_id": f"eq.{user['id']}", "target_user_id": f"eq.{target_user_id}",
                "edge_type": f"eq.{edge_type}", "select": "id,target_user_id,edge_type"},
        prefer="return=representation",
    )
    if not rows:
        raise HTTPException(status_code=404, detail={"code": "SOCIAL_EDGE_NOT_FOUND", "message": "Relasi sosial tidak ditemukan."})
    return {"removed": rows[0]}


@app.get("/v1/me/interests", tags=["social"])
async def get_my_interests(request: Request, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    rows = await user_db_request(
        "GET", "user_interests", request.state.supabase_access_token,
        params={"select": "interest_key,preference,created_at,updated_at",
                "user_id": f"eq.{user['id']}", "order": "interest_key.asc", "limit": "500"},
    )
    return {"items": rows}


@app.put("/v1/me/interests", tags=["social"])
async def upsert_my_interest(payload: InterestPreferenceCreate, request: Request, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    rows = await user_db_request(
        "POST", "user_interests", request.state.supabase_access_token,
        body={"user_id": user["id"], "interest_key": payload.interest_key, "preference": payload.preference},
        params={"on_conflict": "user_id,interest_key", "select": "interest_key,preference,created_at,updated_at"},
        prefer="resolution=merge-duplicates,return=representation",
    )
    if not rows:
        raise HTTPException(status_code=409, detail={"code": "INTEREST_NOT_RECORDED", "message": "Preferensi minat tidak dapat disimpan."})
    return {"item": rows[0]}


@app.delete("/v1/me/interests/{interest_key}", tags=["social"])
async def delete_my_interest(interest_key: str, request: Request, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    if not re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,79}", interest_key):
        raise HTTPException(status_code=422, detail={"code": "INVALID_INTEREST_KEY", "message": "Kunci minat tidak valid."})
    rows = await user_db_request(
        "DELETE", "user_interests", request.state.supabase_access_token,
        params={"user_id": f"eq.{user['id']}", "interest_key": f"eq.{interest_key}",
                "select": "interest_key"},
        prefer="return=representation",
    )
    if not rows:
        raise HTTPException(status_code=404, detail={"code": "INTEREST_NOT_FOUND", "message": "Preferensi minat tidak ditemukan."})
    return {"removed": rows[0]}


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


# ENG-P04 — AI Agent identity is separate from the signed-in Human identity.
_AGENT_CONFIG_MAX_BYTES = 16 * 1024
_AGENT_CONFIG_MAX_DEPTH = 8
_AGENT_CONFIG_MAX_NODES = 256


def _validate_agent_config(value: dict[str, Any] | None) -> dict[str, Any] | None:
    """Bound user-authored JSON configuration before storing it in Postgres."""
    if value is None:
        return None

    nodes = 0

    def walk(item: Any, depth: int) -> None:
        nonlocal nodes
        nodes += 1
        if nodes > _AGENT_CONFIG_MAX_NODES:
            raise ValueError("Konfigurasi Agent terlalu kompleks (maksimum 256 nilai).")
        if depth > _AGENT_CONFIG_MAX_DEPTH:
            raise ValueError("Konfigurasi Agent terlalu dalam (maksimum 8 tingkat).")
        if isinstance(item, dict):
            for key, child in item.items():
                if not isinstance(key, str):
                    raise ValueError("Kunci konfigurasi Agent harus berupa teks.")
                walk(child, depth + 1)
        elif isinstance(item, list):
            for child in item:
                walk(child, depth + 1)
        elif item is None or isinstance(item, (str, bool, int, float)):
            return
        else:
            raise ValueError("Konfigurasi Agent harus berisi nilai JSON yang valid.")

    walk(value, 1)
    try:
        encoded = json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")
    except (TypeError, ValueError, UnicodeEncodeError) as exc:
        raise ValueError("Konfigurasi Agent harus berupa JSON yang valid.") from exc
    if len(encoded) > _AGENT_CONFIG_MAX_BYTES:
        raise ValueError("Konfigurasi Agent maksimal 16 KiB.")
    return value


class AgentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @field_validator("persona", "boundaries")
    @classmethod
    def validate_config_size(cls, value: dict[str, Any]) -> dict[str, Any]:
        return _validate_agent_config(value)
    handle: str = Field(min_length=3, max_length=30, pattern=r"^[a-z0-9_]+$")
    display_name: str = Field(min_length=2, max_length=80)
    description: str = Field(default="", max_length=1000)
    avatar_url: str | None = Field(default=None, max_length=2048)
    persona: dict[str, Any] = Field(default_factory=dict)
    disclosure: str = Field(default="", max_length=1000)
    boundaries: dict[str, Any] = Field(default_factory=dict)
    visibility: Literal["private", "public"] = "private"


class AgentUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @field_validator("persona", "boundaries")
    @classmethod
    def validate_config_size(cls, value: dict[str, Any] | None) -> dict[str, Any] | None:
        return _validate_agent_config(value)

    handle: str | None = Field(default=None, min_length=3, max_length=30, pattern=r"^[a-z0-9_]+$")
    display_name: str | None = Field(default=None, min_length=2, max_length=80)
    description: str | None = Field(default=None, max_length=1000)
    avatar_url: str | None = Field(default=None, max_length=2048)
    persona: dict[str, Any] | None = None
    disclosure: str | None = Field(default=None, max_length=1000)
    boundaries: dict[str, Any] | None = None
    visibility: Literal["private", "public"] | None = None
    status: Literal["draft", "active", "archived"] | None = None


_AGENT_FIELDS = "id,handle,display_name,description,avatar_url,persona,disclosure,boundaries,visibility,status,created_by,created_at,updated_at"


@app.get("/v1/agents", tags=["agents"])
async def list_my_agents(request: Request, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    rows = await user_db_request(
        "GET", "agent_ownerships", request.state.supabase_access_token,
        params={
            "select": f"agent_id,ownership_role,status,created_at,agent:ai_agents({_AGENT_FIELDS})",
            "owner_user_id": f"eq.{user['id']}", "ownership_role": "eq.owner",
            "status": "eq.active", "order": "created_at.desc", "limit": "100",
        },
    )
    items = []
    for row in rows or []:
        agent = row.get("agent")
        if agent:
            items.append({**agent, "ownership": {
                "owner_user_id": user["id"], "role": row["ownership_role"],
                "status": row["status"], "since": row["created_at"],
            }})
    return {"items": items}


@app.post("/v1/agents", status_code=201, tags=["agents"])
async def create_my_agent(payload: AgentCreate, request: Request, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    # RPC derives the owner from auth.uid() and creates Agent + ownership atomically.
    result = await user_db_request(
        "POST", "rpc/create_ai_agent", request.state.supabase_access_token,
        body={
            "p_handle": payload.handle, "p_display_name": payload.display_name,
            "p_description": payload.description, "p_avatar_url": payload.avatar_url,
            "p_persona": payload.persona, "p_visibility": payload.visibility,
            "p_disclosure": payload.disclosure, "p_boundaries": payload.boundaries,
        },
    )
    if not result:
        raise HTTPException(status_code=500, detail={"code": "AGENT_CREATE_FAILED", "message": "Agent tidak dapat dibuat."})
    agent = result[0] if isinstance(result, list) else result
    return {"agent": agent, "ownership": {"owner_user_id": user["id"], "role": "owner", "status": "active"}}


@app.patch("/v1/agents/{agent_id}", tags=["agents"])
async def update_my_agent(agent_id: uuid.UUID, payload: AgentUpdate, request: Request, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    changes = payload.model_dump(exclude_unset=True, exclude_none=True)
    if not changes:
        raise HTTPException(status_code=422, detail={"code": "EMPTY_UPDATE", "message": "Tidak ada perubahan Agent."})
    token = request.state.supabase_access_token
    ownership = await user_db_request(
        "GET", "agent_ownerships", token,
        params={"select": "agent_id,ownership_role,status", "agent_id": f"eq.{agent_id}",
                "owner_user_id": f"eq.{user['id']}", "ownership_role": "eq.owner", "status": "eq.active", "limit": "1"},
    )
    if not ownership:
        raise HTTPException(status_code=404, detail={"code": "AGENT_NOT_FOUND", "message": "Agent tidak ditemukan."})
    rows = await user_db_request(
        "PATCH", "ai_agents", token,
        params={"id": f"eq.{agent_id}", "select": _AGENT_FIELDS},
        body=changes, prefer="return=representation",
    )
    if not rows:
        raise HTTPException(status_code=404, detail={"code": "AGENT_NOT_FOUND", "message": "Agent tidak ditemukan."})
    return {"agent": rows[0], "ownership": {"owner_user_id": user["id"], "role": "owner", "status": "active"}}


@app.get("/v1/agent-passports/{handle}", tags=["agents"])
async def get_public_agent_passport(handle: str) -> dict[str, Any]:
    # Anonymous access is restricted by column grants + RLS to active public Passport fields.
    import re
    if not re.fullmatch(r"[a-z0-9_]{3,30}", handle):
        raise HTTPException(status_code=404, detail={"code": "AGENT_NOT_FOUND", "message": "Passport Agent tidak ditemukan."})
    rows = await user_db_request(
        "GET", "ai_agents", None,
        params={"select": "id,handle,display_name,description,avatar_url,disclosure,visibility,status,created_at",
                "handle": f"eq.{handle}", "visibility": "eq.public", "status": "eq.active", "limit": "1"},
    )
    if not rows:
        raise HTTPException(status_code=404, detail={"code": "AGENT_NOT_FOUND", "message": "Passport Agent tidak ditemukan."})
    passport = rows[0]
    # Anonymous projection deliberately excludes instructions, schemas, tool dependencies,
    # permission scopes, budgets, tests, persona, boundaries, and ownership.
    skills = await user_db_request(
        "GET", "agent_skills", None,
        params={"select": "id,slug,name,description,category,version,status,publication_terms,created_at,updated_at",
                "agent_id": f"eq.{passport['id']}", "status": "eq.published",
                "order": "version.desc", "limit": "50"},
    )
    capabilities = await user_db_request(
        "GET", "agent_capabilities", None,
        params={"select": "id,capability_key,description,risk_level,status,created_at,updated_at",
                "agent_id": f"eq.{passport['id']}", "status": "eq.approved",
                "order": "created_at.desc", "limit": "50"},
    )
    return {"passport": passport, "skills": skills or [], "capabilities": capabilities or []}


@app.get("/v1/agents/{agent_id}", tags=["agents"])
async def get_my_agent(agent_id: uuid.UUID, request: Request, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    token = request.state.supabase_access_token
    ownership = await user_db_request(
        "GET", "agent_ownerships", token,
        params={"select": "agent_id,ownership_role,status,created_at", "agent_id": f"eq.{agent_id}",
                "owner_user_id": f"eq.{user['id']}", "ownership_role": "eq.owner", "status": "eq.active", "limit": "1"},
    )
    if not ownership:
        raise HTTPException(status_code=404, detail={"code": "AGENT_NOT_FOUND", "message": "Agent tidak ditemukan."})
    rows = await user_db_request(
        "GET", "ai_agents", token,
        params={"select": _AGENT_FIELDS, "id": f"eq.{agent_id}", "limit": "1"},
    )
    if not rows:
        raise HTTPException(status_code=404, detail={"code": "AGENT_NOT_FOUND", "message": "Agent tidak ditemukan."})
    owner = ownership[0]
    return {"agent": rows[0], "ownership": {"owner_user_id": user["id"], "role": owner["ownership_role"], "status": owner["status"], "since": owner["created_at"]}}


# ENG-P06 — owner-managed reusable Skills and declared capability requests.
_SKILL_FIELDS = "id,agent_id,created_by,slug,name,description,category,inputs_schema,outputs_schema,instructions,constraints,tool_dependencies,required_permission_scopes,model_requirements,budget_limits,tests,evaluation_rubric,provenance,version,changelog,publication_terms,status,created_at,updated_at"
_CAPABILITY_FIELDS = "id,agent_id,created_by,capability_key,description,required_permission_scopes,risk_level,status,created_at,updated_at"


class AgentSkillCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    slug: str = Field(min_length=3, max_length=60, pattern=r"^[a-z0-9][a-z0-9_-]+$")
    name: str = Field(min_length=2, max_length=100)
    description: str = Field(default="", max_length=2000)
    category: str = Field(default="general", min_length=2, max_length=60)
    inputs_schema: dict[str, Any] = Field(default_factory=lambda: {"type": "object"})
    outputs_schema: dict[str, Any] = Field(default_factory=lambda: {"type": "object"})
    instructions: str = Field(default="", max_length=12000)
    constraints: dict[str, Any] = Field(default_factory=dict)
    tool_dependencies: list[str] = Field(default_factory=list, max_length=30)
    required_permission_scopes: list[str] = Field(default_factory=list, max_length=30)
    model_requirements: dict[str, Any] = Field(default_factory=dict)
    budget_limits: dict[str, Any] = Field(default_factory=lambda: {"max_runtime_seconds": 30, "max_tool_calls": 5})
    tests: list[dict[str, Any]] = Field(default_factory=list, max_length=50)
    evaluation_rubric: dict[str, Any] = Field(default_factory=dict)
    provenance: dict[str, Any] = Field(default_factory=dict)
    changelog: str = Field(default="", max_length=2000)
    publication_terms: dict[str, Any] = Field(default_factory=dict)

    @field_validator("inputs_schema", "outputs_schema", "constraints", "model_requirements", "budget_limits", "evaluation_rubric", "provenance", "publication_terms")
    @classmethod
    def validate_skill_objects(cls, value: dict[str, Any]) -> dict[str, Any]:
        return _validate_agent_config(value) or {}

    @field_validator("budget_limits")
    @classmethod
    def validate_skill_budget_limits(cls, value: dict[str, Any]) -> dict[str, Any]:
        _validate_agent_config(value)
        runtime = value.get("max_runtime_seconds", 30)
        calls = value.get("max_tool_calls", 5)
        if not isinstance(runtime, int) or isinstance(runtime, bool) or not 1 <= runtime <= 3600:
            raise ValueError("max_runtime_seconds must be an integer from 1 to 3600")
        if not isinstance(calls, int) or isinstance(calls, bool) or not 0 <= calls <= 100:
            raise ValueError("max_tool_calls must be an integer from 0 to 100")
        return value

    @field_validator("tests")
    @classmethod
    def validate_skill_tests(cls, value: list[dict[str, Any]]) -> list[dict[str, Any]]:
        for item in value:
            _validate_agent_config(item)
        return value


class AgentSkillUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, min_length=2, max_length=100)
    description: str | None = Field(default=None, max_length=2000)
    category: str | None = Field(default=None, min_length=2, max_length=60)
    inputs_schema: dict[str, Any] | None = None
    outputs_schema: dict[str, Any] | None = None
    instructions: str | None = Field(default=None, max_length=12000)
    constraints: dict[str, Any] | None = None
    tool_dependencies: list[str] | None = Field(default=None, max_length=30)
    required_permission_scopes: list[str] | None = Field(default=None, max_length=30)
    model_requirements: dict[str, Any] | None = None
    budget_limits: dict[str, Any] | None = None
    tests: list[dict[str, Any]] | None = Field(default=None, max_length=50)
    evaluation_rubric: dict[str, Any] | None = None
    provenance: dict[str, Any] | None = None
    changelog: str | None = Field(default=None, max_length=2000)
    publication_terms: dict[str, Any] | None = None
    status: Literal["draft", "published", "archived"] | None = None

    @field_validator("inputs_schema", "outputs_schema", "constraints", "model_requirements", "budget_limits", "evaluation_rubric", "provenance", "publication_terms")
    @classmethod
    def validate_optional_skill_objects(cls, value: dict[str, Any] | None) -> dict[str, Any] | None:
        return _validate_agent_config(value) if value is not None else None

    @field_validator("budget_limits")
    @classmethod
    def validate_optional_skill_budget_limits(cls, value: dict[str, Any] | None) -> dict[str, Any] | None:
        if value is None:
            return None
        _validate_agent_config(value)
        runtime = value.get("max_runtime_seconds", 30)
        calls = value.get("max_tool_calls", 5)
        if not isinstance(runtime, int) or isinstance(runtime, bool) or not 1 <= runtime <= 3600:
            raise ValueError("max_runtime_seconds must be an integer from 1 to 3600")
        if not isinstance(calls, int) or isinstance(calls, bool) or not 0 <= calls <= 100:
            raise ValueError("max_tool_calls must be an integer from 0 to 100")
        return value

    @field_validator("tests")
    @classmethod
    def validate_optional_skill_tests(cls, value: list[dict[str, Any]] | None) -> list[dict[str, Any]] | None:
        if value is not None:
            for item in value:
                _validate_agent_config(item)
        return value


class AgentToolExecutionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tool_key: str = Field(min_length=3, max_length=100, pattern=r"^[a-z][a-z0-9_.:-]+$")
    inputs: dict[str, Any] = Field(default_factory=dict)

    @field_validator("inputs")
    @classmethod
    def validate_tool_input_size(cls, value: dict[str, Any]) -> dict[str, Any]:
        return _validate_agent_config(value)


class AgentCapabilityRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    capability_key: str = Field(min_length=3, max_length=100, pattern=r"^[a-z][a-z0-9_.:-]+$")
    description: str = Field(default="", max_length=1000)
    required_permission_scopes: list[str] = Field(default_factory=list, max_length=30)
    risk_level: Literal["low", "medium", "high", "critical"] = "low"


async def _require_agent_owner(agent_id: uuid.UUID, request: Request, user: dict[str, Any]) -> str:
    token = request.state.supabase_access_token
    ownership = await user_db_request(
        "GET", "agent_ownerships", token,
        params={"select": "agent_id", "agent_id": f"eq.{agent_id}",
                "owner_user_id": f"eq.{user['id']}", "ownership_role": "eq.owner",
                "status": "eq.active", "limit": "1"},
    )
    if not ownership:
        raise HTTPException(status_code=404, detail={"code": "AGENT_NOT_FOUND", "message": "Agent tidak ditemukan."})
    return token


@app.get("/v1/tools", tags=["agent-tools"])
async def get_tool_registry(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    """List tools with concrete handlers; listing them does not grant permission."""
    return {"items": list_tools(), "runtime_mode": "owner_preview_only", "agent_autonomy_enabled": False}


@app.get("/v1/agents/{agent_id}/skills", tags=["agent-studio"])
async def list_agent_skills(agent_id: uuid.UUID, request: Request, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    token = await _require_agent_owner(agent_id, request, user)
    rows = await user_db_request(
        "GET", "agent_skills", token,
        params={"select": _SKILL_FIELDS, "agent_id": f"eq.{agent_id}",
                "order": "updated_at.desc", "limit": "100"},
    )
    return {"items": rows or []}


@app.post("/v1/agents/{agent_id}/skills", status_code=201, tags=["agent-studio"])
async def create_agent_skill(agent_id: uuid.UUID, payload: AgentSkillCreate, request: Request, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    token = await _require_agent_owner(agent_id, request, user)
    try:
        validate_tool_dependencies(payload.tool_dependencies)
    except UnknownToolError as exc:
        raise HTTPException(status_code=422, detail={"code": "UNKNOWN_TOOL_DEPENDENCY", "message": f"Tool tidak terdaftar atau tidak memiliki handler: {exc}"}) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"code": "INVALID_TOOL_DEPENDENCIES", "message": str(exc)}) from exc
    body = payload.model_dump()
    body.update({"agent_id": str(agent_id), "created_by": user["id"], "status": "draft", "version": 1})
    rows = await user_db_request("POST", "agent_skills", token, params={"select": _SKILL_FIELDS},
                                 body=body, prefer="return=representation")
    if not rows:
        raise HTTPException(status_code=500, detail={"code": "SKILL_CREATE_FAILED", "message": "Skill tidak dapat dibuat."})
    return {"skill": rows[0]}


@app.patch("/v1/agents/{agent_id}/skills/{skill_id}", tags=["agent-studio"])
async def update_agent_skill(agent_id: uuid.UUID, skill_id: uuid.UUID, payload: AgentSkillUpdate, request: Request, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    token = await _require_agent_owner(agent_id, request, user)
    changes = payload.model_dump(exclude_unset=True, exclude_none=True)
    if not changes:
        raise HTTPException(status_code=422, detail={"code": "EMPTY_UPDATE", "message": "Tidak ada perubahan Skill."})
    current = await user_db_request(
        "GET", "agent_skills", token,
        params={"select": _SKILL_FIELDS, "id": f"eq.{skill_id}", "agent_id": f"eq.{agent_id}", "limit": "1"},
    )
    if not current:
        raise HTTPException(status_code=404, detail={"code": "SKILL_NOT_FOUND", "message": "Skill tidak ditemukan."})
    changes["version"] = int(current[0].get("version") or 1) + 1
    rows = await user_db_request(
        "PATCH", "agent_skills", token,
        params={"id": f"eq.{skill_id}", "agent_id": f"eq.{agent_id}", "select": _SKILL_FIELDS},
        body=changes, prefer="return=representation",
    )
    if not rows:
        raise HTTPException(status_code=404, detail={"code": "SKILL_NOT_FOUND", "message": "Skill tidak ditemukan."})
    return {"skill": rows[0]}


@app.get("/v1/agents/{agent_id}/skills/{skill_id}/versions", tags=["agent-studio"])
async def list_agent_skill_versions(
    agent_id: uuid.UUID,
    skill_id: uuid.UUID,
    request: Request,
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    token = await _require_agent_owner(agent_id, request, user)
    skill = await user_db_request(
        "GET", "agent_skills", token,
        params={"select": "id", "id": f"eq.{skill_id}", "agent_id": f"eq.{agent_id}", "limit": "1"},
    )
    if not skill:
        raise HTTPException(status_code=404, detail={"code": "SKILL_NOT_FOUND", "message": "Skill tidak ditemukan."})
    versions = await user_db_request(
        "GET", "agent_skill_versions", token,
        params={"select": "id,skill_id,agent_id,version,created_by,snapshot,created_at",
                "skill_id": f"eq.{skill_id}", "agent_id": f"eq.{agent_id}",
                "order": "version.desc", "limit": "50"},
    )
    return {"items": versions or []}


@app.post("/v1/agents/{agent_id}/skills/{skill_id}/execute-tool", tags=["agent-tools"])
async def execute_skill_tool(
    agent_id: uuid.UUID,
    skill_id: uuid.UUID,
    payload: AgentToolExecutionRequest,
    request: Request,
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    """Run one registered low-risk handler as an owner preview, not autonomous Agent runtime."""
    token = await _require_agent_owner(agent_id, request, user)
    rows = await user_db_request(
        "GET", "agent_skills", token,
        params={"select": "id,tool_dependencies,budget_limits,status", "id": f"eq.{skill_id}", "agent_id": f"eq.{agent_id}", "limit": "1"},
    )
    if not rows:
        raise HTTPException(status_code=404, detail={"code": "SKILL_NOT_FOUND", "message": "Skill tidak ditemukan."})
    skill = rows[0]
    try:
        validate_tool_dependencies(skill.get("tool_dependencies") or [])
        registered = {item["key"]: item for item in list_tools()}
        tool = registered.get(payload.tool_key)
        if tool is None:
            raise UnknownToolError(payload.tool_key)
        if payload.tool_key not in (skill.get("tool_dependencies") or []):
            raise HTTPException(status_code=403, detail={"code": "TOOL_NOT_DECLARED", "message": "Tool harus tercantum pada dependensi Skill."})
        budget = skill.get("budget_limits") or {}
        if int(budget.get("max_tool_calls", 5)) < 1:
            raise HTTPException(status_code=422, detail={"code": "TOOL_BUDGET_EXHAUSTED", "message": "Budget Skill tidak mengizinkan pemanggilan tool."})
        result = execute_tool(payload.tool_key, payload.inputs)
    except UnknownToolError as exc:
        raise HTTPException(status_code=422, detail={"code": "UNKNOWN_TOOL_DEPENDENCY", "message": f"Tool tidak terdaftar atau tidak memiliki handler: {exc}"}) from exc
    except ToolInputError as exc:
        raise HTTPException(status_code=422, detail={"code": "INVALID_TOOL_INPUT", "message": str(exc)}) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"code": "INVALID_TOOL_DEPENDENCIES", "message": str(exc)}) from exc
    return {"tool_key": payload.tool_key, "tool_version": tool["version"], "result": result, "execution_mode": "owner_preview", "agent_runtime_authorized": False}


@app.get("/v1/agents/{agent_id}/capabilities", tags=["agent-studio"])
async def list_agent_capabilities(agent_id: uuid.UUID, request: Request, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    token = await _require_agent_owner(agent_id, request, user)
    rows = await user_db_request(
        "GET", "agent_capabilities", token,
        params={"select": _CAPABILITY_FIELDS, "agent_id": f"eq.{agent_id}",
                "order": "created_at.desc", "limit": "100"},
    )
    return {"items": rows or []}


@app.post("/v1/agents/{agent_id}/capabilities", status_code=201, tags=["agent-studio"])
async def request_agent_capability(agent_id: uuid.UUID, payload: AgentCapabilityRequest, request: Request, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    token = await _require_agent_owner(agent_id, request, user)
    body = payload.model_dump()
    body.update({"agent_id": str(agent_id), "created_by": user["id"], "status": "requested"})
    rows = await user_db_request("POST", "agent_capabilities", token, params={"select": _CAPABILITY_FIELDS},
                                 body=body, prefer="return=representation")
    if not rows:
        raise HTTPException(status_code=500, detail={"code": "CAPABILITY_REQUEST_FAILED", "message": "Permintaan capability tidak dapat disimpan."})
    return {"capability": rows[0], "runtime_authorized": False}


# Dedicated platform operator API: every route enforces a live grant, exact scope, and durable audit.
app.include_router(operator_security_router)
app.include_router(knowledge_router)
app.include_router(knowledge_retrieval_router)
app.include_router(agent_runtime_router)
app.include_router(workflow_router)
app.include_router(skill_challenge_router)
app.include_router(official_bots_router)

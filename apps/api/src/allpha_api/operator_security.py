"""Fail-closed platform operator authorization and durable audit routes.

Human authentication is not operator authorization. Every route in this router
requires a live, owner-scoped grant and an exact permission scope.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator

from allpha_api.auth import current_user, user_db_request

router = APIRouter(prefix="/v1/admin", tags=["platform-operations"])
OperatorScope = Literal[
    "platform:operations.read",
    "platform:security.audit.read",
    "platform:capabilities.review",
    "platform:operators.manage",
]


class OperatorGrantCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_id: UUID
    scopes: list[OperatorScope] = Field(min_length=1, max_length=4)
    reason: str = Field(min_length=8, max_length=500)
    expires_at: datetime | None = None

    @field_validator("scopes")
    @classmethod
    def unique_scopes(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("Scope tidak boleh duplikat.")
        return value

    @field_validator("expires_at")
    @classmethod
    def expiry_must_be_future(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return value
        if value.tzinfo is None:
            raise ValueError("expires_at harus menyertakan zona waktu.")
        if value <= datetime.now(timezone.utc):
            raise ValueError("expires_at harus berada di masa depan.")
        return value


class OperatorGrantRevoke(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=8, max_length=500)


_AUDIT_TIMEOUT = httpx.Timeout(5.0, connect=2.0)


def _audit_config() -> tuple[str, dict[str, str]]:
    base_url = os.getenv("SUPABASE_URL", "").rstrip("/")
    service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    secret_key = os.getenv("SUPABASE_SECRET_KEY", "")
    if not base_url or not (service_role_key or secret_key):
        raise HTTPException(
            status_code=503,
            detail={
                "code": "OPERATOR_AUDIT_UNAVAILABLE",
                "message": "Audit istimewa belum dikonfigurasi; operasi ditolak.",
            },
        )
    key = service_role_key or secret_key
    headers = {"apikey": key, "Content-Type": "application/json"}
    # Legacy service-role keys are JWTs. New sb_secret keys are API keys and
    # must not be copied into Authorization as though they were JWTs.
    if service_role_key:
        headers["Authorization"] = f"Bearer {service_role_key}"
    return base_url, headers


async def write_operator_audit(
    request: Request,
    *,
    actor_user_id: str,
    action: str,
    outcome: str,
    resource_type: str = "operator_access",
    resource_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Persist an audit event through a server-only key; fail closed on errors."""
    base_url, headers = _audit_config()
    safe_metadata = metadata or {}
    # Only structured, non-secret policy facts belong in metadata.
    body = {
        "actor_user_id": actor_user_id,
        "action": action,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "outcome": outcome,
        "request_id": getattr(request.state, "request_id", "unknown"),
        "metadata": safe_metadata,
    }
    try:
        async with httpx.AsyncClient(timeout=_AUDIT_TIMEOUT) as client:
            response = await client.post(
                f"{base_url}/rest/v1/platform_operator_audit_events",
                headers={**headers, "Prefer": "return=minimal"},
                json=body,
            )
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=503,
            detail={"code": "OPERATOR_AUDIT_UNAVAILABLE", "message": "Audit istimewa tidak dapat disimpan; operasi ditolak."},
        ) from exc
    if response.status_code not in (200, 201, 204):
        raise HTTPException(
            status_code=503,
            detail={"code": "OPERATOR_AUDIT_UNAVAILABLE", "message": "Audit istimewa tidak dapat disimpan; operasi ditolak."},
        )


async def read_operator_audit(*, limit: int = 100) -> list[dict[str, Any]]:
    base_url, headers = _audit_config()
    try:
        async with httpx.AsyncClient(timeout=_AUDIT_TIMEOUT) as client:
            response = await client.get(
                f"{base_url}/rest/v1/platform_operator_audit_events",
                headers=headers,
                params={
                    "select": "id,actor_user_id,action,resource_type,resource_id,outcome,request_id,metadata,created_at",
                    "order": "created_at.desc",
                    "limit": str(max(1, min(limit, 100))),
                },
            )
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=503,
            detail={"code": "OPERATOR_AUDIT_UNAVAILABLE", "message": "Audit istimewa tidak dapat dibaca."},
        ) from exc
    if response.status_code != 200:
        raise HTTPException(
            status_code=503,
            detail={"code": "OPERATOR_AUDIT_UNAVAILABLE", "message": "Audit istimewa tidak dapat dibaca."},
        )
    payload = response.json()
    if not isinstance(payload, list):
        raise HTTPException(
            status_code=503,
            detail={"code": "OPERATOR_AUDIT_UNAVAILABLE", "message": "Format audit istimewa tidak valid."},
        )
    return payload


async def privileged_rest_request(
    method: str,
    table: str,
    *,
    params: dict[str, str] | None = None,
    body: dict[str, Any] | None = None,
    prefer: str | None = None,
) -> Any:
    """Call PostgREST using a server-only key; never expose it to clients."""
    base_url, headers = _audit_config()
    if prefer:
        headers = {**headers, "Prefer": prefer}
    try:
        async with httpx.AsyncClient(timeout=_AUDIT_TIMEOUT) as client:
            response = await client.request(
                method,
                f"{base_url}/rest/v1/{table}",
                headers=headers,
                params=params,
                json=body,
            )
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=503,
            detail={"code": "OPERATOR_STORE_UNAVAILABLE", "message": "Penyimpanan governance tidak tersedia."},
        ) from exc
    if response.status_code >= 400:
        code = "OPERATOR_GRANT_CONFLICT" if response.status_code == 409 else "OPERATOR_STORE_UNAVAILABLE"
        status = 409 if response.status_code == 409 else 503
        raise HTTPException(
            status_code=status,
            detail={"code": code, "message": "Perubahan grant operator tidak dapat diproses."},
        )
    if not response.content:
        return None
    try:
        return response.json()
    except ValueError as exc:
        raise HTTPException(
            status_code=503,
            detail={"code": "OPERATOR_STORE_UNAVAILABLE", "message": "Respons penyimpanan governance tidak valid."},
        ) from exc


def require_operator_scope(required_scope: str):
    """Return a dependency enforcing a live grant and exact scope."""
    async def dependency(
        request: Request,
        user: dict[str, Any] = Depends(current_user),
    ) -> dict[str, Any]:
        actor_id = str(user["id"])
        token = getattr(request.state, "supabase_access_token", None)
        if not token:
            raise HTTPException(status_code=401, detail={"code": "AUTH_REQUIRED", "message": "Bearer token diperlukan."})
        try:
            grants = await user_db_request(
                "GET",
                "platform_operator_grants",
                token,
                params={
                    "select": "id,user_id,scopes,status,expires_at",
                    "user_id": f"eq.{actor_id}",
                    "status": "eq.active",
                    "order": "created_at.desc",
                    "limit": "20",
                },
            )
        except HTTPException:
            # Do not continue if the grant source is unavailable or its access
            # policy denies the query; unknown authority is never permission.
            await write_operator_audit(
                request,
                actor_user_id=actor_id,
                action="operator.scope.check",
                outcome="error",
                metadata={"required_scope": required_scope, "reason": "grant_lookup_unavailable"},
            )
            raise

        now = datetime.now(timezone.utc)
        scopes: set[str] = set()
        for grant in grants or []:
            expires_at = grant.get("expires_at")
            if expires_at:
                try:
                    expiry = datetime.fromisoformat(str(expires_at).replace("Z", "+00:00"))
                except ValueError:
                    continue
                if expiry.tzinfo is None:
                    expiry = expiry.replace(tzinfo=timezone.utc)
                if expiry <= now:
                    continue
            declared = grant.get("scopes")
            if isinstance(declared, list):
                scopes.update(scope for scope in declared if isinstance(scope, str))

        if required_scope not in scopes:
            await write_operator_audit(
                request,
                actor_user_id=actor_id,
                action="operator.scope.check",
                outcome="denied",
                metadata={"required_scope": required_scope},
            )
            raise HTTPException(
                status_code=403,
                detail={"code": "OPERATOR_SCOPE_REQUIRED", "message": "Hak operator untuk tindakan ini tidak tersedia."},
            )

        # Audit the authorization decision before the route executes. If the
        # audit sink is unavailable, the protected operation does not proceed.
        await write_operator_audit(
            request,
            actor_user_id=actor_id,
            action="operator.scope.check",
            outcome="allowed",
            metadata={"required_scope": required_scope},
        )
        return {"id": actor_id, "email": user.get("email"), "scopes": sorted(scopes)}
    return dependency


@router.get("/operator/access", name="get_operator_access")
async def get_operator_access(
    operator: dict[str, Any] = Depends(require_operator_scope("platform:operations.read")),
) -> dict[str, Any]:
    return {"operator": operator, "authorization": "verified"}


@router.get("/operator/audit", name="get_operator_audit")
async def get_operator_audit(
    limit: int = 100,
    operator: dict[str, Any] = Depends(require_operator_scope("platform:security.audit.read")),
) -> dict[str, Any]:
    events = await read_operator_audit(limit=limit)
    return {"items": events, "limit": min(max(1, limit), 100)}


@router.get("/operator/grants", name="list_operator_grants")
async def list_operator_grants(
    limit: int = 100,
    operator: dict[str, Any] = Depends(require_operator_scope("platform:operators.manage")),
) -> dict[str, Any]:
    rows = await privileged_rest_request(
        "GET",
        "platform_operator_grants",
        params={
            "select": "id,user_id,scopes,status,reason,granted_by,expires_at,created_at,revoked_at,revoked_by,revocation_reason",
            "order": "created_at.desc",
            "limit": str(min(max(1, limit), 100)),
        },
    )
    return {"items": rows or [], "limit": min(max(1, limit), 100)}


@router.post("/operator/grants", status_code=201, name="create_operator_grant")
async def create_operator_grant(
    payload: OperatorGrantCreate,
    request: Request,
    operator: dict[str, Any] = Depends(require_operator_scope("platform:operators.manage")),
) -> dict[str, Any]:
    # Operators may delegate only scopes they themselves hold and may never
    # elevate themselves through a second grant. Initial bootstrap is out-of-band.
    if str(payload.user_id) == operator["id"] or not set(payload.scopes).issubset(set(operator["scopes"])):
        raise HTTPException(
            status_code=403,
            detail={"code": "OPERATOR_SCOPE_ESCALATION_DENIED", "message": "Grant tidak boleh menaikkan hak atau memberikan grant kepada diri sendiri."},
        )
    rows = await privileged_rest_request(
        "POST",
        "platform_operator_grants",
        params={"select": "id,user_id,scopes,status,reason,granted_by,expires_at,created_at"},
        body={
            "user_id": str(payload.user_id),
            "scopes": payload.scopes,
            "status": "active",
            "reason": payload.reason,
            "granted_by": operator["id"],
            "expires_at": payload.expires_at.isoformat() if payload.expires_at else None,
        },
        prefer="return=representation",
    )
    if not rows:
        raise HTTPException(
            status_code=503,
            detail={"code": "OPERATOR_GRANT_CREATE_FAILED", "message": "Grant operator tidak dapat dibuat."},
        )
    return {"grant": rows[0]}


@router.post("/operator/grants/{grant_id}/revoke", name="revoke_operator_grant")
async def revoke_operator_grant(
    grant_id: UUID,
    payload: OperatorGrantRevoke,
    request: Request,
    operator: dict[str, Any] = Depends(require_operator_scope("platform:operators.manage")),
) -> dict[str, Any]:
    rows = await privileged_rest_request(
        "PATCH",
        "platform_operator_grants",
        params={
            "id": f"eq.{grant_id}",
            "status": "eq.active",
            "select": "id,user_id,scopes,status,reason,granted_by,expires_at,created_at,revoked_at,revoked_by,revocation_reason",
        },
        body={
            "status": "revoked",
            "revoked_at": datetime.now(timezone.utc).isoformat(),
            "revoked_by": operator["id"],
            "revocation_reason": payload.reason,
        },
        prefer="return=representation",
    )
    if not rows:
        raise HTTPException(
            status_code=404,
            detail={"code": "OPERATOR_GRANT_NOT_FOUND", "message": "Grant aktif tidak ditemukan."},
        )
    return {"grant": rows[0], "revoked": True}

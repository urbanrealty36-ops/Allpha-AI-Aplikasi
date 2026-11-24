"""Fail-closed platform operator authorization and durable audit routes.

Human authentication is not operator authorization. Every route in this router
requires a live, owner-scoped grant and an exact permission scope.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator

from allpha_api.auth import current_user, user_db_request

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/admin", tags=["platform-operations"])
OperatorScope = Literal[
    "platform:operations.read",
    "platform:security.audit.read",
    "platform:capabilities.review",
    "platform:capabilities.review.high_risk",
    "platform:operators.manage",
    "platform:content.moderate",
    "platform:billing.manage",
    "platform:account_lifecycle.manage",
]


class OperatorGrantCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_id: UUID
    scopes: list[OperatorScope] = Field(min_length=1, max_length=8)
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


class RuntimePolicyCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    agent_id: UUID
    policy_version: str = Field(min_length=1, max_length=120, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,119}$")
    approved_tool_keys: list[str] = Field(min_length=1, max_length=50)
    required_permission_scopes: list[str] = Field(default_factory=list, max_length=50)
    risk_constraints: dict[str, Any] = Field(default_factory=dict)


class RuntimePolicyApproval(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=8, max_length=500)


class CapabilityReviewPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Literal["approved", "denied"]
    reason: str = Field(min_length=8, max_length=500)
    # Trusted operator supplies a version reference; this is not the policy document.
    policy_version: str | None = Field(
        default=None, min_length=1, max_length=80,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,79}$",
    )


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
        # Log only provider status and a bounded, allow-listed error code.
        # Never log request headers, credentials, or audit metadata.
        error_code = "unknown"
        try:
            error_payload = response.json()
            if isinstance(error_payload, dict):
                candidate = error_payload.get("code") or error_payload.get("error")
                if isinstance(candidate, str) and candidate and len(candidate) <= 80:
                    error_code = candidate
                details = error_payload.get("message") or error_payload.get("details")
                if isinstance(details, str) and details and len(details) <= 180:
                    logger.warning(
                        "operator_audit_postgrest_rejected status=%s code=%s detail=%s",
                        response.status_code,
                        error_code,
                        details.replace("\\n", " ")[:180],
                    )
                else:
                    logger.warning("operator_audit_postgrest_rejected status=%s code=%s", response.status_code, error_code)
            else:
                logger.warning("operator_audit_postgrest_rejected status=%s code=%s", response.status_code, error_code)
        except (ValueError, TypeError):
            logger.warning("operator_audit_postgrest_rejected status=%s code=%s", response.status_code, error_code)
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


def require_operator_scope(required_scope: str | None):
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

        if not scopes or (required_scope is not None and required_scope not in scopes):
            await write_operator_audit(
                request,
                actor_user_id=actor_id,
                action="operator.scope.check",
                outcome="denied",
                metadata={"required_scope": required_scope or "any_operator_scope"},
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
            metadata={"required_scope": required_scope or "any_operator_scope"},
        )
        return {"id": actor_id, "email": user.get("email"), "scopes": sorted(scopes)}
    return dependency


@router.get("/operator/access", name="get_operator_access")
async def get_operator_access(
    operator: dict[str, Any] = Depends(require_operator_scope(None)),
) -> dict[str, Any]:
    return {"operator": operator, "authorization": "verified"}


@router.get("/operator/agent-social/audit", name="get_agent_social_audit")
async def get_agent_social_audit(
    limit: int = 100,
    operator: dict[str, Any] = Depends(require_operator_scope("platform:security.audit.read")),
) -> dict[str, Any]:
    rows = await privileged_rest_request(
        "GET", "agent_social_audit_events",
        params={"select": "id,owner_user_id,agent_id,approval_id,actor_user_id,event_type,outcome,metadata,created_at",
                "order": "created_at.desc", "limit": str(min(max(1, limit), 100))},
    )
    return {"items": rows or [], "limit": min(max(1, limit), 100)}


@router.get("/operator/agent-ownership/audit", name="get_agent_ownership_audit")
async def get_agent_ownership_audit(
    limit: int = 100,
    operator: dict[str, Any] = Depends(require_operator_scope("platform:security.audit.read")),
) -> dict[str, Any]:
    bounded_limit = min(max(1, limit), 100)
    transfers, consents = await asyncio.gather(
        privileged_rest_request(
            "GET", "agent_ownership_transfer_events",
            params={"select": "id,request_id,agent_id,event_type,from_owner_subject_ref,to_owner_subject_ref,details,created_at",
                    "order": "created_at.desc", "limit": str(bounded_limit)},
        ),
        privileged_rest_request(
            "GET", "agent_owner_attribution_consent_events",
            params={"select": "id,agent_id,owner_subject_ref,event_type,consent_version,disclosure_snapshot,created_at",
                    "order": "created_at.desc", "limit": str(bounded_limit)},
        ),
    )
    return {"ownership_transfers": transfers or [], "passport_consents": consents or [], "limit": bounded_limit}


@router.get("/operator/agent-social/governance", name="get_agent_social_governance")
async def get_agent_social_governance(
    limit: int = 100,
    operator: dict[str, Any] = Depends(require_operator_scope("platform:security.audit.read")),
) -> dict[str, Any]:
    """Read-only, privacy-redacted Social governance projection across canonical domains."""
    bounded_limit = min(max(1, limit), 100)
    automation_active = os.getenv("ALLPHA_AGENT_SOCIAL_AUTOMATION_SCHEMA_ENABLED", "false").lower() == "true"
    dm_approval_active = os.getenv("ALLPHA_AGENT_SOCIAL_DM_APPROVAL_SCHEMA_ENABLED", "false").lower() == "true"
    dispatch_active = os.getenv("ALLPHA_AGENT_SOCIAL_ACTION_DISPATCH_ENABLED", "false").lower() == "true"
    policy_fields = (
        "id,owner_user_id,agent_id,allowed_actions,approval_mode,disclosure_text,is_enabled,version,updated_at,"
        "auto_reply_enabled,auto_reply_channels,blocked_topics,reply_tone,allowed_tool_scopes,"
        "max_replies_per_minute,daily_credit_budget,quiet_hours,escalation_rules,"
        "owner_approval_required,output_moderation_required,takeover_active,automation_version"
        if automation_active else
        "id,owner_user_id,agent_id,allowed_actions,approval_mode,disclosure_text,is_enabled,version,updated_at"
    )
    approval_fields = "id,owner_user_id,agent_id,action_type,status,content_id,target_content_id,target_comment_id,requested_at,decided_at,decided_by,execution_result"
    if dm_approval_active:
        approval_fields += ",target_conversation_id,target_message_id"
    if dispatch_active:
        approval_fields += ",dispatch_task_id"
    policies, approvals = await asyncio.gather(
        privileged_rest_request(
            "GET", "agent_social_presence_policies",
            params={"select": policy_fields, "order": "updated_at.desc", "limit": str(bounded_limit)},
        ),
        privileged_rest_request(
            "GET", "agent_social_action_approvals",
            params={"select": approval_fields, "order": "requested_at.desc", "limit": str(bounded_limit)},
        ),
    )
    result: dict[str, Any] = {
        "policies": policies or [], "approvals": approvals or [],
        "automation_schema_active": automation_active,
        "dm_approval_schema_active": dm_approval_active,
        "dispatch_schema_active": dispatch_active,
        "runtime_enabled": (
            automation_active
            and os.getenv("ALLPHA_AGENT_SOCIAL_AUTOMATION_WORKER_ENABLED", "false").lower() == "true"
            and os.getenv("ALLPHA_AGENT_RUNTIME_WORKER_ENABLED", "false").lower() == "true"
            and dispatch_active
        ),
        "control_events": [], "automation_grants": [], "automation_runs": [],
        "automation_events": [], "runtime_tasks": [], "credit_reservations": [],
        "effect_receipts": [], "effect_receipts_schema_active": False,
        "automation_budgets": [],
    }
    if not automation_active:
        return result

    control_events, grants, runs, events = await asyncio.gather(
        privileged_rest_request(
            "GET", "agent_social_control_events",
            params={"select": "id,owner_user_id,agent_id,policy_id,event_type,actor_user_id,metadata,created_at",
                    "order": "created_at.desc", "limit": str(bounded_limit)},
        ),
        privileged_rest_request(
            "GET", "agent_social_automation_grants",
            params={"select": "id,owner_user_id,agent_id,granted_scopes,policy_version,status,expires_at,granted_by,granted_at,revoked_at,revoke_reason",
                    "order": "granted_at.desc", "limit": str(bounded_limit)},
        ),
        privileged_rest_request(
            "GET", "agent_social_automation_runs",
            params={"select": "id,owner_user_id,agent_id,runtime_task_id,source_event_id,channel,status,created_at,updated_at",
                    "order": "created_at.desc", "limit": str(bounded_limit)},
        ),
        privileged_rest_request(
            "GET", "agent_social_automation_events",
            params={"select": "id,owner_user_id,agent_id,channel,source_table,source_record_id,status,attempt_count,max_attempts,available_at,runtime_task_id,reason_code,created_at,updated_at",
                    "order": "created_at.desc", "limit": str(bounded_limit)},
        ),
    )
    result.update({
        "control_events": control_events or [], "automation_grants": grants or [],
        "automation_runs": runs or [], "automation_events": events or [],
    })

    task_ids = list(dict.fromkeys(
        str(row["runtime_task_id"]) for row in (runs or []) if row.get("runtime_task_id")
    ))
    task_rows: list[dict[str, Any]] = []
    reservation_rows: list[dict[str, Any]] = []
    if task_ids:
        task_filter = "in.(" + ",".join(task_ids) + ")"
        task_rows, reservation_rows = await asyncio.gather(
            privileged_rest_request(
                "GET", "agent_runtime_tasks",
                params={"select": "id,owner_user_id,agent_id,state,trace_id,error_code,created_at,updated_at,completed_at,output_payload",
                        "id": task_filter, "limit": str(min(500, bounded_limit * 5))},
            ),
            privileged_rest_request(
                "GET", "credit_reservations",
                params={"select": "id,owner_user_id,task_id,capability_id,reserved_credits,settled_credits,state,policy_version,tariff_version,entitlement_version,created_at,updated_at",
                        "task_id": task_filter, "limit": str(min(500, bounded_limit * 5))},
            ),
        )
    result["runtime_tasks"] = [
        {
            "id": row.get("id"), "owner_user_id": row.get("owner_user_id"),
            "agent_id": row.get("agent_id"), "state": row.get("state"),
            "trace_id": row.get("trace_id"), "error_code": row.get("error_code"),
            "created_at": row.get("created_at"), "updated_at": row.get("updated_at"),
            "completed_at": row.get("completed_at"),
            "moderation": (row.get("output_payload") or {}).get("moderation")
                if isinstance(row.get("output_payload"), dict) else None,
            "context_snapshot_sha256": (row.get("output_payload") or {}).get("context_snapshot_sha256")
                if isinstance(row.get("output_payload"), dict) else None,
            "memory_context_sha256": (row.get("output_payload") or {}).get("memory_context_sha256")
                if isinstance(row.get("output_payload"), dict) else None,
        }
        for row in (task_rows or []) if isinstance(row, dict)
    ]
    result["credit_reservations"] = reservation_rows or []

    if dispatch_active:
        dispatch_ids = list(dict.fromkeys(
            str(row["dispatch_task_id"]) for row in (approvals or []) if row.get("dispatch_task_id")
        ))
        if dispatch_ids:
            try:
                receipts = await privileged_rest_request(
                    "GET", "agent_runtime_effect_receipts",
                    params={"select": "id,task_id,step_key,idempotency_key,status,owner_user_id,agent_id,approval_id,provider_key,action_key,external_reference,evidence_reference,started_at,completed_at,updated_at",
                            "task_id": "in.(" + ",".join(dispatch_ids) + ")",
                            "order": "started_at.desc", "limit": str(min(500, bounded_limit * 5))},
                )
                result["effect_receipts"] = receipts or []
                result["effect_receipts_schema_active"] = True
            except Exception:
                logger.exception("WP-06 governance effect receipt projection unavailable")

    utc_day_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    agent_for_task = {str(row["runtime_task_id"]): str(row["agent_id"])
                      for row in (runs or []) if row.get("runtime_task_id") and row.get("agent_id")}
    used_by_agent: dict[str, int] = {}
    for row in reservation_rows or []:
        agent_id = agent_for_task.get(str(row.get("task_id") or ""))
        if not agent_id or not row.get("created_at"):
            continue
        try:
            created = datetime.fromisoformat(str(row["created_at"]).replace("Z", "+00:00"))
        except ValueError:
            continue
        if created < utc_day_start or row.get("state") not in {"reserved", "pending_reconciliation", "settled"}:
            continue
        amount = int(row.get("settled_credits") or 0) if row.get("state") == "settled" else int(row.get("reserved_credits") or 0)
        used_by_agent[agent_id] = used_by_agent.get(agent_id, 0) + amount
    result["automation_budgets"] = [
        {
            "owner_user_id": policy.get("owner_user_id"), "agent_id": policy.get("agent_id"),
            "daily_budget": int(policy.get("daily_credit_budget") or 0),
            "daily_used_or_reserved": used_by_agent.get(str(policy.get("agent_id")), 0),
            "daily_remaining": max(0, int(policy.get("daily_credit_budget") or 0) - used_by_agent.get(str(policy.get("agent_id")), 0)),
            "takeover_active": bool(policy.get("takeover_active")),
        }
        for policy in (policies or []) if isinstance(policy, dict) and policy.get("auto_reply_enabled")
    ]
    return result

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


@router.post("/operator/runtime-policies", status_code=201, name="create_operator_runtime_policy")
async def create_operator_runtime_policy(
    payload: RuntimePolicyCreate,
    request: Request,
    operator: dict[str, Any] = Depends(require_operator_scope("platform:capabilities.review")),
) -> dict[str, Any]:
    if len(payload.approved_tool_keys) != len(set(payload.approved_tool_keys)) or len(payload.required_permission_scopes) != len(set(payload.required_permission_scopes)):
        raise HTTPException(status_code=422, detail={"code": "RUNTIME_POLICY_DUPLICATE_VALUES", "message": "Tool dan scope tidak boleh duplikat."})
    policy_document = {
        "policy_version": payload.policy_version,
        "approved_tool_keys": sorted(payload.approved_tool_keys),
        "required_permission_scopes": sorted(payload.required_permission_scopes),
        "risk_constraints": payload.risk_constraints,
    }
    try:
        encoded = json.dumps(policy_document, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, UnicodeEncodeError) as exc:
        raise HTTPException(status_code=422, detail={"code": "RUNTIME_POLICY_INVALID", "message": "Dokumen policy harus JSON valid."}) from exc
    await write_operator_audit(request, actor_user_id=operator["id"], action="agent.runtime_policy.create",
        outcome="attempted", resource_type="agent_runtime_policy",
        metadata={"agent_id": str(payload.agent_id), "policy_version": payload.policy_version})
    rows = await privileged_rest_request(
        "POST", "agent_runtime_policies", params={"select": "id,agent_id,policy_version,policy_digest,status,created_by,created_at"},
        body={
            "agent_id": str(payload.agent_id), "policy_version": payload.policy_version,
            "policy_document": policy_document, "policy_digest": hashlib.sha256(encoded).hexdigest(),
            "approved_tool_keys": sorted(payload.approved_tool_keys),
            "required_permission_scopes": sorted(payload.required_permission_scopes),
            "risk_constraints": payload.risk_constraints, "status": "draft", "created_by": operator["id"],
        }, prefer="return=representation",
    )
    if not rows:
        raise HTTPException(status_code=503, detail={"code": "RUNTIME_POLICY_PERSISTENCE_UNCONFIRMED", "message": "Pembuatan policy tidak terkonfirmasi."})
    return {"policy": rows[0], "runtime_authorized": False}


@router.post("/operator/runtime-policies/{policy_id}/approve", name="approve_operator_runtime_policy")
async def approve_operator_runtime_policy(
    policy_id: UUID,
    payload: RuntimePolicyApproval,
    request: Request,
    operator: dict[str, Any] = Depends(require_operator_scope("platform:capabilities.review.high_risk")),
) -> dict[str, Any]:
    current = await privileged_rest_request("GET", "agent_runtime_policies", params={
        "select": "id,agent_id,policy_version,status,policy_digest,approved_tool_keys,required_permission_scopes",
        "id": f"eq.{policy_id}", "limit": "1",
    })
    if not current or current[0].get("status") != "draft":
        raise HTTPException(status_code=409, detail={"code": "RUNTIME_POLICY_NOT_DRAFT", "message": "Hanya policy draft yang dapat disetujui."})
    await write_operator_audit(request, actor_user_id=operator["id"], action="agent.runtime_policy.approve",
        outcome="attempted", resource_type="agent_runtime_policy", resource_id=str(policy_id),
        metadata={"agent_id": current[0]["agent_id"], "policy_version": current[0]["policy_version"], "reason": payload.reason})
    timestamp = datetime.now(timezone.utc).isoformat()
    rows = await privileged_rest_request("PATCH", "agent_runtime_policies", params={
        "id": f"eq.{policy_id}", "status": "eq.draft",
        "select": "id,agent_id,policy_version,policy_digest,approved_tool_keys,required_permission_scopes,status,approved_by,approved_at",
    }, body={"status": "approved", "approved_by": operator["id"], "approved_at": timestamp},
       prefer="return=representation")
    if not rows:
        raise HTTPException(status_code=409, detail={"code": "RUNTIME_POLICY_APPROVAL_CONFLICT", "message": "Policy berubah selama proses persetujuan."})
    return {"policy": rows[0], "runtime_authorized": False}


@router.post("/operator/runtime-policies/{policy_id}/revoke", name="revoke_operator_runtime_policy")
async def revoke_operator_runtime_policy(
    policy_id: UUID,
    payload: RuntimePolicyApproval,
    request: Request,
    operator: dict[str, Any] = Depends(require_operator_scope("platform:capabilities.review.high_risk")),
) -> dict[str, Any]:
    current = await privileged_rest_request("GET", "agent_runtime_policies", params={
        "select": "id,agent_id,policy_version,status",
        "id": f"eq.{policy_id}", "status": "eq.approved", "limit": "1",
    })
    if not current:
        raise HTTPException(status_code=409, detail={"code": "RUNTIME_POLICY_NOT_ACTIVE", "message": "Hanya policy aktif yang dapat dicabut."})
    await write_operator_audit(request, actor_user_id=operator["id"], action="agent.runtime_policy.revoke",
        outcome="attempted", resource_type="agent_runtime_policy", resource_id=str(policy_id),
        metadata={"agent_id": current[0]["agent_id"], "policy_version": current[0]["policy_version"], "reason": payload.reason})
    timestamp = datetime.now(timezone.utc).isoformat()
    rows = await privileged_rest_request("PATCH", "agent_runtime_policies", params={
        "id": f"eq.{policy_id}", "status": "eq.approved",
        "select": "id,agent_id,policy_version,status,revoked_by,revoked_at",
    }, body={"status": "revoked", "revoked_by": operator["id"], "revoked_at": timestamp},
       prefer="return=representation")
    if not rows:
        raise HTTPException(status_code=409, detail={"code": "RUNTIME_POLICY_REVOCATION_CONFLICT", "message": "Policy berubah selama proses pencabutan."})
    return {"policy": rows[0], "runtime_authorized": False}


@router.get("/operator/capabilities", name="list_operator_capability_requests")
async def list_operator_capability_requests(
    limit: int = 50,
    operator: dict[str, Any] = Depends(require_operator_scope("platform:capabilities.review")),
) -> dict[str, Any]:
    rows = await privileged_rest_request(
        "GET",
        "agent_capabilities",
        params={
            "select": "id,agent_id,created_by,capability_key,description,required_permission_scopes,risk_level,status,created_at",
            "status": "eq.requested",
            "order": "created_at.asc",
            "limit": str(min(max(1, limit), 100)),
        },
    )
    return {"items": rows or [], "limit": min(max(1, limit), 100)}


@router.post("/operator/capabilities/{capability_id}/review", name="review_operator_capability")
async def review_operator_capability(
    capability_id: UUID,
    payload: CapabilityReviewPayload,
    request: Request,
    operator: dict[str, Any] = Depends(require_operator_scope("platform:capabilities.review")),
) -> dict[str, Any]:
    if payload.decision == "approved" and not payload.policy_version:
        raise HTTPException(
            status_code=422,
            detail={"code": "POLICY_VERSION_REQUIRED", "message": "Persetujuan capability wajib menetapkan policy_version yang eksplisit."},
        )
    if payload.decision == "denied" and payload.policy_version is not None:
        raise HTTPException(
            status_code=422,
            detail={"code": "POLICY_VERSION_NOT_ALLOWED", "message": "Policy version hanya boleh ditetapkan saat capability disetujui."},
        )
    current = await privileged_rest_request(
        "GET",
        "agent_capabilities",
        params={
            "select": "id,agent_id,created_by,capability_key,description,risk_level,status",
            "id": f"eq.{capability_id}",
            "status": "eq.requested",
            "limit": "1",
        },
    )
    if not current:
        raise HTTPException(
            status_code=404,
            detail={"code": "CAPABILITY_REQUEST_NOT_FOUND", "message": "Permintaan capability yang masih menunggu tidak ditemukan."},
        )
    capability = current[0]
    risk_level = capability.get("risk_level", "critical")
    if risk_level in ("high", "critical") and "platform:capabilities.review.high_risk" not in operator["scopes"]:
        await write_operator_audit(
            request,
            actor_user_id=operator["id"],
            action="agent.capability.review",
            outcome="denied",
            resource_type="agent_capability",
            resource_id=str(capability_id),
            metadata={"risk_level": risk_level, "reason": "high_risk_scope_required"},
        )
        raise HTTPException(
            status_code=403,
            detail={"code": "HIGH_RISK_REVIEW_SCOPE_REQUIRED", "message": "Capability berisiko tinggi memerlukan scope review tambahan."},
        )

    runtime_policy = None
    if payload.decision == "approved":
        matches = await privileged_rest_request("GET", "agent_runtime_policies", params={
            "select": "id,agent_id,policy_version,policy_digest,approved_tool_keys,required_permission_scopes,status",
            "agent_id": f"eq.{capability['agent_id']}", "policy_version": f"eq.{payload.policy_version}",
            "status": "eq.approved", "limit": "1",
        })
        runtime_policy = matches[0] if matches else None
        if not runtime_policy:
            raise HTTPException(status_code=409, detail={"code": "APPROVED_RUNTIME_POLICY_REQUIRED", "message": "Capability hanya dapat disetujui dengan policy runtime aktif yang sudah disetujui untuk Agent yang sama."})
        if capability["capability_key"] not in (runtime_policy.get("approved_tool_keys") or []):
            raise HTTPException(status_code=403, detail={"code": "RUNTIME_POLICY_TOOL_DENIED", "message": "Tool capability tidak tercantum dalam policy runtime."})
        if not set(capability.get("required_permission_scopes") or []).issubset(set(runtime_policy.get("required_permission_scopes") or [])):
            raise HTTPException(status_code=403, detail={"code": "RUNTIME_POLICY_SCOPE_DENIED", "message": "Scope capability melampaui policy runtime."})
    timestamp = datetime.now(timezone.utc).isoformat()
    rows = await privileged_rest_request(
        "PATCH",
        "agent_capabilities",
        params={
            "id": f"eq.{capability_id}",
            "status": "eq.requested",
            "select": "id,agent_id,capability_key,description,risk_level,status,policy_version,runtime_policy_id,reviewed_by,reviewed_at,review_reason,updated_at",
        },
        body={
            "status": payload.decision,
            "reviewed_by": operator["id"],
            "reviewed_at": timestamp,
            "review_reason": payload.reason,
            "policy_version": payload.policy_version if payload.decision == "approved" else None,
            "runtime_policy_id": runtime_policy["id"] if runtime_policy else None,
            "updated_at": timestamp,
        },
        prefer="return=representation",
    )
    if not rows:
        raise HTTPException(
            status_code=409,
            detail={"code": "CAPABILITY_REVIEW_CONFLICT", "message": "Permintaan sudah diproses atau berubah; muat ulang daftar."},
        )
    # The database trigger records the decision in the same transaction as the
    # status update. A direct API audit write here would create a non-atomic gap.
    return {"capability": rows[0], "runtime_authorized": False}

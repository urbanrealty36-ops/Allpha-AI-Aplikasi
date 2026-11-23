"""ENG-P03 operator governance for retention policies and legal holds.

This router records explicit operator-supplied policy decisions. It never
invent retention periods, legal bases, or automatic deletion eligibility.
"""
from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from allpha_api.operator_security import (
    privileged_rest_request,
    require_operator_scope,
    write_operator_audit,
)

router = APIRouter(prefix="/v1/admin/account-lifecycle", tags=["account-lifecycle-governance"])
MANAGE_SCOPE = "platform:account_lifecycle.manage"


def fail(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code, "message": message})


class RetentionPolicyCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    data_class: str = Field(min_length=2, max_length=64, pattern=r"^[a-z][a-z0-9_]{1,63}$")
    retention_days: int = Field(ge=0, le=36500)
    policy_version: str = Field(min_length=1, max_length=40, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,39}$")
    legal_basis: str = Field(min_length=8, max_length=500)


class LegalHoldCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    subject_ref: str = Field(min_length=64, max_length=64, pattern=r"^[a-f0-9]{64}$")
    reference_code: str = Field(min_length=3, max_length=120, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:/-]{2,119}$")
    reason_code: str = Field(min_length=3, max_length=80, pattern=r"^[a-z][a-z0-9._-]{2,79}$")


class LegalHoldRelease(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=8, max_length=500)


async def _audit(
    request: Request,
    operator: dict[str, Any],
    *,
    action: str,
    outcome: str,
    resource_type: str,
    resource_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    await write_operator_audit(
        request,
        actor_user_id=str(operator["id"]),
        action=action,
        outcome=outcome,
        resource_type=resource_type,
        resource_id=resource_id,
        metadata=metadata or {},
    )


@router.get("/retention-policies")
async def list_retention_policies(
    limit: int = 100,
    operator: dict[str, Any] = Depends(require_operator_scope(MANAGE_SCOPE)),
) -> dict[str, Any]:
    if not 1 <= limit <= 100:
        raise fail(422, "ACCOUNT_RETENTION_LIMIT_INVALID", "Limit harus 1-100.")
    rows = await privileged_rest_request(
        "GET",
        "account_data_retention_policies",
        params={
            "select": "id,data_class,retention_days,policy_version,legal_basis,approved_by,approved_at,active,updated_at",
            "order": "data_class.asc,updated_at.desc",
            "limit": str(limit),
        },
    )
    return {"items": rows or [], "limit": limit}


@router.post("/retention-policies", status_code=201)
async def create_retention_policy(
    payload: RetentionPolicyCreate,
    request: Request,
    operator: dict[str, Any] = Depends(require_operator_scope(MANAGE_SCOPE)),
) -> dict[str, Any]:
    existing = await privileged_rest_request(
        "GET",
        "account_data_retention_policies",
        params={
            "select": "id",
            "data_class": f"eq.{payload.data_class}",
            "policy_version": f"eq.{payload.policy_version}",
            "limit": "1",
        },
    )
    if existing:
        raise fail(409, "ACCOUNT_RETENTION_POLICY_CONFLICT", "Versi kebijakan untuk kelas data tersebut sudah ada.")

    body = {
        "data_class": payload.data_class,
        "retention_days": payload.retention_days,
        "policy_version": payload.policy_version,
        "legal_basis": payload.legal_basis,
        "approved_by": str(operator["id"]),
        "approved_at": datetime.now(timezone.utc).isoformat(),
        "active": False,
    }
    await _audit(
        request, operator, action="account.retention_policy.create", outcome="attempted",
        resource_type="account_data_retention_policy",
        metadata={"data_class": payload.data_class, "policy_version": payload.policy_version,
                  "retention_days": payload.retention_days},
    )
    rows = await privileged_rest_request(
        "POST", "account_data_retention_policies", body=body, prefer="return=representation"
    )
    if not isinstance(rows, list) or not rows:
        raise fail(503, "ACCOUNT_RETENTION_POLICY_CREATE_FAILED", "Kebijakan retensi tidak dapat disimpan.")
    row = rows[0]
    await _audit(
        request, operator, action="account.retention_policy.create", outcome="allowed",
        resource_type="account_data_retention_policy", resource_id=str(row["id"]),
        metadata={"data_class": payload.data_class, "policy_version": payload.policy_version,
                  "active": False},
    )
    return {"item": row}


@router.post("/retention-policies/{policy_id}/activate")
async def activate_retention_policy(
    policy_id: UUID,
    request: Request,
    operator: dict[str, Any] = Depends(require_operator_scope(MANAGE_SCOPE)),
) -> dict[str, Any]:
    rows = await privileged_rest_request(
        "GET", "account_data_retention_policies",
        params={"select": "id,data_class,policy_version,active,approved_by", "id": f"eq.{policy_id}", "limit": "1"},
    )
    if not rows:
        raise fail(404, "ACCOUNT_RETENTION_POLICY_NOT_FOUND", "Kebijakan retensi tidak ditemukan.")
    policy = rows[0]
    await _audit(
        request, operator, action="account.retention_policy.activate", outcome="attempted",
        resource_type="account_data_retention_policy", resource_id=str(policy_id),
        metadata={"data_class": policy["data_class"], "policy_version": policy["policy_version"]},
    )
    rows = await privileged_rest_request(
        "POST", "rpc/set_account_retention_policy_active",
        body={"p_policy_id": str(policy_id), "p_actor_user_id": str(operator["id"]), "p_active": True},
    )
    if not isinstance(rows, dict) and not (isinstance(rows, list) and rows):
        raise fail(503, "ACCOUNT_RETENTION_POLICY_ACTIVATION_FAILED", "Kebijakan tidak berhasil diaktifkan.")
    row = rows[0] if isinstance(rows, list) else rows
    if str(row.get("id")) != str(policy_id) or row.get("active") is not True:
        raise fail(503, "ACCOUNT_RETENTION_POLICY_ACTIVATION_FAILED", "Database tidak mengonfirmasi aktivasi kebijakan.")
    await _audit(
        request, operator, action="account.retention_policy.activate", outcome="allowed",
        resource_type="account_data_retention_policy", resource_id=str(policy_id),
        metadata={"data_class": policy["data_class"], "policy_version": policy["policy_version"]},
    )
    return {"item": row}


@router.post("/retention-policies/{policy_id}/deactivate")
async def deactivate_retention_policy(
    policy_id: UUID,
    request: Request,
    operator: dict[str, Any] = Depends(require_operator_scope(MANAGE_SCOPE)),
) -> dict[str, Any]:
    rows = await privileged_rest_request(
        "GET", "account_data_retention_policies",
        params={"select": "id,data_class,policy_version,active", "id": f"eq.{policy_id}", "limit": "1"},
    )
    if not rows:
        raise fail(404, "ACCOUNT_RETENTION_POLICY_NOT_FOUND", "Kebijakan retensi tidak ditemukan.")
    policy = rows[0]
    await _audit(
        request, operator, action="account.retention_policy.deactivate", outcome="attempted",
        resource_type="account_data_retention_policy", resource_id=str(policy_id),
        metadata={"data_class": policy["data_class"], "policy_version": policy["policy_version"]},
    )
    rows = await privileged_rest_request(
        "POST", "rpc/set_account_retention_policy_active",
        body={"p_policy_id": str(policy_id), "p_actor_user_id": str(operator["id"]), "p_active": False},
    )
    if not isinstance(rows, dict) and not (isinstance(rows, list) and rows):
        raise fail(503, "ACCOUNT_RETENTION_POLICY_DEACTIVATION_FAILED", "Kebijakan tidak berhasil dinonaktifkan.")
    row = rows[0] if isinstance(rows, list) else rows
    if str(row.get("id")) != str(policy_id) or row.get("active") is not False:
        raise fail(503, "ACCOUNT_RETENTION_POLICY_DEACTIVATION_FAILED", "Database tidak mengonfirmasi penonaktifan kebijakan.")
    await _audit(
        request, operator, action="account.retention_policy.deactivate", outcome="allowed",
        resource_type="account_data_retention_policy", resource_id=str(policy_id),
        metadata={"data_class": policy["data_class"], "policy_version": policy["policy_version"]},
    )
    return {"item": row}


@router.get("/legal-holds")
async def list_legal_holds(
    subject_ref: str | None = None,
    limit: int = 100,
    operator: dict[str, Any] = Depends(require_operator_scope(MANAGE_SCOPE)),
) -> dict[str, Any]:
    if not 1 <= limit <= 100:
        raise fail(422, "ACCOUNT_LEGAL_HOLD_LIMIT_INVALID", "Limit harus 1-100.")
    params = {
        "select": "id,subject_ref,reference_code,reason_code,active,created_by,created_at,released_by,released_at",
        "order": "created_at.desc",
        "limit": str(limit),
    }
    if subject_ref:
        if not re.fullmatch(r"[a-f0-9]{64}", subject_ref):
            raise fail(422, "ACCOUNT_LEGAL_HOLD_SUBJECT_INVALID", "Subject reference harus berupa SHA-256 hex 64 karakter.")
        params["subject_ref"] = f"eq.{subject_ref}"
    rows = await privileged_rest_request("GET", "account_legal_holds", params=params)
    return {"items": rows or [], "limit": limit}


@router.post("/legal-holds", status_code=201)
async def create_legal_hold(
    payload: LegalHoldCreate,
    request: Request,
    operator: dict[str, Any] = Depends(require_operator_scope(MANAGE_SCOPE)),
) -> dict[str, Any]:
    body = {
        "subject_ref": str(payload.subject_ref),
        "reference_code": payload.reference_code,
        "reason_code": payload.reason_code,
        "active": True,
        "created_by": str(operator["id"]),
    }
    await _audit(
        request, operator, action="account.legal_hold.create", outcome="attempted",
        resource_type="account_legal_hold",
        metadata={"reference_code": payload.reference_code, "reason_code": payload.reason_code},
    )
    rows = await privileged_rest_request("POST", "account_legal_holds", body=body, prefer="return=representation")
    if not isinstance(rows, list) or not rows:
        raise fail(503, "ACCOUNT_LEGAL_HOLD_CREATE_FAILED", "Legal hold tidak dapat disimpan.")
    row = rows[0]
    await _audit(
        request, operator, action="account.legal_hold.create", outcome="allowed",
        resource_type="account_legal_hold", resource_id=str(row["id"]),
        metadata={"reference_code": payload.reference_code, "reason_code": payload.reason_code},
    )
    return {"item": row}


@router.post("/legal-holds/{hold_id}/release")
async def release_legal_hold(
    hold_id: UUID,
    payload: LegalHoldRelease,
    request: Request,
    operator: dict[str, Any] = Depends(require_operator_scope(MANAGE_SCOPE)),
) -> dict[str, Any]:
    existing = await privileged_rest_request(
        "GET", "account_legal_holds",
        params={"select": "id,reference_code,reason_code", "id": f"eq.{hold_id}", "active": "eq.true", "limit": "1"},
    )
    if not existing:
        raise fail(404, "ACCOUNT_LEGAL_HOLD_NOT_FOUND", "Legal hold aktif tidak ditemukan.")
    hold = existing[0]
    await _audit(
        request, operator, action="account.legal_hold.release", outcome="attempted",
        resource_type="account_legal_hold", resource_id=str(hold_id),
        metadata={"reference_code": hold["reference_code"], "reason": payload.reason},
    )
    rows = await privileged_rest_request(
        "PATCH", "account_legal_holds",
        params={"id": f"eq.{hold_id}", "active": "eq.true"},
        body={"active": False, "released_by": str(operator["id"]), "released_at": datetime.now(timezone.utc).isoformat()},
        prefer="return=representation",
    )
    if not isinstance(rows, list) or not rows:
        raise fail(409, "ACCOUNT_LEGAL_HOLD_RELEASE_CONFLICT", "Legal hold telah berubah atau tidak dapat dilepas.")
    row = rows[0]
    await _audit(
        request, operator, action="account.legal_hold.release", outcome="allowed",
        resource_type="account_legal_hold", resource_id=str(hold_id),
        metadata={"reference_code": hold["reference_code"], "reason": payload.reason},
    )
    return {"item": row}


@router.get("/deletion-requests")
async def list_deletion_requests(
    status: str | None = None,
    limit: int = 100,
    operator: dict[str, Any] = Depends(require_operator_scope(MANAGE_SCOPE)),
) -> dict[str, Any]:
    if not 1 <= limit <= 100:
        raise fail(422, "ACCOUNT_DELETION_LIMIT_INVALID", "Limit harus 1-100.")
    allowed_statuses = {"awaiting_policy", "scheduled", "processing", "blocked_legal_hold", "blocked_dependency", "completed", "cancelled", "failed"}
    if status is not None and status not in allowed_statuses:
        raise fail(422, "ACCOUNT_DELETION_STATUS_INVALID", "Status permintaan tidak valid.")
    params = {
        "select": "id,user_id,subject_ref,status,policy_version,requested_at,scheduled_for,completed_at,cancelled_at,error_code,request_metadata",
        "order": "requested_at.desc",
        "limit": str(limit),
    }
    if status:
        params["status"] = f"eq.{status}"
    rows = await privileged_rest_request("GET", "account_deletion_requests", params=params)
    return {"items": rows or [], "limit": limit, "status": status}

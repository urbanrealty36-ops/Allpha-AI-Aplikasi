"""Operator-managed model cost configuration.

Tariff configuration is separate from model-policy approval. Activating a tariff
never enables a provider route by itself. Provider credentials remain server-side.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
import os
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator

from allpha_api.operator_security import (
    privileged_rest_request,
    require_operator_scope,
    write_operator_audit,
)

router = APIRouter(prefix="/v1/admin/model-costs", tags=["model-cost-operations"])
_FIELDS = (
    "id,provider_id,model_id,model_version,pricing_version,cost_unit,"
    "input_micro_cost_per_token,output_micro_cost_per_token,max_cost_microunits,"
    "max_prompt_bytes,max_output_tokens,max_latency_ms,status,policy_version,policy_approved,"
    "policy_approval_reference,policy_approved_by,policy_approved_at,effective_at,created_by,updated_by,created_at,updated_at"
)


class ModelCostCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider_id: str = Field(min_length=2, max_length=80, pattern=r"^[a-z0-9][a-z0-9._-]*$")
    model_id: str = Field(min_length=2, max_length=180)
    model_version: str = Field(min_length=1, max_length=180)
    pricing_version: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
    policy_version: str = Field(default="1", min_length=1, max_length=80, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
    cost_unit: str = Field(min_length=2, max_length=40)
    input_micro_cost_per_token: int = Field(ge=0, le=9_000_000_000_000)
    output_micro_cost_per_token: int = Field(ge=0, le=9_000_000_000_000)
    max_cost_microunits: int = Field(gt=0, le=9_000_000_000_000)
    max_prompt_bytes: int = Field(default=16384, ge=1, le=1_000_000)
    max_output_tokens: int = Field(default=1024, ge=1, le=100_000)
    max_latency_ms: int = Field(default=30000, ge=100, le=300_000)


class ModelCostUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    model_version: str | None = Field(default=None, min_length=1, max_length=180)
    pricing_version: str | None = Field(default=None, min_length=1, max_length=80, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
    policy_version: str | None = Field(default=None, min_length=1, max_length=80, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
    cost_unit: str | None = Field(default=None, min_length=2, max_length=40)
    input_micro_cost_per_token: int | None = Field(default=None, ge=0, le=9_000_000_000_000)
    output_micro_cost_per_token: int | None = Field(default=None, ge=0, le=9_000_000_000_000)
    max_cost_microunits: int | None = Field(default=None, gt=0, le=9_000_000_000_000)
    max_prompt_bytes: int | None = Field(default=None, ge=1, le=1_000_000)
    max_output_tokens: int | None = Field(default=None, ge=1, le=100_000)
    max_latency_ms: int | None = Field(default=None, ge=100, le=300_000)


class ModelCostReason(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=8, max_length=500)

class ModelCostApproval(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=8, max_length=500)
    approval_reference: str = Field(min_length=8, max_length=200)

class ModerationPolicyCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    policy_version: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
    approval_reference: str = Field(min_length=3, max_length=160)
    expires_at: datetime | None = None

class ModerationPolicyApproval(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=8, max_length=500)
    approval_reference: str = Field(min_length=3, max_length=160)


@router.get("/runtime-status", name="model_router_runtime_status")
async def model_router_runtime_status(
    request: Request,
    operator: dict[str, Any] = Depends(require_operator_scope("platform:operations.read")),
) -> dict[str, Any]:
    router_instance = getattr(request.app.state, "text_generation_router", None)
    required = (
        "ALLPHA_TEXTGEN_BASE_URL","ALLPHA_TEXTGEN_API_KEY","ALLPHA_TEXTGEN_PROVIDER_ID",
        "ALLPHA_TEXTGEN_MODEL_ID","ALLPHA_TEXTGEN_MODEL_VERSION","ALLPHA_TEXTGEN_POLICY_ID",
        "ALLPHA_TEXTGEN_POLICY_VERSION","ALLPHA_TEXTGEN_PRICING_VERSION","ALLPHA_TEXTGEN_COST_UNIT",
        "ALLPHA_TEXTGEN_INPUT_MICRO_COST_PER_TOKEN","ALLPHA_TEXTGEN_OUTPUT_MICRO_COST_PER_TOKEN",
        "ALLPHA_TEXTGEN_MAX_COST_MICROUNITS","SUPABASE_URL","SUPABASE_SERVICE_ROLE_KEY",
    )
    missing = [name for name in required if not os.getenv(name, "").strip()]
    if router_instance is None:
        return {"configured": False, "ready": False, "reason": "provider_or_policy_configuration_incomplete",
                "missing_configuration": missing}
    try:
        result = await router_instance.preflight("private")
        return {"configured": True, "ready": True, "route": result.get("route", {})}
    except Exception:
        return {"configured": True, "ready": False, "reason": "model_policy_or_tariff_preflight_failed",
                "missing_configuration": missing}


@router.get("/usage-summary", name="model_usage_summary")
async def model_usage_summary(
    since: datetime | None = None,
    until: datetime | None = None,
    operator: dict[str, Any] = Depends(require_operator_scope("platform:operations.read")),
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    start = since or (now - timedelta(days=30))
    end = until or now
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    if start >= end or end - start > timedelta(days=90):
        raise HTTPException(status_code=422, detail={"code": "MODEL_USAGE_PERIOD_INVALID", "message": "Rentang penggunaan harus positif dan maksimal 90 hari."})
    result = await privileged_rest_request(
        "POST", "rpc/get_agent_model_usage_summary",
        body={"p_since": start.isoformat(), "p_until": end.isoformat()},
    )
    if not isinstance(result, dict):
        raise HTTPException(status_code=503, detail={"code": "MODEL_USAGE_SUMMARY_UNAVAILABLE", "message": "Ringkasan penggunaan belum dapat dikonfirmasi."})
    return result


@router.get("/moderation-policies", name="list_generation_output_moderation_policies")
async def list_generation_output_moderation_policies(
    operator: dict[str, Any] = Depends(require_operator_scope("platform:operations.read")),
) -> dict[str, Any]:
    rows = await privileged_rest_request(
        "GET", "generation_output_moderation_policies",
        params={"select": "policy_version,approval_reference,configuration,status,effective_at,expires_at,approved_by,created_at",
                "order": "created_at.desc", "limit": "100"},
    )
    return {"items": rows or []}


@router.post("/moderation-policies", status_code=201, name="create_generation_output_moderation_policy")
async def create_generation_output_moderation_policy(
    payload: ModerationPolicyCreate,
    request: Request,
    operator: dict[str, Any] = Depends(require_operator_scope("platform:capabilities.review")),
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    expiry = payload.expires_at
    if expiry is not None and (expiry.tzinfo is None or expiry <= now):
        raise HTTPException(status_code=422, detail={"code": "MODERATION_POLICY_EXPIRY_INVALID", "message": "Waktu kedaluwarsa harus menggunakan timezone dan berada di masa depan."})
    body = {
        "policy_version": payload.policy_version,
        "approval_reference": payload.approval_reference.strip(),
        "configuration": {"mode": "manual_review_only", "manual_review_only": True},
        "status": "draft",
        "effective_at": now.isoformat(),
        "expires_at": expiry.isoformat() if expiry else None,
        "approved_by": None,
    }
    rows = await privileged_rest_request(
        "POST", "generation_output_moderation_policies",
        params={"select": "policy_version,approval_reference,configuration,status,effective_at,expires_at,approved_by,created_at"},
        body=body, prefer="return=representation",
    )
    if not rows:
        raise HTTPException(status_code=503, detail={"code": "MODERATION_POLICY_CREATE_UNCONFIRMED", "message": "Draft moderation policy tidak terkonfirmasi."})
    item = rows[0]
    await write_operator_audit(
        request, actor_user_id=operator["id"], action="generation_moderation_policy.create", outcome="allowed",
        resource_type="generation_output_moderation_policy", resource_id=item["policy_version"],
        metadata={"mode": "manual_review_only", "status": "draft", "approval_reference": payload.approval_reference},
    )
    return {"item": item, "runtime_enabled": False}


@router.post("/moderation-policies/{policy_version}/approve", name="approve_generation_output_moderation_policy")
async def approve_generation_output_moderation_policy(
    policy_version: str,
    payload: ModerationPolicyApproval,
    request: Request,
    operator: dict[str, Any] = Depends(require_operator_scope("platform:capabilities.review.high_risk")),
) -> dict[str, Any]:
    current = await privileged_rest_request(
        "GET", "generation_output_moderation_policies",
        params={"select": "policy_version,configuration,status,expires_at",
                "policy_version": f"eq.{policy_version}", "limit": "1"},
    )
    if not current:
        raise HTTPException(status_code=404, detail={"code": "MODERATION_POLICY_NOT_FOUND", "message": "Draft moderation policy tidak ditemukan."})
    item = current[0]
    if item["status"] != "draft" or item["configuration"] != {"mode": "manual_review_only", "manual_review_only": True}:
        raise HTTPException(status_code=409, detail={"code": "MODERATION_POLICY_NOT_APPROVABLE", "message": "Hanya draft manual-review-only yang dapat disetujui."})
    now = datetime.now(timezone.utc)
    expiry = item.get("expires_at")
    if expiry and datetime.fromisoformat(expiry.replace("Z", "+00:00")) <= now:
        raise HTTPException(status_code=409, detail={"code": "MODERATION_POLICY_EXPIRED", "message": "Draft moderation policy sudah kedaluwarsa."})
    rows = await privileged_rest_request(
        "PATCH", "generation_output_moderation_policies",
        params={"policy_version": f"eq.{policy_version}", "status": "eq.draft",
                "select": "policy_version,approval_reference,configuration,status,effective_at,expires_at,approved_by,created_at"},
        body={"status": "approved", "effective_at": now.isoformat(),
              "approval_reference": payload.approval_reference.strip(), "approved_by": operator["id"]},
        prefer="return=representation",
    )
    if not rows:
        raise HTTPException(status_code=409, detail={"code": "MODERATION_POLICY_APPROVAL_CONFLICT", "message": "Status policy berubah; muat ulang."})
    approved = rows[0]
    await write_operator_audit(
        request, actor_user_id=operator["id"], action="generation_moderation_policy.approve", outcome="allowed",
        resource_type="generation_output_moderation_policy", resource_id=policy_version,
        metadata={"mode": "manual_review_only", "approval_reference": payload.approval_reference, "reason": payload.reason},
    )
    return {"item": approved, "runtime_enabled": False,
            "message": "Output akan tetap ditahan untuk Human review; policy ini tidak mengaktifkan auto-approval."}


@router.post("/moderation-policies/{policy_version}/retire", name="retire_generation_output_moderation_policy")
async def retire_generation_output_moderation_policy(
    policy_version: str,
    payload: ModelCostReason,
    request: Request,
    operator: dict[str, Any] = Depends(require_operator_scope("platform:capabilities.review.high_risk")),
) -> dict[str, Any]:
    rows = await privileged_rest_request(
        "PATCH", "generation_output_moderation_policies",
        params={"policy_version": f"eq.{policy_version}", "status": "in.(draft,approved)",
                "select": "policy_version,approval_reference,configuration,status,effective_at,expires_at,approved_by,created_at"},
        body={"status": "retired"},
        prefer="return=representation",
    )
    if not rows:
        raise HTTPException(status_code=404, detail={"code": "MODERATION_POLICY_NOT_RETIRABLE", "message": "Moderation policy tidak ditemukan atau sudah retired."})
    retired = rows[0]
    await write_operator_audit(
        request, actor_user_id=operator["id"], action="generation_moderation_policy.retire", outcome="allowed",
        resource_type="generation_output_moderation_policy", resource_id=policy_version,
        metadata={"reason": payload.reason},
    )
    return {"item": retired, "runtime_enabled": False}


@router.get("", name="list_model_cost_configs")
async def list_model_cost_configs(
    limit: int = 100,
    offset: int = 0,
    status: Literal["draft", "active", "archived"] | None = None,
    operator: dict[str, Any] = Depends(require_operator_scope("platform:operations.read")),
) -> dict[str, Any]:
    if not 1 <= limit <= 100 or not 0 <= offset <= 100_000:
        raise HTTPException(status_code=422, detail={"code": "MODEL_COST_PAGINATION_INVALID", "message": "Pagination konfigurasi biaya tidak valid."})
    params = {"select": _FIELDS, "order": "created_at.desc", "limit": str(limit), "offset": str(offset)}
    if status:
        params["status"] = f"eq.{status}"
    rows = await privileged_rest_request("GET", "ai_model_cost_configs", params=params)
    return {"items": rows or [], "limit": limit, "offset": offset}


@router.post("", status_code=201, name="create_model_cost_config")
async def create_model_cost_config(
    payload: ModelCostCreate,
    request: Request,
    operator: dict[str, Any] = Depends(require_operator_scope("platform:capabilities.review")),
) -> dict[str, Any]:
    body = payload.model_dump()
    body.update({
        "status": "draft",
        "policy_approved": False,
        "created_by": operator["id"],
        "updated_by": operator["id"],
    })
    rows = await privileged_rest_request(
        "POST", "ai_model_cost_configs", params={"select": _FIELDS}, body=body,
        prefer="return=representation",
    )
    if not rows:
        raise HTTPException(status_code=503, detail={"code": "MODEL_COST_CREATE_UNCONFIRMED", "message": "Pembuatan konfigurasi biaya tidak terkonfirmasi."})
    item = rows[0]
    await write_operator_audit(
        request, actor_user_id=operator["id"], action="model_cost.create", outcome="allowed",
        resource_type="ai_model_cost_config", resource_id=str(item["id"]),
        metadata={"provider_id": item["provider_id"], "model_id": item["model_id"], "pricing_version": item["pricing_version"], "status": "draft"},
    )
    return {"item": item, "runtime_enabled": False}


@router.patch("/{config_id}", name="update_model_cost_config")
async def update_model_cost_config(
    config_id: UUID,
    payload: ModelCostUpdate,
    request: Request,
    operator: dict[str, Any] = Depends(require_operator_scope("platform:capabilities.review")),
) -> dict[str, Any]:
    changes = payload.model_dump(exclude_unset=True, exclude_none=True)
    if not changes:
        raise HTTPException(status_code=422, detail={"code": "MODEL_COST_EMPTY_UPDATE", "message": "Tidak ada perubahan konfigurasi."})
    current = await privileged_rest_request(
        "GET", "ai_model_cost_configs",
        params={"select": "id,provider_id,model_id,pricing_version,status", "id": f"eq.{config_id}", "limit": "1"},
    )
    if not current:
        raise HTTPException(status_code=404, detail={"code": "MODEL_COST_NOT_FOUND", "message": "Konfigurasi biaya tidak ditemukan."})
    if current[0]["status"] != "draft":
        raise HTTPException(status_code=409, detail={"code": "MODEL_COST_IMMUTABLE", "message": "Tarif aktif/arsip tidak dapat diedit; buat versi tarif baru."})
    changes.update({"updated_by": operator["id"], "updated_at": datetime.now(timezone.utc).isoformat()})
    rows = await privileged_rest_request(
        "PATCH", "ai_model_cost_configs",
        params={"id": f"eq.{config_id}", "status": "eq.draft", "select": _FIELDS},
        body=changes, prefer="return=representation",
    )
    if not rows:
        raise HTTPException(status_code=409, detail={"code": "MODEL_COST_STATE_CHANGED", "message": "Konfigurasi berubah; muat ulang sebelum mencoba lagi."})
    item = rows[0]
    await write_operator_audit(
        request, actor_user_id=operator["id"], action="model_cost.update", outcome="allowed",
        resource_type="ai_model_cost_config", resource_id=str(config_id),
        metadata={"provider_id": item["provider_id"], "model_id": item["model_id"], "pricing_version": item["pricing_version"], "changed_fields": sorted(changes.keys())},
    )
    return {"item": item, "runtime_enabled": False}


@router.post("/{config_id}/activate", name="activate_model_cost_config")
async def activate_model_cost_config(
    config_id: UUID,
    payload: ModelCostReason,
    request: Request,
    operator: dict[str, Any] = Depends(require_operator_scope("platform:capabilities.review.high_risk")),
) -> dict[str, Any]:
    current = await privileged_rest_request(
        "GET", "ai_model_cost_configs",
        params={"select": _FIELDS, "id": f"eq.{config_id}", "limit": "1"},
    )
    if not current:
        raise HTTPException(status_code=404, detail={"code": "MODEL_COST_NOT_FOUND", "message": "Konfigurasi biaya tidak ditemukan."})
    item = current[0]
    if item["status"] != "draft":
        raise HTTPException(status_code=409, detail={"code": "MODEL_COST_NOT_DRAFT", "message": "Hanya konfigurasi draft yang dapat diaktifkan."})
    # The database partial unique index is the concurrency guard for one active
    # tariff per provider/model. The route never approves model execution policy.
    existing = await privileged_rest_request(
        "GET", "ai_model_cost_configs",
        params={"select": "id", "provider_id": f"eq.{item['provider_id']}", "model_id": f"eq.{item['model_id']}", "status": "eq.active", "limit": "1"},
    )
    if existing:
        raise HTTPException(status_code=409, detail={"code": "MODEL_COST_ACTIVE_VERSION_EXISTS", "message": "Tarif aktif untuk provider/model ini sudah ada. Arsipkan versi lama melalui prosedur terkontrol sebelum mengaktifkan versi baru."})
    now = datetime.now(timezone.utc).isoformat()
    rows = await privileged_rest_request(
        "PATCH", "ai_model_cost_configs",
        params={"id": f"eq.{config_id}", "status": "eq.draft", "select": _FIELDS},
        body={"status": "active", "effective_at": now, "updated_by": operator["id"], "updated_at": now},
        prefer="return=representation",
    )
    if not rows:
        raise HTTPException(status_code=409, detail={"code": "MODEL_COST_ACTIVATION_CONFLICT", "message": "Status tarif berubah; muat ulang."})
    active = rows[0]
    await write_operator_audit(
        request, actor_user_id=operator["id"], action="model_cost.activate", outcome="allowed",
        resource_type="ai_model_cost_config", resource_id=str(config_id),
        metadata={"provider_id": active["provider_id"], "model_id": active["model_id"], "pricing_version": active["pricing_version"], "policy_approved": False, "reason": payload.reason},
    )
    return {"item": active, "runtime_enabled": False, "message": "Tarif aktif di registry; ini tidak menyetujui policy atau mengaktifkan eksekusi model."}


@router.post("/{config_id}/approve-policy", name="approve_model_execution_policy")
async def approve_model_execution_policy(
    config_id: UUID,
    payload: ModelCostApproval,
    request: Request,
    operator: dict[str, Any] = Depends(require_operator_scope("platform:capabilities.review.high_risk")),
) -> dict[str, Any]:
    current = await privileged_rest_request(
        "GET", "ai_model_cost_configs",
        params={"select": _FIELDS, "id": f"eq.{config_id}", "limit": "1"},
    )
    if not current:
        raise HTTPException(status_code=404, detail={"code": "MODEL_COST_NOT_FOUND", "message": "Konfigurasi biaya tidak ditemukan."})
    item = current[0]
    if item["status"] != "active" or not item.get("effective_at"):
        raise HTTPException(status_code=409, detail={"code": "MODEL_COST_NOT_ACTIVE", "message": "Tarif harus aktif sebelum policy model dapat disetujui."})
    if item.get("policy_approved"):
        raise HTTPException(status_code=409, detail={"code": "MODEL_POLICY_ALREADY_APPROVED", "message": "Policy model versi ini sudah disetujui."})
    now = datetime.now(timezone.utc).isoformat()
    rows = await privileged_rest_request(
        "PATCH", "ai_model_cost_configs",
        params={"id": f"eq.{config_id}", "status": "eq.active", "policy_approved": "eq.false", "select": _FIELDS},
        body={
            "policy_approved": True,
            "policy_approval_reference": payload.approval_reference,
            "policy_approved_by": operator["id"],
            "policy_approved_at": now,
            "updated_by": operator["id"],
            "updated_at": now,
        },
        prefer="return=representation",
    )
    if not rows:
        raise HTTPException(status_code=409, detail={"code": "MODEL_POLICY_APPROVAL_CONFLICT", "message": "Status policy berubah; muat ulang sebelum mencoba lagi."})
    approved = rows[0]
    await write_operator_audit(
        request, actor_user_id=operator["id"], action="model_cost.policy_approve", outcome="allowed",
        resource_type="ai_model_cost_config", resource_id=str(config_id),
        metadata={
            "provider_id": approved["provider_id"], "model_id": approved["model_id"],
            "model_version": approved["model_version"], "pricing_version": approved["pricing_version"],
            "policy_version": approved["policy_version"], "approval_reference": payload.approval_reference,
            "reason": payload.reason,
        },
    )
    return {"item": approved, "policy_approved": True, "runtime_enabled": False,
            "message": "Model execution policy disetujui. Runtime tetap membutuhkan provider secret dan route config server-side."}


@router.post("/{config_id}/revoke-policy", name="revoke_model_execution_policy")
async def revoke_model_execution_policy(
    config_id: UUID,
    payload: ModelCostReason,
    request: Request,
    operator: dict[str, Any] = Depends(require_operator_scope("platform:capabilities.review.high_risk")),
) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    rows = await privileged_rest_request(
        "PATCH", "ai_model_cost_configs",
        params={"id": f"eq.{config_id}", "status": "eq.active", "policy_approved": "eq.true", "select": _FIELDS},
        body={
            "policy_approved": False,
            "policy_approval_reference": None,
            "policy_approved_by": None,
            "policy_approved_at": None,
            "updated_by": operator["id"],
            "updated_at": now,
        },
        prefer="return=representation",
    )
    if not rows:
        raise HTTPException(status_code=409, detail={"code": "MODEL_POLICY_NOT_APPROVED", "message": "Policy aktif tidak ditemukan atau sudah dicabut."})
    item = rows[0]
    await write_operator_audit(
        request, actor_user_id=operator["id"], action="model_cost.policy_revoke", outcome="allowed",
        resource_type="ai_model_cost_config", resource_id=str(config_id),
        metadata={"provider_id": item["provider_id"], "model_id": item["model_id"],
                  "pricing_version": item["pricing_version"], "policy_version": item["policy_version"],
                  "reason": payload.reason},
    )
    return {"item": item, "policy_approved": False, "runtime_enabled": False}


@router.post("/{config_id}/archive", name="archive_model_cost_config")
async def archive_model_cost_config(
    config_id: UUID,
    payload: ModelCostReason,
    request: Request,
    operator: dict[str, Any] = Depends(require_operator_scope("platform:capabilities.review.high_risk")),
) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    rows = await privileged_rest_request(
        "PATCH", "ai_model_cost_configs",
        params={"id": f"eq.{config_id}", "status": "in.(draft,active)", "select": _FIELDS},
        body={"status": "archived", "policy_approved": False, "policy_approval_reference": None,
              "policy_approved_by": None, "policy_approved_at": None,
              "updated_by": operator["id"], "updated_at": now},
        prefer="return=representation",
    )
    if not rows:
        raise HTTPException(status_code=404, detail={"code": "MODEL_COST_NOT_ARCHIVABLE", "message": "Konfigurasi tidak ditemukan atau sudah diarsipkan."})
    item = rows[0]
    await write_operator_audit(
        request, actor_user_id=operator["id"], action="model_cost.archive", outcome="allowed",
        resource_type="ai_model_cost_config", resource_id=str(config_id),
        metadata={"provider_id": item["provider_id"], "model_id": item["model_id"], "pricing_version": item["pricing_version"], "reason": payload.reason},
    )
    return {"item": item, "runtime_enabled": False}

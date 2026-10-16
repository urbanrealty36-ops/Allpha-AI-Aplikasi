"""Operator-managed model cost configuration.

Tariff configuration is separate from model-policy approval. Activating a tariff
never enables a provider route by itself. Provider credentials remain server-side.
"""
from __future__ import annotations

from datetime import datetime, timezone
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
    "max_prompt_bytes,max_output_tokens,max_latency_ms,status,policy_approved,"
    "effective_at,created_by,updated_by,created_at,updated_at"
)


class ModelCostCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider_id: str = Field(min_length=2, max_length=80, pattern=r"^[a-z0-9][a-z0-9._-]*$")
    model_id: str = Field(min_length=2, max_length=180)
    model_version: str = Field(min_length=1, max_length=180)
    pricing_version: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
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
        body={"status": "archived", "updated_by": operator["id"], "updated_at": now},
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

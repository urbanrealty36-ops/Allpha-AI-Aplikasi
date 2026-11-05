"""Owner-scoped AI generation job API with policy-backed credit reservation.

The PostgreSQL RPC atomically reserves AI Credits and enqueues the durable job.
This module never selects a provider, tariff, credit price, or entitlement value.
"""
from __future__ import annotations

import hashlib
import os
import uuid
from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from allpha_api.auth import current_user, user_db_request

router = APIRouter(prefix="/v1/generation", tags=["ai-generation"])
_TIMEOUT = httpx.Timeout(10.0, connect=3.0)


class GenerationJobCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    agent_id: uuid.UUID
    skill_id: uuid.UUID
    capability_id: str = Field(min_length=3, max_length=128, pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")
    prompt: str = Field(min_length=1, max_length=32768)
    max_output_tokens: int | None = Field(default=None, ge=1, le=16384)


def _db_config() -> tuple[str, str]:
    url = os.getenv("SUPABASE_URL", "").rstrip("/")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "") or os.getenv("SUPABASE_SECRET_KEY", "")
    if not url or not key:
        raise HTTPException(503, detail={"code": "GENERATION_DATABASE_NOT_CONFIGURED", "message": "Layanan generation belum terhubung ke database."})
    return url, key


async def _admin_request(method: str, path: str, *, params: dict[str, str] | None = None,
                         body: dict[str, Any] | None = None) -> Any:
    url, key = _db_config()
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            headers = {"apikey": key, "Content-Type": "application/json", "Accept": "application/json"}
            if os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip():
                headers["Authorization"] = f"Bearer {os.getenv('SUPABASE_SERVICE_ROLE_KEY', '').strip()}"
            response = await client.request(method, f"{url}/rest/v1/{path}",
                params=params, json=body, headers=headers)
    except httpx.HTTPError as exc:
        raise HTTPException(503, detail={"code": "GENERATION_DATABASE_UNAVAILABLE", "message": "Database generation sementara tidak tersedia."}) from exc
    if response.status_code >= 400:
        raise HTTPException(503 if response.status_code >= 500 or response.status_code == 404 else 409,
            detail={"code": "GENERATION_DATABASE_OPERATION_FAILED", "message": "Operasi generation tidak dapat dikonfirmasi."})
    if not response.content:
        return []
    try:
        return response.json()
    except ValueError as exc:
        raise HTTPException(503, detail={"code": "GENERATION_DATABASE_RESPONSE_INVALID", "message": "Respons database generation tidak valid."}) from exc


async def _rpc(name: str, command: dict[str, Any]) -> Any:
    return await _admin_request("POST", f"rpc/{name}", body={"p_command": command})


def _parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


async def _approved_credit_policy(entitlement_version: str) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    rows = await _admin_request("GET", "credit_policy_versions", params={
        "select": "policy_version,credit_scheme_version,approval_reference,configuration,status,effective_at,expires_at",
        "status": "eq.approved", "order": "effective_at.desc", "limit": "100",
    })
    now = datetime.now(timezone.utc)
    for row in rows or []:
        effective = _parse_time(row.get("effective_at"))
        expires = _parse_time(row.get("expires_at"))
        if effective and effective > now:
            continue
        if expires and expires <= now:
            continue
        config = row.get("configuration") if isinstance(row.get("configuration"), dict) else {}
        entitlements = config.get("entitlements") if isinstance(config.get("entitlements"), dict) else {}
        entitlement = entitlements.get(entitlement_version)
        if isinstance(entitlement, dict):
            return row, config, entitlement
    raise HTTPException(503, detail={"code": "AI_CREDIT_POLICY_UNAVAILABLE", "message": "Belum ada AI Credit policy approved yang berlaku untuk entitlement akun ini."})


@router.post("/jobs", status_code=202)
async def create_generation_job(
    payload: GenerationJobCreate,
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    if not idempotency_key or not 8 <= len(idempotency_key) <= 160:
        raise HTTPException(400, detail={"code": "IDEMPOTENCY_KEY_REQUIRED", "message": "Idempotency-Key 8–160 karakter wajib dikirim."})
    token = getattr(request.state, "supabase_access_token", None)
    if not token:
        raise HTTPException(401, detail={"code": "AUTH_REQUIRED", "message": "Sesi login diperlukan."})

    prompt_hash = hashlib.sha256(payload.prompt.encode("utf-8")).hexdigest()
    existing = await _admin_request("GET", "generation_jobs", params={
        "select": "id,task_id,prompt_sha256,agent_id,skill_id,capability_id,status,credits_to_reserve",
        "owner_user_id": f"eq.{user['id']}", "idempotency_key": f"eq.{idempotency_key}", "limit": "1",
    })
    if existing:
        prior = existing[0]
        if (prior.get("prompt_sha256") != prompt_hash or str(prior.get("agent_id")) != str(payload.agent_id)
            or str(prior.get("skill_id")) != str(payload.skill_id) or prior.get("capability_id") != payload.capability_id):
            raise HTTPException(409, detail={"code": "GENERATION_JOB_IDEMPOTENCY_CONFLICT", "message": "Idempotency-Key telah digunakan untuk permintaan generation yang berbeda."})
        return {"job_id": prior["id"], "task_id": prior["task_id"], "status": prior["status"],
            "idempotent_replay": True, "reserved_credits": prior.get("credits_to_reserve")}

    router_instance = getattr(request.app.state, "text_generation_router", None)
    if router_instance is None:
        raise HTTPException(503, detail={"code": "MODEL_ROUTE_UNAVAILABLE", "message": "AI Model Router belum memiliki provider, model, policy, dan metering yang disetujui."})
    try:
        await router_instance.preflight("private")
        route = router_instance.route_snapshot_for("private")
        router_max_tokens = router_instance.max_output_tokens_for("private")
    except Exception as exc:
        raise HTTPException(503, detail={"code": "MODEL_ROUTE_NOT_READY", "message": "AI generation fail-closed karena route, runtime policy, atau model-cost registry belum siap."}) from exc

    prompt_bytes = len(payload.prompt.encode("utf-8"))
    if prompt_bytes > int(route["max_prompt_bytes"]):
        raise HTTPException(422, detail={"code": "PROMPT_EXCEEDS_APPROVED_BOUND", "message": "Prompt melebihi batas byte yang disetujui."})
    max_output_tokens = payload.max_output_tokens or router_max_tokens
    if max_output_tokens > router_max_tokens:
        raise HTTPException(422, detail={"code": "OUTPUT_TOKEN_LIMIT_EXCEEDED", "message": "Batas output melebihi policy model aktif."})

    skill_rows = await user_db_request("GET", "agent_skills", token, params={
        "select": "id,agent_id,version,status", "id": f"eq.{payload.skill_id}",
        "agent_id": f"eq.{payload.agent_id}", "status": "eq.published", "limit": "1",
    })
    if not skill_rows:
        raise HTTPException(404, detail={"code": "PUBLISHED_SKILL_NOT_FOUND", "message": "Skill tidak ditemukan atau belum dipublikasikan untuk Agent ini."})
    skill = skill_rows[0]
    capability_rows = await user_db_request("GET", "agent_capabilities", token, params={
        "select": "capability_key,status", "agent_id": f"eq.{payload.agent_id}",
        "capability_key": f"eq.{payload.capability_id}", "status": "eq.approved", "limit": "1",
    })
    if not capability_rows:
        raise HTTPException(403, detail={"code": "AGENT_CAPABILITY_NOT_APPROVED", "message": "Capability belum disetujui untuk Agent ini."})

    subscriptions = await _admin_request("GET", "billing_subscriptions", params={
        "select": "id,owner_user_id,plan_key,entitlement_version,status,current_period_end",
        "owner_user_id": f"eq.{user['id']}", "status": "eq.active",
        "current_period_end": "gt." + datetime.now(timezone.utc).isoformat(),
        "order": "updated_at.desc", "limit": "1",
    })
    if not subscriptions:
        raise HTTPException(403, detail={"code": "PREMIUM_ENTITLEMENT_REQUIRED", "message": "AI generation memerlukan Premium entitlement yang aktif dan terverifikasi."})
    subscription = subscriptions[0]
    entitlement_version = str(subscription.get("entitlement_version") or "")
    if not entitlement_version:
        raise HTTPException(503, detail={"code": "ENTITLEMENT_VERSION_MISSING", "message": "Versi entitlement Premium belum dikonfigurasi."})

    policy_row, policy_config, entitlement = await _approved_credit_policy(entitlement_version)
    capabilities = policy_config.get("capabilities") if isinstance(policy_config.get("capabilities"), dict) else {}
    capability = capabilities.get(payload.capability_id)
    if not isinstance(capability, dict):
        raise HTTPException(503, detail={"code": "CAPABILITY_TARIFF_UNAVAILABLE", "message": "Capability belum memiliki tarif AI Credit yang disetujui."})
    usage_unit = str(capability.get("usage_unit") or "")
    cost_unit = str(capability.get("cost_unit") or "")
    pricing_version = str(capability.get("cost_pricing_version") or "")
    tariff_version = str(capability.get("tariff_version") or "")
    credits_per_usage_unit = int(capability.get("credits_per_usage_unit") or 0)
    max_cost_microunits = int(capability.get("max_cost_microunits") if capability.get("max_cost_microunits") is not None else -1)
    if (usage_unit != "tokens_total" or not tariff_version or credits_per_usage_unit <= 0
        or cost_unit != route.get("cost_unit") or pricing_version != route.get("pricing_version")
        or max_cost_microunits != int(route.get("max_cost_microunits") or -1)):
        raise HTTPException(503, detail={"code": "MODEL_CREDIT_POLICY_MISMATCH", "message": "Tarif kredit dan pricing model tidak cocok dengan route yang diverifikasi."})
    allow_success = policy_config.get("allow_success_settlement") is True
    allow_partial = policy_config.get("allow_partial_settlement") is True
    allow_failure_release = policy_config.get("allow_definitive_failure_release") is True
    if not allow_success or not allow_partial:
        raise HTTPException(503, detail={"code": "SETTLEMENT_POLICY_NOT_APPROVED", "message": "Kebijakan settlement sukses dan partial belum disetujui."})

    estimated_usage_units = prompt_bytes + max_output_tokens
    credits_to_reserve = estimated_usage_units * credits_per_usage_unit
    max_credits = int(entitlement.get("max_credits_per_request") or 0)
    if max_credits <= 0 or credits_to_reserve > max_credits:
        raise HTTPException(422, detail={"code": "REQUEST_EXCEEDS_ENTITLEMENT_LIMIT", "message": "Estimasi penggunaan melebihi batas AI Credit per permintaan Premium."})
    timeout_ms = min(120000, max(100, int(route.get("max_latency_ms") or 30000)))
    task_id = str(uuid.uuid4())
    trace_id = str(uuid.uuid4())
    command = {
        "owner_user_id": str(user["id"]),
        "agent_id": str(payload.agent_id),
        "skill_id": str(payload.skill_id),
        "source_version": int(skill["version"]),
        "capability_id": payload.capability_id,
        "sensitivity": "private",
        "task_id": task_id,
        "trace_id": trace_id,
        "idempotency_key": idempotency_key,
        "prompt": payload.prompt,
        "prompt_sha256": prompt_hash,
        "max_output_tokens": max_output_tokens,
        "timeout_ms": timeout_ms,
        "estimated_usage_units": estimated_usage_units,
        "usage_unit": usage_unit,
        "estimated_cost_microunits": max_cost_microunits,
        "cost_unit": cost_unit,
        "credits_to_reserve": credits_to_reserve,
        "credits_per_usage_unit": credits_per_usage_unit,
        "credit_scheme_version": str(policy_row["credit_scheme_version"]),
        "tariff_version": tariff_version,
        "entitlement_version": entitlement_version,
        "policy_version": str(policy_row["policy_version"]),
        "policy_approval_reference": str(policy_row["approval_reference"]),
        "allow_success_settlement": allow_success,
        "allow_definitive_failure_release": allow_failure_release,
        "allow_partial_settlement": allow_partial,
        "provider_id": str(route["provider_id"]),
        "model_id": str(route["model_id"]),
        "model_version": str(route["model_version"]),
        "pricing_version": pricing_version,
        "max_cost_microunits": max_cost_microunits,
    }
    created = await _rpc("generation_create_job", command)
    if not isinstance(created, dict) or not created.get("job_id"):
        raise HTTPException(503, detail={"code": "GENERATION_JOB_NOT_CONFIRMED", "message": "Generation job dan AI Credit reservation belum terkonfirmasi."})
    return {"job_id": created["job_id"], "task_id": created.get("task_id"), "status": created.get("status"),
        "idempotent_replay": bool(created.get("idempotent_replay")), "reserved_credits": created.get("reserved_credits")}


@router.get("/jobs")
async def list_generation_jobs(limit: int = 20, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    bounded = min(max(1, limit), 50)
    rows = await _admin_request("GET", "generation_jobs", params={
        "select": "id,task_id,capability_id,status,credits_to_reserve,created_at,started_at,completed_at,error_code",
        "owner_user_id": f"eq.{user['id']}", "order": "created_at.desc", "limit": str(bounded),
    })
    return {"items": rows or [], "limit": bounded}


@router.get("/jobs/{job_id}")
async def get_generation_job(job_id: uuid.UUID, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    rows = await _admin_request("GET", "generation_jobs", params={
        "select": "id,task_id,capability_id,status,credits_to_reserve,created_at,started_at,completed_at,error_code,output_text,input_tokens,output_tokens",
        "id": f"eq.{job_id}", "owner_user_id": f"eq.{user['id']}", "limit": "1",
    })
    if not rows:
        raise HTTPException(404, detail={"code": "GENERATION_JOB_NOT_FOUND", "message": "Generation job tidak ditemukan."})
    job = rows[0]
    if job.get("status") != "succeeded":
        job.pop("output_text", None)
    return {"job": job}

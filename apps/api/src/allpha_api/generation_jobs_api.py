"""Owner-scoped AI generation job API with policy-backed credit reservation.

The PostgreSQL RPC atomically reserves AI Credits and enqueues the durable job.
This module never selects a provider, tariff, credit price, or entitlement value.
"""
from __future__ import annotations

import hashlib
import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from allpha_api.operator_security import require_operator_scope, write_operator_audit

from allpha_api.auth import current_user, user_db_request
from allpha_api.agent_consumer_grants import (
    AgentConsumerGrantStore,
    ConsumerBudgetReservation,
    ConsumerGrantUnavailable,
)
from allpha_api.knowledge_retrieval import (
    KnowledgeAccessDenied,
    KnowledgeRetrievalService,
    KnowledgeRetrievalUnavailable,
    RetrievalRequest,
    request_scoped_retrieval_service,
    request_scoped_external_public_retrieval_service,
)
from allpha_api.generation_prompt import (
    generation_prompt_size_bytes,
    snapshot_sha256,
)
from allpha_api.tool_registry import ToolInputError, UnknownToolError, get_tool, validate_tool_dependencies, validate_tool_input

router = APIRouter(prefix="/v1/generation", tags=["ai-generation"])
_TIMEOUT = httpx.Timeout(10.0, connect=3.0)


class GenerationManualReview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Literal["approve", "reject"]
    reason: str = Field(min_length=8, max_length=500)
    evidence_reference: str = Field(min_length=8, max_length=200)

class GenerationArtifactDeletionRetry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=8, max_length=500)


class GenerationJobCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    agent_id: uuid.UUID
    skill_id: uuid.UUID
    capability_id: str = Field(min_length=3, max_length=128, pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")
    prompt: str = Field(min_length=1, max_length=32768)
    max_output_tokens: int | None = Field(default=None, ge=1, le=16384)
    quoted_credits: int | None = Field(default=None, ge=1)
    quoted_policy_version: str | None = Field(default=None, min_length=1, max_length=80)
    quoted_tariff_version: str | None = Field(default=None, min_length=1, max_length=80)
    quoted_model_id: str | None = Field(default=None, min_length=1, max_length=128)
    knowledge_query: str | None = Field(default=None, min_length=1, max_length=4000)
    quoted_knowledge_context_sha256: str | None = Field(default=None, min_length=64, max_length=64)
    quoted_agent_snapshot_sha256: str | None = Field(default=None, min_length=64, max_length=64)
    quoted_skill_snapshot_sha256: str | None = Field(default=None, min_length=64, max_length=64)
    consumer_grant_id: uuid.UUID | None = None
    tool_inputs: dict[str, dict[str, Any]] = Field(default_factory=dict, max_length=5)
    quoted_tool_inputs_sha256: str | None = Field(default=None, min_length=64, max_length=64)


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
            headers = {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json", "Accept": "application/json"}
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


async def _load_generation_execution_snapshots(
    agent_id: uuid.UUID, skill_id: uuid.UUID, skill_version: int, *, token: str | None = None
) -> dict[str, Any]:
    """Load the exact immutable Skill version and current versioned Agent identity."""
    if token:
        agents = await user_db_request("GET", "ai_agents", token, params={
            "select": "id,version,display_name,description,persona,disclosure,boundaries",
            "id": f"eq.{agent_id}", "limit": "1",
        })
        versions = await user_db_request("GET", "agent_skill_versions", token, params={
            "select": "skill_id,agent_id,version,snapshot",
            "skill_id": f"eq.{skill_id}", "agent_id": f"eq.{agent_id}",
            "version": f"eq.{skill_version}", "limit": "1",
        })
    else:
        agents = await _admin_request("GET", "ai_agents", params={
            "select": "id,version,display_name,description,persona,disclosure,boundaries",
            "id": f"eq.{agent_id}", "limit": "1",
        })
        versions = await _admin_request("GET", "agent_skill_versions", params={
            "select": "skill_id,agent_id,version,snapshot",
            "skill_id": f"eq.{skill_id}", "agent_id": f"eq.{agent_id}",
            "version": f"eq.{skill_version}", "limit": "1",
        })
    if not agents or not versions:
        raise HTTPException(409, detail={
            "code": "GENERATION_EXECUTION_SNAPSHOT_UNAVAILABLE",
            "message": "Snapshot Agent atau Skill versi terpublikasi belum tersedia.",
        })
    agent = agents[0]
    skill_snapshot = versions[0].get("snapshot")
    if not isinstance(skill_snapshot, dict) or skill_snapshot.get("status") != "published" or int(skill_snapshot.get("version") or 0) != skill_version:
        raise HTTPException(409, detail={
            "code": "GENERATION_SKILL_SNAPSHOT_INVALID",
            "message": "Snapshot Skill tidak cocok dengan versi terpublikasi yang dipilih.",
        })
    agent_snapshot = {
        "id": str(agent["id"]),
        "version": int(agent["version"]),
        "display_name": str(agent.get("display_name") or ""),
        "description": str(agent.get("description") or ""),
        "persona": agent.get("persona") if isinstance(agent.get("persona"), dict) else {},
        "disclosure": str(agent.get("disclosure") or ""),
        "boundaries": agent.get("boundaries") if isinstance(agent.get("boundaries"), dict) else {},
    }
    if not skill_snapshot.get("instructions"):
        raise HTTPException(409, detail={
            "code": "GENERATION_SKILL_INSTRUCTIONS_MISSING",
            "message": "Skill terpublikasi belum memiliki instruksi eksekusi.",
        })
    tool_dependencies = skill_snapshot.get("tool_dependencies") or []
    if not isinstance(tool_dependencies, list) or any(not isinstance(item, str) or not item.strip() for item in tool_dependencies):
        raise HTTPException(409, detail={
            "code": "GENERATION_SKILL_TOOL_CONTRACT_INVALID",
            "message": "Daftar dependensi tool Skill tidak valid.",
        })
    try:
        validate_tool_dependencies(tool_dependencies)
    except (UnknownToolError, ValueError) as exc:
        raise HTTPException(409, detail={
            "code": "GENERATION_SKILL_TOOL_UNAVAILABLE",
            "message": "Satu atau lebih tool pada Skill belum tersedia atau kontraknya tidak valid.",
        }) from exc
    skill_budget = skill_snapshot.get("budget_limits") if isinstance(skill_snapshot.get("budget_limits"), dict) else {}
    max_tool_calls = skill_budget.get("max_tool_calls", max(1, len(tool_dependencies)))
    if not isinstance(max_tool_calls, int) or isinstance(max_tool_calls, bool) or max_tool_calls < len(tool_dependencies) or max_tool_calls > 5:
        raise HTTPException(409, detail={
            "code": "GENERATION_SKILL_TOOL_BUDGET_INVALID",
            "message": "Batas pemanggilan tool Skill tidak mencukupi atau melampaui batas runtime.",
        })
    return {
        "agent_snapshot": agent_snapshot,
        "skill_snapshot": skill_snapshot,
        "agent_snapshot_sha256": snapshot_sha256(agent_snapshot),
        "skill_snapshot_sha256": snapshot_sha256(skill_snapshot),
    }


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


def _generation_tool_inputs_enabled() -> bool:
    return os.getenv("ALLPHA_GENERATION_TOOL_INPUTS_ENABLED", "false").lower() == "true"


def _resolve_generation_tool_inputs(
    payload: GenerationJobCreate, skill_snapshot: dict[str, Any], *, external: bool
) -> dict[str, dict[str, Any]]:
    dependencies = skill_snapshot.get("tool_dependencies") or []
    if not isinstance(dependencies, list) or len(dependencies) > 5 or any(not isinstance(key, str) for key in dependencies):
        raise HTTPException(409, detail={"code": "GENERATION_SKILL_TOOL_CONTRACT_INVALID", "message": "Kontrak tool Skill tidak valid."})
    if dependencies and not _generation_tool_inputs_enabled():
        raise HTTPException(503, detail={"code": "GENERATION_TOOL_INPUT_SCHEMA_NOT_ACTIVE", "message": "Generation Skill tool inputs menunggu migration dan aktivasi schema WP-07."})
    try:
        validate_tool_dependencies(dependencies)
    except (UnknownToolError, ValueError) as exc:
        raise HTTPException(409, detail={"code": "GENERATION_SKILL_TOOL_CONTRACT_INVALID", "message": "Skill merujuk tool yang tidak terdaftar."}) from exc
    budget = skill_snapshot.get("budget_limits") if isinstance(skill_snapshot.get("budget_limits"), dict) else {}
    if dependencies:
        max_calls = budget.get("max_tool_calls", len(dependencies))
        max_runtime = budget.get("max_runtime_seconds", 30)
        if (not isinstance(max_calls, int) or isinstance(max_calls, bool) or max_calls < len(dependencies) or max_calls > 5
                or not isinstance(max_runtime, int) or isinstance(max_runtime, bool) or not 1 <= max_runtime <= 30):
            raise HTTPException(403, detail={"code": "GENERATION_SKILL_TOOL_BUDGET_INVALID", "message": "Budget tool Skill tidak memenuhi batas runtime."})
    provided = payload.tool_inputs if isinstance(payload.tool_inputs, dict) else {}
    if set(provided) - set(dependencies):
        raise HTTPException(422, detail={"code": "GENERATION_TOOL_INPUT_NOT_DECLARED", "message": "Tool input memuat tool di luar dependency Skill."})
    if external and set(provided) != set(dependencies):
        raise HTTPException(403, detail={"code": "EXTERNAL_CONSUMER_TOOL_INPUT_REQUIRED", "message": "External Consumer wajib mengirim typed input untuk setiap tool yang diberikan."})
    normalized: dict[str, dict[str, Any]] = {}
    for tool_key in dependencies:
        tool = get_tool(tool_key)
        if tool.execution_class != "pure":
            raise HTTPException(403, detail={"code": "GENERATION_TOOL_NOT_PURE", "message": "Generation hanya menerima deterministic pure tools."})
        raw = provided.get(tool_key)
        if raw is None:
            raw = {}
        if not isinstance(raw, dict):
            raise HTTPException(422, detail={"code": "GENERATION_TOOL_INPUT_INVALID", "message": "Setiap tool input harus berupa object."})
        value = dict(raw)
        properties = tool.input_schema.get("properties", {}) if isinstance(tool.input_schema, dict) else {}
        required = tool.input_schema.get("required", []) if isinstance(tool.input_schema, dict) else []
        if not external and "text" in properties and "text" in required and "text" not in value:
            value["text"] = payload.prompt
        try:
            validate_tool_input(tool_key, value)
        except ToolInputError as exc:
            raise HTTPException(422, detail={"code": "GENERATION_TOOL_INPUT_INVALID", "message": "Input tidak sesuai schema tool " + tool_key + "."}) from exc
        normalized[tool_key] = value
    serialized = json.dumps(normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    if len(serialized.encode("utf-8")) > 16_384:
        raise HTTPException(422, detail={"code": "GENERATION_TOOL_INPUT_TOO_LARGE", "message": "Gabungan tool input melebihi batas 16 KiB."})
    return normalized


def _generation_tool_context_bytes(tool_inputs: dict[str, dict[str, Any]]) -> int:
    if not tool_inputs:
        return 0
    serialized = json.dumps(tool_inputs, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return len(serialized.encode("utf-8")) + 16_384


async def _retrieve_generation_knowledge(
    request: Request, user: dict[str, Any], agent_id: uuid.UUID, query: str | None
) -> dict[str, Any]:
    if not query:
        return {}
    service = request_scoped_retrieval_service(request)
    if not isinstance(service, KnowledgeRetrievalService) or service.policy is None:
        raise HTTPException(503, detail={
            "code": "GENERATION_KNOWLEDGE_POLICY_UNAVAILABLE",
            "message": "Knowledge belum dapat digunakan karena policy dan retrieval ACL belum tersedia.",
        })
    owner_id = str(user["id"])
    trace_id = str(getattr(request.state, "request_id", "") or uuid.uuid4())
    try:
        allowed = await service.policy.allowed_sensitivities(owner_id=owner_id, agent_id=str(agent_id))
        if not allowed:
            raise KnowledgeRetrievalUnavailable("knowledge sensitivity policy is empty")
        hits = await service.retrieve(RetrievalRequest(
            owner_id=owner_id, agent_id=str(agent_id), query=query,
            allowed_sensitivities=allowed, limit=8, trace_id=trace_id,
        ))
    except KnowledgeAccessDenied as exc:
        raise HTTPException(403, detail={
            "code": "GENERATION_KNOWLEDGE_ACCESS_DENIED",
            "message": "Knowledge tidak dapat diakses oleh pemilik Agent ini.",
        }) from exc
    except KnowledgeRetrievalUnavailable as exc:
        raise HTTPException(503, detail={
            "code": "GENERATION_KNOWLEDGE_UNAVAILABLE",
            "message": "Knowledge ACL, consent, index, atau retrieval belum siap.",
        }) from exc
    context_parts: list[str] = []
    sources: list[dict[str, Any]] = []
    remaining = 24000
    for hit in hits:
        content = hit.content[:remaining]
        if not content:
            break
        context_parts.append(content)
        sources.append({
            "source_id": hit.source_id, "source_version": hit.source_version,
            "chunk_id": hit.chunk_id, "content_sha256": hit.content_sha256,
            "source_location": hit.source_location, "sensitivity": hit.sensitivity,
            "retrieval_method": hit.retrieval_method,
        })
        remaining -= len(content)
        if remaining <= 0:
            break
    context = "\n\n".join(context_parts)
    digest = hashlib.sha256(context.encode("utf-8")).hexdigest()
    resolved = getattr(service.policy, "last_resolved", None)
    if resolved is None:
        raise HTTPException(503, detail={
            "code": "GENERATION_KNOWLEDGE_POLICY_SNAPSHOT_MISSING",
            "message": "Snapshot policy Knowledge tidak dapat dikonfirmasi.",
        })
    snapshot_sha256 = hashlib.sha256(json.dumps({
        "context_sha256": digest, "sources": sources,
        "policy_version": resolved.policy_version, "consent_version": resolved.consent_version,
        "resolved_at_version": getattr(resolved, "resolved_at_version", resolved.policy_version),
    }, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()
    return {
        "context": context, "context_sha256": digest, "snapshot_sha256": snapshot_sha256, "sources": sources,
        "policy_version": resolved.policy_version,
        "consent_version": resolved.consent_version,
        "resolved_at_version": getattr(resolved, "resolved_at_version", resolved.policy_version),
        "trace_id": trace_id,
    }


async def _retrieve_external_generation_knowledge(
    owner_id: str, agent_id: uuid.UUID, query: str | None
) -> dict[str, Any]:
    if not query:
        return {}
    service = request_scoped_external_public_retrieval_service()
    if not isinstance(service, KnowledgeRetrievalService) or service.policy is None:
        raise HTTPException(503, detail={
            "code": "EXTERNAL_AGENT_KNOWLEDGE_POLICY_UNAVAILABLE",
            "message": "Policy consent dan retrieval Knowledge publik belum tersedia.",
        })
    trace_id = str(uuid.uuid4())
    try:
        allowed = await service.policy.allowed_sensitivities(owner_id=owner_id, agent_id=str(agent_id))
        if "public" not in allowed:
            raise KnowledgeAccessDenied("owner policy does not permit public Knowledge retrieval")
        hits = await service.retrieve(RetrievalRequest(
            owner_id=owner_id, agent_id=str(agent_id), query=query,
            allowed_sensitivities=["public"], limit=8, trace_id=trace_id,
        ))
    except KnowledgeAccessDenied as exc:
        raise HTTPException(403, detail={
            "code": "EXTERNAL_AGENT_KNOWLEDGE_ACCESS_DENIED",
            "message": "Consent, public sensitivity, atau grant Knowledge tidak mengizinkan retrieval.",
        }) from exc
    except KnowledgeRetrievalUnavailable as exc:
        raise HTTPException(503, detail={
            "code": "EXTERNAL_AGENT_KNOWLEDGE_UNAVAILABLE",
            "message": "Retrieval Knowledge publik belum siap atau provenance tidak valid.",
        }) from exc
    parts: list[str] = []
    sources: list[dict[str, Any]] = []
    remaining = 16000
    for hit in hits:
        content = hit.content[:remaining]
        if not content:
            break
        parts.append(content)
        sources.append({
            "source_id": hit.source_id, "source_version": hit.source_version,
            "chunk_id": hit.chunk_id, "content_sha256": hit.content_sha256,
            "source_location": hit.source_location, "sensitivity": "public",
            "retrieval_method": hit.retrieval_method,
        })
        remaining -= len(content)
        if remaining <= 0:
            break
    context = "\n\n".join(parts)
    resolved = getattr(service.policy, "last_resolved", None)
    if resolved is None:
        raise HTTPException(503, detail={"code":"EXTERNAL_AGENT_KNOWLEDGE_POLICY_SNAPSHOT_MISSING","message":"Snapshot policy Knowledge tidak tersedia."})
    context_sha256 = hashlib.sha256(context.encode("utf-8")).hexdigest()
    snapshot_sha256 = hashlib.sha256(json.dumps({
        "context_sha256": context_sha256, "sources": sources,
        "policy_version": resolved.policy_version, "consent_version": resolved.consent_version,
        "resolved_at_version": getattr(resolved, "resolved_at_version", resolved.policy_version),
        "scope": "public",
    }, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()
    return {
        "context": context, "context_sha256": context_sha256, "snapshot_sha256": snapshot_sha256,
        "sources": sources, "policy_version": resolved.policy_version,
        "consent_version": resolved.consent_version,
        "resolved_at_version": getattr(resolved, "resolved_at_version", resolved.policy_version),
        "trace_id": trace_id, "scope": "public",
    }


async def _require_generation_owner_reward_policy(policy_version: str, approval_reference: str) -> dict[str, Any]:
    rows = await _admin_request("GET", "credit_policy_versions", params={
        "select": "policy_version,approval_reference,configuration,status",
        "policy_version": f"eq.{policy_version}", "approval_reference": f"eq.{approval_reference}",
        "status": "eq.approved", "limit": "1",
    })
    if not rows:
        raise HTTPException(503, detail={"code": "GENERATION_OWNER_REWARD_POLICY_UNAVAILABLE", "message": "Generation eksternal belum dapat ditagihkan sebelum policy reward Agent owner disetujui."})
    config = rows[0].get("configuration") if isinstance(rows[0].get("configuration"), dict) else {}
    reward = config.get("generation_owner_reward") if isinstance(config.get("generation_owner_reward"), dict) else {}
    try:
        enabled = reward.get("enabled") is True
        approval = str(reward.get("approval_reference") or "")
        rate = int(reward.get("credits_per_usage_unit") or 0)
        maximum = int(reward.get("max_credits_per_job") or 0)
        global_max = int(config.get("max_grant_credits") or 0)
        allowed_types = config.get("allowed_grant_types") or []
    except (TypeError, ValueError):
        enabled, approval, rate, maximum, global_max, allowed_types = False, "", 0, 0, 0, []
    if (not enabled or approval != approval_reference or rate <= 0 or maximum <= 0
        or global_max < maximum or config.get("allow_grants") is not True
        or not isinstance(allowed_types, list) or "grant" not in allowed_types):
        raise HTTPException(503, detail={"code": "GENERATION_OWNER_REWARD_POLICY_UNAVAILABLE", "message": "Policy reward belum lengkap atau tidak mengizinkan settlement kredit untuk Agent owner."})
    return {"approval_reference": approval, "credits_per_usage_unit": rate, "max_credits_per_job": maximum}


async def _external_generation_context(
    payload: GenerationJobCreate, requester_id: str, router_instance: Any
) -> dict[str, Any]:
    if payload.consumer_grant_id is None:
        raise HTTPException(422, detail={"code": "CONSUMER_GRANT_REQUIRED", "message": "Grant pemilik Agent wajib dipilih."})
    agent_rows = await _admin_request("GET", "ai_agents", params={
        "select": "id,version,status,visibility,display_name",
        "id": f"eq.{payload.agent_id}", "status": "eq.active", "visibility": "eq.public", "limit": "1",
    })
    owners = await _admin_request("GET", "agent_ownerships", params={
        "select": "owner_user_id,agent_id,ownership_role,status",
        "agent_id": f"eq.{payload.agent_id}", "ownership_role": "eq.owner", "status": "eq.active", "limit": "1",
    })
    skills = await _admin_request("GET", "agent_skills", params={
        "select": "id,agent_id,version,status",
        "id": f"eq.{payload.skill_id}", "agent_id": f"eq.{payload.agent_id}", "status": "eq.published", "limit": "1",
    })
    capabilities = await _admin_request("GET", "agent_capabilities", params={
        "select": "capability_key,status", "agent_id": f"eq.{payload.agent_id}",
        "capability_key": f"eq.{payload.capability_id}", "status": "eq.approved", "limit": "1",
    })
    if not agent_rows or not owners or not skills or not capabilities:
        raise HTTPException(404, detail={"code": "PUBLIC_AGENT_GENERATION_TARGET_NOT_FOUND", "message": "Agent publik, Skill, atau capability tidak tersedia."})
    agent, owner, skill = agent_rows[0], owners[0], skills[0]
    snapshots = await _load_generation_execution_snapshots(
        payload.agent_id, payload.skill_id, int(skill["version"])
    )
    if int(snapshots["agent_snapshot"]["version"]) != int(agent["version"]):
        raise HTTPException(409, detail={"code":"GENERATION_AGENT_SNAPSHOT_STALE","message":"Versi Agent berubah. Minta quote baru."})
    owner_id = str(owner["owner_user_id"])
    if owner_id == requester_id:
        raise HTTPException(422, detail={"code": "OWNED_AGENT_GRANT_NOT_REQUIRED", "message": "Gunakan jalur Agent milik sendiri."})
    try:
        await router_instance.preflight("public")
        route = router_instance.route_snapshot_for("public")
        budget = await ConsumerBudgetReservation.from_environment(
            expected_cost_unit=str(route["cost_unit"]),
            expected_pricing_version=str(route["pricing_version"]),
            expected_max_cost_microunits=int(route["max_cost_microunits"]),
            policy_key="consumer_agent_generation",
            expected_usage_unit="tokens_total",
        )
        runtime_policy_version = router_instance.policy_version_for("public")
        dependencies = snapshots["skill_snapshot"].get("tool_dependencies") or []
        if dependencies and os.getenv("ALLPHA_EXTERNAL_CONSUMER_TOOL_GRANTS_ENABLED", "false").lower() != "true":
            raise HTTPException(503, detail={"code": "EXTERNAL_CONSUMER_TOOL_GRANTS_NOT_ACTIVE", "message": "Per-tool Consumer Grant menunggu migration dan aktivasi schema WP-07."})
        grant_store = AgentConsumerGrantStore.from_environment()
        if dependencies:
            skill_budget = snapshots["skill_snapshot"].get("budget_limits") if isinstance(snapshots["skill_snapshot"].get("budget_limits"), dict) else {}
            max_tool_calls = min(5, int(skill_budget.get("max_tool_calls") or len(dependencies)))
            max_tool_runtime = min(30, int(skill_budget.get("max_runtime_seconds") or 30))
            if max_tool_calls < len(dependencies):
                raise HTTPException(403, detail={"code": "EXTERNAL_CONSUMER_SKILL_TOOL_BUDGET_INVALID", "message": "Budget Skill tidak cukup untuk seluruh tool dependency."})
            grant = await grant_store.resolve(
                requester_id=requester_id, owner_id=owner_id, agent_id=str(payload.agent_id),
                agent_version=int(agent["version"]), skill_id=str(payload.skill_id),
                skill_version=int(skill["version"]), runtime_policy_version=runtime_policy_version,
                policy_snapshot=budget.policy_snapshot(), required_scope="tool_invoke",
                allowed_tool_keys=dependencies, max_tool_calls=max_tool_calls,
                max_tool_runtime_seconds=max_tool_runtime,
            )
        else:
            grant = await grant_store.resolve(
                requester_id=requester_id, owner_id=owner_id, agent_id=str(payload.agent_id),
                agent_version=int(agent["version"]), skill_id=str(payload.skill_id),
                skill_version=int(skill["version"]), runtime_policy_version=runtime_policy_version,
                policy_snapshot=budget.policy_snapshot(), required_scope="generation_invoke",
            )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(503, detail={"code": "EXTERNAL_AGENT_GENERATION_POLICY_UNAVAILABLE", "message": "Tarif, grant, atau policy generation Agent eksternal belum tersedia."}) from exc
    if not grant or str(grant.get("id")) != str(payload.consumer_grant_id):
        raise HTTPException(403, detail={"code": "EXTERNAL_AGENT_GENERATION_GRANT_DENIED", "message": "Grant generation tidak aktif, tidak cocok, atau telah dicabut."})
    if payload.knowledge_query and "knowledge_public_read" not in (grant.get("granted_scopes") or []):
        raise HTTPException(403, detail={"code": "EXTERNAL_AGENT_KNOWLEDGE_SCOPE_DENIED", "message": "Grant tidak mengizinkan Knowledge publik Agent."})
    payer_id = budget.billing_account_id(requester_id=requester_id, owner_id=owner_id)
    owner_reward_policy = None
    if payer_id != owner_id:
        owner_reward_policy = await _require_generation_owner_reward_policy(
            budget.policy_version, budget.approval_reference
        )
    subscriptions = await _admin_request("GET", "billing_subscriptions", params={
        "select": "id,owner_user_id,entitlement_version,status,current_period_end",
        "owner_user_id": f"eq.{payer_id}", "status": "eq.active",
        "entitlement_version": f"eq.{budget.entitlement_version}",
        "current_period_end": "gt." + datetime.now(timezone.utc).isoformat(), "limit": "1",
    })
    if not subscriptions:
        raise HTTPException(403, detail={"code": "EXTERNAL_AGENT_PAYER_ENTITLEMENT_REQUIRED", "message": "Akun pembayar tidak memiliki entitlement generation aktif."})
    return {
        "agent": agent, "owner_id": owner_id, "skill": skill, "grant": grant,
        "budget": budget, "route": route, "payer_user_id": payer_id,
        "runtime_policy_version": runtime_policy_version,
        "owner_reward_policy": owner_reward_policy,
        **snapshots,
    }


@router.get("/agents")
async def list_generation_agents(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    """List only current, public Agent grants that explicitly permit generation."""
    now = datetime.now(timezone.utc).isoformat()
    grant_select = "id,owner_user_id,agent_id,agent_version,skill_id,skill_version,capability_id,granted_scopes,expires_at,status"
    if _generation_tool_inputs_enabled() and os.getenv("ALLPHA_EXTERNAL_CONSUMER_TOOL_GRANTS_ENABLED", "false").lower() == "true":
        grant_select += ",allowed_tool_keys,max_tool_calls,max_tool_runtime_seconds"
    grants = await _admin_request("GET", "agent_consumer_grants", params={
        "select": grant_select,
        "requester_user_id": f"eq.{user['id']}", "status": "eq.active",
        "granted_scopes": "cs.{generation_invoke}",
        "or": f"(expires_at.is.null,expires_at.gt.{now})",
        "order": "granted_at.desc", "limit": "100",
    })
    items: list[dict[str, Any]] = []
    for grant in grants or []:
        agents = await _admin_request("GET", "ai_agents", params={
            "select": "id,version,status,visibility,display_name,description",
            "id": f"eq.{grant['agent_id']}", "status": "eq.active", "visibility": "eq.public", "limit": "1",
        })
        skills = await _admin_request("GET", "agent_skills", params={
            "select": "id,agent_id,version,status,name,display_name,tool_dependencies,budget_limits",
            "id": f"eq.{grant['skill_id']}", "agent_id": f"eq.{grant['agent_id']}", "status": "eq.published", "limit": "1",
        })
        caps = await _admin_request("GET", "agent_capabilities", params={
            "select": "capability_key,status", "agent_id": f"eq.{grant['agent_id']}",
            "capability_key": f"eq.{grant['capability_id']}", "status": "eq.approved", "limit": "1",
        })
        if not agents or not skills:
            continue
        if int(agents[0].get("version") or 0) != int(grant.get("agent_version") or -1):
            continue
        if int(skills[0].get("version") or 0) != int(grant.get("skill_version") or -1):
            continue
        dependencies = skills[0].get("tool_dependencies") if isinstance(skills[0].get("tool_dependencies"), list) else []
        allowed_tools = grant.get("allowed_tool_keys") if isinstance(grant.get("allowed_tool_keys"), list) else []
        if dependencies and ("tool_invoke" not in (grant.get("granted_scopes") or []) or set(allowed_tools) != set(dependencies)):
            continue
        if not dependencies and (allowed_tools or "tool_invoke" in (grant.get("granted_scopes") or [])):
            continue
        tool_contracts = []
        try:
            validate_tool_dependencies(dependencies)
            for tool_key in dependencies:
                definition = get_tool(tool_key)
                if definition.execution_class != "pure" or tool_key not in allowed_tools:
                    tool_contracts = []
                    break
                tool_contracts.append(definition.public_contract())
        except (UnknownToolError, ValueError):
            continue
        items.append({
            "agent": agents[0], "owner_user_id": grant["owner_user_id"],
            "skill": skills[0], "capabilities": caps or [],
            "consumer_grant_id": grant["id"],
            "granted_scopes": grant.get("granted_scopes") or [],
            "allowed_tool_keys": allowed_tools,
            "max_tool_calls": grant.get("max_tool_calls", 0),
            "max_tool_runtime_seconds": grant.get("max_tool_runtime_seconds", 0),
            "tool_contracts": tool_contracts,
        })
    return {"items": items}


@router.post("/quote")
async def quote_generation_job(
    payload: GenerationJobCreate,
    request: Request,
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    """Return a short-lived estimate; job creation independently revalidates every input and tariff."""
    token = getattr(request.state, "supabase_access_token", None)
    if not token:
        raise HTTPException(401, detail={"code": "AUTH_REQUIRED", "message": "Sesi login diperlukan."})
    router_instance = getattr(request.app.state, "text_generation_router", None)
    if payload.consumer_grant_id is not None:
        if router_instance is None:
            raise HTTPException(503, detail={"code": "MODEL_ROUTE_UNAVAILABLE", "message": "AI Model Router belum siap."})
        external = await _external_generation_context(payload, str(user["id"]), router_instance)
        tool_inputs = _resolve_generation_tool_inputs(payload, external["skill_snapshot"], external=True)
        tool_inputs_sha256 = snapshot_sha256(tool_inputs)
        route = external["route"]
        budget: ConsumerBudgetReservation = external["budget"]
        max_output_tokens = payload.max_output_tokens or router_instance.max_output_tokens_for("public")
        if max_output_tokens > router_instance.max_output_tokens_for("public"):
            raise HTTPException(422, detail={"code": "OUTPUT_TOKEN_LIMIT_EXCEEDED", "message": "Batas output melebihi policy model publik."})
        knowledge_snapshot = await _retrieve_external_generation_knowledge(
            external["owner_id"], payload.agent_id, payload.knowledge_query
        )
        prompt_bytes = generation_prompt_size_bytes(
            prompt=payload.prompt, agent_snapshot=external["agent_snapshot"],
            skill_snapshot=external["skill_snapshot"], knowledge_snapshot=knowledge_snapshot,
        ) + _generation_tool_context_bytes(tool_inputs)
        if prompt_bytes > int(route["max_prompt_bytes"]):
            raise HTTPException(422, detail={"code": "PROMPT_EXCEEDS_APPROVED_BOUND", "message": "Prompt dan Knowledge melebihi batas byte model publik."})
        estimated_usage = prompt_bytes + max_output_tokens
        if estimated_usage > budget.max_usage_units:
            raise HTTPException(422, detail={"code": "CONSUMER_USAGE_LIMIT_EXCEEDED", "message": "Permintaan melebihi batas usage yang disetujui pemilik Agent."})
        if budget.capability_id != payload.capability_id:
            raise HTTPException(403, detail={"code": "CONSUMER_CAPABILITY_MISMATCH", "message": "Capability tidak cocok dengan grant generation."})
        estimated_credits = estimated_usage * budget.credits_per_usage_unit
        return {
            "quote_id": str(uuid.uuid4()),
            "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(),
            "estimated_credits": estimated_credits, "estimated_usage_units": estimated_usage,
            "usage_unit": budget.usage_unit, "provider_id": route["provider_id"],
            "model_id": route["model_id"], "model_version": route["model_version"],
            "policy_version": budget.policy_version, "tariff_version": budget.tariff_version,
            "entitlement_version": budget.entitlement_version,
            "consumer_grant_id": str(external["grant"]["id"]),
            "payer_role": budget.payer_role,
            "knowledge_context_sha256": knowledge_snapshot.get("snapshot_sha256"),
            "knowledge_source_count": len(knowledge_snapshot.get("sources") or []),
            "agent_snapshot_sha256": external["agent_snapshot_sha256"],
            "skill_snapshot_sha256": external["skill_snapshot_sha256"],
            "tool_inputs_sha256": tool_inputs_sha256,
        }
    if router_instance is None:
        raise HTTPException(503, detail={"code": "MODEL_ROUTE_UNAVAILABLE", "message": "AI Model Router belum siap."})
    try:
        await router_instance.preflight("private")
        route = router_instance.route_snapshot_for("private")
        router_max_tokens = router_instance.max_output_tokens_for("private")
    except Exception as exc:
        raise HTTPException(503, detail={"code": "MODEL_ROUTE_NOT_READY", "message": "Model, cost policy, atau metering belum disetujui."}) from exc
    knowledge_snapshot = await _retrieve_generation_knowledge(request, user, payload.agent_id, payload.knowledge_query)
    max_output_tokens = payload.max_output_tokens or router_max_tokens
    if max_output_tokens > router_max_tokens:
        raise HTTPException(422, detail={"code": "OUTPUT_TOKEN_LIMIT_EXCEEDED", "message": "Batas output melebihi policy model aktif."})
    skill_rows = await user_db_request("GET", "agent_skills", token, params={
        "select": "id,agent_id,version,status", "id": f"eq.{payload.skill_id}",
        "agent_id": f"eq.{payload.agent_id}", "status": "eq.published", "limit": "1",
    })
    if not skill_rows:
        raise HTTPException(404, detail={"code": "PUBLISHED_SKILL_NOT_FOUND", "message": "Skill tidak ditemukan atau belum dipublikasikan."})
    snapshots = await _load_generation_execution_snapshots(
        payload.agent_id, payload.skill_id, int(skill_rows[0]["version"]), token=token
    )
    tool_inputs = _resolve_generation_tool_inputs(payload, snapshots["skill_snapshot"], external=False)
    tool_inputs_sha256 = snapshot_sha256(tool_inputs)
    prompt_bytes = generation_prompt_size_bytes(
        prompt=payload.prompt, agent_snapshot=snapshots["agent_snapshot"],
        skill_snapshot=snapshots["skill_snapshot"], knowledge_snapshot=knowledge_snapshot,
    ) + _generation_tool_context_bytes(tool_inputs)
    if prompt_bytes > int(route["max_prompt_bytes"]):
        raise HTTPException(422, detail={"code": "PROMPT_EXCEEDS_APPROVED_BOUND", "message": "Prompt, Agent, Skill, dan Knowledge context melebihi batas byte yang disetujui."})
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
        raise HTTPException(403, detail={"code": "PREMIUM_ENTITLEMENT_REQUIRED", "message": "AI generation memerlukan Premium entitlement aktif."})
    entitlement_version = str(subscriptions[0].get("entitlement_version") or "")
    if not entitlement_version:
        raise HTTPException(503, detail={"code": "ENTITLEMENT_VERSION_MISSING", "message": "Versi entitlement belum dikonfigurasi."})
    policy_row, policy_config, entitlement = await _approved_credit_policy(entitlement_version)
    capability = (policy_config.get("capabilities") or {}).get(payload.capability_id)
    if not isinstance(capability, dict):
        raise HTTPException(503, detail={"code": "CAPABILITY_TARIFF_UNAVAILABLE", "message": "Tarif capability belum disetujui."})
    usage_unit = str(capability.get("usage_unit") or "")
    cost_unit = str(capability.get("cost_unit") or "")
    pricing_version = str(capability.get("cost_pricing_version") or "")
    tariff_version = str(capability.get("tariff_version") or "")
    credits_per_usage_unit = int(capability.get("credits_per_usage_unit") or 0)
    max_cost = int(capability.get("max_cost_microunits") if capability.get("max_cost_microunits") is not None else -1)
    if (usage_unit != "tokens_total" or not tariff_version or credits_per_usage_unit <= 0
        or cost_unit != route.get("cost_unit") or pricing_version != route.get("pricing_version")
        or max_cost != int(route.get("max_cost_microunits") or -1)):
        raise HTTPException(503, detail={"code": "MODEL_CREDIT_POLICY_MISMATCH", "message": "Tarif kredit tidak cocok dengan route Model Router."})
    estimated_usage = prompt_bytes + max_output_tokens
    estimated_credits = estimated_usage * credits_per_usage_unit
    max_credits = int(entitlement.get("max_credits_per_request") or 0)
    if max_credits <= 0 or estimated_credits > max_credits:
        raise HTTPException(422, detail={"code": "REQUEST_EXCEEDS_ENTITLEMENT_LIMIT", "message": "Estimasi penggunaan melebihi batas kredit per permintaan."})
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)
    return {
        "quote_id": str(uuid.uuid4()), "expires_at": expires_at.isoformat(),
        "estimated_credits": estimated_credits, "estimated_usage_units": estimated_usage,
        "usage_unit": usage_unit, "provider_id": route["provider_id"],
        "model_id": route["model_id"], "model_version": route["model_version"],
        "policy_version": policy_row["policy_version"], "tariff_version": tariff_version,
        "entitlement_version": entitlement_version,
        "knowledge_context_sha256": knowledge_snapshot.get("snapshot_sha256"),
        "knowledge_source_count": len(knowledge_snapshot.get("sources") or []),
        "knowledge_policy_version": knowledge_snapshot.get("policy_version"),
        "agent_snapshot_sha256": snapshots["agent_snapshot_sha256"],
        "skill_snapshot_sha256": snapshots["skill_snapshot_sha256"],
        "tool_inputs_sha256": tool_inputs_sha256,
    }


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
    router_instance = getattr(request.app.state, "text_generation_router", None)
    if router_instance is None:
        raise HTTPException(503, detail={"code": "MODEL_ROUTE_UNAVAILABLE", "message": "AI Model Router belum memiliki provider, model, policy, dan metering yang disetujui."})
    if payload.consumer_grant_id is not None:
        external = await _external_generation_context(payload, str(user["id"]), router_instance)
        tool_inputs = _resolve_generation_tool_inputs(payload, external["skill_snapshot"], external=True)
        tool_inputs_sha256 = snapshot_sha256(tool_inputs)
        if tool_inputs and payload.quoted_tool_inputs_sha256 != tool_inputs_sha256:
            raise HTTPException(409, detail={"code": "GENERATION_TOOL_INPUT_QUOTE_STALE", "message": "Tool input berubah. Minta quote generation baru."})
        route = external["route"]
        budget: ConsumerBudgetReservation = external["budget"]
        max_output_tokens = payload.max_output_tokens or router_instance.max_output_tokens_for("public")
        if max_output_tokens > router_instance.max_output_tokens_for("public"):
            raise HTTPException(422, detail={"code": "OUTPUT_TOKEN_LIMIT_EXCEEDED", "message": "Batas output melebihi policy model publik."})
        knowledge_snapshot = await _retrieve_external_generation_knowledge(
            external["owner_id"], payload.agent_id, payload.knowledge_query
        )
        if payload.knowledge_query and payload.quoted_knowledge_context_sha256 != knowledge_snapshot.get("snapshot_sha256"):
            raise HTTPException(409, detail={"code":"GENERATION_KNOWLEDGE_QUOTE_STALE","message":"Knowledge publik atau policy berubah. Minta quote baru."})
        if (payload.quoted_agent_snapshot_sha256 != external["agent_snapshot_sha256"]
            or payload.quoted_skill_snapshot_sha256 != external["skill_snapshot_sha256"]):
            raise HTTPException(409, detail={"code":"GENERATION_SKILL_QUOTE_STALE","message":"Versi Agent atau Skill berubah. Minta quote generation baru."})
        prompt_bytes = generation_prompt_size_bytes(
            prompt=payload.prompt, agent_snapshot=external["agent_snapshot"],
            skill_snapshot=external["skill_snapshot"], knowledge_snapshot=knowledge_snapshot,
        ) + _generation_tool_context_bytes(tool_inputs)
        if prompt_bytes > int(route["max_prompt_bytes"]):
            raise HTTPException(422, detail={"code": "PROMPT_EXCEEDS_APPROVED_BOUND", "message": "Prompt, Agent, Skill, dan Knowledge context melebihi batas byte model publik."})
        estimated_usage_units = prompt_bytes + max_output_tokens
        if estimated_usage_units > budget.max_usage_units:
            raise HTTPException(422, detail={"code": "CONSUMER_USAGE_LIMIT_EXCEEDED", "message": "Permintaan melebihi batas usage yang disetujui pemilik Agent."})
        if budget.capability_id != payload.capability_id:
            raise HTTPException(403, detail={"code": "CONSUMER_CAPABILITY_MISMATCH", "message": "Capability tidak cocok dengan grant generation."})
        credits_to_reserve = estimated_usage_units * budget.credits_per_usage_unit
        if payload.quoted_credits is not None and payload.quoted_credits != credits_to_reserve:
            raise HTTPException(409, detail={"code": "GENERATION_QUOTE_STALE", "message": "Estimasi AI Credits berubah. Minta quote baru."})
        if payload.quoted_policy_version and payload.quoted_policy_version != budget.policy_version:
            raise HTTPException(409, detail={"code": "GENERATION_QUOTE_STALE", "message": "Policy generation berubah. Minta quote baru."})
        if payload.quoted_tariff_version and payload.quoted_tariff_version != budget.tariff_version:
            raise HTTPException(409, detail={"code": "GENERATION_QUOTE_STALE", "message": "Tarif generation berubah. Minta quote baru."})
        if payload.quoted_model_id and payload.quoted_model_id != str(route["model_id"]):
            raise HTTPException(409, detail={"code": "GENERATION_QUOTE_STALE", "message": "Model generation berubah. Minta quote baru."})
        if not budget.policy.allow_success_settlement:
            raise HTTPException(503, detail={"code": "SETTLEMENT_POLICY_NOT_APPROVED", "message": "Settlement generation belum disetujui."})
        task_id = str(uuid.uuid4())
        trace_id = str(uuid.uuid4())
        skill = external["skill"]
        command = {
            "owner_user_id": str(user["id"]),
            "agent_owner_user_id": external["owner_id"],
            "payer_user_id": external["payer_user_id"],
            "consumer_grant_id": str(external["grant"]["id"]),
            "payer_role": budget.payer_role,
            "runtime_policy_version": external["runtime_policy_version"],
            "agent_version": external["agent_snapshot"]["version"],
            "agent_snapshot_sha256": external["agent_snapshot_sha256"],
            "skill_snapshot_sha256": external["skill_snapshot_sha256"],
            "agent_id": str(payload.agent_id), "skill_id": str(payload.skill_id),
            "source_version": int(skill["version"]), "capability_id": payload.capability_id,
            "sensitivity": "public", "task_id": task_id, "trace_id": trace_id,
            "idempotency_key": idempotency_key, "prompt": payload.prompt,
            "prompt_sha256": prompt_hash, "knowledge_snapshot": knowledge_snapshot,
            "tool_inputs": tool_inputs,
            "knowledge_context_sha256": knowledge_snapshot.get("snapshot_sha256"), "max_output_tokens": max_output_tokens,
            "timeout_ms": min(120000, max(100, int(route.get("max_latency_ms") or 30000))),
            "estimated_usage_units": estimated_usage_units, "usage_unit": budget.usage_unit,
            "estimated_cost_microunits": budget.max_cost_microunits, "cost_unit": budget.cost_unit,
            "credits_to_reserve": credits_to_reserve, "credits_per_usage_unit": budget.credits_per_usage_unit,
            "credit_scheme_version": budget.credit_scheme_version, "tariff_version": budget.tariff_version,
            "entitlement_version": budget.entitlement_version, "policy_version": budget.policy_version,
            "policy_approval_reference": budget.approval_reference,
            "allow_success_settlement": budget.policy.allow_success_settlement,
            "allow_definitive_failure_release": budget.policy.allow_definitive_failure_release,
            "allow_partial_settlement": budget.policy.allow_partial_settlement,
            "provider_id": route["provider_id"], "model_id": route["model_id"],
            "model_version": route["model_version"], "pricing_version": budget.pricing_version,
            "max_cost_microunits": budget.max_cost_microunits,
        }
        created = await _rpc("generation_create_job_with_tool_inputs" if tool_inputs else "generation_create_job", command)
        if not isinstance(created, dict) or not created.get("job_id"):
            raise HTTPException(503, detail={"code": "GENERATION_JOB_NOT_CONFIRMED", "message": "Generation Job eksternal belum dapat dikonfirmasi."})
        return {
            "job_id": created["job_id"], "task_id": created.get("task_id"),
            "status": created.get("status"), "idempotent_replay": bool(created.get("idempotent_replay")),
            "reserved_credits": created.get("reserved_credits"),
            "consumer_grant_id": str(external["grant"]["id"]), "payer_role": budget.payer_role,
        }
    try:
        await router_instance.preflight("private")
        route = router_instance.route_snapshot_for("private")
        router_max_tokens = router_instance.max_output_tokens_for("private")
    except Exception as exc:
        raise HTTPException(503, detail={"code": "MODEL_ROUTE_NOT_READY", "message": "AI generation fail-closed karena route, runtime policy, atau model-cost registry belum siap."}) from exc

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
    snapshots = await _load_generation_execution_snapshots(
        payload.agent_id, payload.skill_id, int(skill["version"]), token=token
    )
    tool_inputs = _resolve_generation_tool_inputs(payload, snapshots["skill_snapshot"], external=False)
    tool_inputs_sha256 = snapshot_sha256(tool_inputs)
    if tool_inputs and payload.quoted_tool_inputs_sha256 != tool_inputs_sha256:
        raise HTTPException(409, detail={"code": "GENERATION_TOOL_INPUT_QUOTE_STALE", "message": "Tool input berubah. Minta quote generation baru."})
    if (payload.quoted_agent_snapshot_sha256 != snapshots["agent_snapshot_sha256"]
        or payload.quoted_skill_snapshot_sha256 != snapshots["skill_snapshot_sha256"]):
        raise HTTPException(409, detail={"code":"GENERATION_SKILL_QUOTE_STALE","message":"Versi Agent atau Skill berubah. Minta quote generation baru."})
    knowledge_snapshot = await _retrieve_generation_knowledge(request, user, payload.agent_id, payload.knowledge_query)
    if payload.knowledge_query and payload.quoted_knowledge_context_sha256 != knowledge_snapshot.get("snapshot_sha256"):
        raise HTTPException(409, detail={"code": "GENERATION_KNOWLEDGE_QUOTE_STALE", "message": "Sumber atau policy Knowledge berubah. Minta quote baru."})
    prompt_bytes = generation_prompt_size_bytes(
        prompt=payload.prompt, agent_snapshot=snapshots["agent_snapshot"],
        skill_snapshot=snapshots["skill_snapshot"], knowledge_snapshot=knowledge_snapshot,
    ) + _generation_tool_context_bytes(tool_inputs)
    if prompt_bytes > int(route["max_prompt_bytes"]):
        raise HTTPException(422, detail={"code":"PROMPT_EXCEEDS_APPROVED_BOUND","message":"Prompt, Agent, Skill, dan Knowledge context melebihi batas byte model."})
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
    if payload.quoted_credits is not None and payload.quoted_credits != credits_to_reserve:
        raise HTTPException(409, detail={"code": "GENERATION_QUOTE_STALE", "message": "Estimasi AI Credits berubah. Minta quote baru sebelum melanjutkan."})
    if ((payload.quoted_policy_version is not None and payload.quoted_policy_version != str(policy_row["policy_version"])) or (payload.quoted_tariff_version is not None and payload.quoted_tariff_version != tariff_version) or (payload.quoted_model_id is not None and payload.quoted_model_id != str(route["model_id"]))):
        raise HTTPException(409, detail={"code": "GENERATION_QUOTE_STALE", "message": "Model atau kebijakan tarif berubah. Minta quote baru sebelum melanjutkan."})
    max_credits = int(entitlement.get("max_credits_per_request") or 0)
    if max_credits <= 0 or credits_to_reserve > max_credits:
        raise HTTPException(422, detail={"code": "REQUEST_EXCEEDS_ENTITLEMENT_LIMIT", "message": "Estimasi penggunaan melebihi batas AI Credit per permintaan Premium."})
    timeout_ms = min(120000, max(100, int(route.get("max_latency_ms") or 30000)))
    task_id = str(uuid.uuid4())
    trace_id = str(uuid.uuid4())
    command = {
        "owner_user_id": str(user["id"]),
        "agent_owner_user_id": str(user["id"]),
        "payer_user_id": str(user["id"]),
        "consumer_grant_id": None,
        "payer_role": "agent_owner",
        "runtime_policy_version": str(route["policy_version"]),
        "agent_version": snapshots["agent_snapshot"]["version"],
        "agent_snapshot_sha256": snapshots["agent_snapshot_sha256"],
        "skill_snapshot_sha256": snapshots["skill_snapshot_sha256"],
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
        "tool_inputs": tool_inputs,
        "knowledge_snapshot": knowledge_snapshot,
        "knowledge_context_sha256": knowledge_snapshot.get("snapshot_sha256"),
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
    created = await _rpc("generation_create_job_with_tool_inputs" if tool_inputs else "generation_create_job", command)
    if not isinstance(created, dict) or not created.get("job_id"):
        raise HTTPException(503, detail={"code": "GENERATION_JOB_NOT_CONFIRMED", "message": "Generation job dan AI Credit reservation belum terkonfirmasi."})
    return {"job_id": created["job_id"], "task_id": created.get("task_id"), "status": created.get("status"),
        "idempotent_replay": bool(created.get("idempotent_replay")), "reserved_credits": created.get("reserved_credits")}


@router.get("/jobs")
async def list_generation_jobs(limit: int = 20, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    bounded = min(max(1, limit), 50)
    rows = await _admin_request("GET", "generation_jobs", params={
        "select": "id,task_id,capability_id,status,moderation_status,credits_to_reserve,owner_reward_status,dm_conversation_id,created_at,started_at,completed_at,error_code",
        "owner_user_id": f"eq.{user['id']}", "order": "created_at.desc", "limit": str(bounded),
    })
    return {"items": rows or [], "limit": bounded}


@router.post("/jobs/{job_id}/cancel")
async def cancel_generation_job(job_id: uuid.UUID, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    """Cancel only a queued job, before a worker can invoke the provider.

    Running jobs are deliberately not force-cancelled: the provider may already
    have accepted the request, so its cost/outcome must be reconciled instead.
    """
    try:
        result = await _rpc("generation_cancel_queued_job", {
            "job_id": str(job_id),
            "owner_user_id": str(user["id"]),
            "reason_code": "cancelled_by_requester",
        })
    except HTTPException as exc:
        if exc.status_code == 409:
            raise HTTPException(
                409,
                detail={
                    "code": "GENERATION_JOB_NOT_CANCELLABLE",
                    "message": "Job sudah mulai diproses atau tidak lagi berada dalam antrean. Hasil provider tidak dapat dibatalkan secara aman.",
                },
            ) from exc
        raise
    if not isinstance(result, dict) or str(result.get("job_id")) != str(job_id):
        raise HTTPException(503, detail={"code": "GENERATION_CANCEL_UNCONFIRMED", "message": "Status pembatalan belum dapat dikonfirmasi."})
    return result


async def _signed_generation_artifact(bucket: str, path: str, *, expires_in: int = 60) -> str:
    url, key = _db_config()
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            response = await client.post(
                f"{url}/storage/v1/object/sign/{bucket}/{path}",
                headers={"apikey":key,"Authorization":f"Bearer {key}","Content-Type":"application/json"},
                json={"expiresIn":max(60,min(expires_in,600))},
            )
            response.raise_for_status()
            payload=response.json()
            signed=payload.get("signedURL") or payload.get("signedUrl")
            if not isinstance(signed,str) or not signed:
                raise ValueError("signed URL missing")
            return signed if signed.startswith("http") else url + signed
    except (httpx.HTTPError,ValueError) as exc:
        raise HTTPException(503,detail={"code":"GENERATION_ARTIFACT_UNAVAILABLE","message":"Artefak privat belum dapat diakses."}) from exc


@router.get("/jobs/{job_id}/artifact")
async def get_generation_artifact(job_id: uuid.UUID, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    rows=await _admin_request("GET","generation_jobs",params={
        "select":"id,owner_user_id,status,artifact_bucket,artifact_path,moderation_status,artifact_deletion_requested_at,artifact_deleted_at",
        "id":f"eq.{job_id}","owner_user_id":f"eq.{user['id']}","limit":"1",
    })
    if not rows:
        raise HTTPException(404,detail={"code":"GENERATION_JOB_NOT_FOUND","message":"Generation job tidak ditemukan."})
    job=rows[0]
    if job.get("artifact_deleted_at"):
        raise HTTPException(410,detail={"code":"GENERATION_ARTIFACT_DELETED","message":"Artefak privat sudah dihapus oleh pemiliknya."})
    if job.get("artifact_deletion_requested_at"):
        raise HTTPException(409,detail={"code":"GENERATION_ARTIFACT_DELETION_PENDING","message":"Penghapusan artefak sedang diproses; akses telah dinonaktifkan."})
    if job.get("status")!="succeeded" or job.get("moderation_status")!="approved" or job.get("artifact_bucket")!="generation-artifacts" or not job.get("artifact_path"):
        raise HTTPException(409,detail={"code":"GENERATION_ARTIFACT_NOT_READY","message":"Artefak belum selesai dimoderasi dan dipublikasikan secara privat."})
    signed=await _signed_generation_artifact(job["artifact_bucket"],job["artifact_path"])
    return {"job_id":str(job_id),"url":signed,"expires_in_seconds":60,"visibility":"private"}


@router.delete("/jobs/{job_id}/artifact")
async def request_generation_artifact_deletion(
    job_id: uuid.UUID,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    if not idempotency_key or not 8 <= len(idempotency_key) <= 160:
        raise HTTPException(400, detail={"code":"IDEMPOTENCY_KEY_REQUIRED","message":"Idempotency-Key 8–160 karakter wajib dikirim."})
    rows = await _admin_request("GET", "generation_jobs", params={
        "select":"id,owner_user_id,status,moderation_status,artifact_bucket,artifact_path,artifact_deleted_at",
        "id":f"eq.{job_id}", "owner_user_id":f"eq.{user['id']}", "limit":"1",
    })
    if not rows:
        raise HTTPException(404, detail={"code":"GENERATION_JOB_NOT_FOUND","message":"Generation job tidak ditemukan."})
    job = rows[0]
    if job.get("status") != "succeeded" or job.get("moderation_status") != "approved" or job.get("artifact_bucket") != "generation-artifacts" or not job.get("artifact_path"):
        raise HTTPException(409, detail={"code":"GENERATION_ARTIFACT_NOT_DELETABLE","message":"Hanya artefak privat yang selesai dan disetujui yang dapat dihapus."})
    result = await _rpc("generation_request_artifact_deletion", {
        "job_id":str(job_id), "owner_user_id":str(user["id"]),
        "requested_by":str(user["id"]), "idempotency_key":idempotency_key,
    })
    if not isinstance(result, dict) or str(result.get("job_id")) != str(job_id):
        raise HTTPException(503, detail={"code":"GENERATION_ARTIFACT_DELETE_UNCONFIRMED","message":"Permintaan penghapusan belum dapat dikonfirmasi."})
    return {**result, "artifact_available":False}


@router.get("/jobs/{job_id}")
async def get_generation_job(job_id: uuid.UUID, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    rows = await _admin_request("GET", "generation_jobs", params={
        "select": "id,task_id,capability_id,status,credits_to_reserve,owner_reward_status,dm_conversation_id,created_at,started_at,completed_at,error_code,artifact_bucket,artifact_path,output_sha256,moderation_status,input_tokens,output_tokens,artifact_deletion_requested_at,artifact_deleted_at",
        "id": f"eq.{job_id}", "owner_user_id": f"eq.{user['id']}", "limit": "1",
    })
    if not rows:
        raise HTTPException(404, detail={"code": "GENERATION_JOB_NOT_FOUND", "message": "Generation job tidak ditemukan."})
    job = rows[0]
    artifact_available = bool(job.get("status") == "succeeded" and job.get("moderation_status") == "approved"
                              and job.get("artifact_bucket") == "generation-artifacts" and job.get("artifact_path")
                              and not job.get("artifact_deletion_requested_at") and not job.get("artifact_deleted_at"))
    job.pop("artifact_bucket", None)
    job.pop("artifact_path", None)
    job["artifact_available"] = artifact_available
    deletion_status = "deleted" if job.get("artifact_deleted_at") else "pending" if job.get("artifact_deletion_requested_at") else "available" if artifact_available else "unavailable"
    if job.get("artifact_deletion_requested_at") and not job.get("artifact_deleted_at"):
        try:
            deletion_rows = await _admin_request("GET", "generation_artifact_deletion_jobs", params={
                "select":"status", "generation_job_id":f"eq.{job_id}", "limit":"1",
            })
            if deletion_rows:
                deletion_status = str(deletion_rows[0].get("status") or deletion_status)
        except HTTPException:
            pass
    job["artifact_deletion_status"] = deletion_status
    return {"job": job}


@router.get("/admin/review-queue")
async def generation_output_review_queue(
    request: Request,
    limit: int = 50,
    operator: dict[str, Any] = Depends(require_operator_scope("platform:content.moderate")),
) -> dict[str, Any]:
    if limit < 1 or limit > 100:
        raise HTTPException(422, detail={"code": "GENERATION_REVIEW_LIMIT_INVALID", "message": "Batas antrean harus 1–100."})
    rows = await _admin_request("GET", "generation_jobs", params={
        "select": "id,owner_user_id,agent_owner_user_id,agent_id,skill_id,task_id,trace_id,status,moderation_status,error_code,created_at,updated_at",
        "status": "eq.pending_reconciliation", "moderation_status": "eq.review_required",
        "order": "created_at.asc", "limit": str(limit),
    })
    items = rows or []
    await write_operator_audit(request, actor_user_id=str(operator["id"]), action="generation.output_review_queue.read",
        outcome="allowed", resource_type="generation_output_queue", resource_id="pending",
        metadata={"count": len(items)})
    return {"items": items, "limit": limit}


@router.get("/admin/artifact-deletion-queue")
async def generation_artifact_deletion_queue(
    request: Request,
    limit: int = 50,
    operator: dict[str, Any] = Depends(require_operator_scope("platform:content.moderate")),
) -> dict[str, Any]:
    if limit < 1 or limit > 100:
        raise HTTPException(422, detail={"code":"GENERATION_ARTIFACT_DELETE_LIMIT_INVALID","message":"Batas antrean harus 1–100."})
    rows = await _admin_request("GET", "generation_artifact_deletion_jobs", params={
        "select":"id,generation_job_id,owner_user_id,requested_by,bucket_id,status,attempts,max_attempts,error_code,created_at,updated_at,completed_at,last_retried_by,last_retry_reason",
        "status":"in.(queued,processing,dead)", "order":"updated_at.desc", "limit":str(limit),
    })
    items = rows or []
    await write_operator_audit(request, actor_user_id=str(operator["id"]),
        action="generation.artifact_deletion_queue.read", outcome="allowed",
        resource_type="generation_artifact_deletion_queue", resource_id="active",
        metadata={"count":len(items)})
    return {"items":items,"limit":limit}


@router.post("/admin/artifact-deletion-jobs/{deletion_job_id}/retry")
async def retry_generation_artifact_deletion(
    deletion_job_id: uuid.UUID,
    payload: GenerationArtifactDeletionRetry,
    request: Request,
    operator: dict[str, Any] = Depends(require_operator_scope("platform:content.moderate")),
) -> dict[str, Any]:
    await write_operator_audit(request, actor_user_id=str(operator["id"]),
        action="generation.artifact_deletion.retry", outcome="attempted",
        resource_type="generation_artifact_deletion_job", resource_id=str(deletion_job_id),
        metadata={"reason":payload.reason})
    result = await _rpc("generation_retry_artifact_deletion", {
        "deletion_job_id":str(deletion_job_id), "actor_user_id":str(operator["id"]),
        "reason":payload.reason,
    })
    if not isinstance(result, dict) or result.get("status") != "queued":
        raise HTTPException(409, detail={"code":"GENERATION_ARTIFACT_DELETE_RETRY_UNCONFIRMED","message":"Pemulihan antrean penghapusan belum dapat dikonfirmasi."})
    await write_operator_audit(request, actor_user_id=str(operator["id"]),
        action="generation.artifact_deletion.retry", outcome="allowed",
        resource_type="generation_artifact_deletion_job", resource_id=str(deletion_job_id),
        metadata={"reason":payload.reason,"status":"queued"})
    return result


@router.get("/admin/jobs/{job_id}/artifact")
async def generation_output_review_artifact(
    job_id: uuid.UUID,
    request: Request,
    operator: dict[str, Any] = Depends(require_operator_scope("platform:content.moderate")),
) -> dict[str, Any]:
    rows = await _admin_request("GET", "generation_jobs", params={
        "select": "id,status,moderation_status,artifact_bucket,artifact_path,output_sha256",
        "id": f"eq.{job_id}", "status": "eq.pending_reconciliation",
        "moderation_status": "eq.review_required", "limit": "1",
    })
    if not rows:
        raise HTTPException(404, detail={"code": "GENERATION_REVIEW_NOT_FOUND", "message": "Output tidak ditemukan pada antrean review."})
    job = rows[0]
    if job.get("artifact_bucket") != "generation-artifacts" or not job.get("artifact_path") or not job.get("output_sha256"):
        raise HTTPException(409, detail={"code": "GENERATION_REVIEW_ARTIFACT_UNAVAILABLE", "message": "Artefak privat belum memiliki bukti penyimpanan yang lengkap."})
    signed = await _signed_generation_artifact(job["artifact_bucket"], job["artifact_path"], expires_in=180)
    await write_operator_audit(request, actor_user_id=str(operator["id"]), action="generation.output_review.preview",
        outcome="allowed", resource_type="generation_job", resource_id=str(job_id),
        metadata={"expires_in_seconds": 180, "output_sha256": job["output_sha256"]})
    return {"job_id": str(job_id), "url": signed, "expires_in_seconds": 180, "visibility": "private"}


@router.post("/admin/jobs/{job_id}/review")
async def review_generation_output(
    job_id: uuid.UUID,
    payload: GenerationManualReview,
    request: Request,
    operator: dict[str, Any] = Depends(require_operator_scope("platform:content.moderate")),
) -> dict[str, Any]:
    await write_operator_audit(request, actor_user_id=str(operator["id"]), action="generation.output_review",
        outcome="attempted", resource_type="generation_job", resource_id=str(job_id),
        metadata={"decision": payload.decision, "reason": payload.reason, "evidence_reference": payload.evidence_reference})
    prepared = await _admin_request("POST", "rpc/generation_prepare_manual_review", body={
        "p_job_id": str(job_id), "p_reviewer_user_id": str(operator["id"]),
        "p_decision": payload.decision, "p_reason": payload.reason.strip(),
        "p_evidence_reference": payload.evidence_reference.strip(),
    })
    if not isinstance(prepared, dict):
        raise HTTPException(503, detail={"code": "GENERATION_REVIEW_NOT_CONFIRMED", "message": "Keputusan review belum dapat dikonfirmasi."})
    if payload.decision == "reject":
        await write_operator_audit(request, actor_user_id=str(operator["id"]), action="generation.output_review",
            outcome="allowed", resource_type="generation_job", resource_id=str(job_id),
            metadata={"decision": "reject", "status": prepared.get("status"), "reason": payload.reason,
                      "evidence_reference": payload.evidence_reference})
        return {"job_id": str(job_id), "decision": "reject", "status": prepared.get("status"),
                "reservation_state": prepared.get("reservation_state"), "artifact_visibility": "private"}
    if prepared.get("status") == "succeeded":
        return {"job_id": str(job_id), "decision": "approve", "status": "succeeded", "idempotent_replay": True}
    lease_token = prepared.get("lease_token")
    if not isinstance(lease_token, str) or not lease_token:
        raise HTTPException(503, detail={"code": "GENERATION_REVIEW_LEASE_UNAVAILABLE", "message": "Lease finalisasi output belum tersedia."})
    result = {
        "input_tokens": prepared.get("input_tokens"),
        "output_tokens": prepared.get("output_tokens"),
        "cost_microunits": prepared.get("actual_cost_microunits"),
        "source_event_id": prepared.get("source_event_id"),
    }
    try:
        completion = await _admin_request("POST", "rpc/generation_complete_job", body={
            "p_job_id": str(job_id), "p_lease_token": lease_token, "p_result": result,
        })
    except HTTPException:
        current = await _admin_request("GET", "generation_jobs", params={
            "select": "status", "id": f"eq.{job_id}", "limit": "1",
        })
        if current and current[0].get("status") == "succeeded":
            completion = {"status": "succeeded", "idempotent_replay": True}
        else:
            try:
                await _admin_request("POST", "rpc/generation_mark_pending_reconciliation", body={
                    "p_job_id": str(job_id), "p_lease_token": lease_token,
                    "p_reason_code": "manual_moderation_approved_settlement_pending",
                })
            except HTTPException:
                pass
            await write_operator_audit(request, actor_user_id=str(operator["id"]), action="generation.output_review",
                outcome="pending_reconciliation", resource_type="generation_job", resource_id=str(job_id),
                metadata={"decision": "approve", "reason_code": "SETTLEMENT_NOT_CONFIRMED",
                          "evidence_reference": payload.evidence_reference})
            raise HTTPException(409, detail={"code": "GENERATION_REVIEW_SETTLEMENT_PENDING",
                "message": "Moderasi disetujui, tetapi settlement/DM belum terkonfirmasi. Job tetap dalam rekonsiliasi dan tidak akan menjalankan provider ulang."})
    await write_operator_audit(request, actor_user_id=str(operator["id"]), action="generation.output_review",
        outcome="allowed", resource_type="generation_job", resource_id=str(job_id),
        metadata={"decision": "approve", "status": (completion or {}).get("status", "succeeded"),
                  "evidence_reference": payload.evidence_reference})
    return {"job_id": str(job_id), "decision": "approve", "status": "succeeded",
            "completion": completion, "artifact_visibility": "private"}

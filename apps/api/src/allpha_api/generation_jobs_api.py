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
from typing import Any

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

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

router = APIRouter(prefix="/v1/generation", tags=["ai-generation"])
_TIMEOUT = httpx.Timeout(10.0, connect=3.0)


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
        grant = await AgentConsumerGrantStore.from_environment().resolve(
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
    }


@router.get("/agents")
async def list_generation_agents(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    """List only current, public Agent grants that explicitly permit generation."""
    now = datetime.now(timezone.utc).isoformat()
    grants = await _admin_request("GET", "agent_consumer_grants", params={
        "select": "id,owner_user_id,agent_id,agent_version,skill_id,skill_version,capability_id,granted_scopes,expires_at,status",
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
            "select": "id,agent_id,version,status,name,display_name",
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
        items.append({
            "agent": agents[0], "owner_user_id": grant["owner_user_id"],
            "skill": skills[0], "capabilities": caps or [],
            "consumer_grant_id": grant["id"],
            "granted_scopes": grant.get("granted_scopes") or [],
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
        route = external["route"]
        budget: ConsumerBudgetReservation = external["budget"]
        max_output_tokens = payload.max_output_tokens or router_instance.max_output_tokens_for("public")
        if max_output_tokens > router_instance.max_output_tokens_for("public"):
            raise HTTPException(422, detail={"code": "OUTPUT_TOKEN_LIMIT_EXCEEDED", "message": "Batas output melebihi policy model publik."})
        knowledge_snapshot = await _retrieve_external_generation_knowledge(
            external["owner_id"], payload.agent_id, payload.knowledge_query
        )
        prompt_bytes = len(payload.prompt.encode("utf-8")) + len(str(knowledge_snapshot.get("context") or "").encode("utf-8"))
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
    prompt_bytes = len(payload.prompt.encode("utf-8")) + len(str(knowledge_snapshot.get("context") or "").encode("utf-8"))
    if prompt_bytes > int(route["max_prompt_bytes"]):
        raise HTTPException(422, detail={"code": "PROMPT_EXCEEDS_APPROVED_BOUND", "message": "Prompt melebihi batas byte yang disetujui."})
    skill_rows = await user_db_request("GET", "agent_skills", token, params={
        "select": "id,agent_id,version,status", "id": f"eq.{payload.skill_id}",
        "agent_id": f"eq.{payload.agent_id}", "status": "eq.published", "limit": "1",
    })
    if not skill_rows:
        raise HTTPException(404, detail={"code": "PUBLISHED_SKILL_NOT_FOUND", "message": "Skill tidak ditemukan atau belum dipublikasikan."})
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
    existing = await _admin_request("GET", "generation_jobs", params={
        "select": "id,task_id,prompt_sha256,knowledge_context_sha256,consumer_grant_id,agent_id,skill_id,capability_id,status,credits_to_reserve",
        "owner_user_id": f"eq.{user['id']}", "idempotency_key": f"eq.{idempotency_key}", "limit": "1",
    })
    if existing:
        prior = existing[0]
        if (prior.get("prompt_sha256") != prompt_hash or str(prior.get("agent_id")) != str(payload.agent_id)
            or str(prior.get("skill_id")) != str(payload.skill_id) or prior.get("capability_id") != payload.capability_id
            or prior.get("knowledge_context_sha256") != payload.quoted_knowledge_context_sha256
            or str(prior.get("consumer_grant_id") or "") != str(payload.consumer_grant_id or "")):
            raise HTTPException(409, detail={"code": "GENERATION_JOB_IDEMPOTENCY_CONFLICT", "message": "Idempotency-Key telah digunakan untuk permintaan generation yang berbeda."})
        return {"job_id": prior["id"], "task_id": prior["task_id"], "status": prior["status"],
            "idempotent_replay": True, "reserved_credits": prior.get("credits_to_reserve")}

    router_instance = getattr(request.app.state, "text_generation_router", None)
    if router_instance is None:
        raise HTTPException(503, detail={"code": "MODEL_ROUTE_UNAVAILABLE", "message": "AI Model Router belum memiliki provider, model, policy, dan metering yang disetujui."})
    if payload.consumer_grant_id is not None:
        external = await _external_generation_context(payload, str(user["id"]), router_instance)
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
        prompt_bytes = len(payload.prompt.encode("utf-8")) + len(str(knowledge_snapshot.get("context") or "").encode("utf-8"))
        if prompt_bytes > int(route["max_prompt_bytes"]):
            raise HTTPException(422, detail={"code": "PROMPT_EXCEEDS_APPROVED_BOUND", "message": "Prompt dan Knowledge melebihi batas byte model publik."})
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
            "agent_id": str(payload.agent_id), "skill_id": str(payload.skill_id),
            "source_version": int(skill["version"]), "capability_id": payload.capability_id,
            "sensitivity": "public", "task_id": task_id, "trace_id": trace_id,
            "idempotency_key": idempotency_key, "prompt": payload.prompt,
            "prompt_sha256": prompt_hash, "knowledge_snapshot": knowledge_snapshot,
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
        created = await _rpc("generation_create_job", command)
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
    knowledge_snapshot = await _retrieve_generation_knowledge(request, user, payload.agent_id, payload.knowledge_query)
    if payload.knowledge_query and payload.quoted_knowledge_context_sha256 != knowledge_snapshot.get("snapshot_sha256"):
        raise HTTPException(409, detail={"code": "GENERATION_KNOWLEDGE_QUOTE_STALE", "message": "Sumber atau policy Knowledge berubah. Minta quote baru."})
    prompt_bytes = len(payload.prompt.encode("utf-8")) + len(str(knowledge_snapshot.get("context") or "").encode("utf-8"))
    if prompt_bytes > int(route["max_prompt_bytes"]):
        raise HTTPException(422, detail={"code": "PROMPT_EXCEEDS_APPROVED_BOUND", "message": "Prompt melebihi batas byte yang disetujui."})
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
    created = await _rpc("generation_create_job", command)
    if not isinstance(created, dict) or not created.get("job_id"):
        raise HTTPException(503, detail={"code": "GENERATION_JOB_NOT_CONFIRMED", "message": "Generation job dan AI Credit reservation belum terkonfirmasi."})
    return {"job_id": created["job_id"], "task_id": created.get("task_id"), "status": created.get("status"),
        "idempotent_replay": bool(created.get("idempotent_replay")), "reserved_credits": created.get("reserved_credits")}


@router.get("/jobs")
async def list_generation_jobs(limit: int = 20, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    bounded = min(max(1, limit), 50)
    rows = await _admin_request("GET", "generation_jobs", params={
        "select": "id,task_id,capability_id,status,credits_to_reserve,owner_reward_status,dm_conversation_id,created_at,started_at,completed_at,error_code",
        "owner_user_id": f"eq.{user['id']}", "order": "created_at.desc", "limit": str(bounded),
    })
    return {"items": rows or [], "limit": bounded}


async def _signed_generation_artifact(bucket: str, path: str, *, expires_in: int = 300) -> str:
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
        "select":"id,owner_user_id,status,artifact_bucket,artifact_path,moderation_status",
        "id":f"eq.{job_id}","owner_user_id":f"eq.{user['id']}","limit":"1",
    })
    if not rows:
        raise HTTPException(404,detail={"code":"GENERATION_JOB_NOT_FOUND","message":"Generation job tidak ditemukan."})
    job=rows[0]
    if job.get("status")!="succeeded" or job.get("moderation_status")!="approved" or job.get("artifact_bucket")!="generation-artifacts" or not job.get("artifact_path"):
        raise HTTPException(409,detail={"code":"GENERATION_ARTIFACT_NOT_READY","message":"Artefak belum selesai dimoderasi dan dipublikasikan secara privat."})
    signed=await _signed_generation_artifact(job["artifact_bucket"],job["artifact_path"])
    return {"job_id":str(job_id),"url":signed,"expires_in_seconds":300,"visibility":"private"}


@router.get("/jobs/{job_id}")
async def get_generation_job(job_id: uuid.UUID, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    rows = await _admin_request("GET", "generation_jobs", params={
        "select": "id,task_id,capability_id,status,credits_to_reserve,owner_reward_status,dm_conversation_id,created_at,started_at,completed_at,error_code,artifact_bucket,artifact_path,output_sha256,moderation_status,input_tokens,output_tokens",
        "id": f"eq.{job_id}", "owner_user_id": f"eq.{user['id']}", "limit": "1",
    })
    if not rows:
        raise HTTPException(404, detail={"code": "GENERATION_JOB_NOT_FOUND", "message": "Generation job tidak ditemukan."})
    job = rows[0]
    artifact_available = bool(job.get("status") == "succeeded" and job.get("moderation_status") == "approved"
                              and job.get("artifact_bucket") == "generation-artifacts" and job.get("artifact_path"))
    job.pop("artifact_bucket", None)
    job.pop("artifact_path", None)
    job["artifact_available"] = artifact_available
    return {"job": job}

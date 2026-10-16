"""Operator-governed roster for official Allpha bot candidates.

Roster entries are configuration records only. They do not create Agent identities,
grant tool permissions, or execute autonomously. Activation is fail-closed until
canonical Agent identity, approved runtime policy, and verified 3D asset are linked.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from allpha_api.operator_security import (
    privileged_rest_request,
    require_operator_scope,
    write_operator_audit,
)
from allpha_api.skill_catalog import SKILL_CATALOG, SKILL_CATALOG_BY_KEY

router = APIRouter(prefix="/v1/admin/official-bots", tags=["official-agent-bots"])
_FIELDS = (
    "id,skill_key,display_name,category_key,category_label,skill_description,"
    "character_archetype_key,character_asset_key,asset_validation_status,agent_id,"
    "runtime_policy_id,status,autonomy_mode,isolation_reason,created_by,approved_by,"
    "approved_at,activated_by,activated_at,stopped_by,stopped_at,last_action,metadata,"
    "created_at,updated_at"
)


class ProvisionPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    limit: int = Field(default=500, ge=1, le=500)


class BotActionPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["approve", "activate", "stop", "isolate", "resume_to_draft"]
    reason: str = Field(min_length=8, max_length=500)
    autonomy_mode: Literal["supervised", "bounded"] = "supervised"


class BotLinkPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    agent_id: UUID
    runtime_policy_id: UUID
    character_asset_key: str = Field(min_length=3, max_length=180)


@router.get("", name="list_official_bots")
async def list_official_bots(
    limit: int = 100,
    offset: int = 0,
    status: str | None = None,
    operator: dict[str, Any] = Depends(require_operator_scope("platform:operations.read")),
) -> dict[str, Any]:
    if limit < 1 or limit > 100 or offset < 0 or offset > 100_000:
        raise HTTPException(status_code=422, detail={"code": "OFFICIAL_BOT_PAGINATION_INVALID", "message": "Pagination roster tidak valid."})
    params = {"select": _FIELDS, "order": "category_key.asc,display_name.asc", "limit": str(limit), "offset": str(offset)}
    if status:
        if status not in {"draft", "pending_approval", "approved", "active", "stopped", "isolated", "blocked"}:
            raise HTTPException(status_code=422, detail={"code": "OFFICIAL_BOT_STATUS_INVALID", "message": "Filter status tidak valid."})
        params["status"] = f"eq.{status}"
    rows = await privileged_rest_request("GET", "official_agent_bots", params=params)
    return {"items": rows or [], "limit": limit, "offset": offset, "source": "canonical_api_roster"}


@router.post("/provision", status_code=201, name="provision_official_bot_roster")
async def provision_official_bot_roster(
    payload: ProvisionPayload,
    request: Request,
    operator: dict[str, Any] = Depends(require_operator_scope("platform:capabilities.review")),
) -> dict[str, Any]:
    """Seed catalog-backed roster records; never creates or activates Agent runtimes."""
    await write_operator_audit(
        request, actor_user_id=operator["id"], action="official_bots.roster.provision.request",
        outcome="allowed", resource_type="official_agent_bot_roster",
        metadata={"requested_count": payload.limit, "catalog_version": "allpha-skill-catalog-v1"},
    )
    candidates = []
    for skill in SKILL_CATALOG[:payload.limit]:
        profile = skill["character_profile"]
        candidates.append({
            "skill_key": skill["key"],
            "display_name": f"Allpha Official · {skill['name']}",
            "category_key": skill["category"],
            "category_label": skill["category_label"],
            "skill_description": skill["description"],
            "character_archetype_key": profile["archetype_key"],
            "character_asset_key": None,
            "asset_validation_status": "unverified",
            "agent_id": None,
            "runtime_policy_id": None,
            "status": "draft",
            "autonomy_mode": "supervised",
            "created_by": operator["id"],
            "last_action": "roster_provisioned",
            "metadata": {
                "catalog_version": "allpha-skill-catalog-v1",
                "catalog_execution_status": skill["execution_status"],
                "source_repository": skill["source"]["repository"],
                "source_kind": skill["source"]["kind"],
            },
        })
    # Unique skill_key + ignore-duplicates makes repeated provisioning idempotent.
    await privileged_rest_request(
        "POST", "official_agent_bots",
        params={"on_conflict": "skill_key", "select": "id,skill_key"},
        body=candidates,
        prefer="resolution=ignore-duplicates,return=representation",
    )
    rows = await privileged_rest_request(
        "GET", "official_agent_bots",
        params={"select": "id,skill_key,status", "order": "skill_key.asc", "limit": "500"},
    ) or []
    await write_operator_audit(
        request, actor_user_id=operator["id"], action="official_bots.roster.provision.complete",
        outcome="allowed", resource_type="official_agent_bot_roster",
        metadata={"catalog_count": len(SKILL_CATALOG), "roster_count_observed": len(rows)},
    )
    return {
        "requested": payload.limit,
        "roster_count_observed": len(rows),
        "catalog_count": len(SKILL_CATALOG),
        "created_or_existing": len(rows),
        "runtime_activation": "not_performed",
        "message": "Roster kandidat disiapkan; belum membuat Agent identity atau menjalankan bot.",
    }


@router.patch("/{bot_id}/links", name="link_official_bot_runtime")
async def link_official_bot_runtime(
    bot_id: UUID,
    payload: BotLinkPayload,
    request: Request,
    operator: dict[str, Any] = Depends(require_operator_scope("platform:capabilities.review.high_risk")),
) -> dict[str, Any]:
    rows = await privileged_rest_request(
        "GET", "official_agent_bots",
        params={"select": _FIELDS, "id": f"eq.{bot_id}", "limit": "1"},
    )
    if not rows:
        raise HTTPException(status_code=404, detail={"code": "OFFICIAL_BOT_NOT_FOUND", "message": "Roster bot tidak ditemukan."})
    bot = rows[0]
    policy = await privileged_rest_request(
        "GET", "agent_runtime_policies",
        params={
            "select": "id,agent_id,policy_version,policy_digest,status,approved_tool_keys",
            "id": f"eq.{payload.runtime_policy_id}", "agent_id": f"eq.{payload.agent_id}",
            "status": "eq.approved", "limit": "1",
        },
    )
    if not policy:
        raise HTTPException(status_code=409, detail={"code": "OFFICIAL_BOT_POLICY_UNVERIFIED", "message": "Runtime policy kanonis belum ditemukan dalam status approved untuk Agent ini."})
    agent = await privileged_rest_request(
        "GET", "ai_agents",
        params={"select": "id,version,status", "id": f"eq.{payload.agent_id}", "limit": "1"},
    )
    if not agent:
        raise HTTPException(status_code=409, detail={"code": "OFFICIAL_BOT_AGENT_UNVERIFIED", "message": "Agent identity kanonis belum tersedia."})
    updated = await privileged_rest_request(
        "PATCH", "official_agent_bots",
        params={"id": f"eq.{bot_id}", "select": _FIELDS},
        body={
            "agent_id": str(payload.agent_id), "runtime_policy_id": str(payload.runtime_policy_id),
            "character_asset_key": payload.character_asset_key, "asset_validation_status": "unverified",
            "status": "pending_approval", "last_action": "runtime_links_submitted",
        },
        prefer="return=representation",
    )
    await write_operator_audit(
        request, actor_user_id=operator["id"], action="official_bots.runtime_links.submit",
        outcome="allowed", resource_type="official_agent_bot", resource_id=str(bot_id),
        metadata={"agent_id": str(payload.agent_id), "policy_id": str(payload.runtime_policy_id), "asset_validation_status": "unverified"},
    )
    return {"bot": (updated or [bot])[0], "activation": "blocked_until_asset_validation_and_approval"}


@router.post("/{bot_id}/action", name="official_bot_lifecycle_action")
async def official_bot_lifecycle_action(
    bot_id: UUID,
    payload: BotActionPayload,
    request: Request,
    operator: dict[str, Any] = Depends(require_operator_scope("platform:capabilities.review.high_risk")),
) -> dict[str, Any]:
    rows = await privileged_rest_request(
        "GET", "official_agent_bots",
        params={"select": _FIELDS, "id": f"eq.{bot_id}", "limit": "1"},
    )
    if not rows:
        raise HTTPException(status_code=404, detail={"code": "OFFICIAL_BOT_NOT_FOUND", "message": "Roster bot tidak ditemukan."})
    bot = rows[0]
    now = datetime.now(timezone.utc).isoformat()
    now_fields: dict[str, Any] = {
        "updated_at": now,
        "last_action": payload.action,
    }
    if payload.action == "approve":
        if bot["status"] not in {"draft", "pending_approval", "stopped"}:
            raise HTTPException(status_code=409, detail={"code": "OFFICIAL_BOT_TRANSITION_INVALID", "message": "Status bot tidak dapat disetujui dari state saat ini."})
        now_fields.update({"status": "approved", "approved_by": operator["id"], "approved_at": now, "isolation_reason": None})
    elif payload.action == "activate":
        # Do not treat an operator click as proof that the GLB or runtime policy is safe.
        if not bot.get("agent_id") or not bot.get("runtime_policy_id") or not bot.get("character_asset_key") or bot.get("asset_validation_status") != "verified":
            raise HTTPException(status_code=409, detail={"code": "OFFICIAL_BOT_ACTIVATION_BLOCKED", "message": "Aktivasi ditolak: Agent identity, approved runtime policy, dan asset GLB yang diverifikasi backend wajib tersedia."})
        policy = await privileged_rest_request(
            "GET", "agent_runtime_policies",
            params={"select": "id,agent_id,status", "id": f"eq.{bot['runtime_policy_id']}", "agent_id": f"eq.{bot['agent_id']}", "status": "eq.approved", "limit": "1"},
        )
        if not policy:
            raise HTTPException(status_code=409, detail={"code": "OFFICIAL_BOT_POLICY_UNVERIFIED", "message": "Runtime policy tidak lagi berstatus approved."})
        now_fields.update({"status": "active", "autonomy_mode": payload.autonomy_mode, "activated_by": operator["id"], "activated_at": now, "stopped_at": None, "stopped_by": None, "isolation_reason": None})
    elif payload.action == "stop":
        now_fields.update({"status": "stopped", "stopped_by": operator["id"], "stopped_at": now})
    elif payload.action == "isolate":
        now_fields.update({"status": "isolated", "isolation_reason": payload.reason})
    else:
        if bot["status"] not in {"stopped", "isolated", "blocked"}:
            raise HTTPException(status_code=409, detail={"code": "OFFICIAL_BOT_TRANSITION_INVALID", "message": "Hanya bot yang dihentikan/diisolasi/diblokir dapat dikembalikan ke draft."})
        now_fields.update({"status": "draft", "isolation_reason": None, "activated_at": None, "stopped_at": None})
    updated = await privileged_rest_request(
        "PATCH", "official_agent_bots",
        params={"id": f"eq.{bot_id}", "select": _FIELDS},
        body=now_fields,
        prefer="return=representation",
    )
    await write_operator_audit(
        request, actor_user_id=operator["id"], action=f"official_bots.{payload.action}",
        outcome="allowed", resource_type="official_agent_bot", resource_id=str(bot_id),
        metadata={"previous_status": bot["status"], "requested_status": now_fields["status"], "reason": payload.reason},
    )
    return {"bot": (updated or [bot])[0], "runtime_action_dispatched": False}

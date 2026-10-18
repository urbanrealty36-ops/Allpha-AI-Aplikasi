"""Operator-governed roster for official Allpha bot candidates.

Roster entries are configuration records only. They do not create Agent identities,
grant tool permissions, or execute autonomously. Activation is fail-closed until
canonical Agent identity, approved runtime policy, and verified 3D asset are linked.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from allpha_api.operator_security import (
    privileged_rest_request,
    require_operator_scope,
    write_operator_audit,
)
from allpha_api.agency_skill_catalog import AGENCY_SKILL_CATALOG_BY_KEY
from allpha_api.skill_catalog import SKILL_CATALOG_BY_KEY
from allpha_api.catalog_registry import get_skill_catalog_items
from allpha_api.tool_registry import UnknownToolError, get_tool

def _skill_snapshot_digest(snapshot: dict[str, Any]) -> str:
    canonical = json.dumps(snapshot, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _published_version_candidates(rows: list[dict[str, Any]], *, agent_id: str, skill_key: str) -> list[dict[str, Any]]:
    matching = []
    for row in rows:
        snapshot = row.get("snapshot")
        if not isinstance(snapshot, dict):
            continue
        provenance = snapshot.get("provenance")
        if not isinstance(provenance, dict):
            continue
        if str(row.get("agent_id")) != agent_id:
            continue
        if str(snapshot.get("agent_id")) != agent_id:
            continue
        if snapshot.get("status") != "published":
            continue
        if provenance.get("catalog_skill_key") != skill_key:
            continue
        if snapshot.get("version") != row.get("version"):
            continue
        matching.append({**row, "snapshot_digest": _skill_snapshot_digest(snapshot)})
    # Multiple Skill records for one catalog key are ambiguous; never guess which one
    # the official bot should execute.
    skill_ids = {str(row.get("skill_id")) for row in matching}
    if len(skill_ids) != 1:
        return []
    return [max(matching, key=lambda row: int(row.get("version") or 0))] if matching else []


router = APIRouter(prefix="/v1/admin/official-bots", tags=["official-agent-bots"])
_FIELDS = (
    "id,skill_key,display_name,category_key,category_label,skill_description,"
    "character_archetype_key,character_asset_key,asset_validation_status,agent_id,"
    "runtime_policy_id,status,autonomy_mode,isolation_reason,created_by,approved_by,"
    "approved_at,activated_by,activated_at,stopped_by,stopped_at,last_action,metadata,"
    "created_at,updated_at"
)
_RUNTIME_FIELDS = _FIELDS.replace(
    "runtime_policy_id,status",
    "runtime_policy_id,skill_version_id,skill_version_number,skill_version_digest,status",
)
_PIN_FIELDS = "skill_version_id,skill_version_number,skill_version_digest"


class ProvisionPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    limit: int = Field(default=500, ge=1, le=500)
    catalog_source: Literal["allpha-500", "agency-agents"] = "allpha-500"


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


class ProvisionIdentityBatchPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    bot_ids: list[UUID] = Field(min_length=1, max_length=50)


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
    count_params = {"select": "id", "limit": "500"}
    if status:
        count_params["status"] = f"eq.{status}"
    count_rows = await privileged_rest_request("GET", "official_agent_bots", params=count_params)
    return {"items": rows or [], "total": len(count_rows or []), "limit": limit, "offset": offset, "source": "canonical_api_roster"}


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
        metadata={"requested_count": payload.limit, "catalog_source": payload.catalog_source, "catalog_version": get_skill_catalog_items(payload.catalog_source)[1]},
    )
    catalog_items, catalog_version = get_skill_catalog_items(payload.catalog_source)
    candidates = []
    for skill in catalog_items[:payload.limit]:
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
                "catalog_version": catalog_version,
                "catalog_source": payload.catalog_source,
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
        params={"select": "id,skill_key,status", "order": "skill_key.asc", "limit": "1000"},
    ) or []
    await write_operator_audit(
        request, actor_user_id=operator["id"], action="official_bots.roster.provision.complete",
        outcome="allowed", resource_type="official_agent_bot_roster",
        metadata={"catalog_count": len(catalog_items), "catalog_source": payload.catalog_source, "catalog_version": catalog_version, "roster_count_observed": len(rows)},
    )
    return {
        "requested": payload.limit,
        "roster_count_observed": len(rows),
        "catalog_count": len(catalog_items),
        "catalog_source": payload.catalog_source,
        "catalog_version": catalog_version,
        "created_or_existing": len(rows),
        "runtime_activation": "not_performed",
        "message": "Roster kandidat disiapkan; belum membuat Agent identity atau menjalankan bot.",
    }


@router.post("/{bot_id}/provision-identity", status_code=201, name="provision_official_bot_identity")
async def provision_official_bot_identity(
    bot_id: UUID,
    request: Request,
    operator: dict[str, Any] = Depends(require_operator_scope("platform:capabilities.review.high_risk")),
) -> dict[str, Any]:
    """Create a draft platform-owned Agent via the canonical identity tables/RPC."""
    configured_owner = os.getenv("ALLPHA_PLATFORM_OWNER_USER_ID", "").strip()
    try:
        platform_owner_id = UUID(configured_owner)
    except (ValueError, TypeError) as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "PLATFORM_AGENT_OWNER_NOT_CONFIGURED",
                "message": "Identitas pemilik sistem belum dikonfigurasi sebagai UUID akun platform khusus.",
            },
        ) from exc

    rows = await privileged_rest_request(
        "GET", "official_agent_bots",
        params={"select": "id,skill_key,status,agent_id,metadata", "id": f"eq.{bot_id}", "limit": "1"},
    )
    if not rows:
        raise HTTPException(status_code=404, detail={"code": "OFFICIAL_BOT_NOT_FOUND", "message": "Roster bot tidak ditemukan."})
    bot = rows[0]
    replay = bool(bot.get("agent_id"))
    if not replay and bot.get("status") not in {"draft", "pending_approval"}:
        raise HTTPException(
            status_code=409,
            detail={"code": "OFFICIAL_BOT_STATE_NOT_PROVISIONABLE", "message": "Identitas hanya dapat dibuat untuk kandidat draft atau pending approval."},
        )

    await write_operator_audit(
        request, actor_user_id=operator["id"], action="official_bots.identity.provision.request",
        outcome="allowed", resource_type="official_agent_bot", resource_id=str(bot_id),
        metadata={"skill_key": bot["skill_key"], "platform_owner_configured": True},
    )
    result = await privileged_rest_request(
        "POST", "rpc/provision_official_agent_identity",
        body={
            "p_bot_id": str(bot_id),
            "p_platform_owner_user_id": str(platform_owner_id),
        },
    )
    agent = result[0] if isinstance(result, list) and result else result
    if not isinstance(agent, dict) or not agent.get("id"):
        raise HTTPException(
            status_code=503,
            detail={"code": "OFFICIAL_BOT_IDENTITY_UNCONFIRMED", "message": "Backend tidak mengonfirmasi identitas Agent kanonis."},
        )
    await write_operator_audit(
        request, actor_user_id=operator["id"], action="official_bots.identity.provision.complete",
        outcome="allowed", resource_type="official_agent_bot", resource_id=str(bot_id),
        metadata={
            "agent_id": str(agent["id"]),
            "platform_owner_user_id": str(platform_owner_id),
            "idempotent_replay": replay,
            "agent_status": agent.get("status"),
        },
    )
    return {
        "bot_id": str(bot_id),
        "agent": agent,
        "ownership": {"owner_user_id": str(platform_owner_id), "owner_type": "platform", "role": "owner"},
        "idempotent_replay": replay,
        "runtime_activation": "not_performed",
    }


@router.post("/provision-identities", status_code=200, name="provision_official_bot_identities")
async def provision_official_bot_identities(
    payload: ProvisionIdentityBatchPayload,
    request: Request,
    operator: dict[str, Any] = Depends(require_operator_scope("platform:capabilities.review.high_risk")),
) -> dict[str, Any]:
    """Provision up to 50 platform-owned Agent identities through the canonical identity RPC.

    The batch is resumable and reports each result. It never publishes Skills, verifies
    GLBs, approves runtime policies, or activates a bot.
    """
    unique_ids = list(dict.fromkeys(payload.bot_ids))
    if len(unique_ids) != len(payload.bot_ids):
        raise HTTPException(status_code=422, detail={
            "code": "OFFICIAL_BOT_IDENTITY_BATCH_DUPLICATE_IDS",
            "message": "Batch berisi bot ID duplikat; kirim setiap ID satu kali.",
        })

    try:
        UUID(os.getenv("ALLPHA_PLATFORM_OWNER_USER_ID", "").strip())
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=503, detail={
            "code": "PLATFORM_AGENT_OWNER_NOT_CONFIGURED",
            "message": "Identitas pemilik sistem belum dikonfigurasi sebagai UUID akun platform khusus.",
        }) from exc

    await write_operator_audit(
        request, actor_user_id=operator["id"], action="official_bots.identity.batch.request",
        outcome="allowed", resource_type="official_agent_bot_roster",
        metadata={"requested_count": len(payload.bot_ids)},
    )
    items: list[dict[str, Any]] = []
    for bot_id in payload.bot_ids:
        try:
            result = await provision_official_bot_identity(bot_id, request, operator)
            agent = result.get("agent") if isinstance(result, dict) else None
            items.append({
                "bot_id": str(bot_id),
                "status": "already_linked" if result.get("idempotent_replay") else "provisioned",
                "agent_id": str(agent["id"]) if isinstance(agent, dict) and agent.get("id") else None,
                "runtime_activation": "not_performed",
            })
        except HTTPException as exc:
            detail = exc.detail if isinstance(exc.detail, dict) else {}
            items.append({
                "bot_id": str(bot_id),
                "status": "failed",
                "code": str(detail.get("code") or "IDENTITY_PROVISION_FAILED"),
                "http_status": exc.status_code,
            })
        except Exception:
            # Do not leak PostgREST/RPC errors, payloads, or secrets to the caller.
            items.append({
                "bot_id": str(bot_id),
                "status": "failed",
                "code": "IDENTITY_PROVISION_UNCONFIRMED",
                "http_status": 503,
            })

    succeeded = sum(1 for item in items if item["status"] in {"provisioned", "already_linked"})
    failed = len(items) - succeeded
    await write_operator_audit(
        request, actor_user_id=operator["id"], action="official_bots.identity.batch.complete",
        outcome="allowed" if failed == 0 else "error", resource_type="official_agent_bot_roster",
        metadata={"requested_count": len(items), "succeeded_count": succeeded, "failed_count": failed},
    )
    return {
        "requested": len(items),
        "succeeded": succeeded,
        "failed": failed,
        "items": items,
        "runtime_activation": "not_performed",
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
    if bot["status"] in {"active", "isolated", "blocked"}:
        raise HTTPException(status_code=409, detail={"code": "OFFICIAL_BOT_LINK_STATE_INVALID", "message": "Hentikan atau pulihkan bot sebelum mengubah tautan runtime."})

    # A roster blueprint is not an executable Skill. Never promote catalog metadata
    # into runtime authority without a canonical published implementation/version.
    catalog_skill = SKILL_CATALOG_BY_KEY.get(bot["skill_key"]) or AGENCY_SKILL_CATALOG_BY_KEY.get(bot["skill_key"])
    if not catalog_skill:
        raise HTTPException(status_code=409, detail={"code": "OFFICIAL_BOT_SKILL_UNKNOWN", "message": "Skill key tidak ada di katalog kanonis."})
    if not catalog_skill.get("executable") or catalog_skill.get("execution_status") != "implemented":
        raise HTTPException(status_code=409, detail={
            "code": "OFFICIAL_BOT_SKILL_NOT_EXECUTABLE",
            "message": "Skill ini masih blueprint katalog; implementasi dan versi Skill kanonis harus tersedia sebelum binding runtime.",
            "skill_key": bot["skill_key"],
            "execution_status": catalog_skill.get("execution_status", "unknown"),
        })
    if not bot.get("agent_id") or str(bot["agent_id"]) != str(payload.agent_id):
        raise HTTPException(status_code=409, detail={
            "code": "OFFICIAL_BOT_CANONICAL_IDENTITY_REQUIRED",
            "message": "Provision identitas platform-owned melalui layanan kanonis terlebih dahulu; tautan Agent bebas tidak diizinkan.",
        })

    try:
        # Schema readiness is checked before any roster mutation. This preserves list/
        # provision operations while the version-pin migration is still source-only.
        await privileged_rest_request(
            "GET", "official_agent_bots",
            params={"select": _PIN_FIELDS, "limit": "1"},
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail={
            "code": "OFFICIAL_BOT_SKILL_VERSION_SCHEMA_NOT_READY",
            "message": "Migration immutable Skill version pin belum tersedia pada database; runtime linking ditahan tanpa mengubah roster.",
        }) from exc

    version_rows = await privileged_rest_request(
        "GET", "agent_skill_versions",
        params={
            "select": "id,skill_id,agent_id,version,snapshot,created_at",
            "agent_id": f"eq.{payload.agent_id}",
            "order": "version.desc,created_at.desc",
            "limit": "200",
        },
    ) or []
    version_candidates = _published_version_candidates(
        version_rows, agent_id=str(payload.agent_id), skill_key=bot["skill_key"],
    )
    if len(version_candidates) != 1:
        raise HTTPException(status_code=409, detail={
            "code": "OFFICIAL_BOT_PUBLISHED_SKILL_VERSION_REQUIRED",
            "message": "Tidak ditemukan tepat satu immutable Skill version terbaru berstatus published dengan provenance catalog_skill_key yang cocok. Draft katalog tidak dapat diikat ke runtime.",
            "skill_key": bot["skill_key"],
        })
    pinned_skill_version = version_candidates[0]
    snapshot = pinned_skill_version["snapshot"]
    skill_tool_dependencies = snapshot.get("tool_dependencies") or []
    if not isinstance(skill_tool_dependencies, list) or any(not isinstance(key, str) for key in skill_tool_dependencies):
        raise HTTPException(status_code=409, detail={
            "code": "OFFICIAL_BOT_SKILL_TOOL_CONTRACT_INVALID",
            "message": "Snapshot Skill memiliki kontrak tool dependency yang tidak valid.",
        })

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
    approved_tools = policy[0].get("approved_tool_keys") or []
    if not approved_tools:
        raise HTTPException(status_code=409, detail={"code": "OFFICIAL_BOT_POLICY_HAS_NO_TOOLS", "message": "Policy belum menyetujui tool handler yang dapat dieksekusi."})
    missing_skill_tools = sorted(set(skill_tool_dependencies) - set(approved_tools))
    if missing_skill_tools:
        raise HTTPException(status_code=409, detail={
            "code": "OFFICIAL_BOT_SKILL_TOOLS_NOT_APPROVED",
            "message": "Runtime policy belum menyetujui semua tool yang dideklarasikan oleh versi Skill yang dipin.",
            "missing_tool_keys": missing_skill_tools,
        })
    unknown_tools = []
    for tool_key in approved_tools:
        try:
            get_tool(tool_key)
        except UnknownToolError:
            unknown_tools.append(tool_key)
    if unknown_tools:
        raise HTTPException(status_code=409, detail={
            "code": "OFFICIAL_BOT_POLICY_TOOL_NOT_REGISTERED",
            "message": "Policy mencantumkan tool yang tidak terdaftar pada canonical Tool Registry.",
            "unknown_tool_keys": sorted(unknown_tools),
        })
    agent = await privileged_rest_request(
        "GET", "ai_agents",
        params={"select": "id,version,status,persona", "id": f"eq.{payload.agent_id}", "limit": "1"},
    )
    if not agent:
        raise HTTPException(status_code=409, detail={"code": "OFFICIAL_BOT_AGENT_UNVERIFIED", "message": "Agent identity kanonis belum tersedia."})
    persona = agent[0].get("persona") or {}
    persona_skill_key = persona.get("allpha_skill_key") if isinstance(persona, dict) else None
    if persona_skill_key != bot["skill_key"]:
        raise HTTPException(status_code=409, detail={
            "code": "OFFICIAL_BOT_AGENT_SKILL_MISMATCH",
            "message": "Persona Agent tidak menunjuk Skill blueprint roster yang sama.",
            "expected_skill_key": bot["skill_key"],
            "actual_skill_key": persona_skill_key,
        })
    updated = await privileged_rest_request(
        "PATCH", "official_agent_bots",
        params={"id": f"eq.{bot_id}", "status": f"eq.{bot['status']}", "select": _RUNTIME_FIELDS},
        body={
            "agent_id": str(payload.agent_id), "runtime_policy_id": str(payload.runtime_policy_id),
            "skill_version_id": str(pinned_skill_version["id"]),
            "skill_version_number": int(pinned_skill_version["version"]),
            "skill_version_digest": pinned_skill_version["snapshot_digest"],
            "character_asset_key": payload.character_asset_key, "asset_validation_status": "unverified",
            "status": "pending_approval", "approved_by": None, "approved_at": None,
            "updated_at": datetime.now(timezone.utc).isoformat(), "last_action": "runtime_links_submitted",
        },
        prefer="return=representation",
    )
    if not updated:
        raise HTTPException(status_code=409, detail={"code": "OFFICIAL_BOT_STATE_CHANGED", "message": "Status roster berubah saat penautan; muat ulang dan coba lagi."})
    await write_operator_audit(
        request, actor_user_id=operator["id"], action="official_bots.runtime_links.submit",
        outcome="allowed", resource_type="official_agent_bot", resource_id=str(bot_id),
        metadata={"agent_id": str(payload.agent_id), "policy_id": str(payload.runtime_policy_id),
                  "skill_version_id": str(pinned_skill_version["id"]),
                  "skill_version_number": int(pinned_skill_version["version"]),
                  "skill_version_digest": pinned_skill_version["snapshot_digest"],
                  "asset_validation_status": "unverified"},
    )
    return {"bot": updated[0], "activation": "blocked_until_asset_validation_and_approval"}


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
    try:
        pin_rows = await privileged_rest_request(
            "GET", "official_agent_bots",
            params={"select": _PIN_FIELDS, "id": f"eq.{bot_id}", "limit": "1"},
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail={
            "code": "OFFICIAL_BOT_SKILL_VERSION_SCHEMA_NOT_READY",
            "message": "Migration immutable Skill version pin belum tersedia; aktivasi ditahan secara fail-closed.",
        }) from exc
    if pin_rows:
        bot.update(pin_rows[0])
    now = datetime.now(timezone.utc).isoformat()
    now_fields: dict[str, Any] = {
        "updated_at": now,
        "last_action": payload.action,
    }
    # Roster state is not runtime state. Until a real dispatch and cancellation/kill
    # contract is wired to the canonical Agent Runtime, never mark a bot active or
    # claim that stop/isolate has terminated a running worker.
    if bot["status"] == "active" and payload.action in {"stop", "isolate"}:
        raise HTTPException(status_code=409, detail={
            "code": "OFFICIAL_BOT_KILL_SWITCH_UNAVAILABLE",
            "message": "Bot berstatus active tetapi jalur kill/cancellation runtime belum terhubung; status tidak diubah agar tidak memberi kesan runtime sudah berhenti.",
        })
    if payload.action == "approve":
        if bot["status"] not in {"draft", "pending_approval", "stopped"}:
            raise HTTPException(status_code=409, detail={"code": "OFFICIAL_BOT_TRANSITION_INVALID", "message": "Status bot tidak dapat disetujui dari state saat ini."})
        now_fields.update({"status": "approved", "approved_by": operator["id"], "approved_at": now, "isolation_reason": None})
    elif payload.action == "activate":
        # Do not treat an operator click as proof that the GLB or runtime policy is safe.
        if bot["status"] != "approved":
            raise HTTPException(status_code=409, detail={"code": "OFFICIAL_BOT_APPROVAL_REQUIRED", "message": "Bot harus berstatus approved sebelum aktivasi."})
        if (not bot.get("agent_id") or not bot.get("runtime_policy_id")
                or not bot.get("character_asset_key") or bot.get("asset_validation_status") != "verified"):
            raise HTTPException(status_code=409, detail={"code": "OFFICIAL_BOT_ACTIVATION_BLOCKED", "message": "Aktivasi ditolak: Agent identity, approved runtime policy, dan asset GLB yang diverifikasi backend wajib tersedia."})
        if not bot.get("skill_version_id") or not bot.get("skill_version_number") or not bot.get("skill_version_digest"):
            raise HTTPException(status_code=409, detail={
                "code": "OFFICIAL_BOT_PINNED_SKILL_VERSION_REQUIRED",
                "message": "Aktivasi memerlukan immutable Skill version ID, nomor versi, dan digest yang sudah dipin saat review.",
            })
        policy = await privileged_rest_request(
            "GET", "agent_runtime_policies",
            params={"select": "id,agent_id,status,approved_tool_keys", "id": f"eq.{bot['runtime_policy_id']}", "agent_id": f"eq.{bot['agent_id']}", "status": "eq.approved", "limit": "1"},
        )
        if not policy:
            raise HTTPException(status_code=409, detail={"code": "OFFICIAL_BOT_POLICY_UNVERIFIED", "message": "Runtime policy tidak lagi berstatus approved."})
        pinned_rows = await privileged_rest_request(
            "GET", "agent_skill_versions",
            params={"select": "id,skill_id,agent_id,version,snapshot", "id": f"eq.{bot['skill_version_id']}", "agent_id": f"eq.{bot['agent_id']}", "limit": "1"},
        ) or []
        if len(pinned_rows) != 1:
            raise HTTPException(status_code=409, detail={"code": "OFFICIAL_BOT_PINNED_SKILL_VERSION_MISSING", "message": "Immutable Skill version yang dipin tidak ditemukan untuk Agent ini."})
        pinned = pinned_rows[0]
        snapshot = pinned.get("snapshot")
        provenance = snapshot.get("provenance") if isinstance(snapshot, dict) else None
        if (not isinstance(snapshot, dict)
                or snapshot.get("status") != "published"
                or str(snapshot.get("agent_id")) != str(bot["agent_id"])
                or snapshot.get("version") != pinned.get("version")
                or int(pinned.get("version") or 0) != int(bot["skill_version_number"])
                or _skill_snapshot_digest(snapshot) != bot["skill_version_digest"]
                or not isinstance(provenance, dict)
                or provenance.get("catalog_skill_key") != bot["skill_key"]):
            raise HTTPException(status_code=409, detail={
                "code": "OFFICIAL_BOT_PINNED_SKILL_VERSION_INVALID",
                "message": "Digest, status, Agent, nomor versi, atau provenance Skill tidak cocok dengan versi yang direview.",
            })
        approved_tools = policy[0].get("approved_tool_keys") or []
        skill_tools = snapshot.get("tool_dependencies") or []
        if not isinstance(skill_tools, list) or not set(skill_tools).issubset(set(approved_tools)):
            raise HTTPException(status_code=409, detail={
                "code": "OFFICIAL_BOT_SKILL_TOOLS_NOT_APPROVED",
                "message": "Runtime policy tidak lagi menyetujui seluruh tool pada immutable Skill version yang dipin.",
            })
        for tool_key in skill_tools:
            try:
                get_tool(tool_key)
            except UnknownToolError as exc:
                raise HTTPException(status_code=409, detail={
                    "code": "OFFICIAL_BOT_SKILL_TOOL_NOT_REGISTERED",
                    "message": "Immutable Skill version mereferensikan tool yang tidak terdaftar.",
                    "tool_key": tool_key,
                }) from exc
        agent = await privileged_rest_request(
            "GET", "ai_agents",
            params={"select": "id,status", "id": f"eq.{bot['agent_id']}", "limit": "1"},
        )
        if not agent or agent[0].get("status") != "active":
            raise HTTPException(status_code=409, detail={"code": "OFFICIAL_BOT_AGENT_NOT_ACTIVE", "message": "Agent identity kanonis harus aktif sebelum bot dijalankan."})
        raise HTTPException(status_code=409, detail={
            "code": "OFFICIAL_BOT_RUNTIME_DISPATCH_UNAVAILABLE",
            "message": "Semua prasyarat roster tidak cukup untuk aktivasi. Dispatcher runtime kanonis, Skill version pinning, budget enforcement, dan kill/cancellation belum terhubung; bot tetap approved dan tidak diubah menjadi active.",
        })
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
        params={"id": f"eq.{bot_id}", "status": f"eq.{bot['status']}", "select": _FIELDS},
        body=now_fields,
        prefer="return=representation",
    )
    if not updated:
        raise HTTPException(status_code=409, detail={"code": "OFFICIAL_BOT_STATE_CHANGED", "message": "Status roster berubah saat aksi diproses; muat ulang sebelum mencoba lagi."})
    await write_operator_audit(
        request, actor_user_id=operator["id"], action=f"official_bots.{payload.action}",
        outcome="allowed", resource_type="official_agent_bot", resource_id=str(bot_id),
        metadata={"previous_status": bot["status"], "requested_status": now_fields["status"], "reason": payload.reason},
    )
    return {"bot": updated[0], "runtime_action_dispatched": False}

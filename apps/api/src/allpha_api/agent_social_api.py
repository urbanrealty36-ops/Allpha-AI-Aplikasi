"""WP-06 owner-governed Human + AI Agent social presence contracts."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from allpha_api.auth import current_user
from allpha_api.content_api import _server_db

router = APIRouter(prefix="/v1/agent-social", tags=["agent-social-presence"])
_ALLOWED = {"draft_post", "draft_comment", "draft_reply", "suggest_repost", "draft_story"}


class PolicyWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    allowed_actions: list[Literal["draft_post", "draft_comment", "draft_reply", "suggest_repost", "draft_story"]] = Field(default_factory=lambda: ["draft_post"], max_length=5)
    approval_mode: Literal["every_post", "high_risk_only", "disabled"] = "every_post"
    disclosure_text: str = Field(default="Dibuat bersama AI Agent", min_length=8, max_length=180)
    is_enabled: bool = True
    expected_version: int | None = Field(default=None, ge=1)


class CoauthoredDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")
    agent_id: uuid.UUID
    runtime_task_id: uuid.UUID
    visibility: Literal["public", "followers", "private"] = "public"
    content_type: Literal["text", "image", "video", "story"] = "text"
    action_type: Literal["draft_post", "draft_comment", "draft_reply", "suggest_repost", "draft_story"] = "draft_post"
    target_content_id: uuid.UUID | None = None
    idempotency_key: str = Field(min_length=12, max_length=160, pattern=r"^[A-Za-z0-9._:-]+$")


class ApprovalDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Literal["approve", "reject"]
    reason: str | None = Field(default=None, max_length=500)


async def _active_owned_agent(owner_id: str, agent_id: str) -> dict[str, Any]:
    agents = await _server_db("GET", "ai_agents", params={
        "select": "id,handle,display_name,status,disclosure", "id": f"eq.{agent_id}",
        "status": "eq.active", "limit": "1",
    })
    ownerships = await _server_db("GET", "agent_ownerships", params={
        "select": "agent_id", "agent_id": f"eq.{agent_id}", "owner_user_id": f"eq.{owner_id}",
        "ownership_role": "eq.owner", "status": "eq.active", "limit": "1",
    })
    if not agents or not ownerships:
        raise HTTPException(403, detail={"code": "AGENT_SOCIAL_OWNERSHIP_REQUIRED", "message": "Agent harus aktif dan dimiliki oleh akun ini."})
    return agents[0]


@router.get("/policy")
async def get_policy(agent_id: uuid.UUID, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    owner_id = str(user["id"])
    await _active_owned_agent(owner_id, str(agent_id))
    rows = await _server_db("GET", "agent_social_presence_policies", params={
        "select": "id,owner_user_id,agent_id,allowed_actions,approval_mode,disclosure_text,is_enabled,version,updated_at,revoked_at",
        "owner_user_id": f"eq.{owner_id}", "agent_id": f"eq.{agent_id}", "limit": "1",
    })
    return {"policy": rows[0] if rows else None}


@router.put("/policy/{agent_id}")
async def put_policy(agent_id: uuid.UUID, payload: PolicyWrite,
                     user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    owner_id = str(user["id"])
    await _active_owned_agent(owner_id, str(agent_id))
    existing = await _server_db("GET", "agent_social_presence_policies", params={
        "select": "id,version", "owner_user_id": f"eq.{owner_id}",
        "agent_id": f"eq.{agent_id}", "limit": "1",
    })
    if existing:
        current = existing[0]
        if payload.expected_version != int(current["version"]):
            raise HTTPException(409, detail={"code": "AGENT_SOCIAL_POLICY_CONFLICT", "message": "Kebijakan Agent berubah. Muat ulang sebelum menyimpan."})
        rows = await _server_db("PATCH", "agent_social_presence_policies", params={
            "id": f"eq.{current['id']}", "owner_user_id": f"eq.{owner_id}",
            "version": f"eq.{current['version']}", "select": "*",
        }, body={
            "allowed_actions": payload.allowed_actions, "approval_mode": payload.approval_mode,
            "disclosure_text": payload.disclosure_text, "is_enabled": payload.is_enabled,
            "version": int(current["version"]) + 1, "updated_at": datetime.now(timezone.utc).isoformat(),
            "revoked_at": None if payload.is_enabled else datetime.now(timezone.utc).isoformat(),
        }, prefer="return=representation")
    else:
        if payload.expected_version is not None:
            raise HTTPException(409, detail={"code": "AGENT_SOCIAL_POLICY_CONFLICT", "message": "Kebijakan belum tersedia."})
        rows = await _server_db("POST", "agent_social_presence_policies", body={
            "owner_user_id": owner_id, "agent_id": str(agent_id),
            "allowed_actions": payload.allowed_actions, "approval_mode": payload.approval_mode,
            "disclosure_text": payload.disclosure_text, "is_enabled": payload.is_enabled,
        }, prefer="return=representation")
    if not rows:
        raise HTTPException(409, detail={"code": "AGENT_SOCIAL_POLICY_CONFLICT", "message": "Kebijakan tidak tersimpan; muat ulang."})
    if not payload.is_enabled:
        await _server_db("PATCH", "agent_social_action_approvals", params={
            "owner_user_id": f"eq.{owner_id}", "agent_id": f"eq.{agent_id}",
            "status": "in.(pending,approved)",
        }, body={"status": "revoked", "decided_at": datetime.now(timezone.utc).isoformat(),
                 "decision_reason": "owner_policy_disabled"})
    return {"policy": rows[0]}


@router.post("/drafts", status_code=201)
async def create_coauthored_draft(payload: CoauthoredDraft,
                                  user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    owner_id, agent_id = str(user["id"]), str(payload.agent_id)
    agent = await _active_owned_agent(owner_id, agent_id)
    runtime_tasks = await _server_db("GET", "agent_runtime_tasks", params={
        "select": "id,owner_user_id,agent_id,state,output_payload,completed_at",
        "id": f"eq.{payload.runtime_task_id}", "owner_user_id": f"eq.{owner_id}",
        "agent_id": f"eq.{agent_id}", "state": "eq.succeeded", "limit": "1",
    })
    if not runtime_tasks or not runtime_tasks[0].get("completed_at") or not isinstance(runtime_tasks[0].get("output_payload"), dict):
        raise HTTPException(409, detail={"code": "AGENT_SOCIAL_RUNTIME_TASK_REQUIRED", "message": "Draft harus berasal dari task Agent Runtime yang berhasil untuk Agent dan pemilik ini."})
    policies = await _server_db("GET", "agent_social_presence_policies", params={
        "select": "id,allowed_actions,approval_mode,disclosure_text,is_enabled,version,revoked_at",
        "owner_user_id": f"eq.{owner_id}", "agent_id": f"eq.{agent_id}", "limit": "1",
    })
    policy = policies[0] if policies else None
    if (not policy or not policy.get("is_enabled") or policy.get("revoked_at")
            or payload.action_type not in (policy.get("allowed_actions") or [])
            or policy.get("approval_mode") == "disabled"):
        raise HTTPException(403, detail={"code": "AGENT_SOCIAL_ACTION_NOT_AUTHORIZED", "message": "Kebijakan pemilik tidak mengizinkan tindakan sosial Agent ini."})
    output = runtime_tasks[0]["output_payload"]
    generated_body = next((output.get(key) for key in ("content", "text", "body", "generated_text") if isinstance(output.get(key), str) and output.get(key).strip()), None)
    if not generated_body or len(generated_body.strip()) > 10_000:
        raise HTTPException(409, detail={"code": "AGENT_SOCIAL_RUNTIME_OUTPUT_NOT_PUBLISHABLE", "message": "Output task tidak memiliki teks konten yang valid; jalankan ulang Agent Runtime."})
    prior = await _server_db("GET", "agent_social_action_approvals", params={
        "select": "id,content_id,status", "owner_user_id": f"eq.{owner_id}",
        "idempotency_key": f"eq.{payload.idempotency_key}", "limit": "1",
    })
    if prior:
        return {"approval": prior[0], "replayed": True}
    content = await _server_db("POST", "content_items", body={
        "owner_id": owner_id, "ai_agent_id": agent_id, "content_type": payload.content_type,
        "body": generated_body.strip(), "visibility": payload.visibility, "status": "draft",
        "moderation_status": "not_submitted", "version": 1,
        "provenance": {"coauthored": True, "human_owner_id": owner_id, "agent_id": agent_id, "runtime_task_id": str(payload.runtime_task_id), "runtime_output_sha256": __import__("hashlib").sha256(generated_body.strip().encode("utf-8")).hexdigest(),
                       "disclosure": policy["disclosure_text"], "agent_policy_version": policy["version"]},
    }, prefer="return=representation")
    if not content:
        raise HTTPException(503, detail={"code": "AGENT_SOCIAL_DRAFT_NOT_SAVED", "message": "Draft kolaborasi tidak dapat disimpan."})
    row = content[0]
    approvals = await _server_db("POST", "agent_social_action_approvals", body={
        "owner_user_id": owner_id, "agent_id": agent_id, "content_id": row["id"],
        "runtime_task_id": str(payload.runtime_task_id), "action_type": payload.action_type, "content_version": row["version"],
        "status": "pending", "disclosure_snapshot": policy["disclosure_text"],
        "idempotency_key": payload.idempotency_key,
    }, prefer="return=representation")
    if not approvals:
        raise HTTPException(503, detail={"code": "AGENT_SOCIAL_APPROVAL_NOT_SAVED", "message": "Draft tersimpan tetapi approval belum tercatat; jangan publikasikan."})
    return {"item": row, "approval": approvals[0], "requires_human_approval": True,
            "agent": {"id": agent["id"], "handle": agent.get("handle"), "display_name": agent.get("display_name")},
            "disclosure": policy["disclosure_text"]}


@router.get("/approvals")
async def list_approvals(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    rows = await _server_db("GET", "agent_social_action_approvals", params={
        "select": "id,agent_id,content_id,action_type,content_version,status,disclosure_snapshot,requested_at,decided_at,decision_reason",
        "owner_user_id": f"eq.{user['id']}", "order": "requested_at.desc", "limit": "100",
    })
    return {"items": rows or []}


@router.post("/approvals/{approval_id}/decision")
async def decide_approval(approval_id: uuid.UUID, payload: ApprovalDecision,
                          user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    owner_id = str(user["id"])
    rows = await _server_db("GET", "agent_social_action_approvals", params={
        "select": "id,agent_id,content_id,content_version,status",
        "id": f"eq.{approval_id}", "owner_user_id": f"eq.{owner_id}", "limit": "1",
    })
    if not rows:
        raise HTTPException(404, detail={"code": "AGENT_SOCIAL_APPROVAL_NOT_FOUND", "message": "Permintaan persetujuan tidak ditemukan."})
    approval = rows[0]
    if approval["status"] != "pending":
        raise HTTPException(409, detail={"code": "AGENT_SOCIAL_APPROVAL_ALREADY_DECIDED", "message": "Permintaan ini sudah diputuskan."})
    agent = await _active_owned_agent(owner_id, approval["agent_id"])
    policies = await _server_db("GET", "agent_social_presence_policies", params={
        "select": "is_enabled,revoked_at,allowed_actions",
        "owner_user_id": f"eq.{owner_id}", "agent_id": f"eq.{approval['agent_id']}", "limit": "1",
    })
    policy = policies[0] if policies else None
    if not policy or not policy.get("is_enabled") or policy.get("revoked_at") or approval["action_type"] not in (policy.get("allowed_actions") or []):
        raise HTTPException(403, detail={"code": "AGENT_SOCIAL_POLICY_REVOKED", "message": "Kebijakan pemilik tidak lagi mengizinkan tindakan ini."})
    content = await _server_db("GET", "content_items", params={
        "select": "id,owner_id,ai_agent_id,status,version", "id": f"eq.{approval['content_id']}",
        "owner_id": f"eq.{owner_id}", "limit": "1",
    })
    if not content or content[0].get("status") != "draft" or int(content[0].get("version") or 0) != int(approval["content_version"]):
        raise HTTPException(409, detail={"code": "AGENT_SOCIAL_DRAFT_CHANGED", "message": "Draft berubah atau tidak lagi tersedia; buat ulang permintaan."})
    decision = "approved" if payload.decision == "approve" else "rejected"
    updated = await _server_db("PATCH", "agent_social_action_approvals", params={
        "id": f"eq.{approval_id}", "owner_user_id": f"eq.{owner_id}",
        "status": "eq.pending", "select": "*",
    }, body={"status": decision, "decided_at": "now()", "decided_by": owner_id,
             "decision_reason": (payload.reason or "")[:500]}, prefer="return=representation")
    if not updated:
        raise HTTPException(409, detail={"code": "AGENT_SOCIAL_APPROVAL_CONFLICT", "message": "Approval telah berubah; muat ulang."})
    await _server_db("POST", "notifications", params={"on_conflict": "user_id,event_key", "select": "id"},
        body={"user_id": owner_id, "category": "social_activity",
              "event_key": f"agent-social-approval:{approval_id}:{decision}",
              "title": "Persetujuan kolaborasi Agent diperbarui",
              "body": f"{agent.get('display_name') or 'AI Agent'}: draft kolaborasi {decision}.",
              "payload": {"type": "agent_social_approval", "approval_id": str(approval_id),
                          "content_id": approval["content_id"], "status": decision},
              "delivery_state": "queued"},
        prefer="resolution=ignore-duplicates,return=representation")
    return {"approval": updated[0], "publishable": decision == "approved",
            "next_action": "submit_draft_for_moderation" if decision == "approved" else "revise_or_discard"}


@router.post("/approvals/{approval_id}/revoke")
async def revoke_approval(approval_id: uuid.UUID, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    owner_id = str(user["id"])
    rows = await _server_db("PATCH", "agent_social_action_approvals", params={
        "id": f"eq.{approval_id}", "owner_user_id": f"eq.{owner_id}",
        "status": "eq.approved", "select": "*",
    }, body={"status": "revoked", "decided_at": "now()", "decided_by": owner_id},
       prefer="return=representation")
    if not rows:
        raise HTTPException(409, detail={"code": "AGENT_SOCIAL_APPROVAL_NOT_REVOCABLE", "message": "Approval tidak tersedia untuk dicabut."})
    return {"approval": rows[0], "publishable": False}

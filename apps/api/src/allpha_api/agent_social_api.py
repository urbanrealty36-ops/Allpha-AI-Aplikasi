"""WP-06 owner-governed Human + AI Agent social presence contracts."""
from __future__ import annotations

import uuid
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from allpha_api.auth import current_user
from allpha_api.content_api import _server_db

router = APIRouter(prefix="/v1/agent-social", tags=["agent-social-presence"])

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
    target_comment_id: uuid.UUID | None = None
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
    result = await _server_db("POST", "rpc/save_agent_social_policy", body={
        "p_owner_user_id": owner_id,
        "p_agent_id": str(agent_id),
        "p_allowed_actions": payload.allowed_actions,
        "p_approval_mode": payload.approval_mode,
        "p_disclosure_text": payload.disclosure_text,
        "p_is_enabled": payload.is_enabled,
        "p_expected_version": payload.expected_version,
    })
    if not isinstance(result, dict) or result.get("outcome") != "saved" or not result.get("policy"):
        raise HTTPException(503, detail={"code": "AGENT_SOCIAL_POLICY_UNCONFIRMED",
                                         "message": "Kebijakan dan audit belum dapat dikonfirmasi."})
    return {"policy": result["policy"], "revoked_approvals": result.get("revoked_approvals", 0)}


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
    result = await _server_db("POST", "rpc/request_agent_social_draft", body={
        "p_owner_user_id": owner_id,
        "p_agent_id": agent_id,
        "p_runtime_task_id": str(payload.runtime_task_id),
        "p_action_type": payload.action_type,
        "p_content_type": payload.content_type,
        "p_visibility": payload.visibility,
        "p_body": generated_body.strip(),
        "p_target_content_id": str(payload.target_content_id) if payload.target_content_id else None,
        "p_target_comment_id": str(payload.target_comment_id) if payload.target_comment_id else None,
        "p_idempotency_key": payload.idempotency_key,
    })
    if not isinstance(result, dict) or result.get("outcome") not in ("created", "replayed"):
        raise HTTPException(503, detail={"code": "AGENT_SOCIAL_DRAFT_UNCONFIRMED",
                                         "message": "Draft dan approval belum dapat dikonfirmasi."})
    return {
        "item": result.get("item"),
        "approval": result.get("approval"),
        "requires_human_approval": True,
        "replayed": result.get("outcome") == "replayed",
        "agent": {"id": agent["id"], "handle": agent.get("handle"), "display_name": agent.get("display_name")},
        "disclosure": result.get("disclosure") or (policy or {}).get("disclosure_text"),
    }

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
    """The transactional database function is the sole source of truth.

    Approval state, comment/Story DM side effects, audit and ENG-P20 inbox
    notifications are committed or rolled back together by this RPC.
    """
    result = await _server_db("POST", "rpc/decide_agent_social_approval", body={
        "p_approval_id": str(approval_id),
        "p_owner_user_id": str(user["id"]),
        "p_decision": payload.decision,
        "p_reason": (payload.reason or "")[:500],
    })
    if not isinstance(result, dict) or result.get("outcome") not in ("approved", "rejected", "replayed"):
        raise HTTPException(503, detail={"code": "AGENT_SOCIAL_DECISION_UNCONFIRMED",
                                         "message": "Hasil keputusan belum dapat dikonfirmasi; muat ulang sebelum mencoba lagi."})
    approval = result.get("approval") or {}
    execution = result.get("execution") or {}
    return {
        "outcome": result["outcome"],
        "approval": approval,
        "execution": execution,
        "publishable": result["outcome"] in ("approved", "replayed") and approval.get("status") == "approved",
        "next_action": execution.get("next_action") or (
            "open_story_dm" if execution.get("kind") == "story_dm" else
            "open_comment_thread" if execution.get("kind") == "comment" else
            "submit_draft_for_moderation" if approval.get("status") == "approved" else "revise_or_discard"
        ),
    }

@router.post("/approvals/{approval_id}/revoke")
async def revoke_approval(approval_id: uuid.UUID, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    """Revoke approval, audit and notify atomically in the canonical transaction."""
    result = await _server_db("POST", "rpc/revoke_agent_social_approval", body={
        "p_approval_id": str(approval_id),
        "p_owner_user_id": str(user["id"]),
        "p_reason": "owner_revoked",
    })
    if not isinstance(result, dict) or result.get("outcome") not in ("revoked", "replayed"):
        raise HTTPException(503, detail={"code": "AGENT_SOCIAL_REVOKE_UNCONFIRMED",
                                         "message": "Pencabutan belum dapat dikonfirmasi; muat ulang sebelum mencoba lagi."})
    return {"outcome": result["outcome"], "approval": result.get("approval"),
            "execution": result.get("execution"), "publishable": False}

"""WP-06 owner-governed Human + AI Agent social presence contracts."""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator

from allpha_api.auth import current_user
from allpha_api.content_api import _server_db

router = APIRouter(prefix="/v1/agent-social", tags=["agent-social-presence"])


def _automation_schema_enabled() -> bool:
    return os.getenv("ALLPHA_AGENT_SOCIAL_AUTOMATION_SCHEMA_ENABLED", "false").lower() == "true"


def _require_automation_schema() -> None:
    if not _automation_schema_enabled():
        raise HTTPException(503, detail={
            "code": "AGENT_SOCIAL_AUTOMATION_SCHEMA_NOT_ACTIVE",
            "message": "Schema automation WP-06 belum diterapkan pada database kanonis; perubahan belum diaktifkan.",
        })


class PolicyWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    allowed_actions: list[Literal["draft_post", "draft_comment", "draft_reply", "suggest_repost", "draft_story"]] = Field(default_factory=lambda: ["draft_post"], max_length=5)
    approval_mode: Literal["every_post", "disabled"] = "every_post"
    disclosure_text: str = Field(default="Dibuat bersama AI Agent", min_length=8, max_length=180)
    is_enabled: bool = True
    expected_version: int | None = Field(default=None, ge=1)



class AutomationPolicyWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    auto_reply_channels: list[Literal["comments", "mentions", "dm", "live_chat"]] = Field(default_factory=list, max_length=4)
    blocked_topics: list[str] = Field(default_factory=list, max_length=100)
    reply_tone: Literal["friendly_concise", "professional", "warm", "formal"] = "friendly_concise"
    allowed_tool_scopes: list[str] = Field(default_factory=list, max_length=20)
    max_replies_per_minute: int = Field(default=1, ge=1, le=20)
    daily_credit_budget: int = Field(default=0, ge=0)
    quiet_hours: dict[str, Any] = Field(default_factory=dict)
    escalation_rules: dict[str, Any] = Field(default_factory=dict)
    expected_version: int = Field(ge=1)


class TakeoverWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    takeover_active: bool
    reason: str = Field(default="owner_manual_takeover", min_length=3, max_length=500)


class AutomationGrantWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    granted_scopes: list[Literal["comments", "mentions", "dm", "live_chat"]] = Field(min_length=1, max_length=4)
    idempotency_key: str = Field(min_length=8, max_length=160, pattern=r"^[A-Za-z0-9._:-]+$")
    expires_at: datetime

    @model_validator(mode="after")
    def validate_grant(self) -> "AutomationGrantWrite":
        if len(set(self.granted_scopes)) != len(self.granted_scopes):
            raise ValueError("granted_scopes must not contain duplicates")
        if self.expires_at.tzinfo is None or self.expires_at <= datetime.now(timezone.utc):
            raise ValueError("expires_at must be a future timezone-aware timestamp")
        return self


class AutomationGrantRevoke(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(default="owner_revoked", min_length=3, max_length=500)


@router.get("/automation")
async def get_automation(agent_id: uuid.UUID, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    owner_id = str(user["id"])
    await _active_owned_agent(owner_id, str(agent_id))
    if not _automation_schema_enabled():
        return {"policy": None, "auto_reply_runtime_enabled": False,
                "runtime_reason": "AGENT_SOCIAL_AUTOMATION_SCHEMA_NOT_ACTIVE"}
    rows = await _server_db("GET", "agent_social_presence_policies", params={
        "select": "id,agent_id,version,auto_reply_enabled,auto_reply_channels,blocked_topics,reply_tone,allowed_tool_scopes,max_replies_per_minute,daily_credit_budget,quiet_hours,escalation_rules,owner_approval_required,output_moderation_required,takeover_active,takeover_started_at,automation_version",
        "owner_user_id": f"eq.{owner_id}", "agent_id": f"eq.{agent_id}", "limit": "1",
    })
    return {"policy": rows[0] if rows else None, "auto_reply_runtime_enabled": False,
            "runtime_reason": "AUTO_REPLY_RUNTIME_NOT_CONNECTED"}


@router.put("/automation/{agent_id}")
async def put_automation(agent_id: uuid.UUID, payload: AutomationPolicyWrite,
                         user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    owner_id = str(user["id"])
    await _active_owned_agent(owner_id, str(agent_id))
    _require_automation_schema()
    if any(not topic.strip() or len(topic.strip()) > 120 for topic in payload.blocked_topics):
        raise HTTPException(422, detail={"code": "AGENT_SOCIAL_BLOCKED_TOPIC_INVALID", "message": "Topik yang diblokir harus berisi 1–120 karakter."})
    if any(not scope.strip() or len(scope.strip()) > 120 for scope in payload.allowed_tool_scopes):
        raise HTTPException(422, detail={"code": "AGENT_SOCIAL_TOOL_SCOPE_INVALID", "message": "Tool scope harus berisi 1–120 karakter."})
    result = await _server_db("POST", "rpc/save_agent_social_automation_policy", body={
        "p_owner_user_id": owner_id, "p_agent_id": str(agent_id),
        "p_auto_reply_channels": payload.auto_reply_channels,
        "p_blocked_topics": [item.strip() for item in payload.blocked_topics],
        "p_reply_tone": payload.reply_tone, "p_allowed_tool_scopes": payload.allowed_tool_scopes,
        "p_max_replies_per_minute": payload.max_replies_per_minute,
        "p_daily_credit_budget": payload.daily_credit_budget,
        "p_quiet_hours": payload.quiet_hours, "p_escalation_rules": payload.escalation_rules,
        "p_expected_version": payload.expected_version,
    })
    if not isinstance(result, dict) or result.get("outcome") != "saved":
        raise HTTPException(503, detail={"code": "AGENT_SOCIAL_AUTOMATION_UNCONFIRMED", "message": "Pengaturan belum dapat dikonfirmasi."})
    return {"policy": result.get("policy"), "auto_reply_runtime_enabled": False,
            "reason": result.get("reason")}


@router.post("/takeover/{agent_id}")
async def set_takeover(agent_id: uuid.UUID, payload: TakeoverWrite,
                       user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    owner_id = str(user["id"])
    await _active_owned_agent(owner_id, str(agent_id))
    _require_automation_schema()
    result = await _server_db("POST", "rpc/set_agent_social_takeover", body={
        "p_owner_user_id": owner_id, "p_agent_id": str(agent_id),
        "p_takeover_active": payload.takeover_active, "p_reason": payload.reason,
    })
    if not isinstance(result, dict) or result.get("outcome") != "saved":
        raise HTTPException(503, detail={"code": "AGENT_SOCIAL_TAKEOVER_UNCONFIRMED", "message": "Perubahan takeover belum dapat dikonfirmasi."})
    return {"policy": result.get("policy"), "revoked_pending_approvals": result.get("revoked_pending_approvals", 0),
            "automation_grants_revoked": result.get("automation_grants_revoked", 0),
            "tasks_cancelled": result.get("tasks_cancelled", 0),
            "tasks_signalled": result.get("tasks_signalled", 0),
            "auto_reply_enabled": False, "outcome": "saved"}


@router.get("/automation/grants")
async def list_automation_grants(agent_id: uuid.UUID, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    owner_id = str(user["id"])
    await _active_owned_agent(owner_id, str(agent_id))
    if not _automation_schema_enabled():
        return {"items": [], "schema_active": False, "auto_reply_runtime_enabled": False}
    rows = await _server_db("GET", "agent_social_automation_grants", params={
        "select": "id,agent_id,granted_scopes,policy_version,status,expires_at,granted_at,revoked_at,revoke_reason",
        "owner_user_id": f"eq.{owner_id}", "agent_id": f"eq.{agent_id}",
        "order": "granted_at.desc", "limit": "100",
    })
    return {"items": rows or [], "schema_active": True, "auto_reply_runtime_enabled": False}


@router.post("/automation/grants")
async def create_automation_grant(agent_id: uuid.UUID, payload: AutomationGrantWrite,
                                  user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    owner_id = str(user["id"])
    await _active_owned_agent(owner_id, str(agent_id))
    _require_automation_schema()
    result = await _server_db("POST", "rpc/grant_agent_social_automation_scopes", body={
        "p_owner_user_id": owner_id, "p_agent_id": str(agent_id),
        "p_granted_scopes": payload.granted_scopes,
        "p_idempotency_key": payload.idempotency_key,
        "p_expires_at": payload.expires_at.astimezone(timezone.utc).isoformat(),
    })
    if not isinstance(result, dict) or result.get("outcome") not in ("created", "replayed"):
        raise HTTPException(503, detail={
            "code": "AGENT_SOCIAL_AUTOMATION_GRANT_UNCONFIRMED",
            "message": "Permission automation belum dapat dikonfirmasi.",
        })
    return {"outcome": result["outcome"], "grant": result.get("grant"),
            "auto_reply_runtime_enabled": False,
            "runtime_reason": result.get("reason", "AUTO_REPLY_RUNTIME_NOT_CONNECTED")}


@router.post("/automation/grants/{grant_id}/revoke")
async def revoke_automation_grant(agent_id: uuid.UUID, grant_id: uuid.UUID,
                                  payload: AutomationGrantRevoke,
                                  user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    owner_id = str(user["id"])
    await _active_owned_agent(owner_id, str(agent_id))
    _require_automation_schema()
    result = await _server_db("POST", "rpc/revoke_agent_social_automation_grant", body={
        "p_owner_user_id": owner_id, "p_agent_id": str(agent_id),
        "p_grant_id": str(grant_id), "p_reason": payload.reason,
    })
    if not isinstance(result, dict) or result.get("outcome") not in ("revoked", "replayed"):
        raise HTTPException(503, detail={
            "code": "AGENT_SOCIAL_AUTOMATION_REVOKE_UNCONFIRMED",
            "message": "Pencabutan permission automation belum dapat dikonfirmasi.",
        })
    return {"outcome": result["outcome"], "grant": result.get("grant"),
            "auto_reply_runtime_enabled": False}


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

    @model_validator(mode="after")
    def validate_action_targets(self) -> "CoauthoredDraft":
        if self.action_type == "draft_post":
            if self.target_content_id is not None or self.target_comment_id is not None or self.content_type == "story":
                raise ValueError("draft_post cannot target another item and cannot use story content_type")
        elif self.action_type == "draft_comment":
            if self.target_content_id is None or self.target_comment_id is not None or self.content_type != "text":
                raise ValueError("draft_comment requires a content target and text content_type")
        elif self.action_type == "draft_reply":
            if self.target_content_id is None or self.target_comment_id is None or self.content_type != "text":
                raise ValueError("draft_reply requires content and comment targets and text content_type")
        elif self.action_type == "suggest_repost":
            if self.target_content_id is None or self.target_comment_id is not None or self.content_type != "text":
                raise ValueError("suggest_repost requires a content target and text content_type")
        elif self.action_type == "draft_story":
            if self.target_content_id is None or self.target_comment_id is not None or self.content_type != "story":
                raise ValueError("draft_story requires a Story target and story content_type")
        return self


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
        "select": "id,agent_id,content_id,target_content_id,target_comment_id,action_type,content_version,status,disclosure_snapshot,requested_at,decided_at,decision_reason,execution_result",
        "owner_user_id": f"eq.{user['id']}", "order": "requested_at.desc", "limit": "100",
    })
    return {
        "items": rows or [],
        "action_dispatch_enabled": os.getenv("ALLPHA_AGENT_SOCIAL_ACTION_DISPATCH_ENABLED", "false").lower() == "true",
        "dispatch_blocked_actions": ["draft_post", "draft_comment", "draft_reply", "suggest_repost"],
    }


@router.post("/approvals/{approval_id}/decision")
async def decide_approval(approval_id: uuid.UUID, payload: ApprovalDecision,
                          user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    """The transactional database function is the sole source of truth.

    Approval state, comment/Story DM side effects, audit and ENG-P20 inbox
    notifications are committed or rolled back together by this RPC.
    """
    approval_rows = await _server_db("GET", "agent_social_action_approvals", params={
        "select": "id,action_type,status",
        "id": f"eq.{approval_id}", "owner_user_id": f"eq.{user['id']}", "limit": "1",
    })
    if not approval_rows:
        raise HTTPException(404, detail={"code": "AGENT_SOCIAL_APPROVAL_NOT_FOUND",
                                         "message": "Permintaan persetujuan tidak ditemukan."})
    action_type = str(approval_rows[0].get("action_type") or "")
    approval_status = str(approval_rows[0].get("status") or "")
    dispatch_actions = {"draft_post", "draft_comment", "draft_reply", "suggest_repost"}
    if (payload.decision == "approve" and approval_status == "pending" and action_type in dispatch_actions
            and os.getenv("ALLPHA_AGENT_SOCIAL_ACTION_DISPATCH_ENABLED", "false").lower() != "true"):
        raise HTTPException(503, detail={
            "code": "AGENT_SOCIAL_ACTION_SCHEMA_NOT_ACTIVE",
            "message": "Eksekusi aksi sosial Agent menunggu migration atribusi dan dispatch WP-06 serta aktivasi backend. Approval belum diproses.",
        })
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
        "publishable": False,
        "approval_complete": result["outcome"] in ("approved", "replayed") and approval.get("status") == "approved",
        "submitted_for_moderation": execution.get("kind") == "post_moderation",
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

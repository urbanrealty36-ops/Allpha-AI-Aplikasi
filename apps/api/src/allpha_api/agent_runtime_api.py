"""Authenticated FastAPI endpoints for the ENG-P10 Agent Runtime."""
from __future__ import annotations

import hashlib
import json
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from allpha_api.agent_runtime import (
    AgentRuntime, AgentRuntimeBlocked, AgentTask, AgentTaskEnvelope,
    AgentTaskState, RuntimeAuthorization,
)
from allpha_api.agent_runtime_store import AgentRuntimePersistenceError, AgentRuntimeStore
from allpha_api.auth import current_user
from allpha_api.tool_registry import UnknownToolError, get_tool

router = APIRouter(prefix="/v1/agent-runtime", tags=["agent-runtime"])
_runtime = AgentRuntime()


class SessionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    agent_id: uuid.UUID
    title: str = Field(default="Percakapan baru", min_length=1, max_length=120)
    metadata: dict[str, Any] = Field(default_factory=dict)


class TaskCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session_id: uuid.UUID
    skill_id: uuid.UUID
    tool_key: str = Field(min_length=3, max_length=100, pattern=r"^[a-z][a-z0-9_.:-]+$")
    inputs: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str = Field(min_length=8, max_length=160, pattern=r"^[A-Za-z0-9._:-]+$")


def _store() -> AgentRuntimeStore:
    try:
        return AgentRuntimeStore.from_environment()
    except ValueError as exc:
        raise HTTPException(status_code=503, detail={
            "code": "AGENT_RUNTIME_NOT_CONFIGURED",
            "message": "Penyimpanan Agent Runtime belum dikonfigurasi.",
        }) from exc


def _error(exc: AgentRuntimePersistenceError) -> HTTPException:
    return HTTPException(status_code=503, detail={
        "code": "AGENT_RUNTIME_STORAGE_UNAVAILABLE",
        "message": "Status penyimpanan Agent Runtime tidak dapat dipastikan.",
    })


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _event(state: str, trace_id: str, reason: str | None = None) -> dict[str, Any]:
    return {"state": state, "at": _now(), "trace_id": trace_id, "reason_code": reason}


async def _owned_session(store: AgentRuntimeStore, owner_id: str, session_id: str) -> dict[str, Any]:
    try:
        row = await store.get_session(owner_id, session_id)
    except AgentRuntimePersistenceError as exc:
        raise _error(exc) from exc
    if not row:
        raise HTTPException(status_code=404, detail={"code": "SESSION_NOT_FOUND", "message": "Sesi tidak ditemukan."})
    return row


@router.post("/sessions", status_code=201)
async def create_session(payload: SessionCreate, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    store, owner_id = _store(), str(user["id"])
    try:
        agent = await store.get_agent(owner_id, str(payload.agent_id))
        if not agent or agent.get("status") == "archived":
            raise HTTPException(status_code=404, detail={"code": "AGENT_NOT_FOUND", "message": "Agent tidak ditemukan."})
        row = await store.create_session({
            "owner_user_id": owner_id, "agent_id": str(payload.agent_id),
            "title": payload.title, "metadata": payload.metadata,
        })
        return {"session": row}
    except AgentRuntimePersistenceError as exc:
        raise _error(exc) from exc


@router.get("/sessions")
async def list_sessions(limit: int = 50, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    try:
        return {"items": await _store().list_sessions(str(user["id"]), limit=limit)}
    except AgentRuntimePersistenceError as exc:
        raise _error(exc) from exc


@router.get("/sessions/{session_id}")
async def get_session(session_id: uuid.UUID, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    store, owner_id = _store(), str(user["id"])
    session = await _owned_session(store, owner_id, str(session_id))
    try:
        return {"session": session, "tasks": await store.list_tasks(owner_id, str(session_id), limit=50)}
    except AgentRuntimePersistenceError as exc:
        raise _error(exc) from exc


@router.post("/tasks", status_code=201)
async def create_task(payload: TaskCreate, request: Request,
                      user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    store, owner_id = _store(), str(user["id"])
    session = await _owned_session(store, owner_id, str(payload.session_id))
    if session.get("status") != "active":
        raise HTTPException(status_code=409, detail={"code": "SESSION_NOT_ACTIVE", "message": "Sesi tidak aktif."})
    agent_id = str(session["agent_id"])
    try:
        agent = await store.get_agent(owner_id, agent_id)
        skill = await store.get_skill(owner_id, agent_id, str(payload.skill_id))
        if not agent or not skill or skill.get("status") != "published":
            raise HTTPException(status_code=404, detail={"code": "PUBLISHED_SKILL_NOT_FOUND", "message": "Skill terpublikasi tidak ditemukan."})
        try:
            tool = get_tool(payload.tool_key)
        except UnknownToolError as exc:
            raise HTTPException(status_code=422, detail={"code": "UNKNOWN_TOOL", "message": "Tool tidak terdaftar."}) from exc
        if payload.tool_key not in (skill.get("tool_dependencies") or []):
            raise HTTPException(status_code=403, detail={"code": "TOOL_NOT_DECLARED", "message": "Tool tidak tercantum pada Skill."})
        try:
            encoded = json.dumps({
                "session_id": str(payload.session_id), "skill_id": str(payload.skill_id),
                "tool_key": payload.tool_key, "inputs": payload.inputs,
            }, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
        except (TypeError, ValueError, UnicodeEncodeError) as exc:
            raise HTTPException(status_code=422, detail={"code": "INVALID_TASK_INPUT", "message": "Input task harus berupa JSON valid."}) from exc
        if len(encoded) > 16_384:
            raise HTTPException(status_code=413, detail={"code": "TASK_INPUT_TOO_LARGE", "message": "Input task melebihi 16 KiB."})
        fingerprint = hashlib.sha256(encoded).hexdigest()
        trace_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        body = {
            "owner_user_id": owner_id, "session_id": str(payload.session_id),
            "agent_id": agent_id, "skill_id": str(payload.skill_id),
            "agent_version": int(agent["version"]), "skill_version": int(skill["version"]),
            "state": "created", "idempotency_key": payload.idempotency_key,
            "request_fingerprint": fingerprint, "tool_key": payload.tool_key,
            "input_payload": payload.inputs, "event_log": [_event("created", trace_id)],
            "trace_id": trace_id,
        }
        try:
            row = await store.create_task(body)
            return {"task": row, "idempotent_replay": False}
        except AgentRuntimePersistenceError:
            existing = await store.find_task_by_idempotency(owner_id, payload.idempotency_key)
            if existing:
                if existing.get("request_fingerprint") != fingerprint:
                    raise HTTPException(status_code=409, detail={"code": "IDEMPOTENCY_CONFLICT", "message": "Idempotency key sudah digunakan untuk payload berbeda."})
                return {"task": existing, "idempotent_replay": True}
            raise
    except AgentRuntimePersistenceError as exc:
        raise _error(exc) from exc


@router.get("/tasks/{task_id}")
async def get_task(task_id: uuid.UUID, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    try:
        row = await _store().get_task(str(user["id"]), str(task_id))
    except AgentRuntimePersistenceError as exc:
        raise _error(exc) from exc
    if not row:
        raise HTTPException(status_code=404, detail={"code": "TASK_NOT_FOUND", "message": "Task tidak ditemukan."})
    return {"task": row}


@router.post("/tasks/{task_id}/cancel")
async def cancel_task(task_id: uuid.UUID, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    store, owner_id = _store(), str(user["id"])
    try:
        row = await store.get_task(owner_id, str(task_id))
        if not row:
            raise HTTPException(status_code=404, detail={"code": "TASK_NOT_FOUND", "message": "Task tidak ditemukan."})
        if row["state"] in {"succeeded", "partially_succeeded", "failed", "cancelled", "timed_out", "budget_exhausted"}:
            return {"task": row, "cancelled": row["state"] == "cancelled"}
        if row["state"] not in {"created", "queued", "waiting_for_approval", "waiting_for_input"}:
            raise HTTPException(status_code=409, detail={"code": "TASK_NOT_CANCELLABLE", "message": "Task sudah berjalan; pembatalan langsung belum tersedia untuk state ini."})
        event_log = list(row.get("event_log") or [])
        event_log.append(_event("cancelled", row["trace_id"], "owner_requested"))
        updated = await store.update_task(owner_id, str(task_id), {
            "state": "cancelled", "cancel_requested": True, "event_log": event_log,
            "updated_at": _now(), "completed_at": _now(),
        }, expected_state=row["state"])
        if not updated:
            latest = await store.get_task(owner_id, str(task_id))
            if latest and latest["state"] == "cancelled":
                return {"task": latest, "cancelled": True}
            raise HTTPException(status_code=409, detail={"code": "TASK_STATE_CHANGED", "message": "State task berubah; muat ulang sebelum mencoba lagi."})
        return {"task": updated, "cancelled": True}
    except AgentRuntimePersistenceError as exc:
        raise _error(exc) from exc


@router.post("/tasks/{task_id}/recover")
async def recover_task(task_id: uuid.UUID, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    """Recover durable task state without blindly replaying an unknown side effect."""
    store, owner_id = _store(), str(user["id"])
    try:
        row = await store.get_task(owner_id, str(task_id))
        if not row:
            raise HTTPException(status_code=404, detail={"code": "TASK_NOT_FOUND", "message": "Task tidak ditemukan."})
        if row["state"] in {"succeeded", "partially_succeeded", "failed", "cancelled", "timed_out", "budget_exhausted"}:
            return {"task": row, "recovered": True, "replay_performed": False}
        if row["state"] != "executing":
            return {"task": row, "recovered": True, "replay_performed": False}
        try:
            updated_at = datetime.fromisoformat(str(row["updated_at"]).replace("Z", "+00:00"))
        except (KeyError, TypeError, ValueError):
            raise HTTPException(status_code=409, detail={"code": "TASK_RECOVERY_TIME_UNKNOWN", "message": "Waktu update task tidak valid; tidak dilakukan replay otomatis."})
        age_seconds = (datetime.now(timezone.utc) - updated_at.astimezone(timezone.utc)).total_seconds()
        if age_seconds < 120:
            raise HTTPException(status_code=409, detail={"code": "TASK_STILL_RUNNING", "message": "Task masih berada dalam jendela eksekusi; coba pemulihan kembali setelah 120 detik."})
        events = list(row.get("event_log") or [])
        events.append(_event("failed", row["trace_id"], "execution_outcome_unknown_no_replay"))
        updated = await store.update_task(owner_id, str(task_id), {
            "state": "failed", "error_code": "EXECUTION_OUTCOME_UNKNOWN",
            "event_log": events, "updated_at": _now(), "completed_at": _now(),
        }, expected_state="executing")
        if not updated:
            latest = await store.get_task(owner_id, str(task_id))
            if latest and latest["state"] in {"succeeded", "failed", "cancelled", "timed_out"}:
                return {"task": latest, "recovered": True, "replay_performed": False}
            raise HTTPException(status_code=409, detail={"code": "TASK_STATE_CHANGED", "message": "State task berubah saat pemulihan; muat ulang."})
        return {"task": updated, "recovered": True, "replay_performed": False}
    except AgentRuntimePersistenceError as exc:
        raise _error(exc) from exc


@router.post("/tasks/{task_id}/execute")
async def execute_task(task_id: uuid.UUID, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    store, owner_id = _store(), str(user["id"])
    try:
        row = await store.get_task(owner_id, str(task_id))
        if not row:
            raise HTTPException(status_code=404, detail={"code": "TASK_NOT_FOUND", "message": "Task tidak ditemukan."})
        if row["state"] == "succeeded":
            return {"task": row, "idempotent_replay": True}
        if row["state"] == "cancelled":
            raise HTTPException(status_code=409, detail={"code": "TASK_CANCELLED", "message": "Task telah dibatalkan."})
        if row["state"] != "created":
            raise HTTPException(status_code=409, detail={"code": "TASK_NOT_EXECUTABLE", "message": "Task tidak berada pada state yang dapat dieksekusi."})
        agent = await store.get_agent(owner_id, row["agent_id"])
        skill = await store.get_skill(owner_id, row["agent_id"], row["skill_id"])
        capability = await store.get_approved_capability(row["agent_id"], row["tool_key"])
        if not agent or not skill or not capability or not capability.get("runtime_policy_id"):
            raise HTTPException(status_code=409, detail={"code": "RUNTIME_POLICY_UNAVAILABLE", "message": "Capability harus terikat ke policy runtime terdaftar dan disetujui."})
        policy = await store.get_approved_runtime_policy(row["agent_id"], str(capability["runtime_policy_id"]))
        if not policy or policy.get("policy_version") != capability.get("policy_version"):
            raise HTTPException(status_code=409, detail={"code": "RUNTIME_POLICY_UNAVAILABLE", "message": "Referensi policy tidak aktif atau tidak cocok dengan Agent."})
        try:
            canonical_policy = json.dumps(policy["policy_document"], ensure_ascii=False, sort_keys=True,
                                          separators=(",", ":"), allow_nan=False).encode("utf-8")
            actual_digest = hashlib.sha256(canonical_policy).hexdigest()
        except (KeyError, TypeError, ValueError, UnicodeEncodeError) as exc:
            raise HTTPException(status_code=409, detail={"code": "RUNTIME_POLICY_INVALID", "message": "Dokumen policy tidak valid."}) from exc
        if actual_digest != policy.get("policy_digest"):
            raise HTTPException(status_code=409, detail={"code": "RUNTIME_POLICY_DIGEST_MISMATCH", "message": "Digest policy tidak cocok; eksekusi ditolak."})
        if row["tool_key"] not in (policy.get("approved_tool_keys") or []):
            raise HTTPException(status_code=403, detail={"code": "RUNTIME_POLICY_TOOL_DENIED", "message": "Tool tidak tercantum dalam policy runtime."})
        granted_scopes = set(capability.get("required_permission_scopes") or [])
        policy_scopes = set(policy.get("required_permission_scopes") or [])
        skill_scopes = set(skill.get("required_permission_scopes") or [])
        if not granted_scopes.issubset(policy_scopes) or not skill_scopes.issubset(policy_scopes):
            raise HTTPException(status_code=403, detail={"code": "RUNTIME_POLICY_SCOPE_DENIED", "message": "Scope capability atau Skill melampaui policy runtime."})
        if int(agent["version"]) != int(row["agent_version"]) or int(skill["version"]) != int(row["skill_version"]):
            raise HTTPException(status_code=409, detail={"code": "PINNED_VERSION_CHANGED", "message": "Versi Agent atau Skill berubah; buat task baru."})
        if skill.get("status") != "published" or row["tool_key"] not in (skill.get("tool_dependencies") or []):
            raise HTTPException(status_code=403, detail={"code": "SKILL_TOOL_NOT_AUTHORIZED", "message": "Skill atau tool tidak lagi diizinkan."})
        lease_token = str(uuid.uuid4())
        claimed = await store.claim_task(owner_id, str(task_id), lease_token, lease_seconds=60)
        if not claimed:
            latest = await store.get_task(owner_id, str(task_id))
            if latest and latest["state"] == "succeeded":
                return {"task": latest, "idempotent_replay": True}
            raise HTTPException(status_code=409, detail={"code": "TASK_ALREADY_CLAIMED", "message": "Task sedang diproses atau lease tidak tersedia."})
        row = claimed
        limits = skill.get("budget_limits") or {}
        max_runtime = min(30, max(1, int(limits.get("max_runtime_seconds", 30))))
        max_calls = min(5, max(1, int(limits.get("max_tool_calls", 1))))
        envelope = AgentTaskEnvelope(
            task_id=str(row["id"]), task_version=int(row["task_version"]),
            requester_id=owner_id, agent_id=str(row["agent_id"]), agent_version=int(row["agent_version"]),
            owner_id=owner_id, skill_id=str(row["skill_id"]), skill_version=int(row["skill_version"]),
            input_classification="user_input", allowed_memory_scope=(),
            allowed_tool_keys=(str(row["tool_key"]),),
            capability_scopes=tuple(skill.get("required_permission_scopes") or ()),
            idempotency_key=str(row["idempotency_key"]), trace_id=str(row["trace_id"]),
            deadline_monotonic=time.monotonic() + max_runtime,
            max_tool_calls=max_calls, max_runtime_seconds=max_runtime,
        )
        auth = RuntimeAuthorization(
            authenticated_owner_id=owner_id, owned_agent_id=str(row["agent_id"]),
            agent_version=int(agent["version"]), skill_id=str(row["skill_id"]),
            skill_version=int(skill["version"]), skill_published=True,
            policy_approved=True, policy_version=str(capability["policy_version"]),
            approved_tool_keys=tuple(policy.get("approved_tool_keys") or ()),
            granted_scopes=tuple(policy.get("required_permission_scopes") or ()),
        )
        task = AgentTask(envelope)
        try:
            result = await _runtime.execute_tool(task, auth, tool_key=str(row["tool_key"]), inputs=row["input_payload"])
            checkpoint_bytes = json.dumps(result, ensure_ascii=False, sort_keys=True,
                                          separators=(",", ":"), allow_nan=False).encode("utf-8")
            checkpoint = await store.append_checkpoint(
                owner_id, str(task_id), lease_token, int(row["task_version"]),
                int(row.get("checkpoint_seq") or 0) + 1, f"tool:{row['tool_key']}",
                str(row["request_fingerprint"]), hashlib.sha256(checkpoint_bytes).hexdigest(), result,
            )
            if not checkpoint:
                raise AgentRuntimePersistenceError("runtime checkpoint could not be durably committed")
            completed = await store.finalize_task(owner_id, str(task_id), lease_token, int(row["task_version"]),
                state=result["state"], output_payload=result, error_code=None,
                event_log=list(row.get("event_log") or []) + result["events"])
            if not completed:
                raise AgentRuntimePersistenceError("task execution result could not be durably committed")
            return {"task": completed, "idempotent_replay": False}
        except (AgentRuntimeBlocked, UnknownToolError) as exc:
            failed_state = task.state.value if task.state.value in {"failed", "timed_out"} else "failed"
            failed_events = list(row.get("event_log") or []) + task.events
            if not task.events or task.events[-1].get("state") not in {"failed", "timed_out"}:
                failed_events.append(_event("failed", row["trace_id"], "runtime_blocked"))
            failed = await store.finalize_task(owner_id, str(task_id), lease_token, int(row["task_version"]),
                state=failed_state, output_payload=None, error_code=task.error_code or "RUNTIME_BLOCKED",
                event_log=failed_events)
            if not failed:
                raise AgentRuntimePersistenceError("runtime failure state could not be durably committed") from exc
            raise HTTPException(status_code=422, detail={"code": "RUNTIME_EXECUTION_FAILED", "message": "Eksekusi tool ditolak atau gagal; task tercatat gagal."}) from exc
    except AgentRuntimePersistenceError as exc:
        raise _error(exc) from exc

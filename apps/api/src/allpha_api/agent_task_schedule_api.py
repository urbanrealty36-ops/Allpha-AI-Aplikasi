"""Authenticated Human Owner task scheduling API for ENG-P11 / Agent Runtime.

Schedule records are durable intent only. A separate server worker must claim each
due occurrence and dispatch it through the canonical Agent Runtime after rechecking
published skill, tool registration, policy, approvals and budget.
"""
from __future__ import annotations

import uuid
import json
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from allpha_api.agent_runtime_store import AgentRuntimePersistenceError, AgentRuntimeStore
from allpha_api.auth import current_user
from allpha_api.tool_registry import UnknownToolError, get_tool
from allpha_api.workflow_engine import WorkflowDefinition, WorkflowNode
from allpha_api.workflow_store import WorkflowPersistenceError, WorkflowStore

router = APIRouter(prefix="/v1/agent-task-schedules", tags=["agent-task-schedules"])

TaskType = Literal["SCHEDULING_POST", "BROADCAST_INFO", "KNOWLEDGE_DISPATCH", "ANALYTICS_REPORT", "SKILL_EXECUTION"]
ScheduleKind = Literal["once", "daily", "weekly"]


class TaskScheduleCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    agent_id: uuid.UUID
    session_id: uuid.UUID
    skill_id: uuid.UUID
    tool_key: str = Field(min_length=3, max_length=100, pattern=r"^[a-z][a-z0-9_.:-]+$")
    title: str = Field(min_length=1, max_length=160)
    instructions: str = Field(min_length=1, max_length=8000)
    task_type: TaskType
    schedule_kind: ScheduleKind
    timezone_name: str = Field(min_length=1, max_length=80)
    local_time: str = Field(pattern=r"^([01][0-9]|2[0-3]):[0-5][0-9]$")
    weekdays: list[int] = Field(default_factory=list, max_length=7)
    run_at: datetime | None = None
    require_approval: bool = True
    granted_permission_scopes: list[str] = Field(default_factory=list, max_length=40)
    budget_limit: dict[str, Any] = Field(default_factory=dict)
    input_payload: dict[str, Any] = Field(default_factory=dict)

    @field_validator("input_payload")
    @classmethod
    def validate_input_payload(cls, value: dict[str, Any]) -> dict[str, Any]:
        try:
            encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
        except (TypeError, ValueError, UnicodeEncodeError) as exc:
            raise ValueError("input_payload must be finite JSON data") from exc
        if len(encoded) > 16_384:
            raise ValueError("input_payload exceeds 16 KiB")
        return value

    @field_validator("weekdays")
    @classmethod
    def validate_weekdays(cls, value: list[int]) -> list[int]:
        if any(day < 0 or day > 6 for day in value) or len(value) != len(set(value)):
            raise ValueError("weekdays must be unique values from 0 (Monday) to 6 (Sunday)")
        return sorted(value)

    @field_validator("timezone_name")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("timezone_name must be an IANA timezone") from exc
        return value

    @model_validator(mode="after")
    def validate_schedule_shape(self) -> "TaskScheduleCreate":
        if self.schedule_kind == "once":
            if self.run_at is None or self.weekdays:
                raise ValueError("once schedules require run_at and no weekdays")
            if self.run_at.tzinfo is None:
                raise ValueError("run_at must include a timezone offset")
            if self.run_at.astimezone(timezone.utc) <= datetime.now(timezone.utc):
                raise ValueError("run_at must be in the future")
        elif self.schedule_kind == "daily":
            if self.run_at is not None or self.weekdays:
                raise ValueError("daily schedules use local_time and no run_at/weekdays")
        elif self.schedule_kind == "weekly":
            if self.run_at is not None or not self.weekdays:
                raise ValueError("weekly schedules require weekdays and no run_at")
        return self


class ScheduleStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["active", "paused", "cancelled"]


def _store() -> AgentRuntimeStore:
    try:
        return AgentRuntimeStore.from_environment()
    except ValueError as exc:
        raise HTTPException(status_code=503, detail={
            "code": "AGENT_TASK_SCHEDULER_NOT_CONFIGURED",
            "message": "Penyimpanan Task Scheduling belum dikonfigurasi.",
        }) from exc


def _storage_error(exc: AgentRuntimePersistenceError) -> HTTPException:
    return HTTPException(status_code=503, detail={
        "code": "AGENT_TASK_SCHEDULE_STORAGE_UNAVAILABLE",
        "message": "Status penyimpanan Task Scheduling belum dapat dipastikan.",
    })


def _next_occurrence(payload: TaskScheduleCreate, now: datetime) -> datetime | None:
    if payload.schedule_kind == "once":
        candidate = payload.run_at
        assert candidate is not None
        candidate = candidate.astimezone(timezone.utc)
        return candidate if candidate > now else None
    zone = ZoneInfo(payload.timezone_name)
    local_now = now.astimezone(zone)
    hour, minute = (int(part) for part in payload.local_time.split(":"))
    for offset in range(0, 15):
        day = local_now.date() + timedelta(days=offset)
        if payload.schedule_kind == "weekly" and day.weekday() not in payload.weekdays:
            continue
        candidate = datetime.combine(day, time(hour, minute), tzinfo=zone)
        if candidate > local_now:
            return candidate.astimezone(timezone.utc)
    raise ValueError("could not calculate next schedule occurrence within bounded horizon")


async def _verify_runtime_binding(store: AgentRuntimeStore, owner_id: str, payload: TaskScheduleCreate) -> dict[str, Any]:
    session = await store.get_session(owner_id, str(payload.session_id))
    if not session or session.get("status") != "active" or session.get("agent_id") != str(payload.agent_id):
        raise HTTPException(status_code=409, detail={
            "code": "AGENT_TASK_SESSION_INVALID", "message": "Sesi aktif harus dimiliki Human Owner dan Agent yang dipilih."
        })
    agent = await store.get_agent(owner_id, str(payload.agent_id))
    skill = await store.get_skill(owner_id, str(payload.agent_id), str(payload.skill_id))
    if not agent or agent.get("status") == "archived":
        raise HTTPException(status_code=404, detail={"code": "AGENT_NOT_FOUND", "message": "Agent tidak ditemukan."})
    if not skill or skill.get("status") != "published":
        raise HTTPException(status_code=409, detail={
            "code": "PUBLISHED_SKILL_REQUIRED", "message": "Task hanya dapat dijadwalkan dengan Skill yang sudah dipublikasikan."
        })
    if payload.tool_key not in (skill.get("tool_dependencies") or []):
        raise HTTPException(status_code=403, detail={
            "code": "SKILL_TOOL_NOT_AUTHORIZED", "message": "Tool tidak tercantum pada Skill yang dipilih."
        })
    try:
        tool = get_tool(payload.tool_key)
    except (UnknownToolError, KeyError) as exc:
        raise HTTPException(status_code=422, detail={
            "code": "REGISTERED_TOOL_REQUIRED", "message": "Tool tidak terdaftar pada registry kanonis."
        }) from exc
    required_scopes = set(tool.required_permission_scopes)
    if not required_scopes.issubset(set(payload.granted_permission_scopes)):
        raise HTTPException(status_code=403, detail={
            "code": "TASK_TOOL_PERMISSION_NOT_GRANTED",
            "message": "Human Owner harus memberikan seluruh scope yang diwajibkan Tool sebelum menjadwalkan Task."
        })
    if payload.task_type != "SKILL_EXECUTION":
        raise HTTPException(status_code=409, detail={
            "code": "TASK_TYPE_TOOL_NOT_IMPLEMENTED",
            "message": "Jenis Task ini belum memiliki Tool kanonis yang dapat dieksekusi; pilih Eksekusi Skill agar tidak terjadi simulasi.",
        })
    capability = await store.get_approved_capability(str(payload.agent_id), payload.tool_key)
    if not capability or not capability.get("runtime_policy_id") or not capability.get("policy_version"):
        raise HTTPException(status_code=409, detail={
            "code": "APPROVED_RUNTIME_POLICY_REQUIRED", "message": "Capability harus memiliki policy runtime yang disetujui."
        })
    policy = await store.get_approved_runtime_policy(str(payload.agent_id), str(capability["runtime_policy_id"]))
    if not policy or policy.get("policy_version") != capability.get("policy_version"):
        raise HTTPException(status_code=409, detail={
            "code": "APPROVED_RUNTIME_POLICY_REQUIRED", "message": "Policy runtime aktif tidak ditemukan atau versinya tidak cocok."
        })
    allowed_scopes = set(policy.get("required_permission_scopes") or [])
    if not set(payload.granted_permission_scopes).issubset(allowed_scopes) or not set(payload.granted_permission_scopes).issubset(set(skill.get("required_permission_scopes") or [])):
        raise HTTPException(status_code=403, detail={
            "code": "SCHEDULE_PERMISSION_SCOPE_DENIED", "message": "Izin task melampaui scope policy yang disetujui."
        })
    if capability.get("risk_level") in {"high", "critical"} and not payload.require_approval:
        raise HTTPException(status_code=403, detail={
            "code": "HIGH_RISK_TASK_REQUIRES_APPROVAL", "message": "Task berisiko tinggi/kritis wajib memerlukan persetujuan Human Owner."
        })
    skill_budget = skill.get("budget_limits") or {}
    for key in ("max_runtime_seconds", "max_tool_calls"):
        requested = payload.budget_limit.get(key)
        allowed = skill_budget.get(key, 30 if key == "max_runtime_seconds" else 1)
        if requested is not None and (not isinstance(requested, int) or isinstance(requested, bool) or requested < 1 or requested > int(allowed)):
            raise HTTPException(status_code=403, detail={
                "code": "TASK_BUDGET_EXCEEDS_SKILL_LIMIT", "message": "Budget Task melampaui batas Skill yang dipublikasikan."
            })
    return {"agent": agent, "skill": skill, "capability": capability, "policy": policy}


@router.post("", status_code=201)
async def create_schedule(payload: TaskScheduleCreate,
                          user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    store, owner_id = _store(), str(user["id"])
    try:
        binding = await _verify_runtime_binding(store, owner_id, payload)
        now = datetime.now(timezone.utc)
        next_run = _next_occurrence(payload, now)
        schedule_id = str(uuid.uuid4())
        definition = WorkflowDefinition(
            workflow_key=f"agent-task-schedule-{schedule_id.replace('-', '')}",
            version=1,
            nodes=[WorkflowNode(key="execute-agent-task", kind="agent_task",
                                config={"schedule_id": schedule_id}, timeout_seconds=30)],
            edges=[],
            max_runtime_seconds=60,
            max_retries=0,
        )
        workflow_store = WorkflowStore.from_environment()
        workflow_definition = await workflow_store.create_definition({
            "owner_user_id": owner_id,
            "workflow_key": definition.workflow_key,
            "version": definition.version,
            "definition": definition.model_dump(mode="json"),
            "digest": definition.digest(),
            "status": "active",
        })
        row = {
            "id": schedule_id,
            "owner_user_id": owner_id,
                "workflow_definition_id": workflow_definition["id"],
            "agent_id": str(payload.agent_id),
            "session_id": str(payload.session_id),
            "skill_id": str(payload.skill_id),
            "tool_key": payload.tool_key,
            "title": payload.title.strip(),
            "instructions": payload.instructions.strip(),
            "task_type": payload.task_type,
            "schedule_kind": payload.schedule_kind,
            "timezone_name": payload.timezone_name,
            "local_time": payload.local_time,
            "weekdays": payload.weekdays,
            "run_at": payload.run_at.astimezone(timezone.utc).isoformat() if payload.run_at else None,
            "next_run_at": next_run.isoformat() if next_run else None,
            "status": "active" if next_run else "completed",
            "require_approval": payload.require_approval,
            "granted_permission_scopes": payload.granted_permission_scopes,
            "budget_limit": payload.budget_limit,
            "input_payload": payload.input_payload,
            "created_by_agent_version": binding["agent"]["version"],
            "created_by_skill_version": binding["skill"]["version"],
        }
        rows = await store.request("POST", "agent_task_schedules", params={"select": "*"},
                                   body=row, prefer="return=representation")
        if not rows:
            raise AgentRuntimePersistenceError("schedule creation was not confirmed")
        return {"schedule": rows[0], "execution_dispatched": False}
    except AgentRuntimePersistenceError as exc:
        raise _storage_error(exc) from exc
    except WorkflowPersistenceError as exc:
        raise HTTPException(status_code=503, detail={"code": "WORKFLOW_STORAGE_UNAVAILABLE", "message": "Definisi Workflow tidak dapat disimpan."}) from exc
    except ValueError as exc:
        raise HTTPException(status_code=503, detail={"code": "WORKFLOW_NOT_CONFIGURED", "message": "Penyimpanan Workflow Engine belum dikonfigurasi."}) from exc


@router.get("")
async def list_schedules(limit: int = 50, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    store, owner_id = _store(), str(user["id"])
    try:
        rows = await store.request("GET", "agent_task_schedules", params={
            "select": "*", "owner_user_id": f"eq.{owner_id}",
            "order": "created_at.desc", "limit": str(max(1, min(limit, 100))),
        })
        return {"items": rows or []}
    except AgentRuntimePersistenceError as exc:
        raise _storage_error(exc) from exc


@router.get("/{schedule_id}/runs")
async def list_schedule_runs(schedule_id: uuid.UUID, limit: int = 50,
                             user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    store, owner_id = _store(), str(user["id"])
    try:
        schedule = await store.request("GET", "agent_task_schedules", params={
            "select": "id", "id": f"eq.{schedule_id}", "owner_user_id": f"eq.{owner_id}", "limit": "1",
        })
        if not schedule:
            raise HTTPException(status_code=404, detail={"code": "SCHEDULE_NOT_FOUND", "message": "Jadwal tidak ditemukan."})
        rows = await store.request("GET", "agent_task_schedule_runs", params={
            "select": "*", "schedule_id": f"eq.{schedule_id}", "owner_user_id": f"eq.{owner_id}",
            "order": "scheduled_for.desc", "limit": str(max(1, min(limit, 100))),
        })
        return {"items": rows or []}
    except AgentRuntimePersistenceError as exc:
        raise _storage_error(exc) from exc



@router.post("/{schedule_id}/runs/{run_id}/approve")
async def approve_schedule_run(schedule_id: uuid.UUID, run_id: uuid.UUID,
                               user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    """Explicit owner approval releases one held occurrence to the scheduler worker."""
    store, owner_id = _store(), str(user["id"])
    try:
        schedule = await store.request("GET", "agent_task_schedules", params={
            "select": "id,status,require_approval,next_run_at",
            "id": f"eq.{schedule_id}", "owner_user_id": f"eq.{owner_id}", "limit": "1",
        })
        if not schedule:
            raise HTTPException(status_code=404, detail={"code": "SCHEDULE_NOT_FOUND", "message": "Jadwal tidak ditemukan."})
        occurrence = await store.request("GET", "agent_task_schedule_runs", params={
            "select": "*", "id": f"eq.{run_id}", "schedule_id": f"eq.{schedule_id}",
            "owner_user_id": f"eq.{owner_id}", "status": "eq.waiting_for_approval", "limit": "1",
        })
        if not occurrence:
            raise HTTPException(status_code=409, detail={
                "code": "SCHEDULE_RUN_NOT_WAITING_APPROVAL", "message": "Eksekusi tidak sedang menunggu persetujuan."
            })
        released = await store.request("PATCH", "agent_task_schedule_runs", params={
            "id": f"eq.{run_id}", "schedule_id": f"eq.{schedule_id}",
            "owner_user_id": f"eq.{owner_id}", "status": "eq.waiting_for_approval",
        }, body={"status": "claimed", "approved_at": datetime.now(timezone.utc).isoformat(), "approved_by": owner_id}, prefer="return=representation")
        if not released:
            raise HTTPException(status_code=409, detail={
                "code": "SCHEDULE_RUN_STATE_CHANGED", "message": "Status eksekusi berubah; muat ulang sebelum menyetujui."
            })
        next_run_at = schedule[0].get("next_run_at") or occurrence[0]["scheduled_for"]
        updated = await store.request("PATCH", "agent_task_schedules", params={
            "id": f"eq.{schedule_id}", "owner_user_id": f"eq.{owner_id}",
        }, body={"status": "active", "next_run_at": next_run_at,
                 "updated_at": datetime.now(timezone.utc).isoformat()},
            prefer="return=representation")
        return {"schedule": updated[0] if updated else schedule[0], "run": released[0], "approved": True}
    except AgentRuntimePersistenceError as exc:
        raise _storage_error(exc) from exc



@router.patch("/{schedule_id}/status")
async def update_schedule_status(schedule_id: uuid.UUID, payload: ScheduleStatusUpdate,
                                 user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    store, owner_id = _store(), str(user["id"])
    try:
        rows = await store.request("PATCH", "agent_task_schedules", params={
            "select": "*", "id": f"eq.{schedule_id}", "owner_user_id": f"eq.{owner_id}",
            "status": "in.(active,paused,needs_approval)",
        }, body={"status": payload.status, "updated_at": datetime.now(timezone.utc).isoformat()},
            prefer="return=representation")
        if not rows:
            raise HTTPException(status_code=404, detail={
                "code": "SCHEDULE_NOT_FOUND_OR_TERMINAL", "message": "Jadwal tidak ditemukan atau sudah terminal."
            })
        return {"schedule": rows[0]}
    except AgentRuntimePersistenceError as exc:
        raise _storage_error(exc) from exc

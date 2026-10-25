"""Bounded deterministic ENG-P11 workflow step worker.

Only pure node types are executable in this slice. A persistence timeout is an
unknown outcome, not permission to blindly repeat a finalize/side effect.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from allpha_api.workflow_store import WorkflowPersistenceError
from allpha_api.agent_runtime_api import TaskCreate, create_task, execute_task
from allpha_api.agent_runtime_store import AgentRuntimePersistenceError, AgentRuntimeStore
from starlette.requests import Request

TERMINAL_RUN_STATES = frozenset({"succeeded", "failed", "cancelled", "timed_out"})
TERMINAL_STEP_STATES = frozenset({"succeeded", "failed", "cancelled", "skipped"})


class WorkflowWorkerError(RuntimeError):
    """Worker could not safely advance a workflow."""


class WorkflowOutcomeUnknown(WorkflowWorkerError):
    """Durable state could not be reconciled after an uncertain request."""


class WorkflowNodeError(WorkflowWorkerError):
    """A deterministic node input/configuration error that should not be retried."""


def _as_utc(value: str | datetime) -> datetime:
    parsed = value if isinstance(value, datetime) else datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _validate_result(value: Any, *, limit: int = 16_384) -> None:
    try:
        encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError, UnicodeEncodeError) as exc:
        raise WorkflowNodeError("node result is not finite JSON data") from exc
    if len(encoded.encode("utf-8")) > limit:
        raise WorkflowNodeError("node result exceeds 16 KiB")


def evaluate_deterministic_node(step: dict[str, Any], run: dict[str, Any]) -> dict[str, Any]:
    """Evaluate a pure node and return a bounded JSON object for output/checkpoint."""
    kind = step.get("node_kind")
    config = step.get("node_config") or {}
    inputs = run.get("input_payload") or {}
    by_key = {item.get("node_key"): item for item in (run.get("steps") or [])}
    dependencies = list(step.get("depends_on") or [])
    values: list[Any] = []
    for key in dependencies:
        parent = by_key.get(key)
        if not parent or parent.get("status") != "succeeded":
            raise WorkflowNodeError("workflow dependency is not durably successful")
        payload = parent.get("output_payload") or {}
        if not isinstance(payload, dict) or "value" not in payload:
            raise WorkflowNodeError("dependency output checkpoint is missing")
        values.append(payload["value"])

    if kind == "input":
        field = config.get("field")
        if not isinstance(field, str) or field not in inputs:
            raise WorkflowNodeError("required workflow input is missing")
        value = inputs[field]
    elif kind == "constant":
        if "value" not in config:
            raise WorkflowNodeError("constant node has no value")
        value = config["value"]
    elif kind == "pass_through":
        if len(values) != 1:
            raise WorkflowNodeError("pass_through requires exactly one successful dependency")
        value = values[0]
    elif kind == "concat":
        separator = config.get("separator", "")
        if not isinstance(separator, str):
            raise WorkflowNodeError("concat separator must be a string")
        if any(isinstance(item, (dict, list)) for item in values):
            raise WorkflowNodeError("concat dependencies must be scalar values")
        value = separator.join("" if item is None else str(item) for item in values)
    elif kind == "merge":
        merged: dict[str, Any] = {}
        for key, item in zip(dependencies, values, strict=True):
            if isinstance(item, dict):
                if merged.keys() & item.keys():
                    raise WorkflowNodeError("merge contains duplicate object keys")
                merged.update(item)
            else:
                merged[key] = item
        value = merged
    else:
        # Explicit deny-by-default: never execute arbitrary code or unknown node kinds.
        raise WorkflowNodeError("unsupported workflow node kind")

    output = {"value": value}
    checkpoint = {"node_key": step.get("node_key"), "output": output}
    _validate_result(output)
    _validate_result(checkpoint)
    return {"output_payload": output, "checkpoint": checkpoint}


def _step_from_run(run: dict[str, Any], step_id: str) -> dict[str, Any] | None:
    return next((step for step in (run.get("steps") or []) if str(step.get("id")) == str(step_id)), None)




def _internal_request(trace_id: str) -> Request:
    return Request({
        "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
        "method": "POST", "scheme": "http", "path": "/internal/workflow-agent-task",
        "raw_path": b"/internal/workflow-agent-task", "query_string": b"",
        "headers": [(b"x-request-id", trace_id.encode("ascii"))],
        "server": ("localhost", 80), "client": ("127.0.0.1", 0),
    })


async def execute_agent_task_node(step: dict[str, Any], run: dict[str, Any], owner_id: str) -> dict[str, Any]:
    """Execute one scheduled occurrence through Agent Runtime with durable linkage."""
    config = step.get("node_config") or {}
    schedule_id = config.get("schedule_id")
    run_input = run.get("input_payload") or {}
    schedule_run_id = run_input.get("schedule_run_id")
    if not isinstance(schedule_id, str) or not isinstance(schedule_run_id, str):
        raise WorkflowNodeError("agent task node requires schedule_id and schedule_run_id")
    runtime_store = AgentRuntimeStore.from_environment()
    schedules = await runtime_store.request("GET", "agent_task_schedules", params={
        "select": "*", "id": f"eq.{schedule_id}", "owner_user_id": f"eq.{owner_id}", "limit": "1",
    })
    if not schedules:
        raise WorkflowNodeError("scheduled Agent task is not owned by workflow owner")
    schedule = schedules[0]
    occurrences = await runtime_store.request("GET", "agent_task_schedule_runs", params={
        "select": "*", "id": f"eq.{schedule_run_id}", "schedule_id": f"eq.{schedule_id}",
        "owner_user_id": f"eq.{owner_id}", "limit": "1",
    })
    if not occurrences:
        raise WorkflowNodeError("schedule occurrence is not owned by workflow owner")
    occurrence = occurrences[0]
    if schedule.get("require_approval") or occurrence.get("status") not in {"claimed", "running"}:
        raise WorkflowNodeError("schedule occurrence has not passed the owner approval gate")
    runtime_task_id = occurrence.get("runtime_task_id")
    try:
        if not runtime_task_id:
            payload = TaskCreate(
                session_id=schedule["session_id"], skill_id=schedule["skill_id"],
                tool_key=schedule["tool_key"],
                inputs=(schedule.get("input_payload") or {}),
                idempotency_key=occurrence["idempotency_key"],
            )
            created = await create_task(payload, _internal_request(occurrence["trace_id"]), {"id": owner_id})
            runtime_task_id = str(created["task"]["id"])
            saved = await runtime_store.request("PATCH", "agent_task_schedule_runs", params={
                "id": f"eq.{schedule_run_id}", "schedule_id": f"eq.{schedule_id}",
                "owner_user_id": f"eq.{owner_id}", "status": "in.(claimed,running)",
            }, body={"runtime_task_id": runtime_task_id, "status": "running",
                     "started_at": occurrence.get("started_at") or datetime.now(timezone.utc).isoformat()},
                prefer="return=representation")
            if not saved:
                raise AgentRuntimePersistenceError("runtime task link could not be persisted")
        execution = await execute_task(uuid.UUID(str(runtime_task_id)), {"id": owner_id})
        runtime_task = execution.get("task") or {}
        state = runtime_task.get("state")
        output = runtime_task.get("output_payload")
        status_map = {
            "succeeded": "succeeded", "partially_succeeded": "partially_succeeded",
            "failed": "failed", "timed_out": "timed_out", "cancelled": "cancelled",
            "budget_exhausted": "failed", "waiting_for_approval": "waiting_for_approval",
            "waiting_for_input": "waiting_for_approval",
        }
        await runtime_store.request("PATCH", "agent_task_schedule_runs", params={
            "id": f"eq.{schedule_run_id}", "schedule_id": f"eq.{schedule_id}",
            "owner_user_id": f"eq.{owner_id}",
        }, body={"runtime_task_id": str(runtime_task_id), "status": status_map.get(state, "outcome_unknown"),
                 "completed_at": datetime.now(timezone.utc).isoformat(),
                 "result_summary": output.get("summary") if isinstance(output, dict) and isinstance(output.get("summary"), str) else None,
                 "error_code": runtime_task.get("error_code")}, prefer="return=representation")
        await runtime_store.request("PATCH", "agent_task_schedules", params={
            "id": f"eq.{schedule_id}", "owner_user_id": f"eq.{owner_id}",
        }, body={"last_runtime_task_id": str(runtime_task_id), "last_run_at": datetime.now(timezone.utc).isoformat(),
                 "updated_at": datetime.now(timezone.utc).isoformat()}, prefer="return=representation")
        if state != "succeeded":
            raise WorkflowNodeError(f"Agent Runtime ended in state {state or 'unknown'}")
        return {
            "output_payload": {"schedule_run_id": schedule_run_id, "runtime_task_id": str(runtime_task_id),
                               "runtime_state": state, "result": output if isinstance(output, dict) else {}},
            "checkpoint": {"node_key": step.get("node_key"), "schedule_run_id": schedule_run_id,
                           "runtime_task_id": str(runtime_task_id), "runtime_state": state},
        }
    except WorkflowNodeError:
        raise
    except Exception as exc:
        try:
            await runtime_store.request("PATCH", "agent_task_schedule_runs", params={
                "id": f"eq.{schedule_run_id}", "schedule_id": f"eq.{schedule_id}",
                "owner_user_id": f"eq.{owner_id}",
            }, body={"status": "outcome_unknown", "error_code": type(exc).__name__},
                prefer="return=representation")
        except Exception:
            pass
        raise WorkflowNodeError("Agent Runtime outcome is unknown; automatic side-effect replay is blocked") from exc


async def process_next_step(
    store: Any, *, owner_id: str, run_id: str, lease_seconds: int = 30,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Claim and execute at most one node; repeated calls safely advance a run."""
    instant = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    run = await store.get_run(owner_id, run_id)
    if not run:
        raise WorkflowWorkerError("workflow run not found")
    if run.get("status") in TERMINAL_RUN_STATES:
        return {"outcome": "terminal", "run_status": run["status"]}

    started = run.get("started_at") or run.get("created_at")
    if started and run.get("max_runtime_seconds") is not None:
        deadline = _as_utc(started).timestamp() + int(run["max_runtime_seconds"])
        if instant.timestamp() >= deadline:
            try:
                timed_out = await store.timeout_run(owner_id, run_id)
            except WorkflowPersistenceError as exc:
                raise WorkflowOutcomeUnknown("timeout outcome could not be confirmed") from exc
            if timed_out:
                return {"outcome": "terminal", "run_status": "timed_out"}
            latest = await store.get_run(owner_id, run_id)
            if latest and latest.get("status") in TERMINAL_RUN_STATES:
                return {"outcome": "terminal", "run_status": latest["status"]}
            raise WorkflowOutcomeUnknown("workflow timeout transition was not confirmed")

    lease_token = str(uuid.uuid4())
    try:
        step = await store.claim_step(owner_id, run_id, lease_token, lease_seconds=lease_seconds)
    except WorkflowPersistenceError as exc:
        raise WorkflowOutcomeUnknown("step claim outcome could not be confirmed") from exc
    if not step:
        latest = await store.get_run(owner_id, run_id)
        if not latest:
            raise WorkflowWorkerError("workflow run disappeared")
        return {"outcome": "idle", "run_status": latest.get("status", "unknown")}

    # Refresh after claim so dependency outputs and cancellation are authoritative.
    try:
        run = await store.get_run(owner_id, run_id)
    except WorkflowPersistenceError as exc:
        raise WorkflowOutcomeUnknown("claimed step could not be reconciled") from exc
    if not run or run.get("status") in TERMINAL_RUN_STATES or run.get("cancel_requested"):
        return {"outcome": "terminal", "run_status": (run or {}).get("status", "unknown")}

    try:
        if step.get("node_kind") == "agent_task":
            result = await execute_agent_task_node(step, run, owner_id)
        else:
            result = evaluate_deterministic_node(step, run)
        final_state, error_code = "succeeded", None
    except WorkflowNodeError as exc:
        result = {"output_payload": None, "checkpoint": {"node_key": step.get("node_key"), "failed": True}}
        final_state, error_code = "failed", type(exc).__name__.upper()
    except Exception as exc:  # deterministic-only nodes: bounded retry is safe
        attempts, max_attempts = int(step.get("attempts", 1)), int(step.get("max_attempts", 1))
        final_state = "retrying" if attempts < max_attempts else "failed"
        error_code = "DETERMINISTIC_NODE_ERROR"
        result = {"output_payload": None, "checkpoint": {"node_key": step.get("node_key"), "retryable": True}}

    try:
        finalized = await store.finalize_step(
            owner_id=owner_id, run_id=run_id, step_id=str(step["id"]), lease_token=lease_token,
            terminal_state=final_state, output_payload=result["output_payload"],
            error_code=error_code, checkpoint=result["checkpoint"],
        )
    except WorkflowPersistenceError as exc:
        # Reconcile once; never immediately repeat finalize or node execution.
        try:
            latest = await store.get_run(owner_id, run_id)
        except WorkflowPersistenceError as reconcile_exc:
            raise WorkflowOutcomeUnknown("finalize and read-after-write outcome are unknown") from reconcile_exc
        observed = _step_from_run(latest or {}, str(step["id"]))
        if observed and observed.get("status") in TERMINAL_STEP_STATES:
            return {"outcome": "reconciled", "run_status": (latest or {}).get("status"),
                    "step_status": observed.get("status")}
        raise WorkflowOutcomeUnknown("finalize outcome is not yet observable; do not replay this claim") from exc
    if not finalized:
        raise WorkflowOutcomeUnknown("finalize RPC did not confirm a durable step state")
    return {"outcome": "step_finalized", "step_status": finalized.get("status"),
            "run_status": finalized.get("run_status")}

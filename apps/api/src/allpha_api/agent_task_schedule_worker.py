"""Durable schedule poller for the canonical Workflow Engine.

It claims due occurrences atomically and creates a Workflow run. The Workflow
worker delegates the side effect to Agent Runtime after policy checks; this
poller never executes Agent tools itself. Owner-approval gates fail closed.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, time, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo


from allpha_api.agent_runtime_store import AgentRuntimePersistenceError, AgentRuntimeStore
from allpha_api.workflow_engine import WorkflowDefinition
from allpha_api.workflow_store import WorkflowPersistenceError, WorkflowStore

log = logging.getLogger("allpha.agent_task_scheduler")


def _next_run(schedule: dict[str, Any], now: datetime) -> str | None:
    if schedule["schedule_kind"] == "once":
        return None
    zone = ZoneInfo(schedule["timezone_name"])
    hour, minute = (int(part) for part in str(schedule["local_time"])[:5].split(":"))
    local_now = now.astimezone(zone)
    weekdays = set(schedule.get("weekdays") or [])
    for offset in range(0, 15):
        day = local_now.date() + timedelta(days=offset)
        if schedule["schedule_kind"] == "weekly" and day.weekday() not in weekdays:
            continue
        candidate = datetime.combine(day, time(hour, minute), tzinfo=zone)
        if candidate > local_now:
            return candidate.astimezone(timezone.utc).isoformat()
    raise ValueError("next scheduled occurrence could not be computed within 15 days")


def _request(trace_id: str) -> Request:
    return Request({
        "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
        "method": "POST", "scheme": "http", "path": "/internal/scheduler",
        "raw_path": b"/internal/scheduler", "query_string": b"",
        "headers": [(b"x-request-id", trace_id.encode("ascii"))],
        "server": ("localhost", 80), "client": ("127.0.0.1", 0),
    })


async def process_due_schedules(store: Any, *, limit: int = 25, lease_seconds: int = 60) -> dict[str, int]:
    if not 1 <= limit <= 100 or not 5 <= lease_seconds <= 300:
        raise ValueError("scheduler batch or lease bounds are invalid")
    lease_token = str(uuid.uuid4())
    claimed = await store.request("POST", "rpc/claim_due_agent_task_schedules", body={
        "p_lease_token": lease_token, "p_limit": limit, "p_lease_seconds": lease_seconds,
    }) or []
    summary = {"claimed": len(claimed), "dispatched": 0, "waiting_for_approval": 0, "failed": 0, "skipped": 0}
    now = datetime.now(timezone.utc)
    for schedule in claimed:
        schedule_id = str(schedule["id"])
        owner_id = str(schedule["owner_user_id"])
        scheduled_for = str(schedule["next_run_at"])
        try:
            occurrence_key = f"schedule:{schedule_id}:{datetime.fromisoformat(scheduled_for.replace('Z', '+00:00')).timestamp():.0f}"
            occurrence_key = occurrence_key[:160]
            existing = await store.request("GET", "agent_task_schedule_runs", params={
                "select": "*", "schedule_id": f"eq.{schedule_id}",
                "scheduled_for": f"eq.{scheduled_for}", "limit": "1",
            })
            if existing:
                occurrence = existing[0]
                if occurrence["status"] in {"succeeded", "partially_succeeded", "failed", "timed_out", "cancelled"} or (occurrence["status"] == "waiting_for_approval" and schedule.get("require_approval")):
                    summary["skipped"] += 1
                    continue
            else:
                trace_id = str(uuid.uuid4())
                rows = await store.request("POST", "agent_task_schedule_runs", params={"select": "*"},
                    body={"schedule_id": schedule_id, "owner_user_id": owner_id,
                          "scheduled_for": scheduled_for, "status": "claimed",
                          "idempotency_key": occurrence_key, "trace_id": trace_id},
                    prefer="return=representation")
                if not rows:
                    raise AgentRuntimePersistenceError("schedule occurrence insert was not confirmed")
                occurrence = rows[0]

            if schedule.get("require_approval"):
                await store.request("PATCH", "agent_task_schedule_runs", params={
                    "id": f"eq.{occurrence['id']}", "owner_user_id": f"eq.{owner_id}",
                }, body={"status": "waiting_for_approval"}, prefer="return=representation")
                await store.request("PATCH", "agent_task_schedules", params={
                    "id": f"eq.{schedule_id}", "owner_user_id": f"eq.{owner_id}",
                    "lease_token": f"eq.{lease_token}",
                }, body={"status": "needs_approval", "lease_token": None, "lease_expires_at": None,
                         "updated_at": now.isoformat()}, prefer="return=representation")
                summary["waiting_for_approval"] += 1
                continue

            # Dispatch through the canonical Workflow Engine; its agent_task node
            # delegates to the existing Agent Runtime adapter after policy checks.
            workflow_store = WorkflowStore.from_environment()
            trace_id = f"agent-task-schedule:{occurrence['id']}"
            workflow_run = None
            if occurrence.get("workflow_run_id"):
                workflow_run = await workflow_store.get_run(owner_id, str(occurrence["workflow_run_id"]))
            if not workflow_run:
                matches = await workflow_store.request("GET", "workflow_runs", params={
                    "select": "*", "owner_user_id": f"eq.{owner_id}", "trace_id": f"eq.{trace_id}", "limit": "1",
                })
                workflow_run = matches[0] if matches else None
            if not workflow_run:
                definition = await workflow_store.get_definition(owner_id, str(schedule["workflow_definition_id"]))
                if not definition:
                    raise WorkflowPersistenceError("schedule workflow definition is missing")
                if WorkflowDefinition.model_validate(definition["definition"]).digest() != definition.get("digest"):
                    raise WorkflowPersistenceError("schedule workflow definition digest mismatch")
                workflow_run = await workflow_store.create_run(owner_id, definition,
                    {"schedule_id": schedule_id, "schedule_run_id": str(occurrence["id"])}, trace_id)
            await store.request("PATCH", "agent_task_schedule_runs", params={
                "id": f"eq.{occurrence['id']}", "owner_user_id": f"eq.{owner_id}",
            }, body={"workflow_run_id": workflow_run["id"], "status": "running",
                     "started_at": occurrence.get("started_at") or datetime.now(timezone.utc).isoformat()},
                prefer="return=representation")
            next_run = _next_run(schedule, datetime.now(timezone.utc))
            await store.request("PATCH", "agent_task_schedules", params={
                "id": f"eq.{schedule_id}", "owner_user_id": f"eq.{owner_id}",
                "lease_token": f"eq.{lease_token}",
            }, body={"status": "active" if next_run else "completed", "next_run_at": next_run,
                     "last_workflow_run_id": workflow_run["id"], "run_count": int(schedule.get("run_count") or 0) + 1,
                     "lease_token": None, "lease_expires_at": None,
                     "updated_at": datetime.now(timezone.utc).isoformat()}, prefer="return=representation")
            summary["dispatched"] += 1
            continue

        except Exception:
            log.exception("Scheduled Agent task dispatch failed; schedule_id=%s", schedule_id)
            summary["failed"] += 1
            # Clear only this worker's lease. Preserve durable occurrence state for
            # explicit recovery; never mark an uncertain execution successful.
            try:
                await store.request("PATCH", "agent_task_schedules", params={
                    "id": f"eq.{schedule_id}", "owner_user_id": f"eq.{owner_id}",
                    "lease_token": f"eq.{lease_token}",
                }, body={"lease_token": None, "lease_expires_at": None,
                         "updated_at": datetime.now(timezone.utc).isoformat()},
                    prefer="return=representation")
            except Exception:
                log.exception("Could not release schedule lease; schedule_id=%s", schedule_id)
    return summary


async def run_forever(*, poll_interval_seconds: int = 5, limit: int = 25,
                      lease_seconds: int = 60, stop_event: asyncio.Event | None = None) -> None:
    if not 1 <= poll_interval_seconds <= 60:
        raise ValueError("poll interval must be between 1 and 60")
    stop = stop_event or asyncio.Event()
    store = AgentRuntimeStore.from_environment()
    while not stop.is_set():
        try:
            summary = await process_due_schedules(store, limit=limit, lease_seconds=lease_seconds)
            log.info("Agent task scheduler batch completed: %s", summary)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("Agent task scheduler batch failed; next poll remains bounded")
        try:
            await asyncio.wait_for(stop.wait(), timeout=poll_interval_seconds)
        except asyncio.TimeoutError:
            pass


def main() -> None:
    import os
    import signal

    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
    if os.getenv("ALLPHA_AGENT_TASK_SCHEDULER_ENABLED", "false").strip().lower() != "true":
        log.info("Agent task scheduler disabled; set ALLPHA_AGENT_TASK_SCHEDULER_ENABLED=true in an approved worker service")
        return
    poll = int(os.getenv("ALLPHA_AGENT_TASK_SCHEDULER_POLL_INTERVAL_SECONDS", "5"))
    limit = int(os.getenv("ALLPHA_AGENT_TASK_SCHEDULER_BATCH_LIMIT", "25"))
    lease = int(os.getenv("ALLPHA_AGENT_TASK_SCHEDULER_LEASE_SECONDS", "60"))
    async def serve() -> None:
        stop = asyncio.Event()
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, stop.set)
            except (NotImplementedError, RuntimeError):
                pass
        await run_forever(poll_interval_seconds=poll, limit=limit, lease_seconds=lease, stop_event=stop)
    asyncio.run(serve())


if __name__ == "__main__":
    main()

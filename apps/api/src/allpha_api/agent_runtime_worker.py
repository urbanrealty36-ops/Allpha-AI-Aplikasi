"""Durable polling worker for canonical Agent Runtime tool-plan tasks.

Only registered pure tools are executed here. Task claims, checkpoints, leases,
policy checks and finalization remain in AgentRuntimeStore and the shared runtime.
"""
from __future__ import annotations

import asyncio
import logging
import os
from fastapi import HTTPException

from allpha_api.agent_runtime_api import _execute_planned_task
from allpha_api.agent_runtime_store import AgentRuntimePersistenceError, AgentRuntimeStore

logger = logging.getLogger("allpha.agent_runtime_worker")


def _enabled() -> bool:
    return os.getenv("ALLPHA_AGENT_RUNTIME_WORKER_ENABLED", "false").lower() == "true"


def _poll_seconds() -> float:
    try:
        value = float(os.getenv("ALLPHA_AGENT_RUNTIME_WORKER_POLL_SECONDS", "2"))
    except ValueError:
        value = 2.0
    return max(0.5, min(value, 30.0))


def _batch_size() -> int:
    try:
        value = int(os.getenv("ALLPHA_AGENT_RUNTIME_WORKER_BATCH_SIZE", "5"))
    except ValueError:
        value = 5
    return max(1, min(value, 25))


async def run_once(store: AgentRuntimeStore) -> int:
    """Process one bounded batch. Unknown effects are terminalized, never replayed."""
    rows = await store.list_runnable_planned_tasks(limit=_batch_size())
    processed = 0
    for row in rows:
        owner_id, task_id = row.get("owner_user_id"), row.get("id")
        if not isinstance(owner_id, str) or not isinstance(task_id, str):
            logger.error("Skipping malformed runtime task envelope")
            continue
        if row.get("effect_outcome") in {"started", "unknown"}:
            try:
                await store.mark_unknown_effect(owner_id, task_id)
            except AgentRuntimePersistenceError:
                logger.exception("Could not terminalize task with unknown effect; task_id=%s", task_id)
                break
            processed += 1
            continue
        try:
            await _execute_planned_task(store, owner_id, task_id, row)
            processed += 1
        except HTTPException as exc:
            detail = exc.detail if isinstance(exc.detail, dict) else {}
            logger.info("Runtime task not completed; task_id=%s status=%s code=%s",
                        task_id, exc.status_code, detail.get("code", "RUNTIME_TASK_REJECTED"))
            processed += 1
        except AgentRuntimePersistenceError:
            # Outcome may be uncertain. Stop this batch and let lease/recovery logic decide.
            logger.exception("Runtime persistence uncertain; stopping batch at task_id=%s", task_id)
            break
        except Exception:
            logger.exception("Unexpected runtime worker failure; task_id=%s", task_id)
            break
    return processed


async def serve() -> None:
    if not _enabled():
        logger.warning("Agent Runtime worker is disabled; set ALLPHA_AGENT_RUNTIME_WORKER_ENABLED=true only after schema and policy gates pass")
        return
    store = AgentRuntimeStore.from_environment()
    interval = _poll_seconds()
    logger.info("Agent Runtime worker started; poll_seconds=%s batch_size=%s", interval, _batch_size())
    while True:
        try:
            await run_once(store)
            await asyncio.sleep(interval)
        except AgentRuntimePersistenceError:
            logger.exception("Agent Runtime worker persistence unavailable")
            await asyncio.sleep(interval)
        except Exception:
            logger.exception("Agent Runtime worker loop failed")
            await asyncio.sleep(interval)


def main() -> None:
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO").upper())
    asyncio.run(serve())


if __name__ == "__main__":
    main()

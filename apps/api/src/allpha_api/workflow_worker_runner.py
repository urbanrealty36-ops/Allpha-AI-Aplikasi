"""Bounded invocation adapter for the canonical ENG-P11 workflow worker.

This module intentionally processes one bounded polling batch only. It does not
choose a scheduler, queue, or deployment topology; an approved host may call
process_runnable_batch periodically. PostgreSQL claim/finalize RPCs remain the
authority and deterministic nodes remain the only executable node kinds.
"""
from __future__ import annotations

import logging
from typing import Any

from allpha_api.workflow_store import WorkflowPersistenceError
from allpha_api.workflow_worker import (
    WorkflowOutcomeUnknown,
    WorkflowWorkerError,
    process_next_step,
)

log = logging.getLogger("allpha.workflow_worker")


async def process_runnable_batch(
    store: Any,
    *,
    limit: int = 25,
    lease_seconds: int = 30,
) -> dict[str, Any]:
    """Advance at most one step per candidate run; the DB claim is authoritative."""
    if not 1 <= limit <= 100:
        raise ValueError("limit must be between 1 and 100")
    if not 5 <= lease_seconds <= 120:
        raise ValueError("lease_seconds must be between 5 and 120")

    candidates = await store.list_runnable_runs(limit=limit)
    summary: dict[str, Any] = {
        "candidates": len(candidates),
        "processed": 0,
        "idle": 0,
        "terminal": 0,
        "unknown": 0,
        "errors": 0,
    }
    for candidate in candidates:
        owner_id = candidate.get("owner_user_id")
        run_id = candidate.get("id")
        # Fail closed on malformed poll rows; never infer owner identity.
        if not isinstance(owner_id, str) or not owner_id or not isinstance(run_id, str) or not run_id:
            summary["errors"] += 1
            log.error("Skipping malformed workflow poll candidate")
            continue
        try:
            outcome = await process_next_step(
                store,
                owner_id=owner_id,
                run_id=run_id,
                lease_seconds=lease_seconds,
            )
        except WorkflowOutcomeUnknown:
            # Do not retry the same step in this invocation. A later poll must
            # reconcile through the durable claim/lease contract.
            summary["unknown"] += 1
            log.warning("Workflow outcome remains unknown; run_id=%s", run_id)
        except (WorkflowWorkerError, WorkflowPersistenceError):
            summary["errors"] += 1
            log.exception("Workflow worker could not safely advance run_id=%s", run_id)
        else:
            if outcome.get("outcome") == "idle":
                summary["idle"] += 1
            elif outcome.get("outcome") == "terminal":
                summary["terminal"] += 1
            else:
                summary["processed"] += 1
    return summary

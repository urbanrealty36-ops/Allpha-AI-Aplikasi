"""Explicitly gated polling host for the canonical ENG-P11 workflow worker.

This entrypoint is intentionally disabled unless ALLPHA_WORKFLOW_WORKER_ENABLED=true.
It is not wired into the API process or any deployment configuration.
"""
from __future__ import annotations

import asyncio
import logging
import os
import signal
from collections.abc import Awaitable, Callable
from typing import Any

from allpha_api.workflow_store import WorkflowStore
from allpha_api.workflow_worker_runner import process_runnable_batch

log = logging.getLogger("allpha.workflow_worker_host")


def _bounded_int(name: str, default: int, minimum: int, maximum: int) -> int:
    raw = os.getenv(name, str(default)).strip()
    try:
        value = int(raw)
    except ValueError as exc:
        raise SystemExit(f"{name} must be an integer") from exc
    if not minimum <= value <= maximum:
        raise SystemExit(f"{name} must be between {minimum} and {maximum}")
    return value


def _enabled() -> bool:
    value = os.getenv("ALLPHA_WORKFLOW_WORKER_ENABLED", "false").strip().lower()
    if value not in {"true", "false"}:
        raise SystemExit("ALLPHA_WORKFLOW_WORKER_ENABLED must be true or false")
    return value == "true"


async def run_forever(
    store: Any,
    *,
    poll_interval_seconds: int = 5,
    limit: int = 25,
    lease_seconds: int = 30,
    stop_event: asyncio.Event | None = None,
    batch_runner: Callable[..., Awaitable[dict[str, Any]]] = process_runnable_batch,
) -> None:
    """Poll sequentially; isolate batch errors and stop cleanly between batches."""
    if not 1 <= poll_interval_seconds <= 60:
        raise ValueError("poll_interval_seconds must be between 1 and 60")
    if not 1 <= limit <= 100:
        raise ValueError("limit must be between 1 and 100")
    if not 5 <= lease_seconds <= 120:
        raise ValueError("lease_seconds must be between 5 and 120")

    stop = stop_event or asyncio.Event()
    while not stop.is_set():
        try:
            summary = await batch_runner(store, limit=limit, lease_seconds=lease_seconds)
            log.info("Workflow worker batch completed: %s", summary)
        except asyncio.CancelledError:
            raise
        except Exception:
            # A transient poll/batch failure must not crash the host or API.
            log.exception("Workflow worker batch failed; next poll remains bounded")
        if stop.is_set():
            break
        try:
            await asyncio.wait_for(stop.wait(), timeout=poll_interval_seconds)
        except asyncio.TimeoutError:
            pass


def main() -> None:
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
    if not _enabled():
        log.info("Workflow worker is disabled; set ALLPHA_WORKFLOW_WORKER_ENABLED=true in an approved worker environment to enable")
        return

    poll_interval = _bounded_int("ALLPHA_WORKFLOW_POLL_INTERVAL_SECONDS", 5, 1, 60)
    limit = _bounded_int("ALLPHA_WORKFLOW_BATCH_LIMIT", 25, 1, 100)
    lease_seconds = _bounded_int("ALLPHA_WORKFLOW_LEASE_SECONDS", 30, 5, 120)
    try:
        store = WorkflowStore.from_environment()
    except ValueError as exc:
        raise SystemExit(f"Workflow worker configuration invalid: {exc}") from exc

    async def serve() -> None:
        stop = asyncio.Event()
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, stop.set)
            except (NotImplementedError, RuntimeError):
                log.debug("Signal handler unavailable for %s", sig.name)
        await run_forever(
            store,
            poll_interval_seconds=poll_interval,
            limit=limit,
            lease_seconds=lease_seconds,
            stop_event=stop,
        )

    asyncio.run(serve())


if __name__ == "__main__":
    main()

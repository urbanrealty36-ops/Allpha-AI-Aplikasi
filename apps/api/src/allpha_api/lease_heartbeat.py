"""Lease-fenced heartbeat runner shared by Knowledge worker consumers."""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable

log = logging.getLogger(__name__)


async def run_with_lease_heartbeat(
    operation: Callable[[], Awaitable[None]],
    heartbeat: Callable[[], Awaitable[bool]],
    *,
    lease_seconds: int,
    identity: str,
    heartbeat_interval_seconds: float | None = None,
) -> bool:
    """Run work only while its current unexpired lease can be renewed.

    Returns False when the lease is lost; callers must not finalize the job.
    Heartbeat errors are treated as lease loss, never as permission to continue.
    """
    if not 10 <= lease_seconds <= 900:
        raise ValueError("lease_seconds must be between 10 and 900")
    interval = heartbeat_interval_seconds or max(1.0, min(30.0, lease_seconds / 3))
    if interval <= 0 or interval >= lease_seconds:
        raise ValueError("heartbeat interval must be positive and shorter than the lease")

    stop = asyncio.Event()
    lost = asyncio.Event()

    async def pulse() -> None:
        while not stop.is_set():
            try:
                await asyncio.wait_for(stop.wait(), timeout=interval)
                return
            except asyncio.TimeoutError:
                pass
            try:
                active = await heartbeat()
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("Knowledge job heartbeat failed; abandoning lease %s", identity)
                active = False
            if not active:
                log.warning("Knowledge job lease %s is no longer current; cancelling work", identity)
                lost.set()
                return

    heartbeat_task = asyncio.create_task(pulse(), name=f"knowledge-lease-heartbeat:{identity}")
    operation_task = asyncio.create_task(operation(), name=f"knowledge-job-operation:{identity}")
    lost_task = asyncio.create_task(lost.wait(), name=f"knowledge-lease-lost:{identity}")
    try:
        done, _ = await asyncio.wait(
            {operation_task, lost_task},
            return_when=asyncio.FIRST_COMPLETED,
        )
        if lost_task in done and lost.is_set() and operation_task not in done:
            operation_task.cancel()
            await asyncio.gather(operation_task, return_exceptions=True)
            return False
        await operation_task
        return True
    finally:
        stop.set()
        for task in (heartbeat_task, lost_task):
            task.cancel()
        await asyncio.gather(heartbeat_task, lost_task, return_exceptions=True)

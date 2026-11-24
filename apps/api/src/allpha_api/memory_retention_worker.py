"""Bounded retention consumer for the canonical owner-private Memory Coordinator."""
from __future__ import annotations

import asyncio
import logging
import os
import signal
from typing import Any

from allpha_api.memory_coordinator import MemoryCoordinator, MemoryUnavailable

log = logging.getLogger("allpha.memory_retention_worker")


def _enabled() -> bool:
    value = os.getenv("ALLPHA_MEMORY_RETENTION_WORKER_ENABLED", "false").strip().lower()
    if value not in {"true", "false"}:
        raise SystemExit("ALLPHA_MEMORY_RETENTION_WORKER_ENABLED must be true or false")
    return value == "true"


def _bounded_int(name: str, default: int, minimum: int, maximum: int) -> int:
    raw = os.getenv(name, str(default)).strip()
    try:
        value = int(raw)
    except ValueError as exc:
        raise SystemExit(f"{name} must be an integer") from exc
    if not minimum <= value <= maximum:
        raise SystemExit(f"{name} must be between {minimum} and {maximum}")
    return value


class MemoryRetentionWorker:
    def __init__(self, store: Any, *, batch_size: int = 100) -> None:
        if not 1 <= batch_size <= 500:
            raise ValueError("batch_size must be between 1 and 500")
        self.store = store
        self.batch_size = batch_size

    async def process_once(self) -> int:
        result = await self.store.expire_due_batch(limit=self.batch_size)
        if not isinstance(result, dict):
            raise MemoryUnavailable("Memory retention RPC returned an invalid result")
        count = result.get("expired_count")
        if type(count) is not int or not 0 <= count <= self.batch_size:
            raise MemoryUnavailable("Memory retention RPC returned an invalid expiry count")
        return count


async def run_forever(
    worker: MemoryRetentionWorker,
    *,
    poll_interval_seconds: int = 60,
    stop_event: asyncio.Event | None = None,
) -> None:
    if not 10 <= poll_interval_seconds <= 3600:
        raise ValueError("poll_interval_seconds must be between 10 and 3600")
    stop = stop_event or asyncio.Event()
    while not stop.is_set():
        try:
            expired = await worker.process_once()
            if expired:
                log.info("Memory retention batch completed; expired_count=%s", expired)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("Memory retention batch failed; next bounded poll remains scheduled")
        if not stop.is_set():
            try:
                await asyncio.wait_for(stop.wait(), timeout=poll_interval_seconds)
            except asyncio.TimeoutError:
                pass


async def serve_enabled(*, stop_event: asyncio.Event | None = None) -> None:
    if not _enabled():
        return
    if os.getenv("ALLPHA_MEMORY_COORDINATOR_ENABLED", "false").strip().lower() != "true":
        raise SystemExit("Memory retention requires ALLPHA_MEMORY_COORDINATOR_ENABLED=true")
    store = MemoryCoordinator()
    try:
        store._config()
    except MemoryUnavailable as exc:
        raise SystemExit(f"Memory retention configuration is invalid: {exc}") from exc
    batch_size = _bounded_int("ALLPHA_MEMORY_RETENTION_BATCH_SIZE", 100, 1, 500)
    poll_interval = _bounded_int("ALLPHA_MEMORY_RETENTION_POLL_SECONDS", 60, 10, 3600)
    stop = stop_event or asyncio.Event()
    if stop_event is None:
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, stop.set)
            except (NotImplementedError, RuntimeError):
                log.debug("Signal handler unavailable for %s", sig.name)
    log.info(
        "Memory retention consumer enabled; batch_size=%s poll_seconds=%s",
        batch_size, poll_interval,
    )
    await run_forever(
        MemoryRetentionWorker(store, batch_size=batch_size),
        poll_interval_seconds=poll_interval,
        stop_event=stop,
    )


def main() -> None:
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO").upper())
    if not _enabled():
        log.info("Memory retention worker is disabled")
        return
    asyncio.run(serve_enabled())


if __name__ == "__main__":
    main()

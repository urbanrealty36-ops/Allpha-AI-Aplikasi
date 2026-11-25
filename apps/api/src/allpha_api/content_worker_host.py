"""Shared Railway host for the existing canonical ENG-P13 media job consumers.

This composes the existing typed Postgres lifecycle queues; it does not add a
second queue, job table, or duplicate media engine. Each consumer is gated and
failure-isolated so a missing provider/scanner does not disable siblings.
"""
from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from allpha_api import (
    content_media_worker,
    content_transcode_worker,
    content_provider_callback_worker,
    content_provider_cleanup_worker,
)

log = logging.getLogger("allpha.content_worker_host")


@dataclass
class _Consumer:
    name: str
    worker: Any
    batch: Callable[[], Awaitable[int]]
    poll_seconds: float


def _poll_seconds(name: str, default: float) -> float:
    try:
        value = float(os.getenv(name, str(default)))
    except ValueError as exc:
        raise SystemExit(f"{name} must be numeric") from exc
    if not 1 <= value <= 120:
        raise SystemExit(f"{name} must be between 1 and 120")
    return value


def _safe_gate(name: str, gate: Callable[[], bool]) -> bool:
    try:
        return bool(gate())
    except SystemExit as exc:
        log.error("%s consumer remains disabled by configuration: %s", name, exc)
        return False
    except Exception:
        log.exception("%s consumer readiness failed; consumer remains disabled", name)
        return False


def enabled() -> bool:
    """Return true only when at least one media consumer has a complete config."""
    gates = (
        ("Image/subtitle", content_media_worker.enabled),
        ("Cloudinary transcode", content_transcode_worker.enabled),
        ("Cloudinary callback", content_provider_callback_worker.enabled),
        ("Cloudinary cleanup", content_provider_cleanup_worker.enabled),
    )
    return any(_safe_gate(name, gate) for name, gate in gates)


def _build_consumers() -> list[_Consumer]:
    consumers: list[_Consumer] = []
    specs = (
        (
            "Image/subtitle",
            content_media_worker.enabled,
            content_media_worker.MediaWorker,
            "process_batch",
            "CONTENT_IMAGE_POLL_SECONDS",
            3.0,
        ),
        (
            "Cloudinary transcode",
            content_transcode_worker.enabled,
            content_transcode_worker.TranscodeWorker,
            "batch",
            "CONTENT_TRANSCODE_POLL_SECONDS",
            5.0,
        ),
        (
            "Cloudinary callback",
            content_provider_callback_worker.enabled,
            content_provider_callback_worker.CallbackWorker,
            "batch",
            "CONTENT_PROVIDER_CALLBACK_POLL_SECONDS",
            3.0,
        ),
        (
            "Cloudinary cleanup",
            content_provider_cleanup_worker.enabled,
            content_provider_cleanup_worker.CleanupWorker,
            "batch",
            "CONTENT_PROVIDER_CLEANUP_POLL_SECONDS",
            15.0,
        ),
    )
    for name, gate, factory, batch_name, poll_name, default_poll in specs:
        if not _safe_gate(name, gate):
            continue
        try:
            worker = factory()
            batch = getattr(worker, batch_name)
            consumers.append(_Consumer(name, worker, batch, _poll_seconds(poll_name, default_poll)))
        except SystemExit as exc:
            log.error("%s consumer construction rejected; siblings remain active: %s", name, exc)
        except Exception:
            log.exception("%s consumer construction failed; siblings remain active", name)
    return consumers


async def _run_consumer(consumer: _Consumer, stop_event: asyncio.Event) -> None:
    log.info("%s media consumer started; poll_seconds=%s", consumer.name, consumer.poll_seconds)
    try:
        while not stop_event.is_set():
            try:
                processed = await consumer.batch()
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("%s media consumer batch failed; retrying after bounded poll", consumer.name)
                processed = 0
            if processed == 0 and not stop_event.is_set():
                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=consumer.poll_seconds)
                except asyncio.TimeoutError:
                    pass
    finally:
        client = getattr(consumer.worker, "client", None)
        close = getattr(client, "aclose", None)
        if callable(close):
            await close()
        log.info("%s media consumer stopped", consumer.name)


async def serve_enabled(*, stop_event: asyncio.Event) -> None:
    consumers = _build_consumers()
    if not consumers:
        log.warning("Content media host remains idle; no media consumer passed its configuration gate")
        return
    log.info("Content media host started with consumers=%s", [item.name for item in consumers])
    tasks = [
        asyncio.create_task(_run_consumer(consumer, stop_event), name=f"content-{consumer.name.lower().replace('/', '-')}")
        for consumer in consumers
    ]
    try:
        await asyncio.gather(*tasks)
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

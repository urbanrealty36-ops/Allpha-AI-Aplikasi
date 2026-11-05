"""Bounded Vercel Cron orchestration for WP-04 lifecycle work.

This module deliberately invokes one existing durable worker batch per Cron
request. It never starts daemon polling loops. Jobs requiring malware scanning
remain queued/private until an approved scanner adapter is available.
"""
from __future__ import annotations

import logging
import os
from typing import Any

import httpx

from allpha_api.content_scheduler_worker import ContentScheduler
from allpha_api.content_provider_cleanup_worker import CleanupWorker
from allpha_api.content_media_worker import MediaWorker
from allpha_api.content_transcode_worker import TranscodeWorker
from allpha_api.content_provider_callback_worker import CallbackWorker
from allpha_api.content_retention_worker import RetentionWorker

log = logging.getLogger("allpha.wp04_vercel_cron")


async def _run_one_batch(name: str, worker_type: type[Any], required: tuple[str, ...]) -> dict[str, Any]:
    missing = [key for key in required if not os.getenv(key)]
    if missing:
        return {"status": "deferred", "reason": "worker_configuration_missing", "missing": missing}
    worker = None
    try:
        worker = worker_type()
        # These worker methods claim a single durable job using DB leases and
        # execute one bounded unit of work. Never call worker.run() here.
        batch = getattr(worker, "batch", None) or getattr(worker, "process_batch", None)
        if batch is None:
            raise TypeError(f"{name}_batch_method_missing")
        claimed = await batch()
        return {"status": "processed" if claimed else "idle", "claimed": int(claimed)}
    except Exception as exc:
        log.exception("WP-04 Vercel batch failed worker=%s", name)
        return {"status": "error", "error_code": type(exc).__name__}
    finally:
        if worker is not None:
            await worker.client.aclose()


async def _schedule_retention_candidates() -> dict[str, Any]:
    """Enqueue due retention candidates without claiming or deleting any object."""
    base = os.getenv("SUPABASE_URL", "").rstrip("/")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SECRET_KEY")
    if not base or not key:
        return {"status": "deferred", "reason": "supabase_server_credentials_missing"}
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(12, connect=3)) as client:
            response = await client.post(
                f"{base}/rest/v1/rpc/enqueue_expired_content_retention_jobs",
                headers={"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={"p_limit": 100},
            )
            response.raise_for_status()
            result = response.json() if response.content else 0
        return {"status": "scheduled", "enqueued": int(result or 0), "purge_enabled": False}
    except Exception as exc:
        log.exception("WP-04 retention candidate scheduling failed")
        return {"status": "error", "error_code": type(exc).__name__}


async def run_wp04_vercel_batches() -> dict[str, Any]:
    """Run bounded safe lifecycle work; scanner-dependent work remains fail-closed."""
    supabase_required = ("SUPABASE_URL",)
    if not (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SECRET_KEY")):
        supabase_required += ("SUPABASE_SERVICE_ROLE_KEY|SUPABASE_SECRET_KEY",)

    scheduled = await _run_one_batch(
        "scheduled-publication",
        ContentScheduler,
        supabase_required,
    )
    cleanup = await _run_one_batch(
        "cloudinary-provider-cleanup",
        CleanupWorker,
        supabase_required + ("CLOUDINARY_CLOUD_NAME", "CLOUDINARY_API_KEY", "CLOUDINARY_API_SECRET"),
    )
    image_processing = await _run_one_batch(
        "image-processing-clamav", MediaWorker, supabase_required + ("CLAMAV_HOST",)
    )
    transcode = await _run_one_batch(
        "cloudinary-transcode", TranscodeWorker,
        supabase_required + ("CLAMAV_HOST", "CLOUDINARY_CLOUD_NAME", "CLOUDINARY_API_KEY",
                            "CLOUDINARY_API_SECRET", "ALLPHA_CLOUDINARY_CALLBACK_URL"),
    )
    provider_callbacks = await _run_one_batch(
        "cloudinary-provider-callback", CallbackWorker,
        supabase_required + ("CLAMAV_HOST", "CLOUDINARY_CLOUD_NAME"),
    )
    scanner = {
        "image_processing": image_processing,
        "transcode": transcode,
        "provider_callbacks": provider_callbacks,
        "media_ready_promotion": "worker_and_database_guarded",
    }
    retention_enabled = all(
        os.getenv(name, "false").strip().lower() in {"1", "true", "yes"}
        for name in (
            "CONTENT_RETENTION_PURGE_ENABLED",
            "CONTENT_RETENTION_BACKUP_VERIFIED",
            "CONTENT_RETENTION_RESTORE_DRILL_VERIFIED",
            "CONTENT_RETENTION_LEGAL_HOLD_VERIFIED",
            "CONTENT_RETENTION_APPROVAL_VERIFIED",
        )
    )
    retention_schedule = await _schedule_retention_candidates()
    retention_worker = (
        await _run_one_batch("retention-purge", RetentionWorker, supabase_required)
        if retention_enabled else {"status": "locked", "reason": "backup_pitr_restore_and_legal_hold_gates_pending"}
    )
    retention = {
        **retention_schedule,
        "worker": retention_worker,
        "purge_enabled": retention_enabled,
        "purge_status": "enabled" if retention_enabled else "locked",
        "purge_lock_reason": None if retention_enabled else "backup_pitr_restore_and_legal_hold_gates_pending",
    }
    return {
        "scheduled_publication": scheduled,
        "provider_cleanup": cleanup,
        "media_scanning_and_transcode": scanner,
        "retention": retention,
        "execution": {"mode": "vercel_function_bounded_batch", "max_jobs_per_worker": 1},
    }

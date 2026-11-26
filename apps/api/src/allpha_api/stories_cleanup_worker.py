"""Scheduled, one-shot cleanup for expired/removed Stories (ENG-P16).

Run from a dedicated Railway Cron service. Business truth remains in the
canonical content_items/content_media tables; this module creates no registry.
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Any
from allpha_api.content_api import _config
from allpha_api.stories_api import _cleanup_story_media, _expire_due_stories, _server_db

log = logging.getLogger("allpha.stories_cleanup_worker")
ELIGIBLE_MEDIA_STATES = ("uploaded", "ready", "processing", "failed", "deleting")
DEFAULT_BATCH_LIMIT = 100
MAX_BATCH_LIMIT = 200


class StoriesCleanupConfigurationError(RuntimeError):
    """The worker must not run without explicit enablement and server credentials."""


class StoriesCleanupResponseError(RuntimeError):
    """A database response violates the expected list-of-row-objects contract."""


def _require_rows(value: Any, *, operation: str) -> list[dict[str, Any]]:
    """Validate PostgREST response shape before any row access or iteration."""
    if value is None:
        return []
    if not isinstance(value, list):
        raise StoriesCleanupResponseError(
            f"Unexpected database response for {operation}: expected list, "
            f"received {type(value).__name__}"
        )
    for index, row in enumerate(value):
        if not isinstance(row, dict):
            raise StoriesCleanupResponseError(
                f"Unexpected database response for {operation}: row {index} "
                f"is {type(row).__name__}, expected object"
            )
    return value


def _enabled() -> bool:
    raw = os.getenv("ALLPHA_STORIES_CLEANUP_ENABLED", "").strip().lower()
    if raw != "true":
        raise StoriesCleanupConfigurationError(
            "ALLPHA_STORIES_CLEANUP_ENABLED must be explicitly set to true"
        )
    # Validate server-only Supabase credentials before touching any rows.
    _config()
    return True


def _batch_limit() -> int:
    raw = os.getenv("ALLPHA_STORIES_CLEANUP_BATCH_LIMIT", str(DEFAULT_BATCH_LIMIT)).strip()
    try:
        value = int(raw)
    except ValueError as exc:
        raise StoriesCleanupConfigurationError(
            "ALLPHA_STORIES_CLEANUP_BATCH_LIMIT must be an integer"
        ) from exc
    if not 1 <= value <= MAX_BATCH_LIMIT:
        raise StoriesCleanupConfigurationError(
            f"ALLPHA_STORIES_CLEANUP_BATCH_LIMIT must be between 1 and {MAX_BATCH_LIMIT}"
        )
    return value


async def _sweep_archived_story_media(*, limit: int) -> dict[str, int]:
    """Retry archived/deleted Story media with a hard per-run media-row limit."""
    stats = {
        "stories_with_media": 0,
        "media_candidates": 0,
        "media_deleted": 0,
        "storage_failures": 0,
        "metadata_failures": 0,
        "concurrent_changes": 0,
    }
    # Resolve parent Story IDs separately instead of embedding content_items in
    # PostgREST. The embedded relation returned HTTP 300 (ambiguous FK), which
    # _server_db previously treated as a successful JSON response.
    story_rows = _require_rows(await _server_db("GET", "content_items", params={
        "select": "id",
        "content_type": "eq.story",
        "status": "in.(archived,deleted)",
        "order": "created_at.asc",
        "limit": "1000",
    }), operation="list archived/deleted Stories")
    story_ids_for_query = [str(row.get("id") or "") for row in story_rows]
    story_ids_for_query = [story_id for story_id in story_ids_for_query if story_id]
    if not story_ids_for_query:
        return stats

    rows = _require_rows(await _server_db("GET", "content_media", params={
        "select": "id,content_id,owner_id,storage_path,status",
        "content_id": f"in.({','.join(story_ids_for_query)})",
        "status": "in.(uploaded,ready,processing,failed,deleting)",
        "order": "created_at.asc",
        "limit": str(limit),
    async def _sweep_archived_story_media(*, limit: int) -> dict[str, int]:
    """Retry archived/deleted Story media through the canonical provider lifecycle."""
    stats = {
        "stories_with_media": 0, "media_candidates": 0, "media_deleted": 0,
        "provider_cleanup_queued": 0, "media_blocked": 0, "media_failures": 0,
        "concurrent_changes": 0,
    }
    story_rows = _require_rows(await _server_db("GET", "content_items", params={
        "select": "id", "content_type": "eq.story", "status": "in.(archived,deleted)",
        "order": "created_at.asc", "limit": "1000",
    }), operation="list archived/deleted Stories")
    story_ids = [str(row.get("id") or "") for row in story_rows if row.get("id")]
    if not story_ids:
        return stats
    rows = _require_rows(await _server_db("GET", "content_media", params={
        "select": "id,content_id,owner_id,status", "content_id": f"in.({','.join(story_ids)})",
        "status": "in.(uploaded,ready,processing,failed,deleting)",
        "order": "created_at.asc", "limit": str(limit),
    }), operation="list media for archived/deleted Stories")
    stats["media_candidates"] = len(rows)
    story_ids_with_media = set()
    for item in rows:
        story_ids_with_media.add(str(item.get("content_id") or ""))
        try:
            outcome = await _cleanup_story_media(
                str(item["content_id"]), str(item["owner_id"]),
                media_id=str(item["id"]), detailed=True,
            )
        except Exception:
            stats["media_failures"] += 1
            log.exception("Story provider cleanup deferred media_id=%s", item.get("id"))
            continue
        stats["media_deleted"] += outcome["deleted"]
        stats["provider_cleanup_queued"] += outcome["queued"]
        stats["media_blocked"] += outcome["blocked"]
        stats["concurrent_changes"] += outcome["concurrent"]
        stats["media_failures"] += outcome["failed"]
    stats["stories_with_media"] = len(story_ids_with_media)
    return stats

async def run_cleanup_once(*, limit: int | None = None) -> dict[str, Any]:
    """Run a single bounded cleanup pass; raise on fatal configuration/database errors."""
    _enabled()
    effective_limit = _batch_limit() if limit is None else limit
    if not 1 <= effective_limit <= MAX_BATCH_LIMIT:
        raise StoriesCleanupConfigurationError(
            f"limit must be between 1 and {MAX_BATCH_LIMIT}"
        )

    # The canonical lifecycle archives expired Stories and attempts the existing
    # cleanup path. The recovery sweep below handles interrupted cleanup and 404s.
    expired_archived = await _expire_due_stories()
    recovery = await _sweep_archived_story_media(limit=effective_limit)
    result: dict[str, Any] = {
        "phase": "ENG-P16",
        "expired_stories_archived": int(expired_archived),
        "batch_limit": effective_limit,
        **recovery,
    }
    log.info("Stories cleanup pass completed: %s", result)
    return result


def main() -> None:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    try:
        summary = asyncio.run(run_cleanup_once())
    except StoriesCleanupConfigurationError as exc:
        log.error("Stories cleanup pass failed before completion: %s", type(exc).__name__)
        raise SystemExit(1) from exc
    except Exception as exc:
        # Fail the Cron invocation so dependency/runtime faults are visible.
        log.exception("Stories cleanup pass failed: %s", type(exc).__name__)
        raise SystemExit(1) from exc

    # Individual Storage failures are deliberately retained for the next scheduled
    # invocation; the run itself completed its bounded pass and remains observable.
    if summary["media_blocked"] or summary["media_failures"]:
        log.warning(
            "Stories cleanup has retryable work: blocked=%s failures=%s",
            summary["media_blocked"], summary["media_failures"],
        )


if __name__ == "__main__":
    main()

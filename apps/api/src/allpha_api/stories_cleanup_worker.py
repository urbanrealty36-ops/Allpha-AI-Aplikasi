"""Scheduled, bounded cleanup for expired/removed Stories (ENG-P16).

Business truth remains in canonical content_items/content_media tables. All media
cleanup is delegated to the Story API's provider-aware lifecycle helper.
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

from allpha_api.content_api import _config
from allpha_api.stories_api import _cleanup_story_media, _expire_due_stories, _server_db

log = logging.getLogger("allpha.stories_cleanup_worker")
DEFAULT_BATCH_LIMIT = 100
MAX_BATCH_LIMIT = 200


class StoriesCleanupConfigurationError(RuntimeError):
    """The worker must not run without explicit enablement and server credentials."""


class StoriesCleanupResponseError(RuntimeError):
    """A database response violates the expected list-of-row-objects contract."""


def _require_rows(value: Any, *, operation: str) -> list[dict[str, Any]]:
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
    if os.getenv("ALLPHA_STORIES_CLEANUP_ENABLED", "").strip().lower() != "true":
        raise StoriesCleanupConfigurationError(
            "ALLPHA_STORIES_CLEANUP_ENABLED must be explicitly set to true"
        )
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
    """Retry provider deletion for archived/deleted Stories within a hard row limit."""
    stats = {
        "stories_with_media": 0,
        "media_candidates": 0,
        "media_deleted": 0,
        "provider_cleanup_queued": 0,
        "media_blocked": 0,
        "media_failures": 0,
        "concurrent_changes": 0,
    }
    story_rows = _require_rows(await _server_db("GET", "content_items", params={
        "select": "id",
        "content_type": "eq.story",
        "status": "in.(archived,deleted)",
        "order": "created_at.asc",
        "limit": "1000",
    }), operation="list archived/deleted Stories")
    story_ids = [str(row.get("id") or "") for row in story_rows if row.get("id")]
    if not story_ids:
        return stats

    rows = _require_rows(await _server_db("GET", "content_media", params={
        "select": "id,content_id,owner_id,status",
        "content_id": f"in.({','.join(story_ids)})",
        "status": "in.(uploaded,ready,processing,failed,deleting,deleted)",
        "order": "created_at.asc",
        "limit": str(limit),
    }), operation="list media for archived/deleted Stories")
    stats["media_candidates"] = len(rows)
    stories_with_media: set[str] = set()
    for item in rows:
        content_id = str(item.get("content_id") or "")
        stories_with_media.add(content_id)
        try:
            result = await _cleanup_story_media(
                content_id,
                str(item["owner_id"]),
                media_id=str(item["id"]),
                detailed=True,
            )
        except Exception:
            stats["media_failures"] += 1
            log.exception("Story provider cleanup deferred media_id=%s", item.get("id"))
            continue
        stats["media_deleted"] += result["deleted"]
        stats["provider_cleanup_queued"] += result["queued"]
        stats["media_blocked"] += result["blocked"]
        stats["media_failures"] += result["failed"]
        stats["concurrent_changes"] += result["concurrent"]
    stats["stories_with_media"] = len(stories_with_media)
    return stats


async def run_cleanup_once(*, limit: int | None = None) -> dict[str, Any]:
    """Run one bounded cleanup pass; dependency/runtime faults fail the Cron invocation."""
    _enabled()
    effective_limit = _batch_limit() if limit is None else limit
    if not 1 <= effective_limit <= MAX_BATCH_LIMIT:
        raise StoriesCleanupConfigurationError(
            f"limit must be between 1 and {MAX_BATCH_LIMIT}"
        )
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
        log.exception("Stories cleanup pass failed: %s", type(exc).__name__)
        raise SystemExit(1) from exc
    if summary["media_blocked"] or summary["media_failures"]:
        log.warning(
            "Stories cleanup has retryable work: blocked=%s failures=%s",
            summary["media_blocked"],
            summary["media_failures"],
        )


if __name__ == "__main__":
    main()

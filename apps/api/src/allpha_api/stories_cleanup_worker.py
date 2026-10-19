"""Scheduled, one-shot cleanup for expired/removed Stories (ENG-P16).

Run from a dedicated Railway Cron service. Business truth remains in the
canonical content_items/content_media tables; this module creates no registry.
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Any
from urllib.parse import quote

import httpx
from fastapi import HTTPException

from allpha_api.content_api import _config
from allpha_api.stories_api import _expire_due_stories, _server_db

log = logging.getLogger("allpha.stories_cleanup_worker")
ELIGIBLE_MEDIA_STATES = ("uploaded", "ready", "processing", "failed", "deleting")
DEFAULT_BATCH_LIMIT = 100
MAX_BATCH_LIMIT = 200


class StoriesCleanupConfigurationError(RuntimeError):
    """The worker must not run without explicit enablement and server credentials."""


class StoriesCleanupStorageError(RuntimeError):
    """Storage deletion was not confirmed; metadata must remain retryable."""

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


async def _delete_storage_object(storage_path: str) -> bool:
    """Idempotently delete an object; 404 means it was already removed."""
    base, key = _config()
    headers = {"apikey": key, "Authorization": f"Bearer {key}"}
    url = f"{base}/storage/v1/object/{quote('content-media/' + storage_path, safe='/')}"
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=5.0)) as client:
            response = await client.delete(url, headers=headers)
    except httpx.HTTPError as exc:
        raise StoriesCleanupStorageError("Storage request failed") from exc
    if response.status_code in (200, 202, 204, 404):
        return True
    raise StoriesCleanupStorageError(f"Storage deletion not confirmed (HTTP {response.status_code})")


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
    }), operation="list media for archived/deleted Stories")

    story_ids: set[str] = set()
    stats["media_candidates"] = len(rows)
    for item in rows:
        story_ids.add(str(item.get("content_id") or ""))
        current_status = str(item.get("status") or "")
        if current_status not in ELIGIBLE_MEDIA_STATES:
            continue

        marked = item
        if current_status != "deleting":
            changed = _require_rows(await _server_db("PATCH", "content_media", params={
                "id": f"eq.{item['id']}",
                "owner_id": f"eq.{item['owner_id']}",
                "status": f"eq.{current_status}",
                "select": "id,owner_id,storage_path,status",
            }, body={"status": "deleting"}, prefer="return=representation"), operation="mark media deleting")
            if not changed:
                stats["concurrent_changes"] += 1
                continue
            marked = changed[0]

        try:
            await _delete_storage_object(str(marked["storage_path"]))
        except StoriesCleanupStorageError:
            stats["storage_failures"] += 1
            log.warning("Story media cleanup deferred; object deletion was not confirmed")
            continue

        deleted_rows = _require_rows(await _server_db("DELETE", "content_media", params={
            "id": f"eq.{marked['id']}",
            "owner_id": f"eq.{marked['owner_id']}",
            "status": "eq.deleting",
            "select": "id",
        }, prefer="return=representation"), operation="delete media metadata")
        if deleted_rows:
            stats["media_deleted"] += 1
            continue

        # A concurrent idempotent run may already have removed the metadata.
        still_present = _require_rows(await _server_db("GET", "content_media", params={
            "select": "id",
            "id": f"eq.{marked['id']}",
            "owner_id": f"eq.{marked['owner_id']}",
            "limit": "1",
        }), operation="verify media metadata removal")
        if still_present:
            stats["metadata_failures"] += 1
            log.warning("Story media object is gone but metadata cleanup remains pending")
        else:
            stats["media_deleted"] += 1

    stats["stories_with_media"] = len(story_ids - {""})
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
    except (StoriesCleanupConfigurationError, HTTPException, httpx.HTTPError) as exc:
        log.error("Stories cleanup pass failed before completion: %s", type(exc).__name__)
        raise SystemExit(1) from exc
    except Exception as exc:
        # Fail the Cron invocation so dependency/runtime faults are visible.
        log.exception("Stories cleanup pass failed: %s", type(exc).__name__)
        raise SystemExit(1) from exc

    # Individual Storage failures are deliberately retained for the next scheduled
    # invocation; the run itself completed its bounded pass and remains observable.
    if summary["storage_failures"] or summary["metadata_failures"]:
        log.warning(
            "Stories cleanup has retryable work: storage_failures=%s metadata_failures=%s",
            summary["storage_failures"],
            summary["metadata_failures"],
        )


if __name__ == "__main__":
    main()

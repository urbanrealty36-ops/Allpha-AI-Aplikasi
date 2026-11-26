from __future__ import annotations

import asyncio

import pytest

from allpha_api import stories_cleanup_worker as worker


def _async_value(value):
    async def inner():
        return value
    return inner


def _async_stats(value):
    async def inner(*, limit):
        assert 1 <= limit <= worker.MAX_BATCH_LIMIT
        return value
    return inner


@pytest.mark.parametrize("value", [
    {"message": "ambiguous relationship", "code": "PGRST201"},
    ["not-a-row-object"],
])
def test_require_rows_rejects_malformed_database_responses(value):
    with pytest.raises(worker.StoriesCleanupResponseError):
        worker._require_rows(value, operation="regression")


def test_require_rows_accepts_empty_and_object_rows():
    assert worker._require_rows(None, operation="empty") == []
    assert worker._require_rows([], operation="empty") == []
    assert worker._require_rows([{"id": "row-1"}], operation="valid") == [{"id": "row-1"}]


def test_worker_requires_explicit_enablement(monkeypatch):
    monkeypatch.delenv("ALLPHA_STORIES_CLEANUP_ENABLED", raising=False)
    with pytest.raises(worker.StoriesCleanupConfigurationError):
        worker._enabled()


def test_worker_rejects_invalid_batch_limit(monkeypatch):
    monkeypatch.setenv("ALLPHA_STORIES_CLEANUP_BATCH_LIMIT", "201")
    with pytest.raises(worker.StoriesCleanupConfigurationError):
        worker._batch_limit()
    monkeypatch.setenv("ALLPHA_STORIES_CLEANUP_BATCH_LIMIT", "not-an-int")
    with pytest.raises(worker.StoriesCleanupConfigurationError):
        worker._batch_limit()


def test_sweep_fails_closed_on_malformed_story_query_response(monkeypatch):
    async def malformed_db(*_args, **_kwargs):
        return {"message": "Multiple Choices"}

    monkeypatch.setattr(worker, "_server_db", malformed_db)
    with pytest.raises(worker.StoriesCleanupResponseError):
        asyncio.run(worker._sweep_archived_story_media(limit=10))


def test_recovery_sweep_delegates_provider_cleanup_and_distinguishes_queue_from_delete(monkeypatch):
    queries = []
    async def fake_db(method, table, *, params=None, body=None, prefer=None):
        queries.append((method, table, params))
        if table == "content_items":
            return [{"id": "story-1"}, {"id": "story-2"}]
        if table == "content_media":
            return [
                {"id": "media-queued", "content_id": "story-1", "owner_id": "owner-1", "status": "ready"},
                {"id": "media-deleted", "content_id": "story-2", "owner_id": "owner-2", "status": "deleted"},
            ]
        raise AssertionError(table)

    calls = []
    async def cleanup(content_id, owner_id, *, media_id=None, detailed=False):
        calls.append((content_id, owner_id, media_id, detailed))
        if media_id == "media-queued":
            return {"deleted": 0, "queued": 1, "blocked": 0, "failed": 0, "concurrent": 0}
        return {"deleted": 1, "queued": 0, "blocked": 0, "failed": 0, "concurrent": 0}

    monkeypatch.setattr(worker, "_server_db", fake_db)
    monkeypatch.setattr(worker, "_cleanup_story_media", cleanup)
    result = asyncio.run(worker._sweep_archived_story_media(limit=10))
    assert result["media_candidates"] == 2
    assert result["stories_with_media"] == 2
    assert result["media_deleted"] == 1
    assert result["provider_cleanup_queued"] == 1
    assert calls == [
        ("story-1", "owner-1", "media-queued", True),
        ("story-2", "owner-2", "media-deleted", True),
    ]
    media_query = next(params for method, table, params in queries if table == "content_media")
    assert media_query["status"] == "in.(uploaded,ready,processing,failed,deleting,deleted)"
    assert media_query["limit"] == "10"


def test_run_cleanup_once_delegates_expiry_and_emits_summary(monkeypatch):
    monkeypatch.setenv("ALLPHA_STORIES_CLEANUP_ENABLED", "true")
    monkeypatch.setattr(worker, "_config", lambda: ("https://supabase.example", "server-secret"))
    monkeypatch.setattr(worker, "_expire_due_stories", _async_value(3))
    monkeypatch.setattr(worker, "_sweep_archived_story_media", _async_stats({
        "stories_with_media": 2, "media_candidates": 4, "media_deleted": 2,
        "provider_cleanup_queued": 1, "media_blocked": 1, "media_failures": 0,
        "concurrent_changes": 0,
    }))
    summary = asyncio.run(worker.run_cleanup_once(limit=10))
    assert summary["phase"] == "ENG-P16"
    assert summary["expired_stories_archived"] == 3
    assert summary["media_deleted"] == 2
    assert summary["provider_cleanup_queued"] == 1
    assert summary["media_blocked"] == 1
    assert summary["batch_limit"] == 10

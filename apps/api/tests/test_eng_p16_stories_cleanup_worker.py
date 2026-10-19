from __future__ import annotations

import httpx
import pytest

from allpha_api import stories_cleanup_worker as worker



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


def test_sweep_fails_closed_on_malformed_story_query_response(monkeypatch):
    async def malformed_db(*_args, **_kwargs):
        return {"message": "Multiple Choices"}

    monkeypatch.setattr(worker, "_server_db", malformed_db)
    with pytest.raises(worker.StoriesCleanupResponseError):
        __import__("asyncio").run(worker._sweep_archived_story_media(limit=10))

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


@pytest.mark.parametrize("status_code", [200, 202, 204, 404])
def test_storage_delete_is_idempotent_for_success_and_missing_object(monkeypatch, status_code):
    class FakeResponse:
        def __init__(self, code):
            self.status_code = code

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

        async def delete(self, url, *, headers):
            assert url == "https://supabase.example/storage/v1/object/content-media/owner/story/file.png"
            assert headers["Authorization"] == "Bearer server-secret"
            return FakeResponse(status_code)

    monkeypatch.setattr(worker, "_config", lambda: ("https://supabase.example", "server-secret"))
    monkeypatch.setattr(worker.httpx, "AsyncClient", lambda **_kwargs: FakeClient())
    assert __import__("asyncio").run(worker._delete_storage_object("owner/story/file.png", "owner")) is True




@pytest.mark.parametrize("storage_path,owner_id", [
    ("other-owner/story/file.png", "owner"),
    ("owner/../other/file.png", "owner"),
    ("owner//file.png", "owner"),
    ("owner\\story\\file.png", "owner"),
    ("owner/story/file.png", ""),
])
def test_storage_delete_rejects_paths_outside_owner_prefix(monkeypatch, storage_path, owner_id):
    monkeypatch.setattr(worker, "_config", lambda: ("https://supabase.example", "server-secret"))
    with pytest.raises(worker.StoriesCleanupStorageError):
        worker._validated_storage_path(storage_path, owner_id)


def test_storage_path_accepts_normalized_owner_scoped_key():
    assert worker._validated_storage_path("owner/story/file.png", "owner") == "owner/story/file.png"


def test_storage_delete_failure_is_retryable(monkeypatch):
    class FakeResponse:
        status_code = 503

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

        async def delete(self, *_args, **_kwargs):
            return FakeResponse()

    monkeypatch.setattr(worker, "_config", lambda: ("https://supabase.example", "server-secret"))
    monkeypatch.setattr(worker.httpx, "AsyncClient", lambda **_kwargs: FakeClient())
    with pytest.raises(worker.StoriesCleanupStorageError):
        __import__("asyncio").run(worker._delete_storage_object("owner/story/file.png", "owner"))


@pytest.mark.parametrize("initial_status,storage_failure", [
    ("uploaded", True),
    ("deleting", False),
])
def test_recovery_sweep_preserves_failed_media_and_retries_deleting_status(
    monkeypatch, initial_status, storage_failure
):
    calls = []
    media = {
        "id": "media-1", "owner_id": "owner-1",
        "storage_path": "owner-1/story-1/file.png", "status": initial_status,
    }

    async def fake_db(method, table, *, params=None, body=None, prefer=None):
        calls.append((method, table, params, body, prefer))
        if method == "GET" and table == "content_items":
            return [{"id": "story-1"}]
        if method == "GET" and table == "content_media":
            return [{**dict(media), "content_id": "story-1"}]
        if method == "PATCH" and table == "content_media":
            if storage_failure:
                return [{**media, "status": "deleting"}]
            return [{**media, "status": "deleting"}]
        if method == "DELETE" and table == "content_media":
            return [{"id": "media-1"}]
        raise AssertionError((method, table, params, body))

    async def fake_delete(_path, _owner_id):
        if storage_failure:
            raise worker.StoriesCleanupStorageError("test-only transient failure")
        return True

    monkeypatch.setattr(worker, "_server_db", fake_db)
    monkeypatch.setattr(worker, "_delete_storage_object", fake_delete)
    stats = __import__("asyncio").run(worker._sweep_archived_story_media(limit=10))

    query = next(params for method, table, params, _body, _prefer in calls
                 if method == "GET" and table == "content_media")
    assert query["content_id"] == "in.(story-1)"
    assert "content_items!inner" not in query["select"]
    assert query["status"] == "in.(uploaded,ready,processing,failed,deleting)"
    assert query["limit"] == "10"
    assert stats["media_candidates"] == 1
    if storage_failure:
        assert stats["storage_failures"] == 1
        assert not any(method == "DELETE" and table == "content_media" for method, table, *_ in calls)
        assert any(method == "PATCH" and body == {"status": "deleting"}
                   for method, table, _params, body, _prefer in calls)
    else:
        assert stats["media_deleted"] == 1
        assert any(method == "DELETE" and table == "content_media" for method, table, *_ in calls)
        assert not any(method == "PATCH" for method, *_ in calls)


def test_metadata_is_not_deleted_when_storage_delete_fails(monkeypatch):
    calls = []

    async def fake_db(method, table, *, params=None, body=None, prefer=None):
        calls.append((method, table, params, body))
        if method == "GET" and table == "content_items":
            return [{"id": "story-1"}]
        if method == "GET" and table == "content_media":
            return [{
                "id": "media-2", "content_id": "story-1", "owner_id": "owner-1",
                "storage_path": "owner-1/story-1/file.mp4", "status": "ready",
            }]
        if method == "PATCH":
            return [{"id": "media-2", "owner_id": "owner-1",
                     "storage_path": "owner-1/story-1/file.mp4", "status": "deleting"}]
        raise AssertionError((method, table, params, body))

    async def fail_delete(_path, _owner_id):
        raise worker.StoriesCleanupStorageError("transient")

    monkeypatch.setattr(worker, "_server_db", fake_db)
    monkeypatch.setattr(worker, "_delete_storage_object", fail_delete)
    stats = __import__("asyncio").run(worker._sweep_archived_story_media(limit=10))
    assert stats["storage_failures"] == 1
    assert not any(method == "DELETE" for method, *_ in calls)


def test_run_cleanup_once_delegates_expiry_and_emits_summary(monkeypatch):
    monkeypatch.setenv("ALLPHA_STORIES_CLEANUP_ENABLED", "true")
    monkeypatch.setattr(worker, "_config", lambda: ("https://supabase.example", "server-secret"))
    monkeypatch.setattr(worker, "_expire_due_stories", async_value(3))
    monkeypatch.setattr(worker, "_sweep_archived_story_media", async_stats({
        "stories_with_media": 2, "media_candidates": 4, "media_deleted": 3,
        "storage_failures": 1, "metadata_failures": 0, "concurrent_changes": 0,
    }))
    summary = __import__("asyncio").run(worker.run_cleanup_once(limit=10))
    assert summary["phase"] == "ENG-P16"
    assert summary["expired_stories_archived"] == 3
    assert summary["media_deleted"] == 3
    assert summary["storage_failures"] == 1
    assert summary["batch_limit"] == 10


def async_value(value):
    async def inner():
        return value
    return inner


def async_stats(value):
    async def inner(*, limit):
        assert 1 <= limit <= worker.MAX_BATCH_LIMIT
        return value
    return inner


def test_retry_after_transient_storage_failure_removes_metadata_only_on_success(monkeypatch):
    import asyncio

    media_state = {"status": "uploaded"}
    storage_attempts = {"count": 0}
    db_deletes = {"count": 0}

    async def fake_db(method, table, *, params=None, body=None, prefer=None):
        if method == "GET" and table == "content_items":
            return [{"id": "story-retry"}]
        if method == "GET" and table == "content_media":
            if media_state["status"] == "removed":
                return []
            return [{
                "id": "media-retry", "content_id": "story-retry", "owner_id": "owner-retry",
                "storage_path": "owner-retry/story-retry/file.png",
                "status": media_state["status"],
            }]
        if method == "PATCH" and table == "content_media":
            media_state["status"] = "deleting"
            return [{"id": "media-retry", "owner_id": "owner-retry",
                     "storage_path": "owner-retry/story-retry/file.png", "status": "deleting"}]
        if method == "DELETE" and table == "content_media":
            db_deletes["count"] += 1
            media_state["status"] = "removed"
            return [{"id": "media-retry"}]
        raise AssertionError((method, table, params, body))

    async def fake_delete(_path, _owner_id):
        storage_attempts["count"] += 1
        if storage_attempts["count"] == 1:
            raise worker.StoriesCleanupStorageError("transient")
        return True

    monkeypatch.setattr(worker, "_server_db", fake_db)
    monkeypatch.setattr(worker, "_delete_storage_object", fake_delete)

    first = asyncio.run(worker._sweep_archived_story_media(limit=10))
    assert first["storage_failures"] == 1
    assert media_state["status"] == "deleting"
    assert db_deletes["count"] == 0

    second = asyncio.run(worker._sweep_archived_story_media(limit=10))
    assert second["media_deleted"] == 1
    assert storage_attempts["count"] == 2
    assert db_deletes["count"] == 1
    assert media_state["status"] == "removed"

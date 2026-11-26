import asyncio

from allpha_api.content_provider_cleanup_worker import CleanupWorker
from allpha_api.content_retention_worker import RetentionWorker


class _DeleteResponse:
    status_code = 204

    def raise_for_status(self):
        return None


class _StorageClient:
    def __init__(self):
        self.urls = []

    async def delete(self, url):
        self.urls.append(url)
        return _DeleteResponse()


def test_provider_cleanup_deletes_owner_scoped_legacy_derivative_objects():
    worker = object.__new__(CleanupWorker)
    worker.base = "https://supabase.test"
    worker.client = _StorageClient()
    derivatives = [
        {"kind": "thumbnail", "storage_path": "owner-1/content-1/thumb.webp"},
        {"kind": "display", "storage_path": "owner-1/content-1/display.webp"},
        {"kind": "duplicate", "storage_path": "owner-1/content-1/thumb.webp"},
        {"kind": "cloudinary", "provider": "cloudinary", "transformation": "c_fill,w_320"},
    ]
    asyncio.run(worker.delete_legacy_derivative_objects(derivatives, owner_id="owner-1"))
    assert len(worker.client.urls) == 2
    assert all("/content-media/owner-1/" in url for url in worker.client.urls)


def test_provider_cleanup_rejects_derivative_path_outside_owner_prefix():
    worker = object.__new__(CleanupWorker)
    worker.base = "https://supabase.test"
    worker.client = _StorageClient()
    try:
        asyncio.run(worker.delete_legacy_derivative_objects(
            [{"storage_path": "another-owner/content-1/thumb.webp"}],
            owner_id="owner-1",
        ))
    except ValueError as exc:
        assert str(exc) == "LEGACY_STORAGE_IDENTITY_INVALID"
    else:
        raise AssertionError("cross-owner derivative path unexpectedly accepted")


def test_cloudinary_cleanup_worker_deletes_legacy_derivatives_after_provider_asset():
    worker = object.__new__(CleanupWorker)
    worker.worker_id = "provider-cleanup-test"
    calls = []

    async def fake_rpc(name, payload):
        calls.append(("rpc", name, payload))
        if name == "claim_content_lifecycle_jobs":
            return [{
                "id": "job-1", "lease_token": "lease-1", "media_id": "media-1", "owner_id": "owner-1",
                "payload": {
                    "provider": "cloudinary", "action": "delete_media",
                    "provider_public_id": "allpha/media-1", "resource_type": "image",
                    "legacy_storage": {"bucket_id": "content-media", "storage_path": "owner-1/content-1/source.jpg"},
                    "derivatives": [{"storage_path": "owner-1/content-1/thumb.webp"}],
                },
            }]
        return "succeeded"

    async def delete_asset(public_id, resource_type):
        calls.append(("asset", public_id, resource_type))

    async def delete_legacy_storage_object(item, owner_id=None):
        calls.append(("legacy", item["storage_path"], owner_id))

    async def delete_legacy_derivative_objects(items, owner_id):
        calls.append(("derivatives", items, owner_id))

    worker.rpc = fake_rpc
    worker.delete_asset = delete_asset
    worker.delete_legacy_storage_object = delete_legacy_storage_object
    worker.delete_legacy_derivative_objects = delete_legacy_derivative_objects
    assert asyncio.run(worker.batch()) == 1
    assert ("asset", "allpha/media-1", "image") in calls
    assert ("legacy", "owner-1/content-1/source.jpg", "owner-1") in calls
    assert any(call[0] == "derivatives" for call in calls)
    assert any(call[0] == "rpc" and call[1] == "complete_cloudinary_media_delete_job" for call in calls)


def test_content_retention_defers_until_provider_cleanup_is_confirmed():
    worker = object.__new__(RetentionWorker)
    calls = []

    async def fake_rpc(name, payload):
        calls.append((name, payload))
        if name == "request_cloudinary_content_media_delete":
            return {"outcome": "queued"}
        return "deferred"

    worker.rpc = fake_rpc
    job = {"id": "retention-1", "lease_token": "lease-1"}
    media = [{
        "id": "media-1", "owner_id": "owner-1", "status": "ready",
        "storage_provider": "cloudinary", "provider_public_id": "allpha/media-1",
    }]
    complete, objects, rows = asyncio.run(worker._cleanup_media_rows(job, media))
    assert complete is False
    assert objects == [] and rows == []
    assert any(name == "defer_content_retention_job" for name, _ in calls)


def test_content_retention_removes_metadata_only_after_provider_delete_confirmation():
    worker = object.__new__(RetentionWorker)
    calls = []
    media = {
        "id": "media-2", "owner_id": "owner-2", "status": "deleted",
        "storage_provider": "cloudinary", "provider_public_id": "allpha/media-2",
        "provider_delete_state": "deleted", "provider_deleted_at": "2026-11-26T00:00:00Z",
        "derivatives": [],
    }

    async def fake_rpc(name, payload):
        calls.append(("rpc", name, payload))
        if name == "request_cloudinary_content_media_delete":
            return {"outcome": "already_deleted"}
        raise AssertionError(name)

    async def fake_db(method, path, params=None, body=None, prefer=None):
        calls.append((method, path, params, body, prefer))
        if method == "GET":
            return [media]
        if method == "DELETE":
            return [media]
        raise AssertionError((method, path))

    worker.rpc = fake_rpc
    worker.db = fake_db
    job = {"id": "retention-2", "lease_token": "lease-2"}
    complete, objects, rows = asyncio.run(worker._cleanup_media_rows(job, [media]))
    assert complete is True
    assert objects == ["cloudinary:allpha/media-2"]
    assert rows == ["media-2"]
    assert any(call[0] == "DELETE" and call[1] == "content_media" for call in calls)



def test_supabase_storage_cleanup_worker_uses_legacy_provider_completion_rpc():
    worker = object.__new__(CleanupWorker)
    worker.worker_id = "provider-cleanup-test"
    calls = []

    async def fake_rpc(name, payload):
        calls.append(("rpc", name, payload))
        if name == "claim_content_lifecycle_jobs":
            return [{
                "id": "job-2", "lease_token": "lease-2", "media_id": "media-2", "owner_id": "owner-2",
                "payload": {
                    "provider": "supabase", "action": "delete_media",
                    "bucket_id": "content-media", "storage_path": "owner-2/content-2/source.jpg",
                    "derivatives": [{"storage_path": "owner-2/content-2/thumb.webp"}],
                },
            }]
        return "succeeded"

    async def delete_legacy_storage_object(item, owner_id=None):
        calls.append(("legacy", item["storage_path"], owner_id))

    async def delete_legacy_derivative_objects(items, owner_id):
        calls.append(("derivatives", items, owner_id))

    worker.rpc = fake_rpc
    worker.delete_legacy_storage_object = delete_legacy_storage_object
    worker.delete_legacy_derivative_objects = delete_legacy_derivative_objects
    assert asyncio.run(worker.batch()) == 1
    assert ("legacy", "owner-2/content-2/source.jpg", "owner-2") in calls
    assert any(call[0] == "derivatives" for call in calls)
    assert any(call[0] == "rpc" and call[1] == "complete_legacy_content_media_delete_job" for call in calls)

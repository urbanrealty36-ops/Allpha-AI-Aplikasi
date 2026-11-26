import asyncio

from allpha_api import stories_api


def test_story_cloudinary_cleanup_queues_provider_delete_and_preserves_registry(monkeypatch):
    calls = []
    media = {
        "id": "00000000-0000-0000-0000-000000000401",
        "owner_id": "00000000-0000-0000-0000-000000000402",
        "storage_path": "allpha/asset",
        "provider_public_id": "allpha/asset",
        "provider_asset_id": "cloudinary-asset",
        "status": "ready",
    }

    async def fake_db(method, table, *, params=None, body=None, prefer=None):
        calls.append((method, table, params, body))
        if method == "GET" and table == "content_media":
            return [media]
        raise AssertionError((method, table, params, body))

    async def fake_service_rpc(name, *, body):
        calls.append(("RPC", name, body))
        assert name == "request_cloudinary_content_media_delete"
        return {"outcome": "queued", "media": media}

    async def forbidden_storage(*args, **kwargs):
        raise AssertionError("Cloudinary public_id must never be sent to Supabase Storage")

    monkeypatch.setattr(stories_api, "_server_db", fake_db)
    monkeypatch.setattr(stories_api, "service_db_request", fake_service_rpc)
    monkeypatch.setattr(stories_api, "_storage", forbidden_storage)

    result = asyncio.run(stories_api._cleanup_story_media(media["id"], media["owner_id"]))
    assert result == 1
    assert any(call[0] == "RPC" for call in calls)
    assert not any(call[0] in {"PATCH", "DELETE"} and call[1] == "content_media" for call in calls)


def test_story_cloudinary_cleanup_preserves_legal_hold_media(monkeypatch):
    media = {
        "id": "00000000-0000-0000-0000-000000000411",
        "owner_id": "00000000-0000-0000-0000-000000000412",
        "storage_path": "allpha/held",
        "provider_public_id": "allpha/held",
        "provider_asset_id": "cloudinary-held",
        "status": "ready",
    }

    async def fake_db(method, table, *, params=None, body=None, prefer=None):
        if method == "GET" and table == "content_media":
            return [media]
        raise AssertionError((method, table, params, body))

    async def fake_service_rpc(name, *, body):
        return {"outcome": "legal_hold", "media": media}

    async def forbidden_storage(*args, **kwargs):
        raise AssertionError("legal-hold Cloudinary media must remain untouched")

    monkeypatch.setattr(stories_api, "_server_db", fake_db)
    monkeypatch.setattr(stories_api, "service_db_request", fake_service_rpc)
    monkeypatch.setattr(stories_api, "_storage", forbidden_storage)

    assert asyncio.run(stories_api._cleanup_story_media(media["id"], media["owner_id"])) == 0


def test_story_legacy_storage_cleanup_retains_existing_delete_flow(monkeypatch):
    media = {
        "id": "00000000-0000-0000-0000-000000000421",
        "owner_id": "00000000-0000-0000-0000-000000000422",
        "storage_path": "owner/story/file.jpg",
        "provider_public_id": None,
        "provider_asset_id": None,
        "status": "uploaded",
    }
    db_calls = []
    storage_calls = []

    async def fake_db(method, table, *, params=None, body=None, prefer=None):
        db_calls.append((method, table, params, body))
        if method == "GET" and table == "content_media":
            return [media]
        if method == "PATCH" and table == "content_media":
            return [{**media, "status": "deleting"}]
        if method == "DELETE" and table == "content_media":
            return None
        raise AssertionError((method, table, params, body))

    async def fake_storage(method, path):
        storage_calls.append((method, path))

    async def forbidden_service_rpc(*args, **kwargs):
        raise AssertionError("legacy Supabase Storage media must not use Cloudinary deletion RPC")

    monkeypatch.setattr(stories_api, "_server_db", fake_db)
    monkeypatch.setattr(stories_api, "service_db_request", forbidden_service_rpc)
    monkeypatch.setattr(stories_api, "_storage", fake_storage)

    assert asyncio.run(stories_api._cleanup_story_media(media["id"], media["owner_id"])) == 1
    assert storage_calls == [("DELETE", "content-media/owner/story/file.jpg")]
    assert any(call[0] == "DELETE" and call[1] == "content_media" for call in db_calls)



def test_story_cleanup_detailed_result_distinguishes_provider_queue_from_deletion(monkeypatch):
    media = {
        "id": "00000000-0000-0000-0000-000000000431",
        "owner_id": "00000000-0000-0000-0000-000000000432",
        "storage_path": "allpha/asset", "provider_public_id": "allpha/asset",
        "provider_asset_id": "cloudinary-asset", "status": "ready", "derivatives": [],
    }
    async def fake_db(method, table, *, params=None, body=None, prefer=None):
        if method == "GET" and table == "content_media": return [media]
        raise AssertionError((method, table, params, body))
    async def fake_rpc(name, *, body): return {"outcome": "queued"}
    monkeypatch.setattr(stories_api, "_server_db", fake_db)
    monkeypatch.setattr(stories_api, "service_db_request", fake_rpc)
    result = asyncio.run(stories_api._cleanup_story_media(media["id"], media["owner_id"], detailed=True))
    assert result == {"deleted": 0, "queued": 1, "blocked": 0, "failed": 0, "concurrent": 0}

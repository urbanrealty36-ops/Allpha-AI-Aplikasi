from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from allpha_api import stories_api
from allpha_api.main import app


def test_guest_story_discovery_returns_only_public_profile_stories_and_hides_storage_paths(monkeypatch):
    now = datetime.now(timezone.utc)
    story_id = "00000000-0000-0000-0000-000000000101"
    async def fake_db(method, table, *, params=None, body=None, prefer=None):
        params = params or {}
        if table == "content_items":
            assert params.get("visibility") == "eq.public"
            return [{
                "id": story_id,
                "owner_id": "public-story-author",
                "content_type": "story",
                "body": "A real public story",
                "visibility": "public",
                "status": "published",
                "moderation_status": "approved",
                "version": 1,
                "created_at": now.isoformat(),
                "updated_at": now.isoformat(),
                "published_at": now.isoformat(),
                "expires_at": (now + timedelta(hours=12)).isoformat(),
                "provenance": {},
            }]
        if table == "profiles":
            return [{
                "id": "public-story-author",
                "username": "public_author",
                "display_name": "Public Author",
                "avatar_url": None,
                "visibility": "public",
            }]
        if table == "content_media":
            return [{
                "id": "media-1",
                "content_id": story_id,
                "owner_id": "public-story-author",
                "bucket_id": "content-media",
                "storage_path": "private/path/story.jpg",
                "filename": "story.jpg",
                "media_type": "image/jpeg",
                "size_bytes": 123,
                "sha256": "test-only",
                "status": "ready",
                "created_at": now.isoformat(),
            }]
        raise AssertionError(f"unexpected anonymous story query: {table}")

    async def signed_url(path: str, *, expires_in: int = 300):
        assert path == "private/path/story.jpg"
        assert expires_in == 300
        return "https://signed.example.invalid/story.jpg?expires=300"

    monkeypatch.setattr(stories_api, "_server_db", fake_db)
    monkeypatch.setattr(stories_api, "_signed_media_preview_url", signed_url)
    app.dependency_overrides.clear()
    try:
        response = TestClient(app).get("/v1/stories?limit=10")
        assert response.status_code == 200, response.text
        payload = response.json()
        assert len(payload["items"]) == 1
        item = payload["items"][0]
        assert item["id"] == story_id
        assert item["discovery_group"] == "suggested_public"
        assert item["creator"]["display_name"] == "Public Author"
        assert item["media"][0]["preview_url"].startswith("https://signed.example.invalid/")
        assert "storage_path" not in item["media"][0]
    finally:
        app.dependency_overrides.clear()


def test_guest_story_discovery_excludes_non_public_profiles(monkeypatch):
    now = datetime.now(timezone.utc)

    async def fake_db(method, table, *, params=None, body=None, prefer=None):
        if table == "content_items":
            return [{
                "id": "00000000-0000-0000-0000-000000000102",
                "owner_id": "private-story-author",
                "content_type": "story",
                "body": "Not public",
                "visibility": "public",
                "status": "published",
                "moderation_status": "approved",
                "version": 1,
                "created_at": now.isoformat(),
                "updated_at": now.isoformat(),
                "published_at": now.isoformat(),
                "expires_at": (now + timedelta(hours=12)).isoformat(),
                "provenance": {},
            }]
        if table == "profiles":
            return [{
                "id": "private-story-author",
                "username": "private_author",
                "display_name": "Private Author",
                "avatar_url": None,
                "visibility": "private",
            }]
        raise AssertionError(f"private profile must be filtered before {table}")

    monkeypatch.setattr(stories_api, "_server_db", fake_db)
    app.dependency_overrides.clear()
    try:
        response = TestClient(app).get("/v1/stories?limit=10")
        assert response.status_code == 200, response.text
        assert response.json()["items"] == []
    finally:
        app.dependency_overrides.clear()

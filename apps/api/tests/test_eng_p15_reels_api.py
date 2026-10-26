from fastapi import Request
from fastapi.testclient import TestClient

from allpha_api import feed_api
from allpha_api.auth import current_user, optional_current_user
from allpha_api.main import app

client = TestClient(app)


def _auth_as(user_id="reels-viewer"):
    async def fake_current_user(request: Request):
        request.state.user_id = user_id
        request.state.supabase_access_token = "test-token-only"
        return {"id": user_id, "email": "reels-viewer@example.invalid"}
    return fake_current_user


def test_reels_allows_guest_public_read_through_canonical_feed(monkeypatch):
    calls = []

    async def fake_feed(**kwargs):
        calls.append(kwargs)
        return {
            "items": [
                {"id": "public-video", "visibility": "public", "media": [
                    {"id": "v1", "media_type": "video/mp4", "preview_url": "https://signed.invalid/v"}
                ]},
                {"id": "public-image", "visibility": "public", "media": [
                    {"id": "i1", "media_type": "image/jpeg", "preview_url": "https://signed.invalid/i"}
                ]},
            ],
            "next_cursor": None,
            "mode": "recent",
            "personalization_enabled": False,
        }

    monkeypatch.setattr(feed_api, "get_feed", fake_feed)
    response = client.get("/v1/reels?mode=recent&limit=10")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert [item["id"] for item in payload["items"]] == ["public-video"]
    assert calls[0]["user"] is None


def test_reels_reuses_canonical_feed_and_filters_to_video_and_audio(monkeypatch):
    calls = []

    async def fake_feed(**kwargs):
        calls.append(kwargs)
        return {
            "items": [
                {"id": "video", "media": [{"id": "v1", "media_type": "video/mp4", "preview_url": "https://signed.invalid/v"}]},
                {"id": "audio", "media": [{"id": "a1", "media_type": "audio/mpeg", "preview_url": "https://signed.invalid/a"}]},
                {"id": "image", "media": [{"id": "i1", "media_type": "image/jpeg", "preview_url": "https://signed.invalid/i"}]},
                {"id": "text", "media": []},
            ],
            "next_cursor": "existing-feed-cursor",
            "mode": "recent",
            "personalization_enabled": True,
        }

    monkeypatch.setattr(feed_api, "get_feed", fake_feed)
    app.dependency_overrides[current_user] = _auth_as()
    app.dependency_overrides[optional_current_user] = _auth_as()
    try:
        response = client.get("/v1/reels?mode=recent&limit=10")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert [item["id"] for item in payload["items"]] == ["video", "audio"]
    assert payload["next_cursor"] == "existing-feed-cursor"
    assert payload["media_kinds"] == ["video", "audio"]
    assert calls[0]["mode"] == "recent"
    assert calls[0]["limit"] == 10
    assert calls[0]["user"]["id"] == "reels-viewer"


def test_eng_p15_audio_upload_contract_is_added_to_existing_private_pipeline():
    from allpha_api import content_api

    assert content_api.ALLOWED_MEDIA["audio/mpeg"] == (".mp3", content_api.AUDIO_LIMIT)
    assert content_api.ALLOWED_MEDIA["audio/mp4"] == (".m4a", content_api.AUDIO_LIMIT)
    assert content_api.ALLOWED_MEDIA["audio/ogg"] == (".ogg", content_api.AUDIO_LIMIT)
    assert content_api.ContentCreate.model_fields["content_type"].default == "text"
    assert "audio" in str(content_api.ContentCreate.model_fields["content_type"].metadata)
    migration = (
        __import__("pathlib").Path(__file__).parent.parent
        / "supabase/migrations/20261019044440_eng_p15_audio_media.sql"
    ).read_text()
    assert "'audio/mpeg'" in migration and "'audio/webm'" in migration
    assert "public=false" in migration

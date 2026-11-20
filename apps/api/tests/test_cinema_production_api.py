import uuid

from fastapi.testclient import TestClient

from allpha_api import cinema_api
from allpha_api.auth import current_user
from allpha_api.main import app


OWNER = "11111111-1111-4111-8111-111111111111"
TITLE = "22222222-2222-4222-8222-222222222222"
MEDIA = "33333333-3333-4333-8333-333333333333"


def _client(monkeypatch):
    app.dependency_overrides[current_user] = lambda: {"id": OWNER}
    monkeypatch.setattr(cinema_api, "_title_access", lambda *args, **kwargs: None)
    return TestClient(app)


def test_cinema_production_document_saves_only_linked_ready_assets(monkeypatch):
    captured = {}

    async def title_access(*args, **kwargs):
        return {"id": TITLE, "owner_id": OWNER, "status": "draft", "version": 4, "title": "Test Film"}

    async def fake_db(method, table, *, params=None, payload=None, prefer=None):
        if method == "GET" and table == "cinema_assets":
            return [{"media_id": MEDIA}]
        if method == "PATCH" and table == "cinema_titles":
            captured["params"] = params
            captured["payload"] = payload
            return [{
                "id": TITLE, "version": payload["version"], "status": "draft",
                "production_document": payload["production_document"], "updated_at": "2026-11-20T00:00:00Z",
            }]
        raise AssertionError((method, table, params, payload))

    monkeypatch.setattr(cinema_api, "_title_access", title_access)
    monkeypatch.setattr(cinema_api, "_db", fake_db)
    client = _client(monkeypatch)
    try:
        response = client.put(f"/v1/cinema/creator/titles/{TITLE}/production", json={
            "expected_version": 4,
            "document": {
                "schema_version": 1,
                "screenplay": {"logline": "Logline", "synopsis": "Synopsis", "draft": "INT. ROOM - DAY"},
                "storyboard": [{
                    "scene_number": 1, "shot_number": 1, "description": "Wide establishing shot",
                    "image_media_id": MEDIA, "duration_ms": 3000,
                }],
                "scenes": [],
                "timeline": {"tracks": [{
                    "track_id": str(uuid.uuid4()), "kind": "video", "label": "V1",
                    "clips": [{
                        "clip_id": str(uuid.uuid4()), "media_id": MEDIA,
                        "start_ms": 0, "duration_ms": 3000,
                    }],
                }]},
                "audio_tracks": [],
                "export_profile": {"container": "mp4", "resolution": "1080p", "frame_rate": 24, "aspect_ratio": "16:9"},
            },
        })
        assert response.status_code == 200
        assert response.json()["item"]["version"] == 5
        assert captured["params"]["version"] == "eq.4"
        assert captured["payload"]["version"] == 5
        assert captured["payload"]["production_document"]["storyboard"][0]["image_media_id"] == MEDIA
    finally:
        app.dependency_overrides.pop(current_user, None)


def test_cinema_production_document_rejects_unlinked_asset_reference(monkeypatch):
    async def title_access(*args, **kwargs):
        return {"id": TITLE, "owner_id": OWNER, "status": "draft", "version": 4, "title": "Test Film"}

    async def fake_db(method, table, *, params=None, payload=None, prefer=None):
        if method == "GET" and table == "cinema_assets":
            return []
        raise AssertionError("production update must stop before writing unlinked media")

    monkeypatch.setattr(cinema_api, "_title_access", title_access)
    monkeypatch.setattr(cinema_api, "_db", fake_db)
    client = _client(monkeypatch)
    try:
        response = client.put(f"/v1/cinema/creator/titles/{TITLE}/production", json={
            "expected_version": 4,
            "document": {
                "schema_version": 1,
                "screenplay": {"logline": "", "synopsis": "", "draft": ""},
                "storyboard": [{
                    "scene_number": 1, "shot_number": 1, "description": "Shot",
                    "image_media_id": MEDIA,
                }],
                "scenes": [], "timeline": {"tracks": []}, "audio_tracks": [],
                "export_profile": {"container": "mp4", "resolution": "1080p", "frame_rate": 24, "aspect_ratio": "16:9"},
            },
        })
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "CINEMA_PRODUCTION_ASSET_NOT_LINKED"
    finally:
        app.dependency_overrides.pop(current_user, None)


def test_cinema_asset_link_requires_processed_clean_media(monkeypatch):
    async def title_access(*args, **kwargs):
        return {"id": TITLE, "owner_id": OWNER, "status": "draft", "version": 4, "title": "Test Film"}

    async def media_owners(*args, **kwargs):
        return {OWNER}

    async def fake_db(method, table, *, params=None, payload=None, prefer=None):
        if method == "GET" and table == "content_media":
            return [{
                "id": MEDIA, "owner_id": OWNER, "filename": "shot.png", "media_type": "image/png",
                "size_bytes": 100, "status": "ready", "scan_status": "clean",
                "processed_at": "2026-11-20T00:00:00Z", "derivatives": [{"kind": "preview"}],
            }]
        if method == "POST" and table == "cinema_assets":
            return [{"id": str(uuid.uuid4()), "title_id": TITLE, "media_id": MEDIA,
                     "asset_role": payload["asset_role"], "display_name": payload["display_name"]}]
        raise AssertionError((method, table, params, payload))

    monkeypatch.setattr(cinema_api, "_title_access", title_access)
    monkeypatch.setattr(cinema_api, "_title_media_owner_ids", media_owners)
    monkeypatch.setattr(cinema_api, "_db", fake_db)
    client = _client(monkeypatch)
    try:
        response = client.post(f"/v1/cinema/creator/titles/{TITLE}/assets", json={
            "media_id": MEDIA, "asset_role": "storyboard", "display_name": "Shot 01",
        })
        assert response.status_code == 201
        assert response.json()["item"]["media_id"] == MEDIA
    finally:
        app.dependency_overrides.pop(current_user, None)

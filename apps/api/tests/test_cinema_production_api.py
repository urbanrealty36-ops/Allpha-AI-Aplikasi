import uuid

from fastapi.testclient import TestClient

from allpha_api import cinema_api
from allpha_api.auth import current_user
from allpha_api.main import app


OWNER = "11111111-1111-4111-8111-111111111111"
TITLE = "22222222-2222-4222-8222-222222222222"
MEDIA = "33333333-3333-4333-8333-333333333333"
IMAGE_MEDIA = MEDIA
VIDEO_MEDIA = "66666666-6666-4666-8666-666666666666"


def _client(monkeypatch):
    app.dependency_overrides[current_user] = lambda: {"id": OWNER}
    return TestClient(app)


def test_cinema_production_document_saves_only_linked_ready_assets(monkeypatch):
    captured = {}

    async def title_access(*args, **kwargs):
        return {"id": TITLE, "owner_id": OWNER, "status": "draft", "version": 4, "title": "Test Film"}

    async def fake_db(method, table, *, params=None, payload=None, prefer=None):
        if method == "GET" and table == "cinema_assets":
            return [
                {"media_id": IMAGE_MEDIA, "asset_role": "storyboard"},
                {"media_id": VIDEO_MEDIA, "asset_role": "source_video"},
            ]
        if method == "GET" and table == "content_media":
            return [
                {"id": IMAGE_MEDIA, "owner_id": OWNER, "media_type": "image/png", "status": "ready",
                 "scan_status": "clean", "processed_at": "2026-11-20T00:00:00Z", "derivatives": [{"kind": "display"}]},
                {"id": VIDEO_MEDIA, "owner_id": OWNER, "media_type": "video/mp4", "status": "ready",
                 "scan_status": "clean", "processed_at": "2026-11-20T00:00:00Z", "derivatives": [{"kind": "hls_manifest"}]},
            ]
        if method == "PATCH" and table == "cinema_titles":
            captured["params"] = params
            captured["payload"] = payload
            return [{
                "id": TITLE, "version": payload["version"], "status": "draft",
                "production_document": payload["production_document"], "updated_at": "2026-11-20T00:00:00Z",
            }]
        raise AssertionError((method, table, params, payload))

    async def media_owners(_title):
        return {OWNER}

    monkeypatch.setattr(cinema_api, "_title_access", title_access)
    monkeypatch.setattr(cinema_api, "_title_media_owner_ids", media_owners)
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
                    "image_media_id": IMAGE_MEDIA, "duration_ms": 3000,
                }],
                "scenes": [],
                "timeline": {"tracks": [{
                    "track_id": str(uuid.uuid4()), "kind": "video", "label": "V1",
                    "clips": [{
                        "clip_id": str(uuid.uuid4()), "media_id": VIDEO_MEDIA,
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
        assert captured["payload"]["production_document"]["storyboard"][0]["image_media_id"] == IMAGE_MEDIA
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


def test_cinema_episode_accepts_processed_video_from_authorized_collaborator(monkeypatch):
    collaborator = "44444444-4444-4444-8444-444444444444"
    captured = {}

    async def title_access(*args, **kwargs):
        return {"id": TITLE, "owner_id": OWNER, "status": "draft", "version": 2, "title": "Test Film"}

    async def media_owners(_title):
        return {OWNER, collaborator}

    async def fake_db(method, table, *, params=None, payload=None, prefer=None):
        if method == "GET" and table == "content_media":
            captured["media_params"] = params
            return [{
                "id": MEDIA, "owner_id": collaborator, "media_type": "video/mp4",
                "status": "ready", "scan_status": "clean",
                "processed_at": "2026-11-24T10:00:00Z",
                "derivatives": [{"kind": "hls_manifest", "path": "private/derived/master.m3u8"}],
            }]
        if method == "POST" and table == "cinema_episodes":
            captured["episode_payload"] = payload
            return [{"id": "55555555-5555-4555-8555-555555555555", **payload}]
        raise AssertionError((method, table, params, payload))

    monkeypatch.setattr(cinema_api, "_title_access", title_access)
    monkeypatch.setattr(cinema_api, "_title_media_owner_ids", media_owners)
    monkeypatch.setattr(cinema_api, "_db", fake_db)
    app.dependency_overrides[current_user] = lambda: {"id": collaborator}
    client = TestClient(app)
    try:
        response = client.post(f"/v1/cinema/creator/titles/{TITLE}/episodes", json={
            "episode_number": 1, "title": "Episode 1", "synopsis": "Pilot", "media_id": MEDIA,
        })
        assert response.status_code == 201
        assert response.json()["item"]["media_id"] == MEDIA
        assert captured["media_params"]["owner_id"] == f"in.({OWNER},{collaborator})"
        assert captured["episode_payload"]["owner_id"] == OWNER
        assert captured["episode_payload"]["status"] == "ready"
    finally:
        app.dependency_overrides.pop(current_user, None)


def test_cinema_episode_rejects_unprocessed_or_non_video_media(monkeypatch):
    async def title_access(*args, **kwargs):
        return {"id": TITLE, "owner_id": OWNER, "status": "draft", "version": 2, "title": "Test Film"}

    async def media_owners(_title):
        return {OWNER}

    async def fake_db(method, table, *, params=None, payload=None, prefer=None):
        if method == "GET" and table == "content_media":
            return [{
                "id": MEDIA, "owner_id": OWNER, "media_type": "image/png",
                "status": "ready", "scan_status": "clean",
                "processed_at": "2026-11-24T10:00:00Z", "derivatives": [{"kind": "preview"}],
            }]
        raise AssertionError("episode must not be created from non-video media")

    monkeypatch.setattr(cinema_api, "_title_access", title_access)
    monkeypatch.setattr(cinema_api, "_title_media_owner_ids", media_owners)
    monkeypatch.setattr(cinema_api, "_db", fake_db)
    app.dependency_overrides[current_user] = lambda: {"id": OWNER}
    client = TestClient(app)
    try:
        response = client.post(f"/v1/cinema/creator/titles/{TITLE}/episodes", json={
            "episode_number": 1, "title": "Episode 1", "synopsis": "", "media_id": MEDIA,
        })
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "CINEMA_EPISODE_MEDIA_NOT_READY"
    finally:
        app.dependency_overrides.pop(current_user, None)


def test_cinema_subtitle_asset_can_be_linked_without_visual_derivatives(monkeypatch):
    async def title_access(*args, **kwargs):
        return {"id": TITLE, "owner_id": OWNER, "status": "draft", "version": 4, "title": "Test Film"}

    async def media_owners(*args, **kwargs):
        return {OWNER}

    async def fake_db(method, table, *, params=None, payload=None, prefer=None):
        if method == "GET" and table == "content_media":
            return [{
                "id": MEDIA, "owner_id": OWNER, "filename": "id.vtt", "media_type": "text/vtt",
                "size_bytes": 100, "status": "ready", "scan_status": "clean",
                "processed_at": "2026-11-25T00:00:00Z", "derivatives": [],
            }]
        if method == "POST" and table == "cinema_assets":
            return [{"id": str(uuid.uuid4()), "title_id": TITLE, "media_id": MEDIA,
                     "asset_role": "subtitle", "display_name": "Indonesian subtitles"}]
        raise AssertionError((method, table, params, payload))

    monkeypatch.setattr(cinema_api, "_title_access", title_access)
    monkeypatch.setattr(cinema_api, "_title_media_owner_ids", media_owners)
    monkeypatch.setattr(cinema_api, "_db", fake_db)
    client = _client(monkeypatch)
    try:
        response = client.post(f"/v1/cinema/creator/titles/{TITLE}/assets", json={
            "media_id": MEDIA, "asset_role": "subtitle", "display_name": "Indonesian subtitles",
        })
        assert response.status_code == 201
        assert response.json()["item"]["asset_role"] == "subtitle"
    finally:
        app.dependency_overrides.pop(current_user, None)


def test_cinema_asset_rejects_role_and_media_type_mismatch(monkeypatch):
    async def title_access(*args, **kwargs):
        return {"id": TITLE, "owner_id": OWNER, "status": "draft", "version": 4, "title": "Test Film"}

    async def media_owners(*args, **kwargs):
        return {OWNER}

    async def fake_db(method, table, *, params=None, payload=None, prefer=None):
        if method == "GET" and table == "content_media":
            return [{
                "id": MEDIA, "owner_id": OWNER, "filename": "poster.png", "media_type": "image/png",
                "size_bytes": 100, "status": "ready", "scan_status": "clean",
                "processed_at": "2026-11-25T00:00:00Z", "derivatives": [{"kind": "display"}],
            }]
        raise AssertionError("mismatched media must be rejected before inserting asset link")

    monkeypatch.setattr(cinema_api, "_title_access", title_access)
    monkeypatch.setattr(cinema_api, "_title_media_owner_ids", media_owners)
    monkeypatch.setattr(cinema_api, "_db", fake_db)
    client = _client(monkeypatch)
    try:
        response = client.post(f"/v1/cinema/creator/titles/{TITLE}/assets", json={
            "media_id": MEDIA, "asset_role": "subtitle", "display_name": "Wrong role",
        })
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "CINEMA_ASSET_ROLE_MEDIA_TYPE_MISMATCH"
    finally:
        app.dependency_overrides.pop(current_user, None)


def test_cinema_title_primary_cover_and_trailer_require_ready_linked_role(monkeypatch):
    captured = {}
    async def title_access(*args, **kwargs):
        return {"id": TITLE, "owner_id": OWNER, "status": "draft", "version": 4, "title": "Test Film"}
    async def media_owners(_title):
        return {OWNER}
    async def fake_db(method, table, *, params=None, payload=None, prefer=None):
        if method == "GET" and table == "content_media":
            media_id = params["id"].removeprefix("eq.")
            kind = "image/png" if media_id == IMAGE_MEDIA else "video/mp4"
            return [{
                "id": media_id, "owner_id": OWNER, "media_type": kind, "status": "ready",
                "scan_status": "clean", "processed_at": "2026-11-25T00:00:00Z",
                "derivatives": [{"kind": "display" if kind.startswith("image/") else "hls_manifest"}],
            }]
        if method == "GET" and table == "cinema_assets":
            return [{"id": str(uuid.uuid4())}]
        if method == "PATCH" and table == "cinema_titles":
            captured["payload"] = payload
            return [{"id": TITLE, "version": payload["version"], "status": "draft", **payload}]
        raise AssertionError((method, table, params, payload))
    monkeypatch.setattr(cinema_api, "_title_access", title_access)
    monkeypatch.setattr(cinema_api, "_title_media_owner_ids", media_owners)
    monkeypatch.setattr(cinema_api, "_db", fake_db)
    client = _client(monkeypatch)
    try:
        response = client.patch(f"/v1/cinema/creator/titles/{TITLE}", json={
            "expected_version": 4, "cover_media_id": IMAGE_MEDIA, "trailer_media_id": VIDEO_MEDIA,
        })
        assert response.status_code == 200
        assert captured["payload"]["cover_media_id"] == IMAGE_MEDIA
        assert captured["payload"]["trailer_media_id"] == VIDEO_MEDIA
        assert captured["payload"]["version"] == 5
    finally:
        app.dependency_overrides.pop(current_user, None)


def test_cinema_title_primary_media_rejects_unlinked_cover(monkeypatch):
    async def title_access(*args, **kwargs):
        return {"id": TITLE, "owner_id": OWNER, "status": "draft", "version": 4, "title": "Test Film"}
    async def media_owners(_title):
        return {OWNER}
    async def fake_db(method, table, *, params=None, payload=None, prefer=None):
        if method == "GET" and table == "content_media":
            return [{
                "id": IMAGE_MEDIA, "owner_id": OWNER, "media_type": "image/png", "status": "ready",
                "scan_status": "clean", "processed_at": "2026-11-25T00:00:00Z",
                "derivatives": [{"kind": "display"}],
            }]
        if method == "GET" and table == "cinema_assets":
            return []
        raise AssertionError("primary media must be linked with the matching asset role before update")
    monkeypatch.setattr(cinema_api, "_title_access", title_access)
    monkeypatch.setattr(cinema_api, "_title_media_owner_ids", media_owners)
    monkeypatch.setattr(cinema_api, "_db", fake_db)
    client = _client(monkeypatch)
    try:
        response = client.patch(f"/v1/cinema/creator/titles/{TITLE}", json={
            "expected_version": 4, "cover_media_id": IMAGE_MEDIA,
        })
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "CINEMA_PRIMARY_MEDIA_ASSET_NOT_LINKED"
    finally:
        app.dependency_overrides.pop(current_user, None)

def test_cinema_database_client_disables_ambient_proxy_and_redirects(monkeypatch):
    import asyncio

    captured = {}

    class FakeResponse:
        status_code = 200
        content = b"[]"

        def json(self):
            return []

    class FakeClient:
        def __init__(self, *args, **kwargs):
            captured.update(kwargs)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def request(self, *args, **kwargs):
            return FakeResponse()

    monkeypatch.setenv("SUPABASE_URL", "https://project.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "server-only-test-key")
    monkeypatch.setattr(cinema_api.httpx, "AsyncClient", FakeClient)

    result = asyncio.run(cinema_api._db("GET", "cinema_titles"))

    assert result == []
    assert captured["trust_env"] is False
    assert captured["follow_redirects"] is False

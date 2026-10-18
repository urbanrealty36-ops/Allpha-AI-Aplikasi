from pathlib import Path
import uuid

import pytest
from fastapi import Request
from fastapi.testclient import TestClient

from allpha_api.auth import current_user
from allpha_api.main import app
from allpha_api import content_api

client = TestClient(app)
CONTENT_ID = "00000000-0000-0000-0000-000000000301"


def auth_as(user_id="owner-a"):
    async def fake_current_user(request: Request):
        request.state.supabase_access_token = f"token-{user_id}"
        request.state.user_id = user_id
        return {"id": user_id, "email": f"{user_id}@example.invalid"}
    return fake_current_user


def test_content_routes_require_authentication():
    assert client.get("/v1/content/mine").status_code == 401
    assert client.post("/v1/content", json={"body": "hello"}).status_code == 401
    assert client.post(f"/v1/content/{CONTENT_ID}/publish").status_code == 401


def test_content_schema_rejects_client_owned_lifecycle_fields(monkeypatch):
    app.dependency_overrides[current_user] = auth_as("owner-a")
    try:
        response = client.post("/v1/content", json={
            "body": "Hello", "owner_id": "attacker", "status": "published", "moderation_status": "approved"
        })
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 422


def test_content_creation_uses_server_owner_and_draft_state(monkeypatch):
    calls = []
    async def fake_db(method, table, **kwargs):
        calls.append((method, table, kwargs))
        return [{"id": CONTENT_ID, **kwargs["body"]}]
    monkeypatch.setattr(content_api, "_server_db", fake_db)
    app.dependency_overrides[current_user] = auth_as("owner-a")
    try:
        response = client.post("/v1/content", json={"body": "  Halo Allpha  ", "visibility": "public"})
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 201
    item = response.json()["item"]
    assert item["owner_id"] == "owner-a"
    assert item["body"] == "Halo Allpha"
    assert item["status"] == "draft"
    assert item["moderation_status"] == "not_submitted"
    assert calls[0][1] == "content_items"


def test_foreign_content_is_hidden(monkeypatch):
    async def fake_db(method, table, **kwargs):
        return []
    monkeypatch.setattr(content_api, "_server_db", fake_db)
    app.dependency_overrides[current_user] = auth_as("owner-b")
    try:
        response = client.get(f"/v1/content/{CONTENT_ID}/preview")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "CONTENT_NOT_FOUND"


def test_upload_rejects_unsupported_mime_before_storage(monkeypatch):
    calls = []
    async def fake_owner(*args, **kwargs):
        return {"id": CONTENT_ID, "status": "draft", "body": ""}
    async def fake_storage(*args, **kwargs):
        calls.append(args)
    monkeypatch.setattr(content_api, "_owner_content", fake_owner)
    monkeypatch.setattr(content_api, "_storage", fake_storage)
    app.dependency_overrides[current_user] = auth_as("owner-a")
    try:
        response = client.post(f"/v1/content/{CONTENT_ID}/media",
            files={"file": ("payload.exe", b"MZ-not-an-image", "application/octet-stream")})
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 415
    assert calls == []


def test_migration_keeps_media_private_and_public_feed_approved_only():
    path = Path(__file__).parents[1] / "supabase/migrations/20261018153035_eng_p13_content_media_pipeline.sql"
    sql = path.read_text(encoding="utf-8").lower()
    assert "create table if not exists public.content_items" in sql
    assert "create table if not exists public.content_media" in sql
    assert "status='published' and moderation_status='approved' and visibility='public'" in sql
    assert "values ('content-media','content-media',false" in sql
    assert "revoke all on public.content_items, public.content_media from anon, public, authenticated" in sql
    assert "unique (id, owner_id)" in sql


def test_upload_parent_update_failure_cleans_storage_and_metadata(monkeypatch):
    storage_calls = []
    db_calls = []

    async def fake_owner(*args, **kwargs):
        return {"id": CONTENT_ID, "status": "draft", "body": "", "version": 1}

    async def fake_storage(method, path, **kwargs):
        storage_calls.append((method, path))

    async def fake_db(method, table, **kwargs):
        db_calls.append((method, table, kwargs))
        if method == "POST" and table == "content_media":
            return [{"id": "media-1", **kwargs["body"]}]
        if method == "PATCH" and table == "content_items":
            raise content_api.HTTPException(status_code=409, detail={"code": "CONTENT_UPLOAD_CONFLICT"})
        return None

    monkeypatch.setattr(content_api, "_owner_content", fake_owner)
    monkeypatch.setattr(content_api, "_storage", fake_storage)
    monkeypatch.setattr(content_api, "_server_db", fake_db)
    app.dependency_overrides[current_user] = auth_as("owner-a")
    try:
        response = client.post(
            f"/v1/content/{CONTENT_ID}/media",
            files={"file": ("photo.jpg", bytes.fromhex("ffd8ff") + b"test", "image/jpeg")},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409
    assert ("POST", "content-media/" + next(call[1].split("content-media/", 1)[1] for call in storage_calls if call[0] == "POST")) in storage_calls
    assert storage_calls[-1][0] == "DELETE"
    assert any(method == "DELETE" and table == "content_media" for method, table, _ in db_calls)


def test_storage_uses_bearer_auth_even_with_secret_key_fallback(monkeypatch):
    captured = {}

    class FakeResponse:
        status_code = 200

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            return None
        async def request(self, method, url, **kwargs):
            captured.update(kwargs.get("headers", {}))
            return FakeResponse()

    monkeypatch.setenv("SUPABASE_URL", "https://supabase.example")
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "secret-key-test-only")
    monkeypatch.setattr(content_api.httpx, "AsyncClient", FakeClient)

    import asyncio
    asyncio.run(content_api._storage("DELETE", "content-media/owner/path"))

    assert captured["apikey"] == "secret-key-test-only"
    assert captured["Authorization"] == "Bearer secret-key-test-only"


def test_preview_signing_uses_secret_key_fallback_for_authorization(monkeypatch):
    captured = {}

    async def fake_owner(*args, **kwargs):
        return {"id": CONTENT_ID, "status": "draft", "body": "preview"}

    async def fake_db(method, table, **kwargs):
        if method == "GET" and table == "content_media":
            return [{
                "id": "media-1", "content_id": CONTENT_ID, "owner_id": "owner-a",
                "bucket_id": "content-media", "storage_path": "owner-a/" + CONTENT_ID + "/media-1-photo.jpg",
                "filename": "photo.jpg", "media_type": "image/jpeg", "size_bytes": 16,
                "sha256": "a" * 64, "status": "uploaded", "created_at": "2026-10-18T00:00:00Z",
            }]
        return []

    class FakeResponse:
        status_code = 200
        def json(self):
            return {"signedURL": "/object/sign/content-media/private-token"}

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            return None
        async def post(self, url, **kwargs):
            captured.update(kwargs.get("headers", {}))
            return FakeResponse()

    monkeypatch.setenv("SUPABASE_URL", "https://supabase.example")
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "secret-key-test-only")
    monkeypatch.setattr(content_api, "_owner_content", fake_owner)
    monkeypatch.setattr(content_api, "_server_db", fake_db)
    monkeypatch.setattr(content_api.httpx, "AsyncClient", FakeClient)
    app.dependency_overrides[current_user] = auth_as("owner-a")
    try:
        response = client.get(f"/v1/content/{CONTENT_ID}/preview")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert captured["apikey"] == "secret-key-test-only"
    assert captured["Authorization"] == "Bearer secret-key-test-only"
    assert response.json()["media"][0]["preview_url"] == "https://supabase.example/storage/v1/object/sign/content-media/private-token"

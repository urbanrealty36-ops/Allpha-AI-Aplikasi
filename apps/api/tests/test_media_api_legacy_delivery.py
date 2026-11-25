from __future__ import annotations

import uuid

import pytest

from allpha_api import media_api


class _Response:
    def __init__(self, status_code: int, payload: object):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


@pytest.mark.asyncio
async def test_legacy_supabase_media_delivery_returns_signed_original_and_derivative_urls(monkeypatch):
    owner_id = "8f4eec9e-8c5e-4d8c-bd0e-6d7d5e8b7c90"
    media_id = uuid.UUID("1c4c1b6b-9b0a-4e9c-8e39-4a9b8d1b5c61")
    base = "https://allpha-test.supabase.co"
    row = {
        "id": str(media_id),
        "content_id": "4e8f6e9a-35f2-4ed9-8e51-6e4db1a5e0e1",
        "domain": "content",
        "purpose": "attachment",
        "owner_id": owner_id,
        "filename": "original photo.jpg",
        "media_type": "image/jpeg",
        "size_bytes": 1234,
        "sha256": "a" * 64,
        "status": "ready",
        "scan_status": "clean",
        "storage_provider": "supabase",
        "bucket_id": "content-media",
        "storage_path": "owner/original photo.jpg",
        "derivatives": [{
            "kind": "thumbnail",
            "storage_path": "owner/original photo.jpg.derived/thumbnail.webp",
            "mime_type": "image/webp",
            "size_bytes": 456,
            "width": 320,
            "height": 320,
        }],
    }
    requested: list[str] = []

    class _Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url, **kwargs):
            requested.append(url)
            assert url == f"{base}/rest/v1/content_media"
            return _Response(200, [row])

        async def post(self, url, **kwargs):
            requested.append(url)
            return _Response(200, {"signedURL": "/object/sign/content-media/signed-object?token=short-lived"})

    async def _schema_ready():
        return None

    monkeypatch.setattr(media_api, "_require_cloudinary_media_schema", _schema_ready)
    monkeypatch.setattr(media_api, "_config", lambda: (base, "server-only-key"))
    monkeypatch.setattr(media_api.httpx, "AsyncClient", _Client)

    result = await media_api.get_media(media_id, {"id": owner_id})

    signed_url = f"{base}/storage/v1/object/sign/content-media/signed-object?token=short-lived"
    assert result["delivery"]["url"] == signed_url
    assert result["delivery"]["derivatives"] == [{
        "kind": "thumbnail",
        "mime_type": "image/webp",
        "size_bytes": 456,
        "width": 320,
        "height": 320,
        "duration": None,
        "format": None,
        "delivery_url": signed_url,
    }]
    assert any("original%20photo.jpg" in url for url in requested)

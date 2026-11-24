from __future__ import annotations

import pytest

from allpha_api import content_media_worker, content_transcode_worker


def _set_scanner_pins(monkeypatch):
    monkeypatch.setenv("ALLPHA_DOCUMENT_SCANNER_ID", "clamav-local")
    monkeypatch.setenv("ALLPHA_DOCUMENT_SCANNER_ENGINE_VERSION", "1.2.0")
    monkeypatch.setenv("ALLPHA_DOCUMENT_SCANNER_SIGNATURE_VERSION", "12345/Nov 24 2026")


def test_content_image_worker_is_disabled_by_default(monkeypatch):
    monkeypatch.delenv("ALLPHA_CONTENT_MEDIA_WORKER_ENABLED", raising=False)
    assert content_media_worker.enabled() is False


def test_content_image_worker_requires_scanner_and_storage_config(monkeypatch):
    monkeypatch.setenv("ALLPHA_CONTENT_MEDIA_WORKER_ENABLED", "true")
    monkeypatch.setenv("ALLPHA_CLAMAV_ENABLED", "true")
    _set_scanner_pins(monkeypatch)
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    monkeypatch.delenv("SUPABASE_SECRET_KEY", raising=False)
    monkeypatch.delenv("CLAMAV_HOST", raising=False)
    with pytest.raises(SystemExit, match="configuration missing"):
        content_media_worker.enabled()


def test_content_image_worker_enables_only_with_complete_config(monkeypatch):
    monkeypatch.setenv("ALLPHA_CONTENT_MEDIA_WORKER_ENABLED", "true")
    monkeypatch.setenv("ALLPHA_CLAMAV_ENABLED", "true")
    _set_scanner_pins(monkeypatch)
    monkeypatch.setenv("SUPABASE_URL", "https://project.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "server-only")
    monkeypatch.setenv("CLAMAV_HOST", "clamav.internal")
    assert content_media_worker.enabled() is True


def test_content_transcode_worker_is_disabled_by_default(monkeypatch):
    monkeypatch.delenv("ALLPHA_CONTENT_TRANSCODE_WORKER_ENABLED", raising=False)
    assert content_transcode_worker.enabled() is False


def test_content_transcode_worker_requires_cloudinary_and_scanner_config(monkeypatch):
    monkeypatch.setenv("ALLPHA_CONTENT_TRANSCODE_WORKER_ENABLED", "true")
    monkeypatch.setenv("ALLPHA_CLAMAV_ENABLED", "true")
    _set_scanner_pins(monkeypatch)
    for name in (
        "SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_SECRET_KEY",
        "CLAMAV_HOST", "CLOUDINARY_CLOUD_NAME", "CLOUDINARY_API_KEY",
        "CLOUDINARY_API_SECRET", "ALLPHA_CLOUDINARY_CALLBACK_URL",
    ):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(SystemExit, match="configuration missing"):
        content_transcode_worker.enabled()


def test_content_transcode_worker_requires_https_callback(monkeypatch):
    monkeypatch.setenv("ALLPHA_CONTENT_TRANSCODE_WORKER_ENABLED", "true")
    monkeypatch.setenv("ALLPHA_CLAMAV_ENABLED", "true")
    _set_scanner_pins(monkeypatch)
    monkeypatch.setenv("SUPABASE_URL", "https://project.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "server-only")
    monkeypatch.setenv("CLAMAV_HOST", "clamav.internal")
    monkeypatch.setenv("CLOUDINARY_CLOUD_NAME", "cloud")
    monkeypatch.setenv("CLOUDINARY_API_KEY", "key")
    monkeypatch.setenv("CLOUDINARY_API_SECRET", "secret")
    monkeypatch.setenv("ALLPHA_CLOUDINARY_CALLBACK_URL", "http://api.internal/callback")
    with pytest.raises(SystemExit, match="must use HTTPS"):
        content_transcode_worker.enabled()


def test_content_transcode_worker_enables_with_complete_config(monkeypatch):
    monkeypatch.setenv("ALLPHA_CONTENT_TRANSCODE_WORKER_ENABLED", "true")
    monkeypatch.setenv("ALLPHA_CLAMAV_ENABLED", "true")
    monkeypatch.setenv("SUPABASE_URL", "https://project.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "server-only")
    monkeypatch.setenv("CLAMAV_HOST", "clamav.internal")
    monkeypatch.setenv("CLOUDINARY_CLOUD_NAME", "cloud")
    monkeypatch.setenv("CLOUDINARY_API_KEY", "key")
    monkeypatch.setenv("CLOUDINARY_API_SECRET", "secret")
    monkeypatch.setenv("ALLPHA_CLOUDINARY_CALLBACK_URL", "https://api.example/callback")
    assert content_transcode_worker.enabled() is True

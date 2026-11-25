from __future__ import annotations

import ast
from pathlib import Path

import pytest

from allpha_api import (content_media_worker, content_transcode_worker, content_provider_callback_worker, content_provider_cleanup_worker, content_scheduler_worker, content_retention_worker)


def _set_scanner_pins(monkeypatch):
    monkeypatch.setenv("ALLPHA_DOCUMENT_SCANNER_MODE", "clamd")
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
    _set_scanner_pins(monkeypatch)
    monkeypatch.setenv("SUPABASE_URL", "https://project.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "server-only")
    monkeypatch.setenv("CLAMAV_HOST", "clamav.internal")
    monkeypatch.setenv("CLOUDINARY_CLOUD_NAME", "cloud")
    monkeypatch.setenv("CLOUDINARY_API_KEY", "key")
    monkeypatch.setenv("CLOUDINARY_API_SECRET", "secret")
    monkeypatch.setenv("ALLPHA_CLOUDINARY_CALLBACK_URL", "https://api.example/callback")
    assert content_transcode_worker.enabled() is True


def test_webvtt_subtitle_validation_accepts_valid_cues_and_returns_digest():
    from allpha_api.content_media_worker import validate_subtitle_bytes
    data = b"WEBVTT\n\n00:00:00.000 --> 00:00:02.000\nHello\n"
    receipt = validate_subtitle_bytes(data, "text/vtt")
    assert receipt["format"] == "webvtt"
    assert receipt["cue_count"] == 1
    assert len(receipt["sha256"]) == 64


def test_subrip_subtitle_validation_accepts_valid_cues():
    from allpha_api.content_media_worker import validate_subtitle_bytes
    data = b"1\n00:00:00,000 --> 00:00:02,000\nHello\n"
    receipt = validate_subtitle_bytes(data, "application/x-subrip")
    assert receipt["format"] == "subrip"
    assert receipt["cue_count"] == 1


@pytest.mark.parametrize("data,media_type,error", [
    (b"not a subtitle", "text/vtt", "WEBVTT_HEADER_INVALID"),
    (b"WEBVTT\n\n00:00:02.000 --> 00:00:01.000\nBad\n", "text/vtt", "SUBTITLE_TIMING_ORDER_INVALID"),
    (b"1\n00:00:00,000 --> 00:00:02,000\n<script>alert(1)</script>", "application/x-subrip", "SUBTITLE_ACTIVE_CONTENT_REJECTED"),
    (b"\xff", "text/vtt", "SUBTITLE_UTF8_INVALID"),
])
def test_subtitle_validation_rejects_malformed_or_active_content(data, media_type, error):
    from allpha_api.content_media_worker import validate_subtitle_bytes
    with pytest.raises(ValueError, match=error):
        validate_subtitle_bytes(data, media_type)


def test_content_media_workers_disable_ambient_proxy_and_redirects():
    package_dir = Path(__file__).parents[1] / "src" / "allpha_api"
    worker_files = (
        "content_media_worker.py",
        "content_transcode_worker.py",
        "content_provider_callback_worker.py",
        "content_provider_cleanup_worker.py",
        "content_retention_worker.py",
        "content_scheduler_worker.py",
    )
    for filename in worker_files:
        tree = ast.parse((package_dir / filename).read_text(encoding="utf-8"))
        clients = [
            node for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "AsyncClient"
        ]
        assert clients, f"{filename} must declare its HTTP clients"
        for client in clients:
            options = {keyword.arg: keyword.value for keyword in client.keywords}
            assert "trust_env" in options, f"{filename} must disable ambient proxy discovery"
            assert isinstance(options["trust_env"], ast.Constant) and options["trust_env"].value is False
            assert "follow_redirects" in options, f"{filename} must disable authenticated redirects"
            assert isinstance(options["follow_redirects"], ast.Constant) and options["follow_redirects"].value is False


def test_content_auxiliary_workers_are_disabled_by_default(monkeypatch):
    for name in (
        "ALLPHA_CONTENT_PROVIDER_CALLBACK_WORKER_ENABLED",
        "ALLPHA_CONTENT_PROVIDER_CLEANUP_WORKER_ENABLED",
        "ALLPHA_CONTENT_SCHEDULER_WORKER_ENABLED",
        "ALLPHA_CONTENT_RETENTION_WORKER_ENABLED",
    ):
        monkeypatch.delenv(name, raising=False)
    assert content_provider_callback_worker.enabled() is False
    assert content_provider_cleanup_worker.enabled() is False
    assert content_scheduler_worker.enabled() is False
    assert content_retention_worker.enabled() is False


def test_provider_derivative_contract_requires_playback_renditions_and_poster():
    from allpha_api.content_provider_callback_worker import validate_eager_derivative_contract

    validate_eager_derivative_contract("video/mp4", [
        {"transformation": "c_limit,w_1280,vc_h264,f_mp4", "format": "mp4", "status": "success"},
        {"transformation": "c_limit,w_640,vc_h264,f_mp4", "format": "mp4", "status": "success"},
        {"transformation": "so_0,w_640,h_360,c_fill,f_jpg", "format": "jpg", "status": "success"},
    ])
    validate_eager_derivative_contract("audio/mpeg", [
        {"transformation": "ac_mp3,br_128k,f_mp3", "format": "mp3", "status": "success"},
        {"transformation": "ac_aac,br_128k,f_m4a", "format": "m4a", "status": "success"},
    ])
    with pytest.raises(ValueError, match="PROVIDER_VIDEO_RENDITION_CONTRACT_INVALID"):
        validate_eager_derivative_contract("video/mp4", [
            {"transformation": "c_limit,w_1280,vc_h264,f_mp4", "format": "mp4", "status": "success"},
            {"transformation": "c_limit,w_640,vc_h264,f_mp4", "format": "mp4", "status": "success"},
            {"transformation": "so_0,w_640,h_360,c_fill,f_jpg", "format": "mp4", "status": "success"},
        ])
    with pytest.raises(ValueError, match="PROVIDER_EAGER_DERIVATIVES_INCOMPLETE"):
        validate_eager_derivative_contract("audio/mpeg", [
            {"transformation": "ac_mp3,br_128k,f_mp3", "format": "mp3", "status": "success"},
            {"transformation": "ac_aac,br_128k,f_m4a", "format": "m4a", "status": "failed"},
        ])


def test_provider_derivative_download_is_stream_bounded():
    source = (Path(__file__).parents[1] / "src" / "allpha_api" / "content_provider_callback_worker.py").read_text(encoding="utf-8")
    # Cloudinary derivatives stay provider-hosted; only the private original is
    # streamed for malware scanning, with a strict 50 MiB bound.
    assert "MAX_PROVIDER_MEDIA_BYTES = 50 * 1024 * 1024" in source
    assert "async for chunk in response.aiter_bytes()" in source
    assert "PROVIDER_ORIGINAL_TOO_LARGE" in source
    assert "PROVIDER_DERIVATIVE_TOO_LARGE" not in source


def test_content_worker_callback_url_and_cloud_name_are_canonical(monkeypatch):
    monkeypatch.setenv("ALLPHA_CONTENT_TRANSCODE_WORKER_ENABLED", "true")
    monkeypatch.setenv("ALLPHA_CLAMAV_ENABLED", "true")
    _set_scanner_pins(monkeypatch)
    monkeypatch.setenv("SUPABASE_URL", "https://project.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "server-only")
    monkeypatch.setenv("CLAMAV_HOST", "clamav.internal")
    monkeypatch.setenv("CLOUDINARY_CLOUD_NAME", "oiqyjqeg")
    monkeypatch.setenv("CLOUDINARY_API_KEY", "key")
    monkeypatch.setenv("CLOUDINARY_API_SECRET", "secret")
    monkeypatch.setenv("ALLPHA_CLOUDINARY_CALLBACK_URL", "https://api.allpha.web.id/v1/content/internal/providers/cloudinary/eager-callback")
    assert content_transcode_worker.enabled() is True


def _set_remote_scanner(monkeypatch):
    monkeypatch.setenv("ALLPHA_DOCUMENT_SCANNER_MODE", "remote")
    monkeypatch.setenv("ALLPHA_DOCUMENT_SCANNER_URL", "https://scanner.example.com/v1/scan")
    monkeypatch.setenv("ALLPHA_DOCUMENT_SCANNER_API_KEY", "test-only-secret")
    monkeypatch.setenv("ALLPHA_DOCUMENT_SCANNER_ALLOWED_HOSTS", "scanner.example.com")
    monkeypatch.setenv("ALLPHA_DOCUMENT_SCANNER_ID", "scanner-prod")
    monkeypatch.setenv("ALLPHA_DOCUMENT_SCANNER_ENGINE_VERSION", "engine-1")
    monkeypatch.setenv("ALLPHA_DOCUMENT_SCANNER_SIGNATURE_VERSION", "sig-1")


def test_media_workers_accept_shared_remote_scanner_without_local_clamav(monkeypatch):
    _set_remote_scanner(monkeypatch)
    monkeypatch.setenv("SUPABASE_URL", "https://project.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "server-only")
    monkeypatch.setenv("CLOUDINARY_CLOUD_NAME", "cloud")
    monkeypatch.setenv("CLOUDINARY_API_KEY", "key")
    monkeypatch.setenv("CLOUDINARY_API_SECRET", "secret")
    monkeypatch.setenv("ALLPHA_CLOUDINARY_CALLBACK_URL", "https://api.example.com/v1/content/internal/providers/cloudinary/eager-callback")
    monkeypatch.delenv("CLAMAV_HOST", raising=False)
    monkeypatch.delenv("ALLPHA_CLAMAV_ENABLED", raising=False)
    monkeypatch.setenv("ALLPHA_CONTENT_MEDIA_WORKER_ENABLED", "true")
    monkeypatch.setenv("ALLPHA_CONTENT_TRANSCODE_WORKER_ENABLED", "true")
    monkeypatch.setenv("ALLPHA_CONTENT_PROVIDER_CALLBACK_WORKER_ENABLED", "true")
    assert content_media_worker.enabled() is True
    assert content_transcode_worker.enabled() is True
    assert content_provider_callback_worker.enabled() is True


@pytest.mark.parametrize(("index", "mime", "expected"), [
    (0, "video/mp4", ("rendition_1", "mp4")),
    (1, "audio/mpeg", ("rendition_2", "mp3")),
    (0, "audio/mp4", ("rendition_1", "m4a")),
    (2, "image/jpeg", ("moderation_poster", "jpg")),
])
def test_provider_derivative_identity_is_resolved_before_scan(index, mime, expected):
    from allpha_api.content_provider_callback_worker import provider_derivative_identity

    assert provider_derivative_identity(index, mime) == expected


def test_provider_derivative_identity_rejects_unsupported_mime_and_index():
    from allpha_api.content_provider_callback_worker import provider_derivative_identity

    with pytest.raises(ValueError, match="PROVIDER_DERIVATIVE_MIME_INVALID"):
        provider_derivative_identity(0, "application/octet-stream")
    with pytest.raises(ValueError, match="PROVIDER_DERIVATIVE_INDEX_INVALID"):
        provider_derivative_identity(-1, "video/mp4")


@pytest.mark.parametrize(("index", "expected"), [(0, ("display", "jpg")), (1, ("thumbnail", "jpg"))])
def test_image_provider_derivative_identity(index, expected):
    from allpha_api.content_provider_callback_worker import provider_derivative_identity

    assert provider_derivative_identity(index, "image/jpeg", "image/jpeg") == expected


def test_image_eager_contract_requires_two_jpeg_derivatives():
    from allpha_api.content_provider_callback_worker import validate_eager_derivative_contract

    validate_eager_derivative_contract("image/jpeg", [
        {"transformation": "c_limit,w_1600,f_jpg,q_auto", "format": "jpg", "status": "success"},
        {"transformation": "c_fill,w_320,h_320,g_auto,f_jpg,q_auto", "format": "jpg", "status": "success"},
    ])
    with pytest.raises(ValueError, match="PROVIDER_IMAGE_RENDITION_CONTRACT_INVALID"):
        validate_eager_derivative_contract("image/jpeg", [{"transformation": "c_limit,w_1600,f_jpg,q_auto", "format": "jpg", "status": "success"}])


@pytest.mark.parametrize(("resource_type", "path"), [
    ("image", "/image/destroy"),
    ("video", "/video/destroy"),
    ("raw", "/raw/destroy"),
])
def test_cloudinary_cleanup_uses_asset_resource_type(resource_type, path):
    from allpha_api.content_provider_cleanup_worker import cloudinary_destroy_endpoint

    assert cloudinary_destroy_endpoint("allpha-test", resource_type).endswith(path)


def test_cloudinary_cleanup_rejects_untrusted_resource_and_cloud():
    from allpha_api.content_provider_cleanup_worker import cloudinary_destroy_endpoint

    with pytest.raises(ValueError, match="RESOURCE_TYPE"):
        cloudinary_destroy_endpoint("allpha-test", "unknown")
    with pytest.raises(ValueError, match="CLOUD_INVALID"):
        cloudinary_destroy_endpoint("bad/cloud", "image")

from __future__ import annotations

import asyncio
import base64
import hashlib
from urllib.parse import parse_qs, urlsplit

import pytest

from allpha_api.cloudinary_provider import (
    CloudinaryConfig,
    CloudinaryConfigurationError,
    CloudinaryProviderError,
    build_signed_private_download_url,
    build_signed_authenticated_delivery_url,
    fetch_cloudinary_resource,
    build_signed_upload_intent,
    resource_type_for_media_type,
    sign_api_params,
    verify_cloudinary_webhook,
)


def _config():
    return CloudinaryConfig(
        cloud_name="allpha-test",
        api_key="api-key",
        api_secret="api-secret",
        callback_url="https://api.example.test/v1/content/internal/providers/cloudinary/eager-callback",
    )


def test_cloudinary_signature_is_sorted_and_excludes_transport_fields():
    params = {"timestamp": 123, "public_id": "allpha/123", "api_key": "public", "file": "binary"}
    expected = hashlib.sha1(b"public_id=allpha/123&timestamp=123api-secret").hexdigest()
    assert sign_api_params(params, "api-secret") == expected
    assert sign_api_params(dict(reversed(list(params.items()))), "api-secret") == expected


@pytest.mark.parametrize(("media_type", "resource"), [
    ("image/jpeg", "image"),
    ("video/mp4", "video"),
    ("audio/mpeg", "video"),
    ("text/vtt", "raw"),
])
def test_cloudinary_resource_type_is_canonical(media_type, resource):
    assert resource_type_for_media_type(media_type) == resource


def test_cloudinary_signed_upload_intent_is_authenticated_and_short_lived():
    intent = build_signed_upload_intent(
        config=_config(), media_id="12345678-1234-4234-9234-123456789abc",
        media_type="image/jpeg", now=1_800_000_000, ttl_seconds=300,
    )
    assert intent["resource_type"] == "image"
    assert intent["delivery_type"] == "authenticated"
    assert intent["public_id"] == "allpha/12345678-1234-4234-9234-123456789abc"
    assert intent["expires_at"] == 1_800_000_300
    params = intent["params"]
    assert params["type"] == "authenticated"
    assert params["eager_async"] == "true"
    assert params["eager_notification_url"] == _config().callback_url
    assert params["api_key"] == "api-key"
    assert params["signature"] == sign_api_params(
        {k: v for k, v in params.items() if k not in {"api_key", "signature"}},
        "api-secret",
    )
    assert "api_secret" not in params


def test_cloudinary_raw_upload_does_not_request_nonexistent_eager_callback():
    intent = build_signed_upload_intent(
        config=_config(), media_id="12345678-1234-4234-9234-123456789abc",
        media_type="text/vtt", now=1_800_000_000,
    )
    assert intent["resource_type"] == "raw"
    assert "eager" not in intent["params"]
    assert "eager_notification_url" not in intent["params"]


def test_cloudinary_private_download_url_has_expiry_and_authenticated_type():
    url = build_signed_private_download_url(
        config=_config(), public_id="allpha/12345678-1234-4234-9234-123456789abc",
        resource_type="video", format="mp4", expires_in=300, now=1_800_000_000,
    )
    parsed = urlsplit(url)
    params = {k: v[0] for k, v in parse_qs(parsed.query).items()}
    assert parsed.hostname == "api.cloudinary.com"
    assert params["type"] == "authenticated"
    assert params["expires_at"] == "1800000300"
    assert params["api_key"] == "api-key"
    assert params["signature"] == sign_api_params(
        {k: v for k, v in params.items() if k not in {"api_key", "signature"}},
        "api-secret",
    )



def test_cloudinary_authenticated_derivative_delivery_signs_exact_path():
    public_id = "allpha/12345678-1234-4234-9234-123456789abc"
    transformation = "c_fill,w_320,h_320,g_auto,f_jpg,q_auto"
    version = 1_800_000_000
    signed_path = f"{transformation}/v{version}/{public_id}.jpg"
    digest = hashlib.sha1((signed_path + "api-secret").encode("utf-8")).digest()
    signature = base64.urlsafe_b64encode(digest).decode("ascii")[:8]
    url = build_signed_authenticated_delivery_url(
        config=_config(), public_id=public_id, resource_type="image",
        format="jpg", transformation=transformation, version=version,
    )
    assert url == (
        "https://res.cloudinary.com/allpha-test/image/authenticated/"
        f"s--{signature}--/{signed_path}"
    )


def test_cloudinary_authenticated_derivative_rejects_untrusted_transform():
    with pytest.raises(ValueError, match="TRANSFORMATION"):
        build_signed_authenticated_delivery_url(
            config=_config(), public_id="allpha/asset", resource_type="image",
            format="jpg", transformation="https://attacker.example/x",
        )


def test_cloudinary_webhook_requires_fresh_timestamp_and_exact_raw_body():
    body = b'{"notification_type":"eager","public_id":"allpha/asset"}'
    timestamp = "1800000000"
    secret = "webhook-secret"
    signature = hashlib.sha256(body + timestamp.encode() + secret.encode()).hexdigest()
    assert verify_cloudinary_webhook(
        raw_body=body, timestamp=timestamp, signature=signature, secret=secret,
        now=1_800_000_001,
    ) == "valid"
    assert verify_cloudinary_webhook(
        raw_body=body + b" ", timestamp=timestamp, signature=signature, secret=secret,
        now=1_800_000_001,
    ) == "invalid"
    assert verify_cloudinary_webhook(
        raw_body=body, timestamp=timestamp, signature=signature, secret=secret,
        now=1_800_008_000,
    ) == "expired"


def test_cloudinary_upload_intent_rejects_bad_ttl_and_public_id():
    with pytest.raises(ValueError, match="TTL"):
        build_signed_upload_intent(
            config=_config(), media_id="12345678-1234-4234-9234-123456789abc",
            media_type="image/jpeg", ttl_seconds=10,
        )
    with pytest.raises(ValueError, match="MEDIA_ID"):
        build_signed_upload_intent(
            config=_config(), media_id="../../bad",
            media_type="image/jpeg",
        )


def test_cloudinary_delivery_rejects_untrusted_public_id_and_resource_type():
    with pytest.raises(ValueError, match="IDENTITY"):
        build_signed_private_download_url(
            config=_config(), public_id="other/asset", resource_type="image",
            format="jpg",
        )
    with pytest.raises(ValueError, match="IDENTITY"):
        build_signed_private_download_url(
            config=_config(), public_id="allpha/asset", resource_type="other",
            format="jpg",
        )


def test_cloudinary_config_fails_closed_when_credentials_are_missing(monkeypatch):
    for name in ("CLOUDINARY_CLOUD_NAME", "CLOUDINARY_API_KEY", "CLOUDINARY_API_SECRET"):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(CloudinaryConfigurationError):
        CloudinaryConfig.from_environment()


def test_cloudinary_upload_intent_binds_media_context():
    intent = build_signed_upload_intent(
        config=_config(),
        media_id="12345678-1234-4234-9234-123456789abc",
        media_type="image/jpeg",
        now=1_800_000_000,
        context={"allpha_media_id": "12345678-1234-4234-9234-123456789abc"},
    )
    params = intent["params"]
    assert params["context"] == "allpha_media_id=12345678-1234-4234-9234-123456789abc"
    assert params["signature"] == sign_api_params(
        {k: v for k, v in params.items() if k not in {"api_key", "signature"}},
        "api-secret",
    )


def test_fetch_cloudinary_resource_verifies_authenticated_identity():
    import httpx

    requested = {}

    def handler(request):
        requested["url"] = str(request.url)
        requested["authorization"] = request.headers.get("authorization")
        return httpx.Response(200, json={
            "asset_id": "asset-123",
            "public_id": "allpha/12345678-1234-4234-9234-123456789abc",
            "resource_type": "image",
            "type": "authenticated",
            "version": 4,
            "format": "jpg",
            "bytes": 1024,
            "width": 32,
            "height": 32,
        })

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await fetch_cloudinary_resource(
                config=_config(),
                public_id="allpha/12345678-1234-4234-9234-123456789abc",
                resource_type="image",
                client=client,
            )

    asset = asyncio.run(run())
    assert asset["asset_id"] == "asset-123"
    assert "/resources/image/authenticated/allpha/" in requested["url"]
    assert requested["authorization"] is not None


def test_fetch_cloudinary_resource_rejects_non_authenticated_asset():
    import httpx

    def handler(request):
        return httpx.Response(200, json={
            "asset_id": "asset-123",
            "public_id": "allpha/12345678-1234-4234-9234-123456789abc",
            "resource_type": "image",
            "type": "upload",
            "version": 4,
            "format": "jpg",
            "bytes": 1024,
        })

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            with pytest.raises(CloudinaryProviderError, match="CLOUDINARY_ASSET_NOT_AUTHENTICATED"):
                await fetch_cloudinary_resource(
                    config=_config(),
                    public_id="allpha/12345678-1234-4234-9234-123456789abc",
                    resource_type="image",
                    client=client,
                )

    asyncio.run(run())

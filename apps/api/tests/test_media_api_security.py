import uuid

from fastapi import HTTPException

from allpha_api.media_api import UploadIntent, _validate_upload_resource_contract, media_item_response
from allpha_api.admin_media_api import _operator_media_projection


def _upload_intent(domain: str, purpose: str, *, content_id=None, resource_id=None) -> UploadIntent:
    return UploadIntent(
        domain=domain,
        purpose=purpose,
        content_id=content_id,
        resource_id=resource_id,
        filename="photo.jpg",
        media_type="image/jpeg",
        size_bytes=123,
        sha256="a" * 64,
    )


def test_upload_resource_contract_validates_content_and_domain_resource_shapes():
    _validate_upload_resource_contract(
        _upload_intent("content", "attachment", content_id=uuid.uuid4())
    )
    for domain, purpose in (
        ("profile", "avatar"), ("feed", "post_attachment"), ("reels", "reel"),
        ("stories", "story"), ("cinema", "cinema_poster"), ("cinema", "cinema_asset"),
        ("agent", "agent_artifact"), ("messaging", "chat_attachment"),
        ("community", "community_attachment"),
    ):
        _validate_upload_resource_contract(_upload_intent(domain, purpose, resource_id=uuid.uuid4()))


def test_upload_resource_contract_rejects_mixed_or_missing_resource_references():
    invalid = (
        _upload_intent("content", "attachment", resource_id=uuid.uuid4()),
        _upload_intent("feed", "post_attachment", content_id=uuid.uuid4()),
        _upload_intent("profile", "avatar"),
    )
    for payload in invalid:
        try:
            _validate_upload_resource_contract(payload)
        except HTTPException as exc:
            assert exc.status_code == 422
            assert exc.detail["code"] == "MEDIA_RESOURCE_REQUIRED"
        else:
            raise AssertionError("invalid resource binding unexpectedly accepted")


def test_media_domain_resource_authorization_matches_canonical_owner_adapters(monkeypatch):
    owner = str(uuid.uuid4())
    resource = str(uuid.uuid4())
    calls = []

    async def fake_user_db_request(method, path, access_token, *, params=None, body=None, prefer=None):
        calls.append((method, path, access_token, params))
        if path == "community_posts":
            return [{"id": resource, "community_id": "community-1"}]
        return [{"id": resource}]

    monkeypatch.setattr("allpha_api.media_api.user_db_request", fake_user_db_request)
    import asyncio
    from allpha_api.media_api import _authorize_upload_resource

    domains = (
        ("content", "attachment", {"content_id": uuid.UUID(resource)}),
        ("feed", "post_attachment", {"resource_id": uuid.UUID(resource)}),
        ("reels", "reel", {"resource_id": uuid.UUID(resource)}),
        ("stories", "story", {"resource_id": uuid.UUID(resource)}),
        ("profile", "avatar", {"resource_id": uuid.UUID(owner)}),
        ("cinema", "cinema_poster", {"resource_id": uuid.UUID(resource)}),
        ("cinema", "cinema_asset", {"resource_id": uuid.UUID(resource)}),
        ("agent", "agent_artifact", {"resource_id": uuid.UUID(resource)}),
        ("messaging", "chat_attachment", {"resource_id": uuid.UUID(resource)}),
        ("community", "community_attachment", {"resource_id": uuid.UUID(resource)}),
    )
    for domain, purpose, refs in domains:
        asyncio.run(_authorize_upload_resource(
            _upload_intent(domain, purpose, **refs), owner, "verified-user-jwt"
        ))
    assert len(calls) >= len(domains)
    assert all(call[0] == "GET" and call[2] == "verified-user-jwt" for call in calls)


def test_media_domain_authorization_denies_unowned_resource(monkeypatch):
    async def deny(*args, **kwargs):
        return []
    monkeypatch.setattr("allpha_api.media_api.user_db_request", deny)
    import asyncio
    from allpha_api.media_api import _authorize_upload_resource
    try:
        asyncio.run(_authorize_upload_resource(
            _upload_intent("cinema", "cinema_poster", resource_id=uuid.uuid4()),
            str(uuid.uuid4()), "verified-user-jwt",
        ))
    except HTTPException as exc:
        assert exc.status_code == 404
        assert exc.detail["code"] == "MEDIA_RESOURCE_NOT_FOUND"
    else:
        raise AssertionError("unowned media resource unexpectedly authorized")


def test_unknown_media_domain_or_purpose_is_rejected_as_invalid_contract():
    try:
        _validate_upload_resource_contract(_upload_intent("unknown", "attachment", resource_id=uuid.uuid4()))
    except HTTPException as exc:
        assert exc.status_code == 422
        assert exc.detail["code"] == "MEDIA_DOMAIN_PURPOSE_INVALID"
    else:
        raise AssertionError("unknown media domain unexpectedly accepted")


def test_media_response_projection_never_exposes_provider_or_storage_internals():
    row = {
        "id": "media-id",
        "content_id": "content-id",
        "domain": "content",
        "purpose": "attachment",
        "filename": "photo.jpg",
        "media_type": "image/jpeg",
        "size_bytes": 123,
        "sha256": "a" * 64,
        "status": "processing",
        "scan_status": "pending",
        "storage_provider": "cloudinary",
        "owner_id": "owner-id",
        "bucket_id": "cloudinary",
        "storage_path": "allpha/media-id",
        "provider_public_id": "allpha/media-id",
        "provider_asset_id": "provider-asset-secret",
        "provider_batch_id": "provider-batch-secret",
        "provider_metadata": {"legacy_storage": {"bucket_id": "content-media", "storage_path": "private/path"}},
        "scan_receipt": {"scanner_id": "private-scanner"},
        "derivatives": [{"storage_path": "private/derivative.webp", "sha256": "b" * 64}],
        "provider_delete_state": "not_requested",
    }

    projected = media_item_response(row)

    assert projected["id"] == "media-id"
    assert projected["domain"] == "content"
    assert projected["provider_delete_state"] == "not_requested"
    for field in (
        "owner_id", "bucket_id", "storage_path", "provider_public_id", "provider_asset_id",
        "provider_batch_id", "provider_metadata", "scan_receipt", "derivatives",
    ):
        assert field not in projected


def test_super_admin_media_projection_redacts_content_hash_and_provider_storage_details():
    row = {
        "id": "media-id", "content_id": "content-id", "domain": "content",
        "purpose": "attachment", "filename": "photo.jpg", "media_type": "image/jpeg",
        "size_bytes": 123, "sha256": "a" * 64, "status": "ready",
        "scan_status": "clean", "storage_provider": "cloudinary",
        "provider_public_id": "allpha/media-id", "provider_asset_id": "asset-secret",
        "provider_metadata": {"legacy_storage": {"bucket_id": "content-media", "storage_path": "private/path"}},
        "storage_path": "allpha/media-id", "bucket_id": "cloudinary",
    }
    projected = _operator_media_projection(row)
    assert projected["id"] == "media-id"
    assert projected["status"] == "ready"
    for field in ("sha256", "provider_public_id", "provider_asset_id", "provider_metadata", "storage_path", "bucket_id"):
        assert field not in projected

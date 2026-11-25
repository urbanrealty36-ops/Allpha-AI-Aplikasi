from allpha_api.media_api import media_item_response


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

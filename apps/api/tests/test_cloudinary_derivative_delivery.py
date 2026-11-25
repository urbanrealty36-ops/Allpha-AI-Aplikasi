from __future__ import annotations

import pytest

from allpha_api.cloudinary_provider import eager_transformations
from allpha_api.content_provider_callback_worker import (
    build_cloudinary_derivative_metadata,
    validate_eager_derivative_contract,
)

CLOUD = "allpha-test"
PUBLIC_ID = "allpha/12345678-1234-4234-9234-123456789abc"
VERSION = 123


def image_eager():
    transformations = eager_transformations("image/jpeg").split("|")
    return [
        {
            "status": "success",
            "secure_url": f"https://res.cloudinary.com/{CLOUD}/image/authenticated/s--signed--/{transform}/v{VERSION}/{PUBLIC_ID}.jpg",
            "transformation": transform,
            "format": "jpg",
            "bytes": 12000 if index == 0 else 2400,
            "width": 1600 if index == 0 else 320,
            "height": 900 if index == 0 else 320,
        }
        for index, transform in enumerate(transformations)
    ]


def test_eager_callback_persists_cloudinary_transform_metadata_only():
    records = build_cloudinary_derivative_metadata(
        "image/jpeg", image_eager(), cloud_name=CLOUD, resource_type="image",
        public_id=PUBLIC_ID, version=VERSION,
    )
    assert [record["kind"] for record in records] == ["display", "thumbnail"]
    assert all(record["provider"] == "cloudinary" for record in records)
    assert all(record["delivery_type"] == "authenticated" for record in records)
    assert all(record["version"] == VERSION for record in records)
    assert all("transformation" in record for record in records)
    assert all("storage_path" not in record and "sha256" not in record for record in records)




def build_eager(media_type: str, formats: list[str], resource_type: str):
    transformations = eager_transformations(media_type).split("|")
    return [
        {
            "status": "success",
            "secure_url": f"https://res.cloudinary.com/{CLOUD}/{resource_type}/authenticated/s--signed--/{transform}/v{VERSION}/{PUBLIC_ID}.{suffix}",
            "transformation": transform,
            "format": suffix,
            "bytes": 12000 + index,
            "width": 1280 if suffix in {"mp4", "jpg"} else 0,
            "height": 720 if suffix in {"mp4", "jpg"} else 0,
            "duration": 8.5 if suffix in {"mp4", "mp3", "m4a"} else None,
        }
        for index, (transform, suffix) in enumerate(zip(transformations, formats))
    ]


def test_video_derivatives_are_cloudinary_authenticated_renditions_and_poster():
    records = build_cloudinary_derivative_metadata(
        "video/mp4", build_eager("video/mp4", ["mp4", "mp4", "jpg"], "video"),
        cloud_name=CLOUD, resource_type="video", public_id=PUBLIC_ID, version=VERSION,
    )
    assert [record["kind"] for record in records] == ["rendition_1", "rendition_2", "moderation_poster"]
    assert all(record["provider"] == "cloudinary" for record in records)


def test_audio_derivatives_are_cloudinary_authenticated_renditions():
    records = build_cloudinary_derivative_metadata(
        "audio/mpeg", build_eager("audio/mpeg", ["mp3", "m4a"], "video"),
        cloud_name=CLOUD, resource_type="video", public_id=PUBLIC_ID, version=VERSION,
    )
    assert [record["kind"] for record in records] == ["rendition_1", "rendition_2"]
    assert [record["mime_type"] for record in records] == ["audio/mpeg", "audio/mp4"]

def test_cloudinary_success_callback_may_omit_status_field():
    eager = image_eager()
    for item in eager:
        item.pop("status", None)
    records = build_cloudinary_derivative_metadata(
        "image/jpeg", eager, cloud_name=CLOUD, resource_type="image",
        public_id=PUBLIC_ID, version=VERSION,
    )
    assert len(records) == 2


def test_eager_callback_rejects_non_success_transformations():
    eager = image_eager()
    eager[1]["status"] = "pending"
    with pytest.raises(ValueError, match="INCOMPLETE"):
        validate_eager_derivative_contract("image/jpeg", eager)


@pytest.mark.parametrize("mutation", ["host", "path", "transform", "missing_bytes"])
def test_eager_callback_rejects_untrusted_derivative_metadata(mutation):
    eager = image_eager()
    if mutation == "host":
        eager[0]["secure_url"] = eager[0]["secure_url"].replace("res.cloudinary.com", "attacker.example")
    elif mutation == "path":
        eager[0]["secure_url"] = eager[0]["secure_url"].replace("/authenticated/", "/upload/")
    elif mutation == "transform":
        eager[0]["transformation"] = "c_scale,w_1"
    else:
        eager[0]["bytes"] = 0
    with pytest.raises(ValueError):
        build_cloudinary_derivative_metadata(
            "image/jpeg", eager, cloud_name=CLOUD, resource_type="image",
            public_id=PUBLIC_ID, version=VERSION,
        )

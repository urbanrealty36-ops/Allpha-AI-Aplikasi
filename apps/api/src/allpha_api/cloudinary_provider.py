"""Canonical Cloudinary signing, upload intent and private delivery primitives.

Cloudinary is treated as an authenticated binary provider. API credentials
remain server-side. Upload signatures and webhook verification are shared by
FastAPI and workers so no domain reimplements provider cryptography.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import re
import time
from dataclasses import dataclass
from urllib.parse import quote, urlencode


_CLOUD_NAME = re.compile(r"^[a-z0-9][a-z0-9_-]{1,63}$")
_ALLOWED_RESOURCE_TYPES = {"image", "video", "raw"}


class CloudinaryConfigurationError(RuntimeError):
    pass


@dataclass(frozen=True)
class CloudinaryConfig:
    cloud_name: str
    api_key: str
    api_secret: str
    callback_url: str | None = None
    webhook_secret: str | None = None

    @classmethod
    def from_environment(cls, *, require_callback: bool = False) -> "CloudinaryConfig":
        cloud_name = os.getenv("CLOUDINARY_CLOUD_NAME", "").strip()
        api_key = os.getenv("CLOUDINARY_API_KEY", "").strip()
        api_secret = os.getenv("CLOUDINARY_API_SECRET", "").strip()
        callback_url = os.getenv("ALLPHA_CLOUDINARY_CALLBACK_URL", "").strip() or None
        webhook_secret = os.getenv("CLOUDINARY_WEBHOOK_API_SECRET", "").strip() or None
        if not cloud_name or not _CLOUD_NAME.fullmatch(cloud_name) or not api_key or not api_secret:
            raise CloudinaryConfigurationError("CLOUDINARY_CREDENTIALS_NOT_CONFIGURED")
        if require_callback and (not callback_url or not callback_url.startswith("https://")):
            raise CloudinaryConfigurationError("CLOUDINARY_HTTPS_CALLBACK_NOT_CONFIGURED")
        return cls(
            cloud_name=cloud_name,
            api_key=api_key,
            api_secret=api_secret,
            callback_url=callback_url,
            webhook_secret=webhook_secret,
        )


def resource_type_for_media_type(media_type: str) -> str:
    normalized = (media_type or "").lower().split(";", 1)[0].strip()
    if normalized.startswith("image/"):
        return "image"
    if normalized.startswith(("video/", "audio/")):
        return "video"
    if normalized in {"text/vtt", "application/x-subrip"}:
        return "raw"
    raise ValueError("CLOUDINARY_MEDIA_TYPE_UNSUPPORTED")


def _signature_value(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (list, tuple)):
        return ",".join(str(item) for item in value)
    return str(value)


def sign_api_params(params: dict[str, object], api_secret: str) -> str:
    """Cloudinary API signature: sorted non-empty parameters + API secret."""
    if not api_secret:
        raise CloudinaryConfigurationError("CLOUDINARY_API_SECRET_NOT_CONFIGURED")
    values = {
        key: _signature_value(value)
        for key, value in params.items()
        if key not in {"file", "api_key", "signature"} and value is not None and value != ""
    }
    canonical = "&".join(f"{key}={values[key]}" for key in sorted(values))
    return hashlib.sha1((canonical + api_secret).encode("utf-8")).hexdigest()


def eager_transformations(media_type: str) -> str | None:
    resource = resource_type_for_media_type(media_type)
    if resource == "image":
        return "c_limit,w_1600,f_jpg,q_auto|c_fill,w_320,h_320,g_auto,f_jpg,q_auto"
    if resource == "video":
        if media_type.startswith("video/"):
            return "c_limit,w_1280,vc_h264,f_mp4|c_limit,w_640,vc_h264,f_mp4|so_0,w_640,h_360,c_fill,f_jpg"
        return "ac_mp3,br_128k,f_mp3|ac_aac,br_128k,f_m4a"
    return None


def build_signed_upload_intent(
    *,
    config: CloudinaryConfig,
    media_id: str,
    media_type: str,
    callback_url: str | None = None,
    now: int | None = None,
    ttl_seconds: int = 600,
) -> dict[str, object]:
    """Create a scoped signed multipart upload target; never returns API secret."""
    if not re.fullmatch(r"[0-9a-fA-F-]{36}", media_id):
        raise ValueError("CLOUDINARY_MEDIA_ID_INVALID")
    if not 60 <= ttl_seconds <= 900:
        raise ValueError("CLOUDINARY_UPLOAD_TTL_INVALID")
    resource = resource_type_for_media_type(media_type)
    timestamp = int(now if now is not None else time.time())
    public_id = f"allpha/{media_id}"
    params: dict[str, object] = {
        "timestamp": timestamp,
        "public_id": public_id,
        "type": "authenticated",
        "overwrite": "false",
        "unique_filename": "false",
        "use_filename": "false",
    }
    eager = eager_transformations(media_type)
    target_callback = callback_url or config.callback_url
    if eager:
        if not target_callback or not target_callback.startswith("https://"):
            raise CloudinaryConfigurationError("CLOUDINARY_HTTPS_CALLBACK_NOT_CONFIGURED")
        params["eager"] = eager
        params["eager_async"] = "true"
        params["eager_notification_url"] = target_callback
    signature = sign_api_params(params, config.api_secret)
    return {
        "upload_url": f"https://api.cloudinary.com/v1_1/{config.cloud_name}/{resource}/upload",
        "resource_type": resource,
        "delivery_type": "authenticated",
        "public_id": public_id,
        "expires_at": timestamp + ttl_seconds,
        "params": {**params, "api_key": config.api_key, "signature": signature},
    }


def build_signed_private_download_url(
    *,
    config: CloudinaryConfig,
    public_id: str,
    resource_type: str,
    format: str,
    expires_in: int = 300,
    now: int | None = None,
) -> str:
    """Generate a time-limited authenticated download URL supported on Free plans."""
    if resource_type not in _ALLOWED_RESOURCE_TYPES or not public_id.startswith("allpha/"):
        raise ValueError("CLOUDINARY_ASSET_IDENTITY_INVALID")
    if not re.fullmatch(r"[A-Za-z0-9]{1,16}", format):
        raise ValueError("CLOUDINARY_FORMAT_INVALID")
    if not 60 <= expires_in <= 900:
        raise ValueError("CLOUDINARY_DELIVERY_TTL_INVALID")
    timestamp = int(now if now is not None else time.time())
    params: dict[str, object] = {
        "timestamp": timestamp,
        "public_id": public_id,
        "format": format,
        "expires_at": timestamp + expires_in,
        "type": "authenticated",
    }
    signature = sign_api_params(params, config.api_secret)
    query_params = {key: value for key, value in params.items() if value is not None}
    query = urlencode({**query_params, "api_key": config.api_key, "signature": signature})
    return (
        f"https://api.cloudinary.com/v1_1/{config.cloud_name}/"
        f"{resource_type}/download?{query}"
    )



def build_signed_authenticated_delivery_url(
    *,
    config: CloudinaryConfig,
    public_id: str,
    resource_type: str,
    format: str,
    transformation: str,
    version: int | None = None,
) -> str:
    """Build a signed CDN URL for a pre-generated authenticated Cloudinary derivative.

    The signature covers the exact transformation, optional version, public ID
    and output extension. Never accept arbitrary caller-provided transformations.
    """
    if resource_type not in _ALLOWED_RESOURCE_TYPES or not re.fullmatch(
        r"allpha/[A-Za-z0-9_./-]{1,180}", public_id
    ) or ".." in public_id or "//" in public_id:
        raise ValueError("CLOUDINARY_ASSET_IDENTITY_INVALID")
    if not re.fullmatch(r"[A-Za-z0-9]{1,16}", format):
        raise ValueError("CLOUDINARY_FORMAT_INVALID")
    if not isinstance(transformation, str) or not re.fullmatch(
        r"[A-Za-z0-9_,./:=\-]{1,512}", transformation
    ) or ".." in transformation or "//" in transformation:
        raise ValueError("CLOUDINARY_TRANSFORMATION_INVALID")
    if version is not None and (isinstance(version, bool) or int(version) <= 0):
        raise ValueError("CLOUDINARY_VERSION_INVALID")

    components = [transformation]
    if version is not None:
        components.append(f"v{int(version)}")
    components.append(f"{public_id}.{format.lower()}")
    signed_path = "/".join(components)
    digest = hashlib.sha1((signed_path + config.api_secret).encode("utf-8")).digest()
    signature = __import__("base64").urlsafe_b64encode(digest).decode("ascii")[:8]
    path = "/".join((
        config.cloud_name,
        resource_type,
        "authenticated",
        f"s--{signature}--",
        signed_path,
    ))
    return f"https://res.cloudinary.com/{path}"

def verify_cloudinary_webhook(
    *,
    raw_body: bytes,
    timestamp: str,
    signature: str,
    secret: str,
    now: int | None = None,
    max_age_seconds: int = 7200,
) -> str:
    """Verify exact raw payload HMAC and freshness; return valid/expired/invalid."""
    if not secret or not signature:
        return "invalid"
    try:
        issued_at = int(timestamp)
    except (TypeError, ValueError):
        return "invalid"
    current = int(now if now is not None else time.time())
    if abs(current - issued_at) > max_age_seconds:
        return "expired"
    signed = raw_body + timestamp.encode("ascii") + secret.encode("utf-8")
    supplied = signature.lower()
    if any(
        hmac.compare_digest(hashlib.new(algorithm, signed).hexdigest(), supplied)
        for algorithm in ("sha1", "sha256")
    ):
        return "valid"
    return "invalid"

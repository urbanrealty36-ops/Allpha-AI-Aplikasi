"""Canonical authenticated content creation and private media pipeline (ENG-P13)."""
from __future__ import annotations

import os
import re
import uuid
from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from typing import Any
from urllib.parse import quote

import httpx
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from pydantic import BaseModel, ConfigDict, Field

from allpha_api.auth import current_user, user_db_request
from allpha_api.operator_security import require_operator_scope, write_operator_audit

router = APIRouter(prefix="/v1/content", tags=["content"])
TEXT_LIMIT = 10_000
IMAGE_LIMIT = 10 * 1024 * 1024
VIDEO_LIMIT = 50 * 1024 * 1024
AUDIO_LIMIT = 50 * 1024 * 1024
ALLOWED_MEDIA = {
    "image/jpeg": (".jpg", IMAGE_LIMIT),
    "image/png": (".png", IMAGE_LIMIT),
    "image/webp": (".webp", IMAGE_LIMIT),
    "video/mp4": (".mp4", VIDEO_LIMIT),
    "video/webm": (".webm", VIDEO_LIMIT),
    "audio/mpeg": (".mp3", AUDIO_LIMIT),
    "audio/mp4": (".m4a", AUDIO_LIMIT),
    "audio/aac": (".aac", AUDIO_LIMIT),
    "audio/ogg": (".ogg", AUDIO_LIMIT),
    "audio/wav": (".wav", AUDIO_LIMIT),
    "audio/webm": (".weba", AUDIO_LIMIT),
}
CONTENT_FIELDS = "id,owner_id,ai_agent_id,content_type,body,visibility,status,moderation_status,version,created_at,updated_at,published_at,deleted_at,purge_started_at"
MEDIA_FIELDS = "id,content_id,owner_id,bucket_id,storage_path,filename,media_type,size_bytes,sha256,status,scan_status,processed_at,derivatives,created_at"


class ContentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    body: str = Field(default="", max_length=TEXT_LIMIT)
    visibility: str = Field(default="public", pattern="^(public|followers|private)$")
    content_type: str = Field(default="text", pattern="^(text|image|video|audio|story)$")
    ai_agent_id: uuid.UUID | None = None


class ContentUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    body: str = Field(default="", max_length=TEXT_LIMIT)
    visibility: str = Field(default="public", pattern="^(public|followers|private)$")
    expected_version: int = Field(ge=1)


class ContentReview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: str = Field(pattern="^(approve|reject)$")
    expected_version: int = Field(ge=1)
    reason: str = Field(min_length=8, max_length=500)


class ContentScheduleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    publish_at: datetime
    creator_timezone: str = Field(min_length=1, max_length=80)
    expected_version: int = Field(ge=1)
    rights_confirmed: bool
    disclosure_confirmed: bool = True


class ContentAppealCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=8, max_length=2000)
    expected_version: int = Field(ge=1)


class ContentAppealReview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: str = Field(pattern="^(approve|reject)$")
    reason: str = Field(min_length=8, max_length=500)


def _config() -> tuple[str, str]:
    base = os.getenv("SUPABASE_URL", "").rstrip("/")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "") or os.getenv("SUPABASE_SECRET_KEY", "")
    if not base or not key:
        raise HTTPException(503, detail={"code": "CONTENT_PIPELINE_NOT_CONFIGURED", "message": "Layanan konten belum dikonfigurasi di server."})
    return base, key


async def _server_db(method: str, table: str, *, params: dict[str, str] | None = None, body: Any = None, prefer: str | None = None) -> Any:
    base, key = _config()
    headers = {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    if prefer:
        headers["Prefer"] = prefer
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(12, connect=3)) as client:
            response = await client.request(method, f"{base}/rest/v1/{table}", headers=headers, params=params, json=body)
    except httpx.HTTPError as exc:
        raise HTTPException(503, detail={"code": "CONTENT_DATABASE_UNAVAILABLE", "message": "Data konten sementara tidak tersedia."}) from exc
    if response.status_code >= 300:
        if response.status_code == 409:
            raise HTTPException(409, detail={"code": "CONTENT_CONFLICT", "message": "Konten berubah; muat ulang sebelum mencoba lagi."})
        raise HTTPException(503, detail={"code": "CONTENT_DATABASE_WRITE_FAILED", "message": "Perubahan konten tidak dapat disimpan."})
    if not response.content:
        return None
    return response.json()


async def _validate_agent_attribution(agent_id: uuid.UUID | None, owner_user_id: str) -> None:
    if agent_id is None:
        return
    agents = await _server_db("GET", "ai_agents", params={
        "select": "id,status", "id": f"eq.{agent_id}", "status": "eq.active", "limit": "1",
    })
    if not agents:
        raise HTTPException(404, detail={"code": "CONTENT_AGENT_NOT_AVAILABLE", "message": "AI Agent tidak aktif atau tidak tersedia."})
    ownerships = await _server_db("GET", "agent_ownerships", params={
        "select": "agent_id,owner_user_id,ownership_role,status",
        "agent_id": f"eq.{agent_id}", "owner_user_id": f"eq.{owner_user_id}",
        "ownership_role": "eq.owner", "status": "eq.active", "limit": "1",
    })
    if not ownerships:
        raise HTTPException(403, detail={"code": "CONTENT_AGENT_OWNERSHIP_REQUIRED", "message": "Hanya pemilik aktif Agent yang dapat mengatribusikan Agent pada konten."})


async def _owner_content(content_id: uuid.UUID, user_id: str) -> dict[str, Any]:
    rows = await _server_db("GET", "content_items", params={
        "select": CONTENT_FIELDS, "id": f"eq.{content_id}", "owner_id": f"eq.{user_id}", "limit": "1",
    })
    if not rows:
        raise HTTPException(404, detail={"code": "CONTENT_NOT_FOUND", "message": "Konten tidak ditemukan."})
    return rows[0]


async def _storage(method: str, path: str, *, data: bytes | None = None, media_type: str | None = None, upsert: bool = False) -> httpx.Response:
    base, key = _config()
    headers = {"apikey": key, "Authorization": f"Bearer {key}"}
    if media_type:
        headers["Content-Type"] = media_type
    if upsert:
        # Only used after the server has bound the idempotency key to the exact
        # owner/content/type/size/hash tuple in content_media.
        headers["x-upsert"] = "true"
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(60, connect=5)) as client:
            response = await client.request(method, f"{base}/storage/v1/object/{quote(path, safe='/')}", headers=headers, content=data)
    except httpx.HTTPError as exc:
        raise HTTPException(503, detail={"code": "CONTENT_STORAGE_UNAVAILABLE", "message": "Penyimpanan media sementara tidak tersedia."}) from exc
    if response.status_code >= 400:
        raise HTTPException(503, detail={"code": "CONTENT_STORAGE_FAILED", "message": "Unggah media gagal; silakan coba lagi."})
    return response


@router.get("/mine")
async def list_my_content(request: Request, user: dict[str, Any] = Depends(current_user), limit: int = 30, include_deleted: bool = False) -> dict[str, Any]:
    if limit < 1 or limit > 100:
        raise HTTPException(422, detail={"code": "CONTENT_LIMIT_INVALID", "message": "Batas daftar harus 1–100."})
    content_params = {"select": CONTENT_FIELDS, "owner_id": f"eq.{user['id']}", "order": "updated_at.desc", "limit": str(limit)}
    if not include_deleted:
        content_params["status"] = "neq.deleted"
    rows = await _server_db("GET", "content_items", params=content_params)
    media = await _server_db("GET", "content_media", params={
        "select": MEDIA_FIELDS, "owner_id": f"eq.{user['id']}", "order": "created_at.asc", "limit": str(limit * 5),
    })
    by_content: dict[str, list[dict[str, Any]]] = {}
    for item in media or []:
        by_content.setdefault(str(item["content_id"]), []).append(item)
    return {"items": [{**row, "media": by_content.get(str(row["id"]), [])} for row in (rows or [])]}


@router.post("", status_code=201)
async def create_content(payload: ContentCreate, request: Request, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    if not payload.body.strip() and payload.content_type == "text":
        raise HTTPException(422, detail={"code": "CONTENT_BODY_REQUIRED", "message": "Tulis isi konten terlebih dahulu."})
    await _validate_agent_attribution(payload.ai_agent_id, str(user["id"]))
    row = {
        "owner_id": user["id"], "ai_agent_id": str(payload.ai_agent_id) if payload.ai_agent_id else None,
        "content_type": payload.content_type, "body": payload.body.strip(),
        "visibility": payload.visibility, "status": "draft", "moderation_status": "not_submitted", "version": 1,
    }
    created = await _server_db("POST", "content_items", body=row, prefer="return=representation")
    return {"item": created[0]}


@router.patch("/{content_id}")
async def update_content(content_id: uuid.UUID, payload: ContentUpdate, request: Request, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    existing = await _owner_content(content_id, str(user["id"]))
    if existing["status"] not in ("draft", "failed"):
        raise HTTPException(409, detail={"code": "CONTENT_NOT_EDITABLE", "message": "Konten hanya dapat diedit saat draft atau gagal."})
    if int(existing.get("version") or 0) != payload.expected_version:
        raise HTTPException(409, detail={"code": "CONTENT_VERSION_CHANGED", "message": "Draft telah berubah. Muat ulang sebelum menyimpan perubahan."})
    rows = await _server_db("PATCH", "content_items", params={
        "id": f"eq.{content_id}", "owner_id": f"eq.{user['id']}",
        # Compare-and-set both lifecycle state and version to prevent lost edits.
        "status": "in.(draft,failed)", "version": f"eq.{payload.expected_version}", "select": CONTENT_FIELDS,
    }, body={
        "body": payload.body.strip(), "visibility": payload.visibility, "version": payload.expected_version + 1,
        "status": "draft", "moderation_status": "not_submitted", "error_code": None,
    }, prefer="return=representation")
    if not rows:
        raise HTTPException(409, detail={"code": "CONTENT_UPDATE_CONFLICT", "message": "Konten berubah atau sudah tidak dapat diedit."})
    return {"item": rows[0]}

@router.get("/{content_id}/versions")
async def list_content_versions(content_id: uuid.UUID, request: Request, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    # Resolve ownership first; version snapshots are private creator data.
    await _owner_content(content_id, str(user["id"]))
    rows = await _server_db("GET", "content_item_versions", params={
        "select": "id,content_id,owner_id,version,snapshot,created_at",
        "content_id": f"eq.{content_id}", "owner_id": f"eq.{user['id']}",
        "order": "version.desc", "limit": "50",
    })
    return {"items": rows or [], "limit": 50}


@router.post("/{content_id}/media", status_code=201)
async def upload_media(content_id: uuid.UUID, request: Request, file: UploadFile = File(...), user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    content = await _owner_content(content_id, str(user["id"]))
    if content["status"] not in ("draft", "failed"):
        raise HTTPException(409, detail={"code": "CONTENT_NOT_EDITABLE", "message": "Media hanya dapat ditambahkan ke draft."})
    media_type = (file.content_type or "").lower().split(";")[0].strip()
    spec = ALLOWED_MEDIA.get(media_type)
    if not spec:
        raise HTTPException(415, detail={"code": "MEDIA_TYPE_UNSUPPORTED", "message": "Format media yang didukung: JPG, PNG, WebP, MP4, WebM, MP3, M4A, AAC, OGG, WAV, dan audio WebM."})
    raw_idempotency_key = request.headers.get("Idempotency-Key")
    try:
        media_id = str(uuid.UUID(raw_idempotency_key)) if raw_idempotency_key else str(uuid.uuid4())
    except (ValueError, AttributeError) as exc:
        raise HTTPException(400, detail={"code": "MEDIA_IDEMPOTENCY_KEY_INVALID", "message": "Idempotency-Key harus berupa UUID yang valid."}) from exc
    data = await file.read(spec[1] + 1)
    if not data:
        raise HTTPException(422, detail={"code": "MEDIA_EMPTY", "message": "File media kosong."})
    if len(data) > spec[1]:
        raise HTTPException(413, detail={"code": "MEDIA_TOO_LARGE", "message": "Ukuran media melampaui batas untuk format ini."})
    # Check file signatures, not just the client-supplied MIME.
    signatures = {
        "image/jpeg": lambda b: b.startswith(bytes.fromhex("ffd8ff")),
        "image/png": lambda b: b.startswith(bytes.fromhex("89504e470d0a1a0a")),
        "image/webp": lambda b: len(b) >= 12 and b[:4] == b"RIFF" and b[8:12] == b"WEBP",
        "video/mp4": lambda b: len(b) >= 12 and b[4:8] == b"ftyp",
        "video/webm": lambda b: b.startswith(bytes.fromhex("1a45dfa3")),
        "audio/mpeg": lambda b: b.startswith(b"ID3") or (len(b) >= 2 and b[0] == 0xFF and (b[1] & 0xE0) == 0xE0),
        "audio/mp4": lambda b: len(b) >= 12 and b[4:8] == b"ftyp",
        "audio/aac": lambda b: len(b) >= 2 and b[0] == 0xFF and (b[1] & 0xF6) == 0xF0,
        "audio/ogg": lambda b: b.startswith(b"OggS"),
        "audio/wav": lambda b: len(b) >= 12 and b[:4] == b"RIFF" and b[8:12] == b"WAVE",
        "audio/webm": lambda b: b.startswith(bytes.fromhex("1a45dfa3")),
    }
    if not signatures[media_type](data):
        raise HTTPException(422, detail={"code": "MEDIA_SIGNATURE_INVALID", "message": "Isi file tidak sesuai dengan format media yang dipilih."})
    safe_name = re.sub(r"[^a-zA-Z0-9._-]+", "-", (file.filename or "media").split("/")[-1].split("\\")[-1])[:100].strip(".-") or "media"
    import hashlib
    digest = hashlib.sha256(data).hexdigest()
    storage_path = f"{user['id']}/{content_id}/{media_id}-{safe_name}"
    existing = await _server_db("GET", "content_media", params={
        "select": MEDIA_FIELDS, "id": f"eq.{media_id}",
        "owner_id": f"eq.{user['id']}", "limit": "1",
    })
    prior = existing[0] if existing else None
    if prior:
        if str(prior.get("content_id")) != str(content_id) or prior.get("sha256") != digest or prior.get("media_type") != media_type or int(prior.get("size_bytes") or 0) != len(data):
            raise HTTPException(409, detail={"code": "MEDIA_IDEMPOTENCY_KEY_REUSED", "message": "Idempotency-Key sudah digunakan untuk file media yang berbeda."})
        storage_path = str(prior["storage_path"])
        if prior.get("status") in ("uploaded", "processing", "ready"):
            return {"item": prior, "content": content, "idempotent_replay": True}
        # An interrupted upload can safely resume because the same key is
        # already bound to the same immutable file fingerprint.
    else:
        try:
            reserved = await _server_db("POST", "content_media", body={
                "id": media_id, "content_id": str(content_id), "owner_id": user["id"], "bucket_id": "content-media",
                "storage_path": storage_path, "filename": safe_name, "media_type": media_type,
                "size_bytes": len(data), "sha256": digest, "status": "uploading",
            }, prefer="return=representation")
            prior = reserved[0]
        except HTTPException as exc:
            # A concurrent request may have reserved this same idempotency key.
            # Re-read and verify the full fingerprint before touching Storage.
            if exc.status_code != 409:
                raise
            raced = await _server_db("GET", "content_media", params={
                "select": MEDIA_FIELDS, "id": f"eq.{media_id}",
                "owner_id": f"eq.{user['id']}", "limit": "1",
            })
            if not raced:
                raise
            prior = raced[0]
            if str(prior.get("content_id")) != str(content_id) or prior.get("sha256") != digest or prior.get("media_type") != media_type or int(prior.get("size_bytes") or 0) != len(data):
                raise HTTPException(409, detail={"code": "MEDIA_IDEMPOTENCY_KEY_REUSED", "message": "Idempotency-Key sudah digunakan untuk file media yang berbeda."})
            storage_path = str(prior["storage_path"])
            if prior.get("status") in ("uploaded", "processing", "ready"):
                return {"item": prior, "content": content, "idempotent_replay": True}

    try:
        # Upsert is safe here: the idempotency row proves this exact key is
        # bound to the same content owner and SHA-256 fingerprint.
        await _storage("POST", f"content-media/{storage_path}", data=data, media_type=media_type, upsert=True)
    except HTTPException:
        try:
            await _server_db("PATCH", "content_media", params={
                "id": f"eq.{media_id}", "owner_id": f"eq.{user['id']}",
                "status": "in.(uploading,failed)",
            }, body={"status": "failed"})
        except HTTPException:
            pass
        raise

    rows = await _server_db("PATCH", "content_media", params={
        "id": f"eq.{media_id}", "owner_id": f"eq.{user['id']}",
        "status": "in.(uploading,failed)", "select": MEDIA_FIELDS,
    }, body={"status": "uploaded"}, prefer="return=representation")
    if not rows:
        latest = await _server_db("GET", "content_media", params={
            "select": MEDIA_FIELDS, "id": f"eq.{media_id}",
            "owner_id": f"eq.{user['id']}", "limit": "1",
        })
        if not latest or latest[0].get("status") not in ("uploaded", "processing", "ready"):
            raise HTTPException(409, detail={"code": "MEDIA_UPLOAD_STATE_CONFLICT", "message": "Status unggahan berubah; muat ulang sebelum mencoba lagi."})
        return {"item": latest[0], "content": content, "idempotent_replay": True}

    try:
        updated = await _server_db("PATCH", "content_items", params={
            "id": f"eq.{content_id}", "owner_id": f"eq.{user['id']}",
            "status": "in.(draft,failed)", "select": CONTENT_FIELDS,
        }, body={
            "status": "draft", "content_type": "story" if content.get("content_type") == "story" else "video" if media_type.startswith("video/") else "audio" if media_type.startswith("audio/") else "image",
            "version": int(content.get("version") or 1) + 1,
        }, prefer="return=representation")
        if not updated:
            raise HTTPException(409, detail={"code": "CONTENT_UPLOAD_CONFLICT", "message": "Draft berubah saat media diunggah; silakan muat ulang dan coba lagi."})
    except HTTPException:
        # Preserve a failed metadata row for safe same-key retry; do not leave
        # an untracked Storage object or silently delete owner media.
        try:
            await _server_db("PATCH", "content_media", params={
                "id": f"eq.{media_id}", "owner_id": f"eq.{user['id']}",
                "status": "eq.uploaded",
            }, body={"status": "failed"})
        except HTTPException:
            pass
        raise
    latest_media = await _server_db("GET", "content_media", params={
        "select": MEDIA_FIELDS, "id": f"eq.{media_id}", "owner_id": f"eq.{user['id']}", "limit": "1",
    })
    return {"item": latest_media[0] if latest_media else rows[0], "content": updated[0]}


async def _signed_media_preview_url(storage_path: str, *, expires_in: int = 300) -> str:
    """Issue a short-lived URL for a private object; never make the bucket public."""
    base, key = _config()
    object_path = quote(f"content-media/{storage_path}", safe="/")
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(8, connect=3)) as client:
            response = await client.post(
                f"{base}/storage/v1/object/sign/{object_path}",
                headers={"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={"expiresIn": expires_in},
            )
    except httpx.HTTPError as exc:
        raise HTTPException(503, detail={"code": "CONTENT_PREVIEW_UNAVAILABLE", "message": "Pratinjau media belum tersedia."}) from exc
    if response.status_code >= 400:
        raise HTTPException(503, detail={"code": "CONTENT_PREVIEW_UNAVAILABLE", "message": "Pratinjau media belum tersedia."})
    signed = response.json().get("signedURL") or response.json().get("signedUrl")
    if not isinstance(signed, str) or not signed:
        raise HTTPException(503, detail={"code": "CONTENT_PREVIEW_INVALID", "message": "Penyimpanan tidak mengembalikan URL pratinjau yang valid."})
    if signed.startswith(("https://", "http://")):
        return signed
    if signed.startswith("/storage/v1/"):
        return f"{base}{signed}"
    if signed.startswith("/"):
        return f"{base}/storage/v1{signed}"
    return f"{base}/storage/v1/{signed.lstrip('/')}"


async def _media_preview_projection(item: dict[str, Any]) -> dict[str, Any]:
    original_url = await _signed_media_preview_url(item["storage_path"])
    derivative_previews = []
    for derivative in item.get("derivatives") or []:
        path = derivative.get("storage_path")
        if not isinstance(path, str) or not path:
            continue
        derivative_previews.append({**derivative, "preview_url": await _signed_media_preview_url(path)})
    preferred = next((entry["preview_url"] for entry in derivative_previews
        if entry.get("kind") in ("display", "rendition_1")), original_url)
    moderation_preview = next((entry["preview_url"] for entry in derivative_previews
        if entry.get("kind") in ("moderation_poster", "thumbnail")), None)
    return {**item, "preview_url": preferred, "original_preview_url": original_url,
        "moderation_preview_url": moderation_preview, "derivative_previews": derivative_previews}


@router.get("/{content_id}/preview")
async def preview_content(content_id: uuid.UUID, request: Request, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    content = await _owner_content(content_id, str(user["id"]))
    if content["status"] == "deleted":
        raise HTTPException(404, detail={"code": "CONTENT_NOT_FOUND", "message": "Konten tidak ditemukan."})
    media = await _server_db("GET", "content_media", params={
        "select": MEDIA_FIELDS, "content_id": f"eq.{content_id}", "owner_id": f"eq.{user['id']}", "order": "created_at.asc",
    })
    previews = []
    for item in media or []:
        previews.append(await _media_preview_projection(item))
    return {"item": content, "media": previews, "preview_expires_in": 300}


@router.post("/{content_id}/publish")
async def publish_content(content_id: uuid.UUID, request: Request, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    content = await _owner_content(content_id, str(user["id"]))
    media = await _server_db("GET", "content_media", params={
        "select": "id,status", "content_id": f"eq.{content_id}",
        "owner_id": f"eq.{user['id']}", "limit": "100",
    })
    if not content["body"].strip() and not media:
        raise HTTPException(422, detail={"code": "CONTENT_EMPTY", "message": "Tambahkan teks atau media sebelum mengirim konten."})
    if any(item.get("status") != "ready" for item in (media or [])):
        raise HTTPException(409, detail={
            "code": "CONTENT_MEDIA_NOT_READY",
            "message": "Media masih diproses atau belum lolos pemeriksaan keamanan. Konten belum dapat dikirim untuk moderasi.",
        })
    if content["status"] not in ("draft", "failed"):
        raise HTTPException(409, detail={"code": "CONTENT_ALREADY_SUBMITTED", "message": "Konten sudah dikirim atau tidak dapat dipublikasikan ulang."})
    rows = await _server_db("PATCH", "content_items", params={"id": f"eq.{content_id}", "owner_id": f"eq.{user['id']}", "status": "in.(draft,failed)", "select": CONTENT_FIELDS}, body={
        "status": "review", "moderation_status": "pending", "version": content["version"] + 1,
    }, prefer="return=representation")
    if not rows:
        raise HTTPException(409, detail={"code": "CONTENT_PUBLISH_CONFLICT", "message": "Status konten berubah; muat ulang sebelum mengirim lagi."})
    scheduled = await _server_db("GET", "content_schedules", params={
        "select": "id", "content_id": f"eq.{content_id}", "owner_id": f"eq.{user['id']}",
        "status": "eq.scheduled", "limit": "1",
    })
    if scheduled:
        await _server_db("PATCH", "content_schedules", params={"id": f"eq.{scheduled[0]['id']}", "status": "eq.scheduled"},
            body={"content_version": int(rows[0]["version"]), "updated_at": datetime.now(timezone.utc).isoformat()})
    return {"item": rows[0], "message": "Konten masuk antrean moderasi; belum ditampilkan ke publik."}


@router.post("/{content_id}/retry")
async def retry_content(content_id: uuid.UUID, request: Request, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    content = await _owner_content(content_id, str(user["id"]))
    if content["status"] != "failed":
        raise HTTPException(409, detail={"code": "CONTENT_NOT_RETRYABLE", "message": "Hanya konten berstatus gagal yang dapat dicoba ulang."})
    rows = await _server_db("PATCH", "content_items", params={"id": f"eq.{content_id}", "owner_id": f"eq.{user['id']}", "status": "eq.failed", "select": CONTENT_FIELDS}, body={
        "status": "draft", "moderation_status": "not_submitted",
    }, prefer="return=representation")
    return {"item": rows[0] if rows else content, "message": "Draft dipulihkan; periksa media lalu kirim ulang."}


@router.post("/{content_id}/archive")
async def archive_content(content_id: uuid.UUID, request: Request, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    """Remove content from public surfaces while retaining its private owner record."""
    content = await _owner_content(content_id, str(user["id"]))
    if content["status"] not in ("draft", "failed", "published"):
        raise HTTPException(409, detail={"code": "CONTENT_NOT_ARCHIVABLE", "message": "Konten yang sedang ditinjau atau sudah diarsipkan tidak dapat diarsipkan ulang."})
    rows = await _server_db("PATCH", "content_items", params={
        "id": f"eq.{content_id}", "owner_id": f"eq.{user['id']}",
        "status": f"eq.{content['status']}", "select": CONTENT_FIELDS,
    }, body={"status": "archived", "version": int(content["version"]) + 1}, prefer="return=representation")
    if not rows:
        raise HTTPException(409, detail={"code": "CONTENT_ARCHIVE_CONFLICT", "message": "Status konten berubah; muat ulang sebelum mengarsipkan."})
    return {"item": rows[0], "message": "Konten diarsipkan dan tidak lagi ditampilkan pada Feed publik. Media privat tetap tersimpan."}


@router.delete("/{content_id}")
async def delete_content(content_id: uuid.UUID, request: Request, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    """Soft-delete a draft/failed/archived item; private media retention is unchanged."""
    content = await _owner_content(content_id, str(user["id"]))
    if content["status"] not in ("draft", "failed", "archived"):
        raise HTTPException(409, detail={"code": "CONTENT_NOT_DELETABLE", "message": "Arsipkan konten terbit terlebih dahulu; konten yang sedang ditinjau tidak dapat dihapus."})
    rows = await _server_db("PATCH", "content_items", params={
        "id": f"eq.{content_id}", "owner_id": f"eq.{user['id']}",
        "status": f"eq.{content['status']}", "select": CONTENT_FIELDS,
    }, body={"status": "deleted", "moderation_status": "removed", "deleted_at": datetime.now(timezone.utc).isoformat(), "version": int(content["version"]) + 1}, prefer="return=representation")
    if not rows:
        raise HTTPException(409, detail={"code": "CONTENT_DELETE_CONFLICT", "message": "Status konten berubah; muat ulang sebelum menghapus."})
    return {"item": rows[0], "message": "Konten dihapus dari akun dan Feed. Salinan media privat tidak dihapus otomatis."}


@router.get("/feed/public")
async def public_content_feed(request: Request, limit: int = 20) -> dict[str, Any]:
    if limit < 1 or limit > 50:
        raise HTTPException(422, detail={"code": "CONTENT_LIMIT_INVALID", "message": "Batas feed harus 1–50."})
    rows = await _server_db("GET", "content_items", params={
        "select": CONTENT_FIELDS, "status": "eq.published", "moderation_status": "eq.approved",
        "visibility": "eq.public", "order": "published_at.desc", "limit": str(limit),
    })
    items = rows or []
    if not items:
        return {"items": [], "media_preview_expires_in": 300}
    content_ids = [str(item["id"]) for item in items]
    media = await _server_db("GET", "content_media", params={
        "select": MEDIA_FIELDS, "content_id": f"in.({','.join(content_ids)})",
        "status": "eq.ready", "order": "created_at.asc", "limit": str(min(250, limit * 5)),
    })
    media_by_content: dict[str, list[dict[str, Any]]] = {}
    for row in media or []:
        # The parent list above is already restricted to published, approved,
        # public items; only those IDs are eligible for signed media URLs.
        media_by_content.setdefault(str(row["content_id"]), []).append(await _media_preview_projection(row))
    return {
        "items": [{**item, "media": media_by_content.get(str(item["id"]), [])} for item in items],
        "media_preview_expires_in": 300,
    }


@router.get("/admin/review-queue", tags=["content-moderation"])
async def content_review_queue(
    request: Request,
    limit: int = 50,
    operator: dict[str, Any] = Depends(require_operator_scope("platform:content.moderate")),
) -> dict[str, Any]:
    if limit < 1 or limit > 100:
        raise HTTPException(422, detail={"code": "CONTENT_LIMIT_INVALID", "message": "Batas antrean harus 1–100."})
    rows = await _server_db("GET", "content_items", params={
        "select": CONTENT_FIELDS, "status": "eq.review", "moderation_status": "eq.pending",
        "order": "updated_at.asc", "limit": str(limit),
    })
    items = rows or []
    media_by_content: dict[str, list[dict[str, Any]]] = {}
    if items:
        content_ids = [str(item["id"]) for item in items]
        media_rows = await _server_db("GET", "content_media", params={
            "select": MEDIA_FIELDS, "content_id": f"in.({','.join(content_ids)})",
            "status": "eq.ready", "order": "created_at.asc", "limit": str(min(500, limit * 10)),
        })
        for media in media_rows or []:
            media_by_content.setdefault(str(media["content_id"]), []).append(await _media_preview_projection(media))
    await write_operator_audit(request, actor_user_id=str(operator["id"]), action="content.review_queue.read",
        outcome="allowed", resource_type="content_queue", resource_id="pending",
        metadata={"count": len(items), "media_count": sum(len(v) for v in media_by_content.values())})
    return {
        "items": [{**item, "media": media_by_content.get(str(item["id"]), [])} for item in items],
        "media_preview_expires_in": 300,
    }


@router.post("/admin/{content_id}/review", tags=["content-moderation"])
async def review_content(
    content_id: uuid.UUID,
    payload: ContentReview,
    request: Request,
    operator: dict[str, Any] = Depends(require_operator_scope("platform:content.moderate")),
) -> dict[str, Any]:
    current = await _server_db("GET", "content_items", params={
        "select": CONTENT_FIELDS, "id": f"eq.{content_id}", "status": "eq.review",
        "moderation_status": "eq.pending", "limit": "1",
    })
    if not current:
        raise HTTPException(404, detail={"code": "CONTENT_REVIEW_NOT_FOUND", "message": "Konten tidak ditemukan di antrean moderasi."})
    item = current[0]
    if int(item.get("version") or 0) != payload.expected_version:
        raise HTTPException(409, detail={"code": "CONTENT_VERSION_CHANGED", "message": "Versi konten berubah; muat ulang antrean sebelum meninjau."})
    allowed = payload.decision == "approve"
    schedule_rows = await _server_db("GET", "content_schedules", params={
        "select": "id,status", "content_id": f"eq.{content_id}",
        "owner_id": f"eq.{item['owner_id']}", "status": "in.(scheduled,processing)", "limit": "1",
    })
    scheduled = bool(schedule_rows) and allowed
    await write_operator_audit(request, actor_user_id=str(operator["id"]), action="content.moderate",
        outcome="attempted", resource_type="content_item", resource_id=str(content_id),
        metadata={"decision": payload.decision, "expected_version": payload.expected_version, "reason": payload.reason})
    now = datetime.now(timezone.utc).isoformat()
    changes = {
        "status": "scheduled" if scheduled else "published" if allowed else "failed",
        "moderation_status": "approved" if allowed else "rejected",
        "published_at": None if scheduled or not allowed else now,
        "error_code": None if allowed else "MODERATION_REJECTED",
        "version": payload.expected_version + 1,
    }
    rows = await _server_db("PATCH", "content_items", params={
        "id": f"eq.{content_id}", "status": "eq.review", "moderation_status": "eq.pending",
        "version": f"eq.{payload.expected_version}", "select": CONTENT_FIELDS,
    }, body=changes, prefer="return=representation")
    if not rows:
        raise HTTPException(409, detail={"code": "CONTENT_REVIEW_CONFLICT", "message": "Konten berubah saat moderasi; keputusan tidak diterapkan."})
    if scheduled:
        await _server_db("PATCH", "content_schedules", params={"id": f"eq.{schedule_rows[0]['id']}", "status": "in.(scheduled,processing)"},
            body={"content_version": int(rows[0]["version"]), "updated_at": datetime.now(timezone.utc).isoformat()})
    elif not allowed and schedule_rows:
        await _server_db("PATCH", "content_schedules", params={"id": f"eq.{schedule_rows[0]['id']}", "status": "in.(scheduled,processing)"},
            body={"status": "cancelled", "cancelled_at": now, "last_error_code": "MODERATION_REJECTED", "updated_at": now})
    await write_operator_audit(request, actor_user_id=str(operator["id"]), action="content.moderate",
        outcome="allowed", resource_type="content_item", resource_id=str(content_id),
        metadata={"decision": payload.decision, "version": payload.expected_version + 1, "reason": payload.reason})
    return {"item": rows[0]}


@router.post("/{content_id}/appeals", status_code=201, tags=["content-appeals"])
async def create_content_appeal(
    content_id: uuid.UUID,
    payload: ContentAppealCreate,
    request: Request,
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    content = await _owner_content(content_id, str(user["id"]))
    if content["status"] != "failed" or content["moderation_status"] != "rejected":
        raise HTTPException(409, detail={"code": "CONTENT_NOT_APPEALABLE", "message": "Banding hanya tersedia untuk konten yang ditolak oleh moderasi."})
    if int(content["version"]) != payload.expected_version:
        raise HTTPException(409, detail={"code": "CONTENT_VERSION_CHANGED", "message": "Versi konten berubah; muat ulang sebelum mengajukan banding."})
    try:
        rows = await _server_db("POST", "content_appeals", body={
            "content_id": str(content_id), "owner_id": user["id"],
            "submitted_version": payload.expected_version, "reason": payload.reason.strip(),
            "status": "pending",
        }, prefer="return=representation")
    except HTTPException as exc:
        if exc.status_code == 409:
            raise HTTPException(409, detail={"code": "CONTENT_APPEAL_ALREADY_PENDING", "message": "Banding untuk konten ini masih menunggu keputusan."}) from exc
        raise
    await write_operator_audit(request, actor_user_id=str(user["id"]), action="content.appeal.submit",
        outcome="allowed", resource_type="content_item", resource_id=str(content_id),
        metadata={"appeal_id": rows[0]["id"], "submitted_version": payload.expected_version})
    return {"item": rows[0], "message": "Banding diterima dan menunggu pemeriksaan manusia."}


@router.get("/{content_id}/appeals", tags=["content-appeals"])
async def list_my_content_appeals(
    content_id: uuid.UUID,
    request: Request,
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    await _owner_content(content_id, str(user["id"]))
    rows = await _server_db("GET", "content_appeals", params={
        "select": "id,content_id,owner_id,submitted_version,reason,status,decision_reason,decided_at,created_at,updated_at",
        "content_id": f"eq.{content_id}", "owner_id": f"eq.{user['id']}",
        "order": "created_at.desc", "limit": "20",
    })
    return {"items": rows or []}


@router.get("/admin/appeal-queue", tags=["content-appeals"])
async def content_appeal_queue(
    request: Request,
    limit: int = 50,
    operator: dict[str, Any] = Depends(require_operator_scope("platform:content.moderate")),
) -> dict[str, Any]:
    if limit < 1 or limit > 100:
        raise HTTPException(422, detail={"code": "CONTENT_LIMIT_INVALID", "message": "Batas antrean harus 1–100."})
    appeals = await _server_db("GET", "content_appeals", params={
        "select": "id,content_id,owner_id,submitted_version,reason,status,created_at",
        "status": "eq.pending", "order": "created_at.asc", "limit": str(limit),
    })
    items = appeals or []
    content_by_id: dict[str, dict[str, Any]] = {}
    if items:
        ids = [str(item["content_id"]) for item in items]
        contents = await _server_db("GET", "content_items", params={
            "select": CONTENT_FIELDS, "id": f"in.({','.join(ids)})", "status": "eq.failed",
            "moderation_status": "eq.rejected", "limit": str(limit),
        })
        content_by_id = {str(row["id"]): row for row in (contents or [])}
    await write_operator_audit(request, actor_user_id=str(operator["id"]), action="content.appeal_queue.read",
        outcome="allowed", resource_type="content_appeal_queue", resource_id="pending",
        metadata={"count": len(items)})
    return {"items": [{**item, "content": content_by_id.get(str(item["content_id"]))} for item in items]}


@router.post("/admin/appeals/{appeal_id}/review", tags=["content-appeals"])
async def review_content_appeal(
    appeal_id: uuid.UUID,
    payload: ContentAppealReview,
    request: Request,
    operator: dict[str, Any] = Depends(require_operator_scope("platform:content.moderate")),
) -> dict[str, Any]:
    # The RPC locks the appeal and content rows and commits both lifecycle
    # transitions in one PostgreSQL transaction (or changes neither).
    await write_operator_audit(request, actor_user_id=str(operator["id"]), action="content.appeal.review",
        outcome="attempted", resource_type="content_appeal", resource_id=str(appeal_id),
        metadata={"decision": payload.decision, "reason": payload.reason})
    result = await _server_db("POST", "rpc/decide_content_appeal", body={
        "p_appeal_id": str(appeal_id),
        "p_operator_id": str(operator["id"]),
        "p_decision": payload.decision,
        "p_reason": payload.reason.strip(),
    })
    outcome = result.get("outcome") if isinstance(result, dict) else None
    if outcome == "appeal_conflict":
        raise HTTPException(409, detail={"code": "CONTENT_APPEAL_CONFLICT", "message": "Banding tidak ditemukan atau sudah diputuskan."})
    if outcome == "content_conflict":
        raise HTTPException(409, detail={"code": "CONTENT_APPEAL_CONTENT_CHANGED", "message": "Konten berubah setelah banding diajukan; tidak ada perubahan yang diterapkan."})
    if outcome in ("invalid_decision", "invalid_reason") or outcome != "committed":
        raise HTTPException(422, detail={"code": "CONTENT_APPEAL_DECISION_INVALID", "message": "Keputusan banding tidak valid."})
    await write_operator_audit(request, actor_user_id=str(operator["id"]), action="content.appeal.review",
        outcome="allowed", resource_type="content_appeal", resource_id=str(appeal_id),
        metadata={"decision": payload.decision, "content_id": result["appeal"]["content_id"]})
    return {
        "item": result["appeal"], "content": result.get("content"),
        "message": "Banding diterima; konten dikembalikan ke antrean moderasi independen." if payload.decision == "approve" else "Banding ditolak.",
    }

@router.post("/internal/providers/cloudinary/eager-callback", include_in_schema=False)
async def cloudinary_eager_callback(request: Request) -> dict[str, Any]:
    """Verify and durably enqueue provider callback; never download large media in the webhook request."""
    import hashlib
    import hmac
    import json
    import time

    secret = os.getenv("CLOUDINARY_WEBHOOK_API_SECRET") or os.getenv("CLOUDINARY_API_SECRET", "")
    cloud_name = os.getenv("CLOUDINARY_CLOUD_NAME", "")
    signature = request.headers.get("X-Cld-Signature", "")
    timestamp = request.headers.get("X-Cld-Timestamp", "")
    raw = await request.body()
    if len(raw) > 1024 * 1024:
        raise HTTPException(413, detail={"code": "MEDIA_CALLBACK_TOO_LARGE", "message": "Payload callback terlalu besar."})
    if not secret or not cloud_name or not signature or not timestamp:
        raise HTTPException(503, detail={"code": "MEDIA_PROVIDER_NOT_CONFIGURED", "message": "Callback media provider belum dikonfigurasi."})
    try:
        issued_at = int(timestamp)
    except ValueError as exc:
        raise HTTPException(401, detail={"code": "MEDIA_CALLBACK_SIGNATURE_INVALID", "message": "Callback provider tidak valid."}) from exc
    if abs(int(time.time()) - issued_at) > 7200:
        raise HTTPException(401, detail={"code": "MEDIA_CALLBACK_EXPIRED", "message": "Callback provider sudah kedaluwarsa."})
    signed = raw + timestamp.encode("ascii") + secret.encode("utf-8")
    valid = any(hmac.compare_digest(hashlib.new(algorithm, signed).hexdigest(), signature.lower())
                for algorithm in ("sha1", "sha256"))
    if not valid:
        raise HTTPException(401, detail={"code": "MEDIA_CALLBACK_SIGNATURE_INVALID", "message": "Tanda tangan callback provider tidak cocok."})
    try:
        payload = json.loads(raw)
    except (ValueError, UnicodeDecodeError) as exc:
        raise HTTPException(400, detail={"code": "MEDIA_CALLBACK_PAYLOAD_INVALID", "message": "Payload callback tidak valid."}) from exc
    if not isinstance(payload, dict) or payload.get("notification_type") != "eager":
        raise HTTPException(422, detail={"code": "MEDIA_CALLBACK_TYPE_UNSUPPORTED", "message": "Jenis callback tidak didukung."})
    public_id = payload.get("public_id")
    eager = payload.get("eager")
    batch_id = payload.get("batch_id")
    if not isinstance(public_id, str) or not public_id.startswith("allpha/") or not isinstance(eager, list) or not eager or not isinstance(batch_id, str):
        raise HTTPException(422, detail={"code": "MEDIA_CALLBACK_ASSET_INVALID", "message": "Identitas asset, batch atau derivative tidak lengkap."})
    try:
        media_uuid = uuid.UUID(public_id.split("/", 1)[1])
    except (ValueError, IndexError) as exc:
        raise HTTPException(422, detail={"code": "MEDIA_CALLBACK_ASSET_INVALID", "message": "Identitas media tidak valid."}) from exc
    media_rows = await _server_db("GET", "content_media", params={
        "select": "id,media_type,status,provider_asset_id,provider_public_id,provider_batch_id",
        "id": f"eq.{media_uuid}", "status": "eq.processing", "provider_public_id": f"eq.{public_id}", "limit": "1",
    })
    if not media_rows:
        raise HTTPException(404, detail={"code": "MEDIA_CALLBACK_MEDIA_NOT_FOUND", "message": "Media tidak ditemukan atau callback sudah diproses."})
    media = media_rows[0]
    if payload.get("asset_id") != media.get("provider_asset_id") or batch_id != media.get("provider_batch_id"):
        raise HTTPException(409, detail={"code": "MEDIA_CALLBACK_ASSET_MISMATCH", "message": "Asset atau batch callback tidak cocok dengan job aktif."})
    jobs = await _server_db("GET", "content_lifecycle_jobs", params={
        "select": "id,media_id,status,payload", "media_id": f"eq.{media_uuid}",
        "job_type": "eq.media_transcode", "status": "eq.awaiting_provider", "limit": "1",
    })
    if not jobs:
        raise HTTPException(409, detail={"code": "MEDIA_CALLBACK_JOB_NOT_FOUND", "message": "Job transcoding tidak sedang menunggu callback."})
    job = jobs[0]
    if (job.get("payload") or {}).get("provider_asset_id") != media["provider_asset_id"] or (job.get("payload") or {}).get("provider_batch_id") != batch_id:
        raise HTTPException(409, detail={"code": "MEDIA_CALLBACK_BATCH_MISMATCH", "message": "Batch callback sudah usang atau tidak cocok."})
    expected = 3 if media["media_type"].startswith("video/") else 2
    if len(eager) < expected or any(not isinstance(item, dict) for item in eager):
        raise HTTPException(422, detail={"code": "MEDIA_CALLBACK_DERIVATIVES_INCOMPLETE", "message": "Provider belum menghasilkan seluruh derivative yang diwajibkan."})
    digest = hashlib.sha256(raw).hexdigest()
    event_id = str(payload.get("request_id") or batch_id)
    if any(item.get("status") == "failed" for item in eager):
        await _server_db("PATCH", "content_lifecycle_jobs", params={"id": f"eq.{job['id']}", "status": "eq.awaiting_provider"},
            body={"status": "failed", "last_error_code": "CLOUDINARY_EAGER_FAILED"})
        await _server_db("PATCH", "content_media", params={"id": f"eq.{media_uuid}", "status": "eq.processing"},
            body={"status": "failed", "scan_status": "unavailable"})
        return {"status": "failed", "event_id": event_id}
    result = await _server_db("POST", "rpc/enqueue_content_provider_callback", body={
        "p_provider_event_id": event_id, "p_media_id": str(media_uuid),
        "p_transcode_job_id": job["id"], "p_payload_sha256": digest, "p_payload": payload,
    })
    outcome = result.get("outcome") if isinstance(result, dict) else None
    if outcome in ("queued", "already_processed"):
        return {"status": "queued" if outcome == "queued" else "duplicate", "event_id": event_id}
    if outcome == "callback_replay_mismatch":
        raise HTTPException(409, detail={"code": "MEDIA_CALLBACK_REPLAY_MISMATCH", "message": "Event callback sudah pernah diterima dengan payload berbeda."})
    if outcome in ("media_not_processing", "transcode_job_not_waiting", "provider_identity_mismatch"):
        raise HTTPException(409, detail={"code": "MEDIA_CALLBACK_STATE_CONFLICT", "message": "Status media atau job provider sudah berubah."})
    raise HTTPException(503, detail={"code": "MEDIA_CALLBACK_ENQUEUE_FAILED", "message": "Callback terverifikasi tetapi belum dapat dimasukkan ke antrean."})


@router.post("/{content_id}/restore", tags=["content-retention"])
async def restore_content(content_id: uuid.UUID, request: Request, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    content = await _owner_content(content_id, str(user["id"]))
    if content["status"] != "deleted" or not content.get("deleted_at"):
        raise HTTPException(409, detail={"code": "CONTENT_NOT_RESTORABLE", "message": "Konten tidak berada dalam masa pemulihan."})
    deleted_at = datetime.fromisoformat(str(content["deleted_at"]).replace("Z", "+00:00"))
    if (datetime.now(timezone.utc) - deleted_at).total_seconds() > 30 * 86400:
        raise HTTPException(410, detail={"code": "CONTENT_RECOVERY_EXPIRED", "message": "Masa pemulihan 30 hari telah berakhir."})
    if content.get("purge_started_at"):
        raise HTTPException(409, detail={"code": "CONTENT_PURGE_STARTED", "message": "Penghapusan fisik sudah dimulai dan konten tidak dapat dipulihkan."})
    versions = await _server_db("GET", "content_item_versions", params={
        "select": "snapshot,version", "content_id": f"eq.{content_id}", "owner_id": f"eq.{user['id']}",
        "order": "version.desc", "limit": "1",
    })
    snapshot = versions[0]["snapshot"] if versions else {}
    restored_status = "archived" if snapshot.get("status") == "archived" else "draft"
    rows = await _server_db("PATCH", "content_items", params={
        "id": f"eq.{content_id}", "owner_id": f"eq.{user['id']}", "status": "eq.deleted",
        "version": f"eq.{content['version']}", "purge_started_at": "is.null", "select": CONTENT_FIELDS,
    }, body={
        "status": restored_status, "moderation_status": snapshot.get("moderation_status", "not_submitted"),
        "body": snapshot.get("body", content["body"]), "visibility": snapshot.get("visibility", content["visibility"]),
        "deleted_at": None, "version": int(content["version"]) + 1,
    }, prefer="return=representation")
    if not rows:
        raise HTTPException(409, detail={"code": "CONTENT_RESTORE_CONFLICT", "message": "Konten berubah atau penghapusan fisik sudah dimulai."})
    await _server_db("POST", "content_lifecycle_events", body={
        "event_key": f"content.restored:{content_id}:{rows[0]['version']}", "event_type": "content.restored",
        "content_id": str(content_id), "owner_id": str(user["id"]),
        "payload": {"restored_status": restored_status, "version": rows[0]["version"]},
    }, prefer="return=minimal")
    return {"item": rows[0], "message": "Konten berhasil dipulihkan."}


@router.post("/{content_id}/schedule", status_code=201, tags=["content-scheduling"])
async def schedule_content(
    content_id: uuid.UUID, payload: ContentScheduleRequest, request: Request,
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    key = request.headers.get("Idempotency-Key") or f"content-schedule:{content_id}:{payload.expected_version}:{payload.publish_at.isoformat()}"
    if len(key) > 200:
        raise HTTPException(400, detail={"code": "IDEMPOTENCY_KEY_INVALID", "message": "Idempotency-Key terlalu panjang."})
    existing_schedule = await _server_db("GET", "content_schedules", params={
        "select": "*", "idempotency_key": f"eq.{key}", "owner_id": f"eq.{user['id']}", "content_id": f"eq.{content_id}", "limit": "1",
    })
    if existing_schedule:
        current = await _owner_content(content_id, str(user["id"]))
        return {"item": existing_schedule[0], "content": current, "idempotent_replay": True}
    content = await _owner_content(content_id, str(user["id"]))
    if content["status"] not in ("draft", "failed") or int(content["version"]) != payload.expected_version:
        raise HTTPException(409, detail={"code": "CONTENT_SCHEDULE_CONFLICT", "message": "Hanya draft versi terbaru yang dapat dijadwalkan."})
    if not payload.rights_confirmed or not payload.disclosure_confirmed:
        raise HTTPException(422, detail={"code": "CONTENT_SCHEDULE_ATTESTATION_REQUIRED", "message": "Konfirmasi hak penggunaan dan disclosure wajib diberikan."})
    try:
        ZoneInfo(payload.creator_timezone)
    except ZoneInfoNotFoundError as exc:
        raise HTTPException(422, detail={"code": "CONTENT_TIMEZONE_INVALID", "message": "Gunakan IANA timezone yang valid."}) from exc
    if payload.publish_at.tzinfo is None or payload.publish_at.utcoffset() is None:
        raise HTTPException(422, detail={"code": "CONTENT_SCHEDULE_TIMEZONE_REQUIRED", "message": "Waktu publikasi harus memiliki timezone."})
    publish_at = payload.publish_at.astimezone(timezone.utc)
    if publish_at <= datetime.now(timezone.utc):
        raise HTTPException(422, detail={"code": "CONTENT_SCHEDULE_MUST_BE_FUTURE", "message": "Waktu publikasi harus berada di masa depan."})
    media = await _server_db("GET", "content_media", params={
        "select": "id,status", "content_id": f"eq.{content_id}", "owner_id": f"eq.{user['id']}", "limit": "100",
    })
    if any(row.get("status") not in ("ready", "processing", "uploaded") for row in media or []):
        raise HTTPException(409, detail={"code": "CONTENT_MEDIA_INVALID", "message": "Media gagal atau tidak valid; perbaiki sebelum menjadwalkan."})
    result = await _server_db("POST", "rpc/create_content_schedule", body={
        "p_content_id": str(content_id), "p_owner_id": str(user["id"]),
        "p_expected_version": payload.expected_version, "p_publish_at": publish_at.isoformat(),
        "p_creator_timezone": payload.creator_timezone, "p_idempotency_key": key,
        "p_rights_confirmed": payload.rights_confirmed, "p_disclosure_confirmed": payload.disclosure_confirmed,
    })
    outcome = result.get("outcome") if isinstance(result, dict) else None
    if outcome == "content_conflict":
        raise HTTPException(409, detail={"code": "CONTENT_SCHEDULE_CONFLICT", "message": "Konten berubah atau tidak dapat dijadwalkan."})
    if outcome == "schedule_exists":
        raise HTTPException(409, detail={"code": "CONTENT_SCHEDULE_EXISTS", "message": "Konten sudah memiliki jadwal aktif."})
    if outcome == "idempotency_conflict":
        raise HTTPException(409, detail={"code": "IDEMPOTENCY_KEY_REUSED", "message": "Idempotency-Key digunakan untuk jadwal lain."})
    if outcome == "invalid_timezone":
        raise HTTPException(422, detail={"code": "CONTENT_TIMEZONE_INVALID", "message": "Gunakan IANA timezone yang valid."})
    if outcome == "invalid_schedule":
        raise HTTPException(422, detail={"code": "CONTENT_SCHEDULE_INVALID", "message": "Waktu atau konfirmasi jadwal tidak valid."})
    if outcome not in ("created", "replayed"):
        raise HTTPException(503, detail={"code": "CONTENT_SCHEDULE_UNAVAILABLE", "message": "Jadwal belum dapat disimpan."})
    rows = [result["schedule"]]
    updated = [result["content"]]
    await write_operator_audit(request, actor_user_id=str(user["id"]), action="content.schedule.create",
        outcome="allowed", resource_type="content_item", resource_id=str(content_id),
        metadata={"schedule_id": rows[0]["id"], "publish_at": publish_at.isoformat(), "timezone": payload.creator_timezone})
    return {"item": rows[0], "content": updated[0]}


@router.patch("/{content_id}/schedule", tags=["content-scheduling"])
async def reschedule_content(
    content_id: uuid.UUID, payload: ContentScheduleRequest, request: Request,
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    content = await _owner_content(content_id, str(user["id"]))
    if content["status"] not in ("draft", "failed", "review", "scheduled") or int(content["version"]) != payload.expected_version:
        raise HTTPException(409, detail={"code": "CONTENT_SCHEDULE_CONFLICT", "message": "Konten berubah atau tidak dapat dijadwalkan ulang."})
    if not payload.rights_confirmed or not payload.disclosure_confirmed:
        raise HTTPException(422, detail={"code": "CONTENT_SCHEDULE_ATTESTATION_REQUIRED", "message": "Konfirmasi hak penggunaan dan disclosure wajib diberikan."})
    try:
        ZoneInfo(payload.creator_timezone)
    except ZoneInfoNotFoundError as exc:
        raise HTTPException(422, detail={"code": "CONTENT_TIMEZONE_INVALID", "message": "Gunakan IANA timezone yang valid."}) from exc
    if payload.publish_at.tzinfo is None or payload.publish_at.astimezone(timezone.utc) <= datetime.now(timezone.utc):
        raise HTTPException(422, detail={"code": "CONTENT_SCHEDULE_TIME_INVALID", "message": "Waktu baru harus memiliki timezone dan berada di masa depan."})
    schedules = await _server_db("GET", "content_schedules", params={
        "select": "id,status", "content_id": f"eq.{content_id}", "owner_id": f"eq.{user['id']}",
        "status": "eq.scheduled", "limit": "1",
    })
    if not schedules:
        raise HTTPException(404, detail={"code": "CONTENT_SCHEDULE_NOT_FOUND", "message": "Jadwal aktif tidak ditemukan."})
    result = await _server_db("POST", "rpc/reschedule_content_schedule", body={
        "p_content_id": str(content_id), "p_owner_id": str(user["id"]),
        "p_expected_version": payload.expected_version,
        "p_publish_at": payload.publish_at.astimezone(timezone.utc).isoformat(),
        "p_creator_timezone": payload.creator_timezone,
    })
    outcome = result.get("outcome") if isinstance(result, dict) else None
    if outcome == "schedule_not_found":
        raise HTTPException(404, detail={"code": "CONTENT_SCHEDULE_NOT_FOUND", "message": "Jadwal aktif tidak ditemukan."})
    if outcome == "content_conflict":
        raise HTTPException(409, detail={"code": "CONTENT_SCHEDULE_CONFLICT", "message": "Konten berubah atau tidak dapat dijadwalkan ulang."})
    if outcome != "rescheduled":
        raise HTTPException(422, detail={"code": "CONTENT_SCHEDULE_INVALID", "message": "Waktu atau timezone jadwal tidak valid."})
    schedule = [result["schedule"]]
    updated_content = [result["content"]]
    await write_operator_audit(request, actor_user_id=str(user["id"]), action="content.schedule.reschedule",
        outcome="allowed", resource_type="content_item", resource_id=str(content_id),
        metadata={"schedule_id": schedule[0]["id"], "publish_at": payload.publish_at.astimezone(timezone.utc).isoformat()})
    return {"item": schedule[0], "content": updated_content[0]}


@router.delete("/{content_id}/schedule", tags=["content-scheduling"])
async def cancel_content_schedule(
    content_id: uuid.UUID, request: Request, user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    content = await _owner_content(content_id, str(user["id"]))
    result = await _server_db("POST", "rpc/cancel_content_schedule", body={
        "p_content_id": str(content_id), "p_owner_id": str(user["id"]),
    })
    outcome = result.get("outcome") if isinstance(result, dict) else None
    if outcome == "content_not_found":
        raise HTTPException(404, detail={"code": "CONTENT_NOT_FOUND", "message": "Konten tidak ditemukan."})
    if outcome == "schedule_not_found":
        raise HTTPException(404, detail={"code": "CONTENT_SCHEDULE_NOT_FOUND", "message": "Jadwal aktif tidak ditemukan."})
    if outcome != "cancelled":
        raise HTTPException(409, detail={"code": "CONTENT_SCHEDULE_CANCEL_CONFLICT", "message": "Jadwal tidak dapat dibatalkan."})
    updated = [result["schedule"]]
    await write_operator_audit(request, actor_user_id=str(user["id"]), action="content.schedule.cancel",
        outcome="allowed", resource_type="content_item", resource_id=str(content_id),
        metadata={"schedule_id": updated[0]["id"]})
    return {"item": updated[0], "message": "Jadwal publikasi dibatalkan."}


@router.get("/admin/retention/preview", tags=["content-retention"])
async def retention_preview(
    request: Request,
    operator: dict[str, Any] = Depends(require_operator_scope("platform:content.moderate")),
) -> dict[str, Any]:
    deleted = await _server_db("GET", "content_items", params={
        "select": "id,owner_id,deleted_at,status", "status": "eq.deleted",
        "deleted_at": f"lte.{(datetime.now(timezone.utc) - __import__('datetime').timedelta(days=30)).isoformat()}",
        "purge_started_at": "is.null", "limit": "100",
    })
    abandoned = await _server_db("GET", "content_media", params={
        "select": "id,content_id,owner_id,status,created_at", "status": "in.(uploading,failed)",
        "created_at": f"lte.{(datetime.now(timezone.utc) - __import__('datetime').timedelta(days=7)).isoformat()}",
        "limit": "100",
    })
    await write_operator_audit(request, actor_user_id=str(operator["id"]), action="content.retention.preview",
        outcome="allowed", resource_type="content_retention", resource_id="dry-run",
        metadata={"deleted_content_candidates": len(deleted or []), "abandoned_upload_candidates": len(abandoned or []), "dry_run": True})
    return {"dry_run": True, "content_candidates": deleted or [], "abandoned_upload_candidates": abandoned or [],
        "note": "Preview tidak menghapus data; legal hold diperiksa ulang oleh executor sebelum penghapusan."}


@router.post("/admin/retention/holds", status_code=201, tags=["content-retention"])
async def create_content_retention_hold(
    payload: dict[str, Any], request: Request,
    operator: dict[str, Any] = Depends(require_operator_scope("platform:content.moderate")),
) -> dict[str, Any]:
    try:
        content_id = uuid.UUID(str(payload.get("content_id", "")))
    except (ValueError, TypeError, AttributeError) as exc:
        raise HTTPException(422, detail={"code": "RETENTION_CONTENT_ID_INVALID", "message": "Content ID harus berupa UUID yang valid."}) from exc
    hold_type = str(payload.get("hold_type", ""))
    reason = str(payload.get("reason", "")).strip()
    if hold_type not in ("legal", "safety", "regulatory") or not 8 <= len(reason) <= 1000:
        raise HTTPException(422, detail={"code": "RETENTION_HOLD_INVALID", "message": "Jenis dan alasan legal hold tidak valid."})
    content = await _server_db("GET", "content_items", params={"select": "id,owner_id,purge_started_at", "id": f"eq.{content_id}", "limit": "1"})
    if not content or content[0].get("purge_started_at"):
        raise HTTPException(409, detail={"code": "RETENTION_PURGE_LOCKED", "message": "Konten tidak tersedia atau penghapusan sudah dimulai."})
    rows = await _server_db("POST", "content_retention_holds", body={
        "content_id": str(content_id), "owner_id": content[0]["owner_id"], "hold_type": hold_type,
        "reason": reason, "created_by": operator["id"],
    }, prefer="return=representation")
    await write_operator_audit(request, actor_user_id=str(operator["id"]), action="content.retention.hold.create",
        outcome="allowed", resource_type="content_item", resource_id=str(content_id),
        metadata={"hold_id": rows[0]["id"], "hold_type": hold_type, "reason": reason})
    return {"item": rows[0]}


@router.post("/admin/retention/holds/{hold_id}/release", tags=["content-retention"])
async def release_content_retention_hold(
    hold_id: uuid.UUID, payload: dict[str, Any], request: Request,
    operator: dict[str, Any] = Depends(require_operator_scope("platform:content.moderate")),
) -> dict[str, Any]:
    reason = str(payload.get("reason", "")).strip()
    if len(reason) < 8:
        raise HTTPException(422, detail={"code": "RETENTION_HOLD_RELEASE_REASON_REQUIRED", "message": "Alasan pelepasan hold minimal 8 karakter."})
    rows = await _server_db("PATCH", "content_retention_holds", params={
        "id": f"eq.{hold_id}", "released_at": "is.null", "select": "*",
    }, body={"released_by": operator["id"], "released_at": datetime.now(timezone.utc).isoformat()},
        prefer="return=representation")
    if not rows:
        raise HTTPException(409, detail={"code": "RETENTION_HOLD_NOT_ACTIVE", "message": "Hold tidak aktif atau sudah dilepas."})
    await write_operator_audit(request, actor_user_id=str(operator["id"]), action="content.retention.hold.release",
        outcome="allowed", resource_type="content_retention_hold", resource_id=str(hold_id),
        metadata={"reason": reason})
    return {"item": rows[0]}


@router.get("/admin/lifecycle/events", tags=["content-lifecycle-admin"])
async def list_content_lifecycle_events(
    request: Request, limit: int = 100,
    operator: dict[str, Any] = Depends(require_operator_scope("platform:content.moderate")),
) -> dict[str, Any]:
    if limit < 1 or limit > 200:
        raise HTTPException(422, detail={"code": "CONTENT_LIMIT_INVALID", "message": "Batas audit 1–200."})
    rows = await _server_db("GET", "content_lifecycle_events", params={
        "select": "id,event_key,event_type,content_id,media_id,owner_id,payload,created_at",
        "order": "created_at.desc", "limit": str(limit),
    })
    await write_operator_audit(request, actor_user_id=str(operator["id"]), action="content.lifecycle.events.read",
        outcome="allowed", resource_type="content_lifecycle_events", resource_id="latest",
        metadata={"count": len(rows or [])})
    return {"items": rows or []}


@router.get("/admin/retention/holds", tags=["content-retention"])
async def list_content_retention_holds(
    request: Request, active_only: bool = True, limit: int = 100,
    operator: dict[str, Any] = Depends(require_operator_scope("platform:content.moderate")),
) -> dict[str, Any]:
    if limit < 1 or limit > 200:
        raise HTTPException(422, detail={"code": "CONTENT_LIMIT_INVALID", "message": "Batas hold 1–200."})
    params = {"select": "*", "order": "created_at.desc", "limit": str(limit)}
    if active_only:
        params["released_at"] = "is.null"
    rows = await _server_db("GET", "content_retention_holds", params=params)
    await write_operator_audit(request, actor_user_id=str(operator["id"]), action="content.retention.holds.read",
        outcome="allowed", resource_type="content_retention_holds", resource_id="latest",
        metadata={"count": len(rows or []), "active_only": active_only})
    return {"items": rows or []}


@router.get("/admin/retention/receipts", tags=["content-retention"])
async def list_content_retention_receipts(
    request: Request, limit: int = 100,
    operator: dict[str, Any] = Depends(require_operator_scope("platform:content.moderate")),
) -> dict[str, Any]:
    if limit < 1 or limit > 200:
        raise HTTPException(422, detail={"code": "CONTENT_LIMIT_INVALID", "message": "Batas receipt 1–200."})
    rows = await _server_db("GET", "content_retention_receipts", params={
        "select": "*", "order": "completed_at.desc", "limit": str(limit),
    })
    await write_operator_audit(request, actor_user_id=str(operator["id"]), action="content.retention.receipts.read",
        outcome="allowed", resource_type="content_retention_receipts", resource_id="latest",
        metadata={"count": len(rows or [])})
    return {"items": rows or []}


@router.post("/admin/retention/enqueue", tags=["content-retention"])
async def enqueue_content_retention(
    request: Request, payload: dict[str, Any],
    operator: dict[str, Any] = Depends(require_operator_scope("platform:content.moderate")),
) -> dict[str, Any]:
    if payload.get("confirm") is not True:
        raise HTTPException(422, detail={"code": "RETENTION_CONFIRMATION_REQUIRED", "message": "Konfirmasi eksplisit diperlukan untuk membuat job penghapusan."})
    count = await _server_db("POST", "rpc/enqueue_expired_content_retention_jobs", body={"p_limit": 100})
    await write_operator_audit(request, actor_user_id=str(operator["id"]), action="content.retention.enqueue",
        outcome="allowed", resource_type="content_retention_jobs", resource_id="eligible",
        metadata={"enqueued": count, "batch_limit": 100})
    return {"enqueued": count, "message": "Job retention masuk antrean. Worker tetap memeriksa legal hold sebelum menghapus."}


@router.get("/admin/lifecycle/jobs", tags=["content-lifecycle-admin"])
async def list_content_lifecycle_jobs(
    request: Request, status: str = "dead", limit: int = 100,
    operator: dict[str, Any] = Depends(require_operator_scope("platform:content.moderate")),
) -> dict[str, Any]:
    if status not in ("pending", "processing", "awaiting_provider", "failed", "dead", "succeeded", "cancelled") or limit < 1 or limit > 200:
        raise HTTPException(422, detail={"code": "CONTENT_JOB_FILTER_INVALID", "message": "Filter status atau batas job tidak valid."})
    rows = await _server_db("GET", "content_lifecycle_jobs", params={
        "select": "id,job_type,content_id,media_id,owner_id,idempotency_key,status,attempts,max_attempts,run_at,last_error_code,created_at,updated_at,completed_at",
        "status": f"eq.{status}", "order": "updated_at.desc", "limit": str(limit),
    })
    await write_operator_audit(request, actor_user_id=str(operator["id"]), action="content.lifecycle.jobs.read",
        outcome="allowed", resource_type="content_lifecycle_jobs", resource_id=status,
        metadata={"count": len(rows or [])})
    return {"items": rows or []}


@router.post("/admin/lifecycle/jobs/{job_id}/retry", tags=["content-lifecycle-admin"])
async def retry_content_lifecycle_job(
    job_id: uuid.UUID, payload: dict[str, Any], request: Request,
    operator: dict[str, Any] = Depends(require_operator_scope("platform:content.moderate")),
) -> dict[str, Any]:
    reason = str(payload.get("reason", "")).strip()
    if len(reason) < 8:
        raise HTTPException(422, detail={"code": "CONTENT_JOB_RETRY_REASON_REQUIRED", "message": "Alasan retry minimal 8 karakter."})
    result = await _server_db("POST", "rpc/retry_content_lifecycle_job", body={
        "p_job_id": str(job_id), "p_operator_id": str(operator["id"]), "p_reason": reason,
    })
    outcome = result.get("outcome") if isinstance(result, dict) else None
    if outcome == "job_not_retryable":
        raise HTTPException(409, detail={"code": "CONTENT_JOB_NOT_RETRYABLE", "message": "Job tidak berada pada status failed/dead."})
    if outcome == "media_not_retryable":
        raise HTTPException(409, detail={"code": "CONTENT_MEDIA_NOT_RETRYABLE", "message": "Media tidak dapat diproses ulang dalam status saat ini."})
    if outcome == "reason_required":
        raise HTTPException(422, detail={"code": "CONTENT_JOB_RETRY_REASON_REQUIRED", "message": "Alasan retry minimal 8 karakter."})
    if outcome != "requeued":
        raise HTTPException(409, detail={"code": "CONTENT_JOB_RECOVERY_BLOCKED", "message": "Job tidak dapat dipulihkan; periksa dependensi dan kebijakan lifecycle."})
    await write_operator_audit(request, actor_user_id=str(operator["id"]), action="content.lifecycle.job.retry",
        outcome="allowed", resource_type="content_lifecycle_job", resource_id=str(job_id),
        metadata={"reason": reason, "job_type": result["job"]["job_type"]})
    return {"item": result["job"], "message": "Job masuk kembali ke antrean."}


@router.get("/admin/schedules", tags=["content-lifecycle-admin"])
async def list_content_schedules(
    request: Request, status: str = "failed", limit: int = 100,
    operator: dict[str, Any] = Depends(require_operator_scope("platform:content.moderate")),
) -> dict[str, Any]:
    if status not in ("scheduled", "processing", "published", "cancelled", "failed") or limit < 1 or limit > 200:
        raise HTTPException(422, detail={"code": "CONTENT_SCHEDULE_FILTER_INVALID", "message": "Filter jadwal tidak valid."})
    rows = await _server_db("GET", "content_schedules", params={
        "select": "id,content_id,owner_id,content_version,publish_at,creator_timezone,status,attempts,last_error_code,created_at,updated_at",
        "status": f"eq.{status}", "order": "updated_at.desc", "limit": str(limit),
    })
    await write_operator_audit(request, actor_user_id=str(operator["id"]), action="content.schedules.read",
        outcome="allowed", resource_type="content_schedules", resource_id=status,
        metadata={"count": len(rows or [])})
    return {"items": rows or []}


@router.post("/admin/schedules/{schedule_id}/retry", tags=["content-lifecycle-admin"])
async def retry_content_schedule(
    schedule_id: uuid.UUID, payload: dict[str, Any], request: Request,
    operator: dict[str, Any] = Depends(require_operator_scope("platform:content.moderate")),
) -> dict[str, Any]:
    reason = str(payload.get("reason", "")).strip()
    if len(reason) < 8:
        raise HTTPException(422, detail={"code": "CONTENT_SCHEDULE_RETRY_REASON_REQUIRED", "message": "Alasan retry minimal 8 karakter."})
    result = await _server_db("POST", "rpc/retry_content_schedule", body={
        "p_schedule_id": str(schedule_id), "p_operator_id": str(operator["id"]), "p_reason": reason,
    })
    outcome = result.get("outcome") if isinstance(result, dict) else None
    if outcome == "schedule_not_retryable":
        raise HTTPException(409, detail={"code": "CONTENT_SCHEDULE_NOT_RETRYABLE", "message": "Jadwal tidak berstatus failed."})
    if outcome == "content_policy_blocked":
        raise HTTPException(409, detail={"code": "CONTENT_SCHEDULE_POLICY_BLOCKED", "message": "Konten tidak lagi memenuhi kebijakan publikasi."})
    if outcome == "media_not_ready":
        raise HTTPException(409, detail={"code": "CONTENT_SCHEDULE_MEDIA_NOT_READY", "message": "Media belum siap."})
    if outcome != "requeued":
        raise HTTPException(409, detail={"code": "CONTENT_SCHEDULE_RECOVERY_BLOCKED", "message": "Jadwal tidak dapat dipulihkan."})
    await write_operator_audit(request, actor_user_id=str(operator["id"]), action="content.schedule.retry",
        outcome="allowed", resource_type="content_schedule", resource_id=str(schedule_id),
        metadata={"reason": reason})
    return {"item": result["schedule"], "message": "Jadwal dimasukkan kembali ke antrean."}

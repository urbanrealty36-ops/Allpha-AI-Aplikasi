"""Canonical authenticated content creation and private media pipeline (ENG-P13)."""
from __future__ import annotations

import os
import re
import uuid
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
ALLOWED_MEDIA = {
    "image/jpeg": (".jpg", IMAGE_LIMIT),
    "image/png": (".png", IMAGE_LIMIT),
    "image/webp": (".webp", IMAGE_LIMIT),
    "video/mp4": (".mp4", VIDEO_LIMIT),
    "video/webm": (".webm", VIDEO_LIMIT),
}
CONTENT_FIELDS = "id,owner_id,content_type,body,visibility,status,moderation_status,version,created_at,updated_at,published_at"
MEDIA_FIELDS = "id,content_id,owner_id,bucket_id,storage_path,filename,media_type,size_bytes,sha256,status,created_at"


class ContentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    body: str = Field(default="", max_length=TEXT_LIMIT)
    visibility: str = Field(default="public", pattern="^(public|followers|private)$")
    content_type: str = Field(default="text", pattern="^(text|image|video)$")


class ContentUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    body: str = Field(min_length=1, max_length=TEXT_LIMIT)
    visibility: str = Field(default="public", pattern="^(public|followers|private)$")


class ContentReview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: str = Field(pattern="^(approve|reject)$")
    expected_version: int = Field(ge=1)
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
    if response.status_code >= 400:
        if response.status_code == 409:
            raise HTTPException(409, detail={"code": "CONTENT_CONFLICT", "message": "Konten berubah; muat ulang sebelum mencoba lagi."})
        raise HTTPException(503, detail={"code": "CONTENT_DATABASE_WRITE_FAILED", "message": "Perubahan konten tidak dapat disimpan."})
    if not response.content:
        return None
    return response.json()


async def _owner_content(content_id: uuid.UUID, user_id: str) -> dict[str, Any]:
    rows = await _server_db("GET", "content_items", params={
        "select": CONTENT_FIELDS, "id": f"eq.{content_id}", "owner_id": f"eq.{user_id}", "limit": "1",
    })
    if not rows:
        raise HTTPException(404, detail={"code": "CONTENT_NOT_FOUND", "message": "Konten tidak ditemukan."})
    return rows[0]


async def _storage(method: str, path: str, *, data: bytes | None = None, media_type: str | None = None) -> httpx.Response:
    base, key = _config()
    headers = {"apikey": key, "Authorization": f"Bearer {key}"}
    if media_type:
        headers["Content-Type"] = media_type
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(60, connect=5)) as client:
            response = await client.request(method, f"{base}/storage/v1/object/{quote(path, safe='/')}", headers=headers, content=data)
    except httpx.HTTPError as exc:
        raise HTTPException(503, detail={"code": "CONTENT_STORAGE_UNAVAILABLE", "message": "Penyimpanan media sementara tidak tersedia."}) from exc
    if response.status_code >= 400:
        raise HTTPException(503, detail={"code": "CONTENT_STORAGE_FAILED", "message": "Unggah media gagal; silakan coba lagi."})
    return response


@router.get("/mine")
async def list_my_content(request: Request, user: dict[str, Any] = Depends(current_user), limit: int = 30) -> dict[str, Any]:
    if limit < 1 or limit > 100:
        raise HTTPException(422, detail={"code": "CONTENT_LIMIT_INVALID", "message": "Batas daftar harus 1–100."})
    rows = await _server_db("GET", "content_items", params={
        "select": CONTENT_FIELDS, "owner_id": f"eq.{user['id']}", "order": "updated_at.desc", "limit": str(limit),
    })
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
    row = {
        "owner_id": user["id"], "content_type": payload.content_type, "body": payload.body.strip(),
        "visibility": payload.visibility, "status": "draft", "moderation_status": "not_submitted", "version": 1,
    }
    created = await _server_db("POST", "content_items", body=row, prefer="return=representation")
    return {"item": created[0]}


@router.patch("/{content_id}")
async def update_content(content_id: uuid.UUID, payload: ContentUpdate, request: Request, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    existing = await _owner_content(content_id, str(user["id"]))
    if existing["status"] not in ("draft", "failed"):
        raise HTTPException(409, detail={"code": "CONTENT_NOT_EDITABLE", "message": "Konten hanya dapat diedit saat draft atau gagal."})
    rows = await _server_db("PATCH", "content_items", params={"id": f"eq.{content_id}", "owner_id": f"eq.{user['id']}", "select": CONTENT_FIELDS}, body={
        "body": payload.body.strip(), "visibility": payload.visibility, "version": existing["version"] + 1, "status": "draft",
    }, prefer="return=representation")
    if not rows:
        raise HTTPException(409, detail={"code": "CONTENT_UPDATE_CONFLICT", "message": "Konten tidak berubah atau sudah tidak dapat diedit."})
    return {"item": rows[0]}


@router.post("/{content_id}/media", status_code=201)
async def upload_media(content_id: uuid.UUID, request: Request, file: UploadFile = File(...), user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    content = await _owner_content(content_id, str(user["id"]))
    if content["status"] not in ("draft", "failed"):
        raise HTTPException(409, detail={"code": "CONTENT_NOT_EDITABLE", "message": "Media hanya dapat ditambahkan ke draft."})
    media_type = (file.content_type or "").lower().split(";")[0].strip()
    spec = ALLOWED_MEDIA.get(media_type)
    if not spec:
        raise HTTPException(415, detail={"code": "MEDIA_TYPE_UNSUPPORTED", "message": "Format media yang didukung: JPG, PNG, WebP, MP4, dan WebM."})
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
    }
    if not signatures[media_type](data):
        raise HTTPException(422, detail={"code": "MEDIA_SIGNATURE_INVALID", "message": "Isi file tidak sesuai dengan format media yang dipilih."})
    safe_name = re.sub(r"[^a-zA-Z0-9._-]+", "-", (file.filename or "media").split("/")[-1].split("\\")[-1])[:100].strip(".-") or "media"
    media_id = str(uuid.uuid4())
    storage_path = f"{user['id']}/{content_id}/{media_id}-{safe_name}"
    await _storage("POST", f"content-media/{storage_path}", data=data, media_type=media_type)
    import hashlib
    try:
        rows = await _server_db("POST", "content_media", body={
            "id": media_id, "content_id": str(content_id), "owner_id": user["id"], "bucket_id": "content-media",
            "storage_path": storage_path, "filename": safe_name, "media_type": media_type,
            "size_bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(), "status": "uploaded",
        }, prefer="return=representation")
    except HTTPException:
        # Best-effort cleanup prevents untracked private objects on metadata failure.
        try:
            await _storage("DELETE", f"content-media/{storage_path}")
        except HTTPException:
            pass
        raise
    try:
        updated = await _server_db("PATCH", "content_items", params={
            "id": f"eq.{content_id}", "owner_id": f"eq.{user['id']}",
            "status": "in.(draft,failed)", "select": CONTENT_FIELDS,
        }, body={
            "status": "draft", "content_type": "video" if media_type.startswith("video/") else "image",
            "version": int(content.get("version") or 1) + 1,
        }, prefer="return=representation")
        if not updated:
            raise HTTPException(409, detail={"code": "CONTENT_UPLOAD_CONFLICT", "message": "Draft berubah saat media diunggah; silakan muat ulang dan coba lagi."})
    except HTTPException:
        # Keep the object store and metadata consistent if the parent draft changed or failed to update.
        try:
            await _server_db("DELETE", "content_media", params={"id": f"eq.{media_id}", "owner_id": f"eq.{user['id']}"})
        except HTTPException:
            pass
        try:
            await _storage("DELETE", f"content-media/{storage_path}")
        except HTTPException:
            pass
        raise
    return {"item": rows[0], "content": updated[0]}


@router.get("/{content_id}/preview")
async def preview_content(content_id: uuid.UUID, request: Request, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    content = await _owner_content(content_id, str(user["id"]))
    media = await _server_db("GET", "content_media", params={
        "select": MEDIA_FIELDS, "content_id": f"eq.{content_id}", "owner_id": f"eq.{user['id']}", "order": "created_at.asc",
    })
    previews = []
    base, key = _config()
    for item in media or []:
        path = quote(f"content-media/{item['storage_path']}", safe="/")
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(8, connect=3)) as client:
                response = await client.post(f"{base}/storage/v1/object/sign/{path}", headers={"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"}, json={"expiresIn": 300})
        except httpx.HTTPError as exc:
            raise HTTPException(503, detail={"code": "CONTENT_PREVIEW_UNAVAILABLE", "message": "Pratinjau media belum tersedia."}) from exc
        if response.status_code >= 400:
            raise HTTPException(503, detail={"code": "CONTENT_PREVIEW_UNAVAILABLE", "message": "Pratinjau media belum tersedia."})
        signed = response.json().get("signedURL") or response.json().get("signedUrl")
        previews.append({**item, "preview_url": f"{base}/storage/v1{signed}" if signed and signed.startswith("/") else f"{base}/storage/v1/{signed}" if signed else None})
    return {"item": content, "media": previews, "preview_expires_in": 300}


@router.post("/{content_id}/publish")
async def publish_content(content_id: uuid.UUID, request: Request, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    content = await _owner_content(content_id, str(user["id"]))
    media = await _server_db("GET", "content_media", params={"select": "id", "content_id": f"eq.{content_id}", "owner_id": f"eq.{user['id']}", "limit": "1"})
    if not content["body"].strip() and not media:
        raise HTTPException(422, detail={"code": "CONTENT_EMPTY", "message": "Tambahkan teks atau media sebelum mengirim konten."})
    if content["status"] not in ("draft", "failed"):
        raise HTTPException(409, detail={"code": "CONTENT_ALREADY_SUBMITTED", "message": "Konten sudah dikirim atau tidak dapat dipublikasikan ulang."})
    rows = await _server_db("PATCH", "content_items", params={"id": f"eq.{content_id}", "owner_id": f"eq.{user['id']}", "status": "in.(draft,failed)", "select": CONTENT_FIELDS}, body={
        "status": "review", "moderation_status": "pending", "version": content["version"] + 1,
    }, prefer="return=representation")
    if not rows:
        raise HTTPException(409, detail={"code": "CONTENT_PUBLISH_CONFLICT", "message": "Status konten berubah; muat ulang sebelum mengirim lagi."})
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


@router.get("/feed/public")
async def public_content_feed(request: Request, limit: int = 20) -> dict[str, Any]:
    if limit < 1 or limit > 50:
        raise HTTPException(422, detail={"code": "CONTENT_LIMIT_INVALID", "message": "Batas feed harus 1–50."})
    rows = await _server_db("GET", "content_items", params={
        "select": CONTENT_FIELDS, "status": "eq.published", "moderation_status": "eq.approved",
        "visibility": "eq.public", "order": "published_at.desc", "limit": str(limit),
    })
    return {"items": rows or []}


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
    await write_operator_audit(request, actor_user_id=str(operator["id"]), action="content.review_queue.read",
        outcome="allowed", resource_type="content_queue", resource_id="pending", metadata={"count": len(rows or [])})
    return {"items": rows or []}


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
    await write_operator_audit(request, actor_user_id=str(operator["id"]), action="content.moderate",
        outcome="attempted", resource_type="content_item", resource_id=str(content_id),
        metadata={"decision": payload.decision, "expected_version": payload.expected_version, "reason": payload.reason})
    now = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()
    changes = {
        "status": "published" if allowed else "failed",
        "moderation_status": "approved" if allowed else "rejected",
        "published_at": now if allowed else None,
        "error_code": None if allowed else "MODERATION_REJECTED",
        "version": payload.expected_version + 1,
    }
    rows = await _server_db("PATCH", "content_items", params={
        "id": f"eq.{content_id}", "status": "eq.review", "moderation_status": "eq.pending",
        "version": f"eq.{payload.expected_version}", "select": CONTENT_FIELDS,
    }, body=changes, prefer="return=representation")
    if not rows:
        raise HTTPException(409, detail={"code": "CONTENT_REVIEW_CONFLICT", "message": "Konten berubah saat moderasi; keputusan tidak diterapkan."})
    await write_operator_audit(request, actor_user_id=str(operator["id"]), action="content.moderate",
        outcome="allowed", resource_type="content_item", resource_id=str(content_id),
        metadata={"decision": payload.decision, "version": payload.expected_version + 1, "reason": payload.reason})
    return {"item": rows[0]}

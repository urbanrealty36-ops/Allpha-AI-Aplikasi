"""Authenticated media API foundation backed by canonical content_media."""
from __future__ import annotations
import os, uuid, re, hashlib, json
from datetime import datetime, timezone
from pydantic import BaseModel, ConfigDict, Field
from allpha_api.auth import user_db_request, service_db_request
from allpha_api.cloudinary_provider import CloudinaryConfig, CloudinaryConfigurationError, build_signed_upload_intent, verify_cloudinary_webhook, build_signed_private_download_url, build_signed_authenticated_delivery_url
from typing import Any
import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from allpha_api.auth import current_user
router = APIRouter(prefix="/v1/media", tags=["media"])
class UploadIntent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    content_id: uuid.UUID
    filename: str = Field(min_length=1, max_length=120)
    media_type: str = Field(min_length=1, max_length=80)
    size_bytes: int = Field(gt=0, le=50 * 1024 * 1024)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
class UploadCompletion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    media_id: uuid.UUID
MEDIA_LIMITS = {"image/jpeg":10*1024*1024,"image/png":10*1024*1024,"image/webp":10*1024*1024,"video/mp4":50*1024*1024,"video/webm":50*1024*1024,"audio/mpeg":50*1024*1024,"audio/mp4":50*1024*1024,"audio/aac":50*1024*1024,"audio/ogg":50*1024*1024,"audio/wav":50*1024*1024,"audio/webm":50*1024*1024,"text/vtt":10*1024*1024,"application/x-subrip":10*1024*1024}
def _config():
    base=os.getenv("SUPABASE_URL","").rstrip("/")
    key=os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SECRET_KEY")
    if not base or not key:
        raise HTTPException(503,detail={"code":"MEDIA_DB_NOT_CONFIGURED","message":"Media database is not configured."})
    return base,key


async def _owned(media_id: uuid.UUID, owner_id: str) -> dict[str, Any]:
    """Load one media row through the service boundary with an explicit owner fence."""
    base, key = _config()
    params = {
        "select": "id,owner_id,status,storage_provider,provider_public_id,provider_resource_type,provider_asset_id,provider_batch_id,provider_version,provider_format,size_bytes,sha256",
        "id": f"eq.{media_id}",
        "owner_id": f"eq.{owner_id}",
        "limit": "1",
    }
    try:
        async with httpx.AsyncClient(timeout=12, trust_env=False, follow_redirects=False) as client:
            response = await client.get(
                f"{base}/rest/v1/content_media",
                params=params,
                headers={"apikey": key, "Authorization": f"Bearer {key}"},
            )
        if response.status_code >= 300:
            raise HTTPException(503, detail={"code": "MEDIA_DB_UNAVAILABLE", "message": "Media registry tidak tersedia."})
        rows = response.json()
    except HTTPException:
        raise
    except (httpx.HTTPError, ValueError, TypeError) as exc:
        raise HTTPException(503, detail={"code": "MEDIA_DB_UNAVAILABLE", "message": "Media registry tidak tersedia."}) from exc
    if not isinstance(rows, list) or not rows:
        raise HTTPException(404, detail={"code": "MEDIA_NOT_FOUND", "message": "Media tidak ditemukan."})
    return rows[0]

@router.post("/upload-intents", status_code=201)
async def create_upload_intent(payload: UploadIntent, request: Request, user: dict[str, Any] = Depends(current_user), idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")):
    media_type = payload.media_type.lower().split(";", 1)[0].strip()
    if media_type not in MEDIA_LIMITS:
        raise HTTPException(415, detail={"code":"MEDIA_TYPE_UNSUPPORTED","message":"Format media tidak didukung."})
    if payload.size_bytes > MEDIA_LIMITS[media_type]:
        raise HTTPException(413, detail={"code":"MEDIA_TOO_LARGE","message":"Ukuran media melebihi batas."})
    try:
        media_id = uuid.UUID(idempotency_key or "")
    except (ValueError, TypeError):
        raise HTTPException(400, detail={"code":"MEDIA_IDEMPOTENCY_REQUIRED","message":"Idempotency-Key UUID wajib dikirim."})
    token = getattr(request.state, "supabase_access_token", None)
    if not token:
        raise HTTPException(401, detail={"code":"AUTH_CONTEXT_MISSING","message":"Sesi terverifikasi tidak tersedia."})
    rows = await user_db_request("GET","content_items",token,params={"select":"id,status","id":f"eq.{payload.content_id}","owner_id":f"eq.{user['id']}","limit":"1"})
    if not rows or rows[0].get("status") not in {"draft","failed"}:
        raise HTTPException(404, detail={"code":"MEDIA_RESOURCE_NOT_FOUND","message":"Draft konten tidak tersedia."})
    try:
        cfg = CloudinaryConfig.from_environment(require_callback=True)
        intent = build_signed_upload_intent(config=cfg,media_id=str(media_id),media_type=media_type,ttl_seconds=600)
    except (CloudinaryConfigurationError,ValueError) as exc:
        raise HTTPException(503,detail={"code":"CLOUDINARY_NOT_READY","message":"Upload Cloudinary belum siap."}) from exc
    filename = re.sub(r"[^A-Za-z0-9._-]+","-",payload.filename.split("/")[-1])[:120]
    result = await service_db_request("reserve_cloudinary_media_upload",body={
        "p_media_id":str(media_id),"p_content_id":str(payload.content_id),"p_owner_id":str(user["id"]),
        "p_domain":"content","p_purpose":"attachment","p_resource_id":None,"p_tenant_id":None,"p_session_id":None,
        "p_filename":filename,"p_media_type":media_type,"p_size_bytes":payload.size_bytes,"p_sha256":payload.sha256,
        "p_public_id":intent["public_id"],"p_resource_type":intent["resource_type"],"p_delivery_type":"authenticated",
        "p_upload_expires_at":datetime.fromtimestamp(int(intent["expires_at"]),tz=timezone.utc).isoformat(),
        "p_idempotency_key":str(media_id)})
    if not isinstance(result,dict) or not isinstance(result.get("media"),dict):
        raise HTTPException(503,detail={"code":"MEDIA_RESERVATION_UNCONFIRMED","message":"Reservasi media belum terkonfirmasi."})
    return {"item":result["media"],"upload":intent,"expires_in_seconds":600}

@router.post("/complete")
async def complete_upload(payload: UploadCompletion,user:dict[str,Any]=Depends(current_user)):
    item=await _owned(payload.media_id,str(user["id"]))
    if item.get("storage_provider")!="cloudinary":
        raise HTTPException(409,detail={"code":"MEDIA_PROVIDER_MISMATCH","message":"Media bukan asset Cloudinary."})
    if item.get("status") in {"uploaded","processing","ready"}:
        return {"item":item,"idempotent_replay":True}
    if item.get("status")!="uploading":
        raise HTTPException(409,detail={"code":"MEDIA_STATE_INVALID","message":"Status media tidak dapat dikonfirmasi."})
    cfg=CloudinaryConfig.from_environment()
    url=f"https://api.cloudinary.com/v1_1/{cfg.cloud_name}/resources/{item['provider_resource_type']}/authenticated"
    try:
        async with httpx.AsyncClient(timeout=12,trust_env=False,follow_redirects=False) as client:
            response=await client.get(url,params={"public_ids":[item["provider_public_id"]]},auth=(cfg.api_key,cfg.api_secret))
        if response.status_code!=200:
            raise HTTPException(409,detail={"code":"CLOUDINARY_ASSET_NOT_FOUND","message":"Asset belum ditemukan."})
        asset=(response.json().get("resources") or [])[0]
    except (httpx.HTTPError,ValueError,IndexError,KeyError,TypeError) as exc:
        raise HTTPException(503,detail={"code":"CLOUDINARY_METADATA_UNAVAILABLE","message":"Metadata asset belum dapat diverifikasi."}) from exc
    if asset.get("public_id")!=item.get("provider_public_id") or asset.get("resource_type")!=item.get("provider_resource_type") or asset.get("type")!="authenticated" or int(asset.get("bytes") or 0)!=int(item.get("size_bytes") or 0):
        raise HTTPException(403,detail={"code":"CLOUDINARY_ASSET_IDENTITY_MISMATCH","message":"Identitas asset tidak cocok."})
    result=await service_db_request("complete_cloudinary_content_media_upload",body={
        "p_media_id":str(payload.media_id),"p_owner_id":str(user["id"]),"p_asset_id":asset.get("asset_id"),
        "p_public_id":asset["public_id"],"p_resource_type":asset["resource_type"],"p_delivery_type":asset["type"],
        "p_batch_id":asset.get("batch_id"),"p_version":int(asset.get("version") or 0),"p_format":asset.get("format") or "",
        "p_width":asset.get("width"),"p_height":asset.get("height"),"p_duration":asset.get("duration"),
        "p_bytes":int(asset.get("bytes") or 0),"p_tags":asset.get("tags") or [],
        "p_provider_metadata":{"resource_type":asset.get("resource_type"),"type":asset.get("type"),"format":asset.get("format")}})
    if not isinstance(result,dict) or not isinstance(result.get("media"),dict):
        raise HTTPException(409,detail={"code":"MEDIA_COMPLETION_UNCONFIRMED","message":"Konfirmasi asset belum tersimpan."})
    return {"item":result["media"],"idempotent_replay":bool(result.get("idempotent_replay"))}

@router.post("/cloudinary/callback", status_code=202)
async def cloudinary_callback(
    request: Request,
    timestamp: str | None = Header(default=None, alias="X-Cld-Timestamp"),
    signature: str | None = Header(default=None, alias="X-Cld-Signature"),
):
    """Verify Cloudinary's exact webhook body, then atomically enqueue its lifecycle event."""
    raw = await request.body()
    if not raw or len(raw) > 1024 * 1024:
        raise HTTPException(413, detail={"code":"CLOUDINARY_CALLBACK_BODY_INVALID","message":"Payload callback tidak valid."})
    try:
        cfg = CloudinaryConfig.from_environment()
    except CloudinaryConfigurationError as exc:
        raise HTTPException(503, detail={"code":"CLOUDINARY_CALLBACK_NOT_CONFIGURED","message":"Verifikasi callback belum dikonfigurasi."}) from exc
    verdict = verify_cloudinary_webhook(raw_body=raw, timestamp=timestamp or "", signature=signature or "",
        secret=cfg.webhook_secret or cfg.api_secret, max_age_seconds=7200)
    if verdict != "valid":
        raise HTTPException(408 if verdict == "expired" else 401,
            detail={"code":"CLOUDINARY_CALLBACK_SIGNATURE_INVALID","message":"Signature atau timestamp callback tidak valid."})
    try:
        event = json.loads(raw)
    except (ValueError, UnicodeDecodeError) as exc:
        raise HTTPException(400, detail={"code":"CLOUDINARY_CALLBACK_JSON_INVALID","message":"Payload callback bukan JSON valid."}) from exc
    if not isinstance(event, dict) or event.get("notification_type") != "eager":
        raise HTTPException(422, detail={"code":"CLOUDINARY_CALLBACK_TYPE_UNSUPPORTED","message":"Jenis callback Cloudinary tidak didukung."})
    public_id, asset_id, batch_id = event.get("public_id"), event.get("asset_id"), event.get("batch_id")
    if not isinstance(public_id, str) or not public_id.startswith("allpha/") or not isinstance(asset_id, str) or not isinstance(batch_id, str) or not batch_id:
        raise HTTPException(422, detail={"code":"CLOUDINARY_CALLBACK_IDENTITY_INVALID","message":"Identitas asset callback tidak lengkap."})
    base, key = _config()
    headers = {"apikey":key,"Authorization":f"Bearer {key}"}
    async with httpx.AsyncClient(timeout=12, trust_env=False, follow_redirects=False) as client:
        media_response = await client.get(f"{base}/rest/v1/content_media", params={
            "select":"id,provider_asset_id,provider_public_id,provider_batch_id,status,storage_provider",
            "provider_public_id":f"eq.{public_id}","provider_asset_id":f"eq.{asset_id}",
            "storage_provider":"eq.cloudinary","status":"eq.processing","limit":"1",
        }, headers=headers)
        if media_response.status_code >= 300:
            raise HTTPException(503, detail={"code":"MEDIA_DB_UNAVAILABLE","message":"Registry media tidak tersedia."})
        media_rows = media_response.json()
        if not media_rows:
            raise HTTPException(404, detail={"code":"MEDIA_CALLBACK_ASSET_NOT_FOUND","message":"Asset callback tidak cocok dengan media aktif."})
        media = media_rows[0]
        if media.get("provider_batch_id") and media["provider_batch_id"] != batch_id:
            raise HTTPException(409, detail={"code":"MEDIA_CALLBACK_BATCH_MISMATCH","message":"Batch callback tidak cocok."})
        job_response = await client.get(f"{base}/rest/v1/content_lifecycle_jobs", params={
            "select":"id,payload","media_id":f"eq.{media['id']}","job_type":"eq.media_transcode",
            "status":"eq.awaiting_provider","limit":"1",
        }, headers=headers)
        if job_response.status_code >= 300:
            raise HTTPException(503, detail={"code":"MEDIA_JOB_LOOKUP_FAILED","message":"Job transcode tidak tersedia."})
        jobs = job_response.json()
    if not jobs:
        raise HTTPException(409, detail={"code":"MEDIA_TRANSCODE_NOT_WAITING","message":"Job transcode tidak sedang menunggu callback."})
    event_id = hashlib.sha256(raw).hexdigest()
    queued = await service_db_request("enqueue_content_provider_callback", body={
        "p_provider_event_id":event_id,"p_media_id":media["id"],"p_transcode_job_id":jobs[0]["id"],
        "p_payload_sha256":event_id,"p_payload":event,
    })
    outcome = queued.get("outcome") if isinstance(queued, dict) else None
    if outcome not in {"queued","already_processed"}:
        raise HTTPException(409, detail={"code":"MEDIA_CALLBACK_REJECTED","message":"Callback tidak dapat dimasukkan ke lifecycle media."})
    return {"accepted":True,"outcome":outcome,"event_id":event_id}


@router.delete("/{media_id}", status_code=202)
async def delete_media(media_id: uuid.UUID, user: dict[str, Any] = Depends(current_user)):
    """Queue owner-scoped provider deletion; bytes are removed by the durable worker."""
    item = await _owned(media_id, str(user["id"]))
    if item.get("storage_provider") != "cloudinary":
        raise HTTPException(
            409,
            detail={"code": "MEDIA_LEGACY_PROVIDER_DELETE_UNSUPPORTED",
                    "message": "Media lama harus dihapus melalui lifecycle domain asal."},
        )
    result = await service_db_request(
        "request_cloudinary_content_media_delete",
        body={"p_media_id": str(media_id), "p_owner_id": str(user["id"])},
    )
    if not isinstance(result, dict):
        raise HTTPException(503, detail={"code": "MEDIA_DELETE_NOT_CONFIRMED",
                                         "message": "Permintaan penghapusan belum terkonfirmasi."})
    outcome = result.get("outcome")
    if outcome in {"queued", "already_queued", "already_deleted"}:
        return {
            "item": result.get("media") or item,
            "outcome": outcome,
            "idempotent_replay": outcome != "queued",
        }
    if outcome == "media_not_found":
        raise HTTPException(404, detail={"code": "MEDIA_NOT_FOUND", "message": "Media tidak ditemukan."})
    if outcome == "legacy_provider_requires_domain_delete":
        raise HTTPException(409, detail={"code": "MEDIA_LEGACY_PROVIDER_DELETE_UNSUPPORTED",
                                         "message": "Media lama harus dihapus melalui lifecycle domain asal."})
    if outcome == "provider_identity_missing":
        raise HTTPException(409, detail={"code": "MEDIA_PROVIDER_IDENTITY_MISSING",
                                         "message": "Identitas asset provider tidak lengkap."})
    if outcome == "domain_delete_not_supported":
        raise HTTPException(409, detail={"code": "MEDIA_DOMAIN_DELETE_UNSUPPORTED",
                                         "message": "Penghapusan harus melalui lifecycle domain asal."})
    if outcome == "legal_hold":
        raise HTTPException(409, detail={"code": "MEDIA_LEGAL_HOLD",
                                         "message": "Media terkait konten yang sedang berada dalam legal hold."})
    if outcome == "media_in_use":
        raise HTTPException(409, detail={"code": "MEDIA_IN_USE",
                                         "message": "Media masih digunakan oleh konten aktif."})
    raise HTTPException(409, detail={"code": "MEDIA_DELETE_REJECTED", "message": "Media tidak dapat dihapus pada status saat ini."})


@router.get("/{media_id}")
async def get_media(media_id:uuid.UUID,user:dict[str,Any]=Depends(current_user)):
    base,key=_config()
    async with httpx.AsyncClient(timeout=12,trust_env=False,follow_redirects=False) as client:
        response=await client.get(f"{base}/rest/v1/content_media",params={"select":"id,content_id,owner_id,filename,media_type,size_bytes,sha256,status,scan_status,storage_provider,storage_path,provider_public_id,provider_resource_type,provider_delivery_type,provider_format,provider_version,provider_width,provider_height,provider_duration,provider_bytes,provider_delete_state,derivatives,created_at,processed_at,provider_asset_id","id":f"eq.{media_id}","owner_id":f"eq.{user['id']}","limit":"1"},headers={"apikey":key,"Authorization":f"Bearer {key}"})
    if response.status_code>=300:
        raise HTTPException(503,detail={"code":"MEDIA_DB_UNAVAILABLE","message":"Media status unavailable."})
    rows=response.json()
    if not rows:
        raise HTTPException(404,detail={"code":"MEDIA_NOT_FOUND","message":"Media not found."})
    item=rows[0]
    delivery=None
    if item.get("storage_provider")=="cloudinary" and item.get("status")=="ready":
        try:
            cfg=CloudinaryConfig.from_environment()
            delivery=build_signed_private_download_url(config=cfg,public_id=str(item["provider_public_id"]),
                resource_type=str(item["provider_resource_type"]),format=str(item["provider_format"]),expires_in=300)
            derivative_deliveries=[]
            for derivative in item.get("derivatives") or []:
                if not isinstance(derivative,dict) or derivative.get("provider")!="cloudinary":
                    continue
                derivative_url=build_signed_authenticated_delivery_url(
                    config=cfg,public_id=str(item["provider_public_id"]),
                    resource_type=str(item["provider_resource_type"]),
                    format=str(derivative["format"]),
                    transformation=str(derivative["transformation"]),
                    version=int(derivative.get("version") or item["provider_version"]),
                )
                derivative_deliveries.append({**derivative,"delivery_url":derivative_url})
        except (CloudinaryConfigurationError,ValueError,KeyError,TypeError):
            raise HTTPException(503,detail={"code":"MEDIA_DELIVERY_NOT_READY","message":"Private media delivery belum siap."})
    else:
        derivative_deliveries=[]
    return {"item":item,"delivery":{"url":delivery,"derivatives":derivative_deliveries,"expires_in_seconds":300} if delivery else None}

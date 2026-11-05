"""AI Cinema catalogue and creator project API (ENG-P13).

Uses canonical Supabase Postgres and the existing private content-media records.
No generation provider, billing policy, playback entitlement or moderation decision
is fabricated here; publication remains gated until those canonical owners act.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Any, Literal

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from allpha_api.auth import current_user
from allpha_api.operator_security import require_operator_scope, write_operator_audit

router = APIRouter(prefix="/v1/cinema", tags=["cinema"])
TITLE_FIELDS = "id,owner_id,title,original_title,synopsis,genre,language_code,maturity_rating,ai_disclosure,credits,status,moderation_status,rights_status,cover_media_id,trailer_media_id,version,created_at,updated_at,published_at"
EPISODE_FIELDS = "id,title_id,owner_id,episode_number,title,synopsis,media_id,duration_seconds,is_free_preview,status,created_at,updated_at"
GENRES = {"c_drama","k_drama","scifi","romance","thriller","animation_3d","documentary","other"}


def _credentials() -> tuple[str, str]:
    base = os.getenv("SUPABASE_URL", "").rstrip("/")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "") or os.getenv("SUPABASE_SECRET_KEY", "")
    if not base or not key:
        raise HTTPException(503, detail={"code":"CINEMA_NOT_CONFIGURED","message":"Layanan AI Cinema belum dikonfigurasi."})
    return base, key


async def _db(method: str, table: str, *, params: dict[str,str] | None = None, payload: Any = None, prefer: str | None = None) -> Any:
    base,key = _credentials()
    headers = {"apikey":key,"Authorization":f"Bearer {key}","Content-Type":"application/json","Accept":"application/json"}
    if prefer: headers["Prefer"] = prefer
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(12,connect=3)) as client:
            response = await client.request(method,f"{base}/rest/v1/{table}",headers=headers,params=params,json=payload)
    except httpx.HTTPError as exc:
        raise HTTPException(503,detail={"code":"CINEMA_DATABASE_UNAVAILABLE","message":"Data AI Cinema sementara tidak tersedia."}) from exc
    if response.status_code >= 400:
        if response.status_code == 409:
            raise HTTPException(409,detail={"code":"CINEMA_CONFLICT","message":"Data berubah; muat ulang sebelum mencoba lagi."})
        raise HTTPException(503,detail={"code":"CINEMA_PERSISTENCE_FAILED","message":"Perubahan AI Cinema tidak dapat disimpan."})
    return response.json() if response.content else None


class TitleCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1,max_length=160)
    original_title: str | None = Field(default=None,max_length=160)
    synopsis: str = Field(default="",max_length=5000)
    genre: str
    language_code: str = Field(default="id",min_length=2,max_length=12)
    maturity_rating: Literal["unrated","all_ages","13_plus","17_plus","21_plus"] = "unrated"
    ai_disclosure: str = Field(default="AI-assisted content",min_length=1,max_length=300)
    credits: list[dict[str,Any]] = Field(default_factory=list,max_length=30)


class TitleSubmitCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)
    rights_confirmed: bool
    ai_disclosure_confirmed: bool


class EpisodeCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    episode_number: int = Field(gt=0,le=10000)
    title: str = Field(min_length=1,max_length=160)
    synopsis: str = Field(default="",max_length=3000)
    media_id: uuid.UUID | None = None
    duration_seconds: int | None = Field(default=None,gt=0,le=86400)
    is_free_preview: bool = False


@router.get("/catalog")
async def public_catalog(limit: int = Query(default=24,ge=1,le=50), genre: str | None = None) -> dict[str,Any]:
    """Only public, moderated and rights-cleared titles are discoverable."""
    params = {"select":TITLE_FIELDS,"status":"eq.published","moderation_status":"eq.approved","rights_status":"eq.cleared","order":"published_at.desc","limit":str(limit)}
    if genre:
        if genre not in GENRES: raise HTTPException(422,detail={"code":"CINEMA_GENRE_INVALID","message":"Genre tidak valid."})
        params["genre"] = f"eq.{genre}"
    rows = await _db("GET","cinema_titles",params=params)
    return {"items":rows or [],"next_cursor":None}


@router.get("/creator/titles")
async def creator_titles(user: dict[str,Any] = Depends(current_user), limit: int = Query(default=50,ge=1,le=100)) -> dict[str,Any]:
    rows = await _db("GET","cinema_titles",params={"select":TITLE_FIELDS,"owner_id":f"eq.{user['id']}","order":"updated_at.desc","limit":str(limit)})
    return {"items":rows or []}


@router.post("/creator/titles",status_code=201)
async def create_title(payload: TitleCreate, user: dict[str,Any] = Depends(current_user)) -> dict[str,Any]:
    if payload.genre not in GENRES:
        raise HTTPException(422,detail={"code":"CINEMA_GENRE_INVALID","message":"Genre tidak valid."})
    rows = await _db("POST","cinema_titles",payload={**payload.model_dump(),"owner_id":user["id"],"status":"draft","moderation_status":"not_submitted","rights_status":"unverified"},prefer="return=representation")
    if not rows:
        raise HTTPException(503,detail={"code":"CINEMA_CREATE_UNCONFIRMED","message":"Draft film belum dapat dikonfirmasi."})
    return {"item":rows[0]}


@router.post("/creator/titles/{title_id}/submit-review")
async def submit_title_for_review(
    title_id: uuid.UUID,
    payload: TitleSubmitCommand,
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    if not payload.rights_confirmed or not payload.ai_disclosure_confirmed:
        raise HTTPException(422, detail={"code": "CINEMA_CREATOR_CONFIRMATIONS_REQUIRED", "message": "Konfirmasi hak atas materi dan pengungkapan penggunaan AI wajib diberikan."})
    current = await _db("GET", "cinema_titles", params={
        "select": TITLE_FIELDS, "id": f"eq.{title_id}", "owner_id": f"eq.{user['id']}",
        "status": "in.(draft,rejected)", "limit": "1",
    })
    if not current:
        raise HTTPException(404, detail={"code": "CINEMA_TITLE_NOT_EDITABLE", "message": "Draft film tidak ditemukan atau tidak dapat diajukan."})
    item = current[0]
    if int(item.get("version") or 0) != payload.expected_version:
        raise HTTPException(409, detail={"code": "CINEMA_VERSION_CHANGED", "message": "Versi draft berubah; muat ulang sebelum mengajukan review."})
    episodes = await _db("GET", "cinema_episodes", params={
        "select": "id,media_id,status", "title_id": f"eq.{title_id}",
        "owner_id": f"eq.{user['id']}", "order": "episode_number.asc",
    })
    episode_rows = episodes or []
    if not episode_rows or any(not episode.get("media_id") or episode.get("status") != "ready" for episode in episode_rows):
        raise HTTPException(409, detail={"code": "CINEMA_EPISODE_MEDIA_NOT_READY", "message": "Tambahkan minimal satu episode dan pastikan semua episode memiliki media ready serta scan clean."})
    media_ids = [str(episode["media_id"]) for episode in episode_rows]
    media_rows = await _db("GET", "content_media", params={
        "select": "id", "id": f"in.({','.join(media_ids)})",
        "owner_id": f"eq.{user['id']}", "status": "eq.ready",
        "scan_status": "eq.clean", "limit": str(min(100, len(media_ids))),
    })
    clean_ids = {str(media["id"]) for media in (media_rows or [])}
    if any(media_id not in clean_ids for media_id in media_ids):
        raise HTTPException(409, detail={"code": "CINEMA_EPISODE_MEDIA_NOT_READY", "message": "Seluruh media episode harus ready dan scan clean."})
    now = datetime.now(timezone.utc).isoformat()
    rows = await _db("PATCH", "cinema_titles", params={
        "id": f"eq.{title_id}", "owner_id": f"eq.{user['id']}",
        "status": "in.(draft,rejected)", "version": f"eq.{payload.expected_version}",
        "select": TITLE_FIELDS,
    }, payload={
        "status": "pending_review", "moderation_status": "pending",
        "rights_status": "pending", "published_at": None,
        "version": payload.expected_version + 1, "updated_at": now,
    }, prefer="return=representation")
    if not rows:
        raise HTTPException(409, detail={"code": "CINEMA_SUBMISSION_CONFLICT", "message": "Draft berubah saat pengajuan; tidak ada keputusan review yang diterapkan."})
    return {"item": rows[0]}


@router.get("/creator/titles/{title_id}/episodes")
async def creator_episodes(title_id: uuid.UUID, user: dict[str,Any] = Depends(current_user)) -> dict[str,Any]:
    title = await _db("GET","cinema_titles",params={"select":"id","id":f"eq.{title_id}","owner_id":f"eq.{user['id']}","limit":"1"})
    if not title: raise HTTPException(404,detail={"code":"CINEMA_TITLE_NOT_FOUND","message":"Draft film tidak ditemukan."})
    rows = await _db("GET","cinema_episodes",params={"select":EPISODE_FIELDS,"title_id":f"eq.{title_id}","owner_id":f"eq.{user['id']}","order":"episode_number.asc"})
    return {"items":rows or []}


@router.post("/creator/titles/{title_id}/episodes",status_code=201)
async def create_episode(title_id: uuid.UUID,payload: EpisodeCreate,user: dict[str,Any] = Depends(current_user)) -> dict[str,Any]:
    title = await _db("GET","cinema_titles",params={"select":"id","id":f"eq.{title_id}","owner_id":f"eq.{user['id']}","status":"in.(draft,rejected)","limit":"1"})
    if not title: raise HTTPException(404,detail={"code":"CINEMA_TITLE_NOT_EDITABLE","message":"Film tidak ditemukan atau tidak dapat diedit."})
    if payload.media_id:
        media = await _db("GET","content_media",params={"select":"id","id":f"eq.{payload.media_id}","owner_id":f"eq.{user['id']}","status":"eq.ready","scan_status":"eq.clean","limit":"1"})
        if not media: raise HTTPException(404,detail={"code":"CINEMA_MEDIA_NOT_OWNED","message":"Media tidak ditemukan atau bukan milik Anda."})
    rows = await _db("POST","cinema_episodes",payload={**payload.model_dump(),"title_id":str(title_id),"owner_id":user["id"],"status":"ready" if payload.media_id else "draft"},prefer="return=representation")
    if not rows: raise HTTPException(503,detail={"code":"CINEMA_EPISODE_CREATE_UNCONFIRMED","message":"Episode belum dapat dikonfirmasi."})
    return {"item":rows[0]}


@router.get("/creator/media-ready")
async def creator_ready_media(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    """Expose only this creator's fully processed and clean media for Cinema drafts."""
    rows = await _db("GET", "content_media", params={
        "select": "id,content_id,filename,media_type,size_bytes,status,scan_status,processed_at,created_at",
        "owner_id": f"eq.{user['id']}", "status": "eq.ready",
        "scan_status": "eq.clean", "order": "created_at.desc", "limit": "100",
    })
    media_rows = rows or []
    content_ids = sorted({str(row["content_id"]) for row in media_rows if row.get("content_id")})
    if not content_ids:
        return {"items": []}
    content_rows = await _db("GET", "content_items", params={
        "select": "id", "id": f"in.({','.join(content_ids)})",
        "owner_id": f"eq.{user['id']}", "status": "not.in.(deleted,archived)",
        "limit": str(min(100, len(content_ids))),
    })
    eligible_content_ids = {str(row["id"]) for row in (content_rows or [])}
    return {"items": [row for row in media_rows if str(row.get("content_id")) in eligible_content_ids]}


@router.get("/creator/status")
async def creator_capability_status(user: dict[str,Any] = Depends(current_user)) -> dict[str,Any]:
    # The endpoint reports configuration only; it never exposes balances or estimates.
    policies = await _db("GET","credit_policy_versions",params={"select":"policy_version,status","status":"eq.approved","limit":"1"})
    return {"catalog":"available","project_drafts":"available","media":"existing_content_media_pipeline","generation":"unavailable" if not policies else "policy_present_runtime_unverified","generation_jobs":"not_implemented","billing":"not_configured","playback_entitlement":"not_configured","generation_reason":None if policies else "APPROVED_CREDIT_POLICY_MISSING","billing_reason":"PAYMENT_PROVIDER_AND_BILLING_POLICY_NOT_APPROVED","entitlement_reason":"PLAYBACK_ENTITLEMENT_CONTRACT_NOT_IMPLEMENTED"}

class CinemaModerationCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Literal["approve", "reject"]
    expected_version: int = Field(ge=1)
    reason: str = Field(min_length=8, max_length=500)


class CinemaRightsReviewCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Literal["clear", "reject"]
    expected_version: int = Field(ge=1)
    evidence_reference: str = Field(min_length=8, max_length=500)
    reason: str = Field(min_length=8, max_length=500)


class CinemaLifecycleCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["archive", "block", "restore_to_draft"]
    expected_version: int = Field(ge=1)
    reason: str = Field(min_length=8, max_length=500)


@router.get("/admin/moderation-queue")
async def cinema_moderation_queue(
    request: Request,
    limit: int = Query(default=50, ge=1, le=100),
    operator: dict[str, Any] = Depends(require_operator_scope("platform:content.moderate")),
) -> dict[str, Any]:
    rows = await _db("GET", "cinema_titles", params={
        "select": TITLE_FIELDS,
        "status": "eq.pending_review",
        "moderation_status": "eq.pending",
        "order": "updated_at.asc",
        "limit": str(limit),
    })
    items = rows or []
    await write_operator_audit(
        request, actor_user_id=str(operator["id"]), action="cinema.moderation_queue.read",
        outcome="allowed", resource_type="cinema_queue", resource_id="pending",
        metadata={"count": len(items)},
    )
    return {"items": items}


@router.get("/admin/rights-queue")
async def cinema_rights_queue(
    request: Request,
    limit: int = Query(default=50, ge=1, le=100),
    operator: dict[str, Any] = Depends(require_operator_scope("platform:content.moderate")),
) -> dict[str, Any]:
    rows = await _db("GET", "cinema_titles", params={
        "select": TITLE_FIELDS,
        "rights_status": "eq.pending",
        "status": "eq.pending_review",
        "order": "updated_at.asc",
        "limit": str(limit),
    })
    items = rows or []
    await write_operator_audit(
        request, actor_user_id=str(operator["id"]), action="cinema.rights_queue.read",
        outcome="allowed", resource_type="cinema_rights_queue", resource_id="unverified",
        metadata={"count": len(items)},
    )
    return {"items": items}


@router.post("/admin/titles/{title_id}/rights-review")
async def review_cinema_rights(
    title_id: uuid.UUID,
    payload: CinemaRightsReviewCommand,
    request: Request,
    operator: dict[str, Any] = Depends(require_operator_scope("platform:content.moderate")),
) -> dict[str, Any]:
    current = await _db("GET", "cinema_titles", params={
        "select": TITLE_FIELDS, "id": f"eq.{title_id}",
        "rights_status": "eq.pending", "status": "eq.pending_review", "limit": "1",
    })
    if not current:
        raise HTTPException(404, detail={"code": "CINEMA_RIGHTS_REVIEW_NOT_FOUND", "message": "Judul tidak ditemukan atau haknya sudah ditinjau."})
    item = current[0]
    if int(item.get("version") or 0) != payload.expected_version:
        raise HTTPException(409, detail={"code": "CINEMA_VERSION_CHANGED", "message": "Versi judul berubah; muat ulang antrean."})
    await write_operator_audit(
        request, actor_user_id=str(operator["id"]), action="cinema.rights.review",
        outcome="attempted", resource_type="cinema_title", resource_id=str(title_id),
        metadata={"decision": payload.decision, "expected_version": payload.expected_version,
                  "evidence_reference": payload.evidence_reference, "reason": payload.reason},
    )
    rows = await _db("PATCH", "cinema_titles", params={
        "id": f"eq.{title_id}", "version": f"eq.{payload.expected_version}",
        "rights_status": "eq.pending", "status": "eq.pending_review", "select": TITLE_FIELDS,
    }, payload={
        "rights_status": "cleared" if payload.decision == "clear" else "rejected",
        "version": payload.expected_version + 1,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }, prefer="return=representation")
    if not rows:
        raise HTTPException(409, detail={"code": "CINEMA_RIGHTS_REVIEW_CONFLICT", "message": "Status hak berubah saat peninjauan; keputusan tidak diterapkan."})
    await write_operator_audit(
        request, actor_user_id=str(operator["id"]), action="cinema.rights.review",
        outcome="allowed", resource_type="cinema_title", resource_id=str(title_id),
        metadata={"decision": payload.decision, "version": payload.expected_version + 1,
                  "evidence_reference": payload.evidence_reference, "reason": payload.reason},
    )
    return {"item": rows[0]}


@router.post("/admin/titles/{title_id}/moderation")
async def review_cinema_moderation(
    title_id: uuid.UUID,
    payload: CinemaModerationCommand,
    request: Request,
    operator: dict[str, Any] = Depends(require_operator_scope("platform:content.moderate")),
) -> dict[str, Any]:
    current = await _db("GET", "cinema_titles", params={
        "select": TITLE_FIELDS, "id": f"eq.{title_id}",
        "status": "eq.pending_review", "moderation_status": "eq.pending", "limit": "1",
    })
    if not current:
        raise HTTPException(404, detail={"code": "CINEMA_MODERATION_NOT_FOUND", "message": "Judul tidak ditemukan di antrean moderasi."})
    item = current[0]
    if int(item.get("version") or 0) != payload.expected_version:
        raise HTTPException(409, detail={"code": "CINEMA_VERSION_CHANGED", "message": "Versi judul berubah; muat ulang antrean."})
    if payload.decision == "approve":
        if item.get("rights_status") != "cleared":
            raise HTTPException(409, detail={"code": "CINEMA_RIGHTS_NOT_CLEARED", "message": "Moderasi tidak dapat menerbitkan judul sebelum hak cipta berstatus cleared."})
        episodes = await _db("GET", "cinema_episodes", params={
            "select": "id,media_id,status", "title_id": f"eq.{title_id}",
            "owner_id": f"eq.{item['owner_id']}", "order": "episode_number.asc",
        })
        episode_rows = episodes or []
        if not episode_rows or any(not episode.get("media_id") or episode.get("status") != "ready" for episode in episode_rows):
            raise HTTPException(409, detail={"code": "CINEMA_EPISODE_MEDIA_NOT_READY", "message": "Semua episode harus memiliki media yang siap sebelum publikasi."})
        media_ids = [str(episode["media_id"]) for episode in episode_rows]
        if item.get("cover_media_id"):
            media_ids.append(str(item["cover_media_id"]))
        if item.get("trailer_media_id"):
            media_ids.append(str(item["trailer_media_id"]))
        media_rows = await _db("GET", "content_media", params={
            "select": "id", "id": f"in.({','.join(media_ids)})",
            "owner_id": f"eq.{item['owner_id']}", "status": "eq.ready",
            "scan_status": "eq.clean", "limit": str(min(100, len(media_ids))),
        })
        clean_ids = {str(media["id"]) for media in (media_rows or [])}
        if any(media_id not in clean_ids for media_id in media_ids):
            raise HTTPException(409, detail={"code": "CINEMA_EPISODE_MEDIA_NOT_READY", "message": "Semua media episode, cover, dan trailer harus ready serta scan berstatus clean sebelum publikasi."})
    await write_operator_audit(
        request, actor_user_id=str(operator["id"]), action="cinema.moderation.review",
        outcome="attempted", resource_type="cinema_title", resource_id=str(title_id),
        metadata={"decision": payload.decision, "expected_version": payload.expected_version, "reason": payload.reason},
    )
    now = datetime.now(timezone.utc).isoformat()
    allowed = payload.decision == "approve"
    rows = await _db("PATCH", "cinema_titles", params={
        "id": f"eq.{title_id}", "version": f"eq.{payload.expected_version}",
        "status": "eq.pending_review", "moderation_status": "eq.pending",
        "select": TITLE_FIELDS,
    }, payload={
        "status": "published" if allowed else "rejected",
        "moderation_status": "approved" if allowed else "rejected",
        "published_at": now if allowed else None,
        "version": payload.expected_version + 1,
        "updated_at": now,
    }, prefer="return=representation")
    if not rows:
        raise HTTPException(409, detail={"code": "CINEMA_MODERATION_CONFLICT", "message": "Judul berubah saat moderasi; keputusan tidak diterapkan."})
    await write_operator_audit(
        request, actor_user_id=str(operator["id"]), action="cinema.moderation.review",
        outcome="allowed", resource_type="cinema_title", resource_id=str(title_id),
        metadata={"decision": payload.decision, "version": payload.expected_version + 1, "reason": payload.reason},
    )
    return {"item": rows[0]}


@router.get("/admin/lifecycle-queue")
async def cinema_lifecycle_queue(
    request: Request,
    limit: int = Query(default=100, ge=1, le=100),
    operator: dict[str, Any] = Depends(require_operator_scope("platform:content.moderate")),
) -> dict[str, Any]:
    rows = await _db("GET", "cinema_titles", params={
        "select": TITLE_FIELDS, "order": "updated_at.desc", "limit": str(limit),
    })
    items = rows or []
    await write_operator_audit(
        request, actor_user_id=str(operator["id"]), action="cinema.lifecycle_queue.read",
        outcome="allowed", resource_type="cinema_lifecycle_queue", resource_id="recent",
        metadata={"count": len(items)},
    )
    return {"items": items}


@router.post("/admin/titles/{title_id}/lifecycle")
async def manage_cinema_lifecycle(
    title_id: uuid.UUID,
    payload: CinemaLifecycleCommand,
    request: Request,
    operator: dict[str, Any] = Depends(require_operator_scope("platform:content.moderate")),
) -> dict[str, Any]:
    current = await _db("GET", "cinema_titles", params={
        "select": TITLE_FIELDS, "id": f"eq.{title_id}", "limit": "1",
    })
    if not current:
        raise HTTPException(404, detail={"code": "CINEMA_TITLE_NOT_FOUND", "message": "Judul AI Cinema tidak ditemukan."})
    item = current[0]
    if int(item.get("version") or 0) != payload.expected_version:
        raise HTTPException(409, detail={"code": "CINEMA_VERSION_CHANGED", "message": "Versi judul berubah; muat ulang sebelum lifecycle action."})
    transitions = {
        "archive": {"from": {"draft", "rejected", "published"}, "to": "archived"},
        "block": {"from": {"draft", "processing", "pending_review", "published", "rejected"}, "to": "blocked"},
        "restore_to_draft": {"from": {"archived", "blocked"}, "to": "draft"},
    }
    transition = transitions[payload.action]
    if item.get("status") not in transition["from"]:
        raise HTTPException(409, detail={"code": "CINEMA_LIFECYCLE_TRANSITION_INVALID", "message": "Transisi lifecycle tidak diizinkan dari status saat ini."})
    await write_operator_audit(
        request, actor_user_id=str(operator["id"]), action="cinema.lifecycle.manage",
        outcome="attempted", resource_type="cinema_title", resource_id=str(title_id),
        metadata={"action": payload.action, "from": item.get("status"), "reason": payload.reason},
    )
    now = datetime.now(timezone.utc).isoformat()
    rows = await _db("PATCH", "cinema_titles", params={
        "id": f"eq.{title_id}", "version": f"eq.{payload.expected_version}",
        "status": f"eq.{item['status']}", "select": TITLE_FIELDS,
    }, payload={
        "status": transition["to"],
        "moderation_status": "needs_changes" if payload.action == "restore_to_draft" else item.get("moderation_status"),
        "published_at": None if payload.action != "restore_to_draft" else None,
        "version": payload.expected_version + 1,
        "updated_at": now,
    }, prefer="return=representation")
    if not rows:
        raise HTTPException(409, detail={"code": "CINEMA_LIFECYCLE_CONFLICT", "message": "Judul berubah saat lifecycle action; perubahan tidak diterapkan."})
    await write_operator_audit(
        request, actor_user_id=str(operator["id"]), action="cinema.lifecycle.manage",
        outcome="allowed", resource_type="cinema_title", resource_id=str(title_id),
        metadata={"action": payload.action, "to": transition["to"], "version": payload.expected_version + 1, "reason": payload.reason},
    )
    return {"item": rows[0]}


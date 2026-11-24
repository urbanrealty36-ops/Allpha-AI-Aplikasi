"""AI Cinema catalogue and creator project API (ENG-P13).

Uses canonical Supabase Postgres and the existing private content-media records.
No generation provider, billing policy, playback entitlement or moderation decision
is fabricated here; publication remains gated until those canonical owners act.
"""
from __future__ import annotations

import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Literal
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field

import allpha_api.generation_jobs_api as generation_jobs_api

from allpha_api.auth import current_user, optional_current_user
from allpha_api.content_api import _signed_media_preview_url
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
    headers = {"apikey":key,"Content-Type":"application/json","Accept":"application/json"}
    if os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip():
        headers["Authorization"] = f"Bearer {os.getenv('SUPABASE_SERVICE_ROLE_KEY', '').strip()}"
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


class TitleUpdateCommand(BaseModel):
    model_config = ConfigDict(extra='forbid')
    expected_version: int = Field(ge=1)
    title: str | None = Field(default=None,min_length=1,max_length=160)
    original_title: str | None = Field(default=None,max_length=160)
    synopsis: str | None = Field(default=None,max_length=5000)
    genre: str | None = None
    language_code: str | None = Field(default=None,max_length=12)
    maturity_rating: str | None = None
    ai_disclosure: str | None = Field(default=None,max_length=1000)


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

class CinemaScreenplay(BaseModel):
    model_config = ConfigDict(extra="forbid")
    logline: str = Field(default="", max_length=1000)
    synopsis: str = Field(default="", max_length=5000)
    draft: str = Field(default="", max_length=60000)


class CinemaDialogueLine(BaseModel):
    model_config = ConfigDict(extra="forbid")
    character: str = Field(min_length=1, max_length=100)
    line: str = Field(min_length=1, max_length=2000)


class CinemaScene(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scene_id: uuid.UUID
    scene_number: int = Field(ge=1, le=1000)
    slugline: str = Field(min_length=1, max_length=250)
    location: str = Field(default="", max_length=160)
    time_of_day: Literal["day", "night", "dawn", "dusk", "continuous", "unspecified"] = "unspecified"
    action: str = Field(default="", max_length=5000)
    dialogue: list[CinemaDialogueLine] = Field(default_factory=list, max_length=100)


class CinemaStoryboardShot(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scene_number: int = Field(ge=1, le=1000)
    shot_number: int = Field(ge=1, le=1000)
    framing: str = Field(default="", max_length=100)
    camera_movement: str = Field(default="", max_length=100)
    description: str = Field(min_length=1, max_length=2000)
    visual_prompt: str = Field(default="", max_length=2000)
    image_media_id: uuid.UUID | None = None
    duration_ms: int = Field(default=3000, ge=100, le=120000)


class CinemaTimelineClip(BaseModel):
    model_config = ConfigDict(extra="forbid")
    clip_id: uuid.UUID
    media_id: uuid.UUID
    start_ms: int = Field(ge=0, le=86_400_000)
    duration_ms: int = Field(gt=0, le=86_400_000)
    trim_start_ms: int = Field(default=0, ge=0, le=86_400_000)
    trim_end_ms: int | None = Field(default=None, ge=1, le=86_400_000)
    volume: float = Field(default=1.0, ge=0, le=2)


class CinemaTimelineTrack(BaseModel):
    model_config = ConfigDict(extra="forbid")
    track_id: uuid.UUID
    kind: Literal["video", "audio", "subtitle"]
    label: str = Field(min_length=1, max_length=120)
    clips: list[CinemaTimelineClip] = Field(default_factory=list, max_length=200)


class CinemaTimeline(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tracks: list[CinemaTimelineTrack] = Field(default_factory=list, max_length=30)


class CinemaAudioTrack(BaseModel):
    model_config = ConfigDict(extra="forbid")
    track_id: uuid.UUID
    media_id: uuid.UUID
    label: str = Field(min_length=1, max_length=120)
    start_ms: int = Field(default=0, ge=0, le=86_400_000)
    duration_ms: int = Field(gt=0, le=86_400_000)
    volume: float = Field(default=1.0, ge=0, le=2)


class CinemaExportProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    container: Literal["mp4"] = "mp4"
    resolution: Literal["720p", "1080p", "4k"] = "1080p"
    frame_rate: Literal[24, 25, 30, 50, 60] = 24
    aspect_ratio: Literal["16:9", "9:16", "1:1", "4:3", "21:9"] = "16:9"


class CinemaProductionDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[1] = 1
    screenplay: CinemaScreenplay = Field(default_factory=CinemaScreenplay)
    storyboard: list[CinemaStoryboardShot] = Field(default_factory=list, max_length=500)
    scenes: list[CinemaScene] = Field(default_factory=list, max_length=1000)
    timeline: CinemaTimeline = Field(default_factory=CinemaTimeline)
    audio_tracks: list[CinemaAudioTrack] = Field(default_factory=list, max_length=100)
    export_profile: CinemaExportProfile = Field(default_factory=CinemaExportProfile)


class CinemaProductionWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)
    document: CinemaProductionDocument


class CinemaAssetAttach(BaseModel):
    model_config = ConfigDict(extra="forbid")
    media_id: uuid.UUID
    asset_role: Literal["reference", "storyboard", "source_video", "source_audio", "music",
                        "subtitle", "generated_image", "generated_video", "cover", "trailer"]
    display_name: str = Field(min_length=1, max_length=160)


class CinemaGenerationCreate(generation_jobs_api.GenerationJobCreate):
    target_section: Literal["screenplay_draft"] = "screenplay_draft"


class CinemaGenerationApply(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)


@router.get("/catalog")
async def public_catalog(limit: int = Query(default=24,ge=1,le=50), genre: str | None = None) -> dict[str,Any]:
    """Return only public titles and server-derived, permission-safe catalogue metadata."""
    params = {"select":TITLE_FIELDS,"status":"eq.published","moderation_status":"eq.approved","rights_status":"eq.cleared","order":"published_at.desc","limit":str(limit)}
    if genre:
        if genre not in GENRES: raise HTTPException(422,detail={"code":"CINEMA_GENRE_INVALID","message":"Genre tidak valid."})
        params["genre"] = f"eq.{genre}"
    rows = await _db("GET","cinema_titles",params=params)
    titles = rows or []
    if not titles:
        return {"items":[],"next_cursor":None}

    title_ids = [str(item["id"]) for item in titles if item.get("id")]
    episode_rows = await _db("GET","cinema_episodes",params={
        "select":"id,title_id,owner_id", "title_id":"in.("+",".join(title_ids)+")",
        "status":"eq.ready", "limit":"5000",
    })
    episode_counts: dict[str,int] = {}
    title_owner = {str(item["id"]):str(item["owner_id"]) for item in titles}
    for episode in episode_rows or []:
        title_id = str(episode.get("title_id") or "")
        if title_id in title_owner and str(episode.get("owner_id")) == title_owner[title_id]:
            episode_counts[title_id] = episode_counts.get(title_id,0) + 1

    media_ids = sorted({str(item[key]) for item in titles for key in ("cover_media_id","trailer_media_id") if item.get(key)})
    media_by_id: dict[str,dict[str,Any]] = {}
    if media_ids:
        media_rows = await _db("GET","content_media",params={
            "select":"id,owner_id,storage_path,media_type,status,scan_status,processed_at,derivatives",
            "id":"in.("+",".join(media_ids)+")", "status":"eq.ready", "scan_status":"eq.clean",
            "limit":str(min(100,len(media_ids))),
        })
        media_by_id = {
            str(media["id"]):media for media in (media_rows or [])
            if media.get("processed_at") and isinstance(media.get("derivatives"),list)
            and media.get("storage_path")
        }

    for item in titles:
        title_id = str(item["id"])
        item["episodes_count"] = episode_counts.get(title_id,0)
        for source_key, output_key in (("cover_media_id","cover_preview_url"),("trailer_media_id","trailer_preview_url")):
            media = media_by_id.get(str(item.get(source_key) or ""))
            if not media or str(media.get("owner_id")) != str(item.get("owner_id")):
                item[output_key] = None
                continue
            media_type = str(media.get("media_type") or "").lower()
            derivatives = media.get("derivatives") or []
            if output_key == "cover_preview_url":
                if not media_type.startswith("image/"):
                    item[output_key] = None
                    continue
                preferred = next((d.get("storage_path") for d in derivatives
                    if isinstance(d,dict) and d.get("kind") in ("display","rendition_1","thumbnail")
                    and isinstance(d.get("storage_path"),str) and d.get("storage_path")),None)
            elif media_type.startswith("video/"):
                # The catalogue renders this field as a poster image, never as a video URL.
                preferred = next((d.get("storage_path") for d in derivatives
                    if isinstance(d,dict) and d.get("kind") in ("moderation_poster","thumbnail","poster")
                    and isinstance(d.get("storage_path"),str) and d.get("storage_path")),None)
                if not preferred:
                    item[output_key] = None
                    continue
            elif media_type.startswith("image/"):
                preferred = next((d.get("storage_path") for d in derivatives
                    if isinstance(d,dict) and d.get("kind") in ("display","rendition_1","thumbnail")
                    and isinstance(d.get("storage_path"),str) and d.get("storage_path")),None)
            else:
                item[output_key] = None
                continue
            try:
                item[output_key] = await _signed_media_preview_url(preferred or str(media["storage_path"]),expires_in=300)
            except HTTPException:
                item[output_key] = None
    return {"items":titles,"next_cursor":None}



@router.get("/titles/{title_id}/playback")
async def title_playback(title_id: uuid.UUID, user: dict[str, Any] | None = Depends(optional_current_user)) -> dict[str,Any]:
    """Return catalogue metadata only; private playback URLs require a durable session."""
    titles = await _db("GET","cinema_titles",params={
        "select":TITLE_FIELDS,"id":f"eq.{title_id}","status":"eq.published",
        "moderation_status":"eq.approved","rights_status":"eq.cleared","limit":"1",
    })
    if not titles:
        raise HTTPException(404,detail={"code":"CINEMA_TITLE_NOT_AVAILABLE","message":"Judul belum tersedia untuk ditonton."})
    title=titles[0]
    episodes=await _db("GET","cinema_episodes",params={
        "select":EPISODE_FIELDS,"title_id":f"eq.{title_id}","owner_id":f"eq.{title['owner_id']}",
        "status":"eq.ready","order":"episode_number.asc","limit":"500",
    })
    return {
        "title":{"id":title["id"],"title":title["title"],"maturity_rating":title["maturity_rating"]},
        "episodes":[{
            "id":episode["id"],"episode_number":episode["episode_number"],"title":episode["title"],
            "synopsis":episode.get("synopsis"),"duration_seconds":episode.get("duration_seconds"),
            "is_free_preview":episode.get("is_free_preview") is True,
            "locked":True,"session_required":True,"playback_url":None,
            "lock_reason":"CINEMA_PLAYBACK_SESSION_REQUIRED",
        } for episode in (episodes or [])],
        "premium_entitled":False,
        "playback_mode":"session_required",
        "message":"URL media hanya diterbitkan oleh endpoint playback-session setelah pemeriksaan policy dan entitlement.",
    }


async def _title_access(title_id: uuid.UUID, user_id: str, scopes: set[str]) -> dict[str,Any]:
    rows=await _db("GET","cinema_titles",params={
        "select":"id,owner_id,status,version,title","id":"eq."+str(title_id),"limit":"1",
    })
    if not rows:
        raise HTTPException(404,detail={"code":"CINEMA_TITLE_NOT_FOUND","message":"Judul Cinema tidak ditemukan."})
    title=rows[0]
    if str(title["owner_id"])==user_id:
        return title
    grants=await _db("GET","cinema_collaborators",params={
        "select":"permissions,status,expires_at","title_id":"eq."+str(title_id),
        "owner_id":"eq."+str(title["owner_id"]),"collaborator_user_id":"eq."+user_id,
        "status":"eq.active","limit":"20",
    })
    now=datetime.now(timezone.utc)
    for grant in grants or []:
        expiry=grant.get("expires_at")
        if expiry:
            parsed=datetime.fromisoformat(expiry.replace("Z","+00:00"))
            if parsed<=now:
                continue
        if scopes.intersection(set(grant.get("permissions") or [])):
            return title
    raise HTTPException(403,detail={"code":"CINEMA_COLLABORATOR_PERMISSION_REQUIRED","message":"Akses collaborator untuk tindakan ini belum diberikan."})


async def _title_media_owner_ids(title: dict[str,Any]) -> set[str]:
    owners={str(title["owner_id"])}
    grants=await _db("GET","cinema_collaborators",params={
        "select":"collaborator_user_id,permissions,expires_at","title_id":"eq."+str(title["id"]),
        "owner_id":"eq."+str(title["owner_id"]),"status":"eq.active","limit":"100",
    })
    now=datetime.now(timezone.utc)
    for grant in grants or []:
        expiry=grant.get("expires_at")
        if expiry and datetime.fromisoformat(expiry.replace("Z","+00:00"))<=now:
            continue
        if "upload_episodes" in (grant.get("permissions") or []) and grant.get("collaborator_user_id"):
            owners.add(str(grant["collaborator_user_id"]))
    return owners

def _production_document_media_ids(document: CinemaProductionDocument) -> set[str]:
    ids = {
        str(shot.image_media_id) for shot in document.storyboard
        if shot.image_media_id is not None
    }
    for track in document.timeline.tracks:
        ids.update(str(clip.media_id) for clip in track.clips)
    ids.update(str(track.media_id) for track in document.audio_tracks)
    return ids


@router.get("/creator/titles/{title_id}/production")
async def get_cinema_production(title_id: uuid.UUID, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    title = await _title_access(title_id, str(user["id"]), {"edit_metadata", "upload_episodes"})
    rows = await _db("GET", "cinema_titles", params={
        "select": "id,owner_id,status,version,production_document",
        "id": "eq." + str(title_id), "owner_id": "eq." + str(title["owner_id"]), "limit": "1",
    })
    if not rows:
        raise HTTPException(404, detail={"code": "CINEMA_TITLE_NOT_FOUND", "message": "Judul Cinema tidak ditemukan."})
    document = CinemaProductionDocument.model_validate(rows[0].get("production_document") or {})
    return {
        "title_id": str(title_id), "version": int(rows[0].get("version") or 1),
        "status": rows[0].get("status"), "document": document.model_dump(mode="json"),
    }


@router.put("/creator/titles/{title_id}/production")
async def save_cinema_production(
    title_id: uuid.UUID, payload: CinemaProductionWrite,
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    title = await _title_access(title_id, str(user["id"]), {"edit_metadata"})
    if title.get("status") not in {"draft", "rejected"}:
        raise HTTPException(409, detail={"code": "CINEMA_PRODUCTION_LOCKED", "message": "Production document hanya dapat diubah pada draft atau judul yang dikembalikan."})
    document = payload.document
    encoded = document.model_dump(mode="json")
    if len(json.dumps(encoded, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")) > 262144:
        raise HTTPException(422, detail={"code": "CINEMA_PRODUCTION_DOCUMENT_TOO_LARGE", "message": "Production document melebihi batas 256 KiB."})
    media_ids = _production_document_media_ids(document)
    if media_ids:
        assets = await _db("GET", "cinema_assets", params={
            "select": "media_id", "title_id": "eq." + str(title_id),
            "owner_id": "eq." + str(title["owner_id"]),
            "media_id": "in.(" + ",".join(sorted(media_ids)) + ")", "limit": "1000",
        })
        linked_ids = {str(item.get("media_id")) for item in assets or []}
        if linked_ids != media_ids:
            raise HTTPException(422, detail={
                "code": "CINEMA_PRODUCTION_ASSET_NOT_LINKED",
                "message": "Semua media pada storyboard, timeline, dan audio harus lebih dahulu ditautkan ke Asset Library film.",
                "unlinked_media_ids": sorted(media_ids - linked_ids),
            })
    rows = await _db("PATCH", "cinema_titles", params={
        "id": "eq." + str(title_id), "owner_id": "eq." + str(title["owner_id"]),
        "status": "in.(draft,rejected)", "version": "eq." + str(payload.expected_version),
        "select": "id,version,status,production_document,updated_at",
    }, payload={
        "production_document": encoded,
        "version": payload.expected_version + 1,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }, prefer="return=representation")
    if not rows:
        raise HTTPException(409, detail={"code": "CINEMA_PRODUCTION_VERSION_CONFLICT", "message": "Versi production berubah atau akses edit telah dicabut."})
    return {"item": rows[0]}


@router.get("/creator/production-readiness")
async def cinema_production_readiness(
    request: Request,
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    """Return truthful, non-billable readiness for the authenticated Cinema creator.

    This endpoint never starts generation or reserves credits. It reports the
    canonical database/schema and Model Router gates so clients can distinguish
    an unavailable production service from an empty creator catalogue.
    """
    del user  # Authentication is required; readiness itself is not user-specific.
    checks: dict[str, Any] = {
        "api_credentials": "ready",
        "generation_schema": "not_checked",
        "model_router": "not_checked",
    }
    try:
        _credentials()
    except HTTPException:
        checks["api_credentials"] = "not_configured"
    if checks["api_credentials"] == "ready":
        try:
            readiness = await _db("POST", "rpc/cinema_generation_schema_readiness", payload={})
            checks["generation_schema"] = (
                "ready" if isinstance(readiness, dict) and readiness.get("ready") is True
                else "incomplete"
            )
        except HTTPException:
            checks["generation_schema"] = "unavailable"

    router_instance = getattr(request.app.state, "text_generation_router", None)
    if router_instance is None or not callable(getattr(router_instance, "preflight", None)):
        checks["model_router"] = "not_configured"
    else:
        try:
            await router_instance.preflight("private")
            checks["model_router"] = "ready"
        except Exception:
            # Provider, tariff, policy and metering details remain server-side.
            checks["model_router"] = "not_ready"

    ready = all(value == "ready" for value in checks.values())
    return {
        "status": "ready" if ready else "not_ready",
        "can_create_generation_job": ready,
        "checks": checks,
        "billing": "verified_during_generation_quote",
        "message": (
            "Layanan AI Cinema siap menerima generation job."
            if ready else
            "Layanan AI Cinema belum siap. Periksa konfigurasi database, schema, Model Router, kebijakan, tarif, dan metering."
        ),
    }


async def _require_cinema_generation_schema() -> None:
    try:
        readiness = await _db("POST", "rpc/cinema_generation_schema_readiness", payload={})
    except HTTPException as exc:
        raise HTTPException(503, detail={
            "code": "CINEMA_GENERATION_SCHEMA_NOT_READY",
            "message": "Schema Cinema Generation belum diterapkan melalui migration canonical.",
        }) from exc
    if not isinstance(readiness, dict) or readiness.get("ready") is not True:
        missing = readiness.get("missing") if isinstance(readiness, dict) else []
        raise HTTPException(503, detail={
            "code": "CINEMA_GENERATION_SCHEMA_NOT_READY",
            "message": "Schema Cinema Generation belum lengkap; Generation Job tidak dibuat agar AI Credits tidak ter-reserve tanpa link Cinema.",
            "missing": missing if isinstance(missing, list) else [],
        })


async def _require_cinema_generation_link(
    title_id: uuid.UUID, job_id: uuid.UUID, user: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    await _require_cinema_generation_schema()
    title = await _title_access(title_id, str(user["id"]), {"edit_metadata"})
    rows = await _db("GET", "cinema_generation_job_links", params={
        "select": "generation_job_id,title_id,owner_id,requester_user_id,target_section,expected_title_version,idempotency_key,applied_at,applied_version",
        "generation_job_id": "eq." + str(job_id),
        "title_id": "eq." + str(title_id),
        "owner_id": "eq." + str(title["owner_id"]),
        "requester_user_id": "eq." + str(user["id"]),
        "limit": "1",
    })
    if not rows:
        raise HTTPException(404, detail={
            "code": "CINEMA_GENERATION_JOB_NOT_FOUND",
            "message": "Generation job tidak terhubung ke judul Cinema ini.",
        })
    return title, rows[0]


@router.post("/creator/titles/{title_id}/generation-jobs", status_code=202)
async def create_cinema_generation_job(
    title_id: uuid.UUID, payload: CinemaGenerationCreate, request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    if not idempotency_key or not 8 <= len(idempotency_key) <= 160:
        raise HTTPException(400, detail={
            "code": "IDEMPOTENCY_KEY_REQUIRED",
            "message": "Idempotency-Key 8–160 karakter wajib dikirim.",
        })
    title = await _title_access(title_id, str(user["id"]), {"edit_metadata"})
    if title.get("status") not in {"draft", "rejected"}:
        raise HTTPException(409, detail={
            "code": "CINEMA_PRODUCTION_LOCKED",
            "message": "AI screenplay generation hanya tersedia untuk draft atau judul yang dikembalikan.",
        })
    await _require_cinema_generation_schema()
    generation_payload = generation_jobs_api.GenerationJobCreate.model_validate(
        payload.model_dump(exclude={"target_section"})
    )
    # Reuse the canonical Generation Job, Model Router, credit reservation,
    # moderation, private artifact storage, retry and cancellation lifecycle.
    job = await generation_jobs_api.create_generation_job(
        generation_payload, request, idempotency_key, user,
    )
    job_id = str(job.get("job_id") or "")
    if not job_id:
        raise HTTPException(503, detail={
            "code": "CINEMA_GENERATION_JOB_UNCONFIRMED",
            "message": "Canonical Generation Job belum dapat dikonfirmasi.",
        })
    link_payload = {
        "generation_job_id": job_id, "title_id": str(title_id),
        "owner_id": str(title["owner_id"]), "requester_user_id": str(user["id"]),
        "target_section": payload.target_section,
        "expected_title_version": int(title.get("version") or 1),
        "idempotency_key": idempotency_key,
    }
    try:
        links = await _db(
            "POST", "cinema_generation_job_links",
            params={"on_conflict": "requester_user_id,idempotency_key"},
            payload=link_payload,
            prefer="resolution=ignore-duplicates,return=representation",
        )
    except HTTPException:
        # Job creation already reserved credits. If the Cinema association cannot
        # be persisted, compensate only a newly-created queued job; never cancel
        # an idempotent replay that may be owned by a prior successful request.
        if not job.get("idempotent_replay"):
            try:
                await generation_jobs_api.cancel_generation_job(uuid.UUID(job_id), user)
            except HTTPException:
                pass  # Running jobs are reconciled by the canonical generation lifecycle.
        raise
    if not links:
        existing = await _db("GET", "cinema_generation_job_links", params={
            "select": "generation_job_id,title_id,owner_id,target_section,expected_title_version",
            "requester_user_id": "eq." + str(user["id"]),
            "idempotency_key": "eq." + idempotency_key, "limit": "1",
        })
        if (not existing or str(existing[0].get("generation_job_id")) != job_id
                or str(existing[0].get("title_id")) != str(title_id)
                or str(existing[0].get("owner_id")) != str(title["owner_id"])
                or existing[0].get("target_section") != payload.target_section):
            if not job.get("idempotent_replay"):
                try:
                    await generation_jobs_api.cancel_generation_job(uuid.UUID(job_id), user)
                except HTTPException:
                    pass
            raise HTTPException(409, detail={
                "code": "CINEMA_GENERATION_IDEMPOTENCY_CONFLICT",
                "message": "Idempotency-Key telah digunakan untuk konteks Cinema yang berbeda.",
            })
    return {
        "job_id": job_id, "task_id": job.get("task_id"), "status": job.get("status"),
        "idempotent_replay": bool(job.get("idempotent_replay")),
        "target_section": payload.target_section,
        "expected_title_version": int(title.get("version") or 1),
        "reserved_credits": job.get("reserved_credits"),
    }


@router.get("/creator/titles/{title_id}/generation-jobs/{job_id}")
async def get_cinema_generation_job(
    title_id: uuid.UUID, job_id: uuid.UUID, user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    _, link = await _require_cinema_generation_link(title_id, job_id, user)
    result = await generation_jobs_api.get_generation_job(job_id, user)
    return {
        **result, "target_section": link["target_section"],
        "expected_title_version": link["expected_title_version"],
        "applied_at": link.get("applied_at"), "applied_version": link.get("applied_version"),
    }


@router.post("/creator/titles/{title_id}/generation-jobs/{job_id}/cancel")
async def cancel_cinema_generation_job(
    title_id: uuid.UUID, job_id: uuid.UUID, user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    await _require_cinema_generation_link(title_id, job_id, user)
    return await generation_jobs_api.cancel_generation_job(job_id, user)


@router.get("/creator/titles/{title_id}/generation-jobs/{job_id}/artifact")
async def get_cinema_generation_artifact(
    title_id: uuid.UUID, job_id: uuid.UUID, user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    await _require_cinema_generation_link(title_id, job_id, user)
    return await generation_jobs_api.get_generation_artifact(job_id, user)


@router.post("/creator/titles/{title_id}/generation-jobs/{job_id}/apply")
async def apply_cinema_generation_job(
    title_id: uuid.UUID, job_id: uuid.UUID, payload: CinemaGenerationApply,
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    title, link = await _require_cinema_generation_link(title_id, job_id, user)
    if link.get("applied_at"):
        return {
            "outcome": "replayed", "generation_job_id": str(job_id),
            "title_id": str(title_id), "title_version": link.get("applied_version"),
        }
    expected_version = int(payload.expected_version)
    if (expected_version != int(link.get("expected_title_version") or 0)
            or expected_version != int(title.get("version") or 0)):
        raise HTTPException(409, detail={
            "code": "CINEMA_PRODUCTION_VERSION_CONFLICT",
            "message": "Production document berubah sejak generation job dibuat. Buat generation job baru berdasarkan versi terkini.",
        })
    jobs = await generation_jobs_api._admin_request("GET", "generation_jobs", params={
        "select": "id,owner_user_id,status,moderation_status,artifact_bucket,artifact_path,output_sha256,artifact_deletion_requested_at,artifact_deleted_at",
        "id": "eq." + str(job_id), "owner_user_id": "eq." + str(user["id"]), "limit": "1",
    })
    if not jobs:
        raise HTTPException(404, detail={
            "code": "GENERATION_JOB_NOT_FOUND", "message": "Canonical Generation Job tidak ditemukan.",
        })
    job = jobs[0]
    if job.get("artifact_deleted_at") or job.get("artifact_deletion_requested_at"):
        raise HTTPException(410, detail={
            "code": "GENERATION_ARTIFACT_UNAVAILABLE",
            "message": "Artefak generation telah dihapus atau sedang dihapus.",
        })
    if (job.get("status") != "succeeded" or job.get("moderation_status") != "approved"
            or job.get("artifact_bucket") != "generation-artifacts" or not job.get("artifact_path")):
        raise HTTPException(409, detail={
            "code": "CINEMA_GENERATION_ARTIFACT_NOT_READY",
            "message": "Screenplay hanya dapat diterapkan setelah Generation Job sukses dan moderasi menyetujui artefaknya.",
        })
    signed_url = await generation_jobs_api._signed_generation_artifact(
        str(job["artifact_bucket"]), str(job["artifact_path"]),
    )
    expected_host = urlparse(os.getenv("SUPABASE_URL", "")).netloc
    if not expected_host or urlparse(signed_url).netloc != expected_host:
        raise HTTPException(503, detail={
            "code": "CINEMA_GENERATION_ARTIFACT_HOST_INVALID",
            "message": "Host artefak privat tidak cocok dengan Supabase canonical.",
        })
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(12, connect=3)) as client:
            response = await client.get(signed_url)
            response.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(503, detail={
            "code": "CINEMA_GENERATION_ARTIFACT_DOWNLOAD_FAILED",
            "message": "Artefak screenplay belum dapat diunduh dari Storage privat.",
        }) from exc
    content_type = str(response.headers.get("content-type") or "").split(";")[0].lower()
    if content_type not in {"text/plain", "text/markdown", "application/octet-stream"}:
        raise HTTPException(415, detail={
            "code": "CINEMA_GENERATION_ARTIFACT_TYPE_INVALID",
            "message": "Artefak bukan dokumen teks screenplay yang didukung.",
        })
    expected_sha256 = str(job.get("output_sha256") or "")
    if not expected_sha256 or hashlib.sha256(response.content).hexdigest() != expected_sha256:
        raise HTTPException(409, detail={
            "code": "CINEMA_GENERATION_ARTIFACT_HASH_MISMATCH",
            "message": "Checksum artefak screenplay tidak cocok dengan receipt Generation Job.",
        })
    if len(response.content) > 60000:
        raise HTTPException(422, detail={
            "code": "CINEMA_SCREENPLAY_OUTPUT_TOO_LARGE",
            "message": "Hasil screenplay melebihi batas 60 KiB.",
        })
    try:
        screenplay_text = response.content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(422, detail={
            "code": "CINEMA_SCREENPLAY_OUTPUT_ENCODING_INVALID",
            "message": "Hasil screenplay harus berupa UTF-8.",
        }) from exc
    if not screenplay_text.strip():
        raise HTTPException(422, detail={
            "code": "CINEMA_SCREENPLAY_OUTPUT_EMPTY",
            "message": "Hasil screenplay kosong dan tidak dapat diterapkan.",
        })
    result = await _db("POST", "rpc/cinema_apply_generation_job_output", payload={
        "p_generation_job_id": str(job_id), "p_owner_id": str(title["owner_id"]),
        "p_requester_user_id": str(user["id"]), "p_expected_version": expected_version,
        "p_output_text": screenplay_text,
    })
    if not isinstance(result, dict) or result.get("outcome") not in {"applied", "replayed"}:
        raise HTTPException(503, detail={
            "code": "CINEMA_GENERATION_APPLY_UNCONFIRMED",
            "message": "Penerapan screenplay belum dapat dikonfirmasi oleh database.",
        })
    return result


@router.get("/creator/titles/{title_id}/assets")
async def list_cinema_assets(title_id: uuid.UUID, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    title = await _title_access(title_id, str(user["id"]), {"edit_metadata", "upload_episodes"})
    rows = await _db("GET", "cinema_assets", params={
        "select": "id,title_id,media_id,asset_role,display_name,metadata,created_at",
        "title_id": "eq." + str(title_id), "owner_id": "eq." + str(title["owner_id"]),
        "order": "created_at.desc", "limit": "500",
    })
    items = rows or []
    media_ids = sorted({str(item.get("media_id")) for item in items if item.get("media_id")})
    if not media_ids:
        return {"items": []}
    owners = await _title_media_owner_ids(title)
    media_rows = await _db("GET", "content_media", params={
        "select": "id,owner_id,filename,media_type,size_bytes,status,scan_status,processed_at,derivatives,storage_path",
        "id": "in.(" + ",".join(media_ids) + ")",
        "owner_id": "in.(" + ",".join(sorted(owners)) + ")", "limit": "1000",
    })
    media_by_id = {str(item.get("id")): item for item in media_rows or []}
    result = []
    for item in items:
        media = media_by_id.get(str(item.get("media_id")))
        if not media:
            continue
        projected = {key: value for key, value in media.items() if key not in {"storage_path", "derivatives"}}
        if media.get("status") == "ready" and media.get("scan_status") == "clean" and media.get("processed_at"):
            projected["preview_url"] = await _signed_media_preview_url(str(media["storage_path"]), expires_in=300)
        result.append({**item, "media": projected})
    return {"items": result}


@router.post("/creator/titles/{title_id}/assets", status_code=201)
async def attach_cinema_asset(
    title_id: uuid.UUID, payload: CinemaAssetAttach,
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    title = await _title_access(title_id, str(user["id"]), {"upload_episodes"})
    owners = await _title_media_owner_ids(title)
    media_rows = await _db("GET", "content_media", params={
        "select": "id,owner_id,filename,media_type,size_bytes,status,scan_status,processed_at,derivatives",
        "id": "eq." + str(payload.media_id),
        "owner_id": "in.(" + ",".join(sorted(owners)) + ")", "limit": "1",
    })
    if not media_rows:
        raise HTTPException(404, detail={"code": "CINEMA_ASSET_NOT_FOUND", "message": "Media tidak ditemukan atau bukan milik pemilik/collaborator yang berhak."})
    media = media_rows[0]
    if (media.get("status") != "ready" or media.get("scan_status") != "clean"
            or not media.get("processed_at") or not isinstance(media.get("derivatives"), list)
            or not media.get("derivatives")):
        raise HTTPException(409, detail={"code": "CINEMA_ASSET_NOT_READY", "message": "Media harus selesai diproses, lolos scan, dan memiliki derivative sebelum ditautkan."})
    rows = await _db("POST", "cinema_assets", payload={
        "title_id": str(title_id), "owner_id": str(title["owner_id"]),
        "media_id": str(payload.media_id), "asset_role": payload.asset_role,
        "display_name": payload.display_name.strip(), "created_by": str(user["id"]),
    }, prefer="return=representation")
    if not rows:
        raise HTTPException(503, detail={"code": "CINEMA_ASSET_LINK_UNCONFIRMED", "message": "Tautan asset belum dapat dikonfirmasi."})
    return {"item": rows[0], "media": {key: value for key, value in media.items() if key not in {"derivatives"}}}


@router.delete("/creator/titles/{title_id}/assets/{asset_id}")
async def remove_cinema_asset(
    title_id: uuid.UUID, asset_id: uuid.UUID,
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    title = await _title_access(title_id, str(user["id"]), {"upload_episodes"})
    rows = await _db("DELETE", "cinema_assets", params={
        "id": "eq." + str(asset_id), "title_id": "eq." + str(title_id),
        "owner_id": "eq." + str(title["owner_id"]), "select": "id,media_id",
    }, prefer="return=representation")
    if not rows:
        raise HTTPException(404, detail={"code": "CINEMA_ASSET_LINK_NOT_FOUND", "message": "Tautan asset tidak ditemukan."})
    return {"removed": True, "asset_id": str(asset_id), "media_id": rows[0].get("media_id")}




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


@router.patch("/creator/titles/{title_id}")
async def update_creator_title(title_id: uuid.UUID,payload: TitleUpdateCommand,
                               user: dict[str,Any]=Depends(current_user))->dict[str,Any]:
    title=await _title_access(title_id,str(user["id"]),{"edit_metadata"})
    if title.get("status") not in {"draft","rejected"}:
        raise HTTPException(409,detail={"code":"CINEMA_TITLE_NOT_EDITABLE","message":"Metadata hanya dapat diubah pada draft atau judul yang dikembalikan."})
    changes=payload.model_dump(exclude_unset=True)
    expected=changes.pop("expected_version")
    if not changes:
        raise HTTPException(422,detail={"code":"CINEMA_TITLE_UPDATE_EMPTY","message":"Tidak ada perubahan metadata."})
    if "genre" in changes and changes["genre"] not in GENRES:
        raise HTTPException(422,detail={"code":"CINEMA_GENRE_INVALID","message":"Genre tidak valid."})
    if "maturity_rating" in changes and changes["maturity_rating"] not in {"unrated","all_ages","13_plus","17_plus","21_plus"}:
        raise HTTPException(422,detail={"code":"CINEMA_MATURITY_INVALID","message":"Klasifikasi usia tidak valid."})
    changes.update({"version":expected+1,"updated_at":datetime.now(timezone.utc).isoformat()})
    rows=await _db("PATCH","cinema_titles",params={
        "id":"eq."+str(title_id),"owner_id":"eq."+str(title["owner_id"]),
        "status":"in.(draft,rejected)","version":"eq."+str(expected),
    },payload=changes,prefer="return=representation")
    if not rows:
        raise HTTPException(409,detail={"code":"CINEMA_TITLE_VERSION_CONFLICT","message":"Versi film berubah atau hak edit sudah dicabut."})
    return {"item":rows[0]}


@router.post("/creator/titles/{title_id}/submit-review")
async def submit_title_for_review(
    title_id: uuid.UUID,
    payload: TitleSubmitCommand,
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    if not payload.rights_confirmed or not payload.ai_disclosure_confirmed:
        raise HTTPException(422, detail={"code": "CINEMA_CREATOR_CONFIRMATIONS_REQUIRED", "message": "Konfirmasi hak atas materi dan pengungkapan penggunaan AI wajib diberikan."})
    access = await _title_access(title_id,str(user["id"]),{"submit_review"})
    current = await _db("GET", "cinema_titles", params={
        "select": TITLE_FIELDS, "id": f"eq.{title_id}", "owner_id": f"eq.{access['owner_id']}",
        "status": "in.(draft,rejected)", "limit": "1",
    })
    if not current:
        raise HTTPException(404, detail={"code": "CINEMA_TITLE_NOT_EDITABLE", "message": "Draft film tidak ditemukan atau tidak dapat diajukan."})
    item = current[0]
    if int(item.get("version") or 0) != payload.expected_version:
        raise HTTPException(409, detail={"code": "CINEMA_VERSION_CHANGED", "message": "Versi draft berubah; muat ulang sebelum mengajukan review."})
    episodes = await _db("GET", "cinema_episodes", params={
        "select": "id,media_id,status", "title_id": f"eq.{title_id}",
        "owner_id": f"eq.{access['owner_id']}", "order": "episode_number.asc",
    })
    episode_rows = episodes or []
    if not episode_rows or any(not episode.get("media_id") or episode.get("status") != "ready" for episode in episode_rows):
        raise HTTPException(409, detail={"code": "CINEMA_EPISODE_MEDIA_NOT_READY", "message": "Tambahkan minimal satu episode dan pastikan semua episode memiliki media ready serta scan clean."})
    media_ids = [str(episode["media_id"]) for episode in episode_rows]
    media_rows = await _db("GET", "content_media", params={
        "select": "id,owner_id,processed_at,derivatives", "id": f"in.({','.join(media_ids)})",
        "status": "eq.ready", "scan_status": "eq.clean", "limit": str(min(100, len(media_ids))),
    })
    clean_ids = {str(media["id"]) for media in (media_rows or [])
                 if media.get("processed_at") and isinstance(media.get("derivatives"),list) and media.get("derivatives")}
    allowed_media_owners=await _title_media_owner_ids(access)
    if any(media_id not in clean_ids for media_id in media_ids) or any(str(media.get("owner_id")) not in allowed_media_owners for media in (media_rows or [])):
        raise HTTPException(409, detail={"code": "CINEMA_EPISODE_MEDIA_NOT_READY", "message": "Seluruh media episode harus ready dan scan clean."})
    now = datetime.now(timezone.utc).isoformat()
    rows = await _db("PATCH", "cinema_titles", params={
        "id": f"eq.{title_id}", "owner_id": f"eq.{access['owner_id']}",
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
    title = await _title_access(title_id,str(user["id"]),{"edit_metadata","upload_episodes"})
    rows = await _db("GET","cinema_episodes",params={"select":EPISODE_FIELDS,"title_id":f"eq.{title_id}","owner_id":f"eq.{title['owner_id']}","order":"episode_number.asc"})
    return {"items":rows or []}


@router.post("/creator/titles/{title_id}/episodes",status_code=201)
async def create_episode(title_id: uuid.UUID,payload: EpisodeCreate,user: dict[str,Any] = Depends(current_user)) -> dict[str,Any]:
    title = await _title_access(title_id,str(user["id"]),{"upload_episodes"})
    if title.get("status") not in {"draft","rejected"}:
        raise HTTPException(409,detail={"code":"CINEMA_TITLE_NOT_EDITABLE","message":"Episode hanya dapat diubah pada draft atau judul yang dikembalikan."})
    if payload.media_id:
        allowed_media_owners = await _title_media_owner_ids(title)
        media = await _db("GET", "content_media", params={
            "select": "id,owner_id,media_type,status,scan_status,processed_at,derivatives",
            "id": f"eq.{payload.media_id}",
            "owner_id": "in.(" + ",".join(sorted(allowed_media_owners)) + ")",
            "limit": "1",
        })
        if not media:
            raise HTTPException(404, detail={
                "code": "CINEMA_MEDIA_NOT_OWNED",
                "message": "Media tidak ditemukan atau bukan milik pemilik/kolaborator yang berhak.",
            })
        media_item = media[0]
        if (
            media_item.get("status") != "ready"
            or media_item.get("scan_status") != "clean"
            or not str(media_item.get("media_type") or "").startswith("video/")
            or not media_item.get("processed_at")
            or not isinstance(media_item.get("derivatives"), list)
            or not media_item.get("derivatives")
        ):
            raise HTTPException(409, detail={
                "code": "CINEMA_EPISODE_MEDIA_NOT_READY",
                "message": "Part film harus berupa video yang selesai diproses, lolos pemindaian, dan memiliki derivative.",
            })
    rows = await _db("POST","cinema_episodes",payload={**payload.model_dump(),"title_id":str(title_id),"owner_id":title["owner_id"],"status":"ready" if payload.media_id else "draft"},prefer="return=representation")
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


@router.get("/creator/media")
async def creator_media_library(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    """Return owner-scoped media processing states for the Cinema Creator Workspace."""
    owner_id = str(user["id"])
    rows = await _db("GET", "content_media", params={
        "select": "id,content_id,filename,media_type,size_bytes,status,scan_status,processed_at,created_at",
        "owner_id": "eq." + owner_id, "order": "created_at.desc", "limit": "100",
    })
    media_rows = rows or []
    content_ids = sorted({str(row["content_id"]) for row in media_rows if row.get("content_id")})
    if not content_ids:
        return {"items": []}
    content_rows = await _db("GET", "content_items", params={
        "select": "id", "id": "in.(" + ",".join(content_ids) + ")",
        "owner_id": "eq." + owner_id, "status": "not.in.(deleted,archived)",
        "limit": str(min(100, len(content_ids))),
    })
    eligible = {str(row["id"]) for row in (content_rows or [])}
    return {"items": [row for row in media_rows if str(row.get("content_id")) in eligible]}


@router.get("/creator/status")
async def creator_capability_status(request: Request,user: dict[str,Any] = Depends(current_user)) -> dict[str,Any]:
    async def available(table: str) -> bool:
        try:
            await _db("GET",table,params={"select":"*","limit":"1"})
            return True
        except HTTPException:
            return False

    policies = await _db("GET","credit_policy_versions",params={
        "select":"policy_version,status","status":"eq.approved","limit":"1",
    })
    checks = {}
    for table in ("generation_jobs","generation_output_moderation_policies","billing_products",
                  "billing_subscriptions","playback_entitlements","cinema_subscription_plans",
                  "cinema_access_policy_versions","cinema_watch_policy_versions",
                  "cinema_qualified_watches","cinema_creator_earning_policy_versions","cinema_creator_earnings","cinema_film_versions",
                  "cinema_collaborators"):
        checks[table] = await available(table)

    model_router = getattr(request.app.state,"text_generation_router",None)
    generation_ready = bool(policies and checks["generation_jobs"] and checks["generation_output_moderation_policies"] and model_router)
    billing_ready = all(checks[x] for x in ("billing_products","billing_subscriptions"))
    entitlement_ready = all(checks[x] for x in ("playback_entitlements","cinema_subscription_plans","cinema_access_policy_versions"))
    qualified_watch_ready = all(checks[x] for x in ("cinema_watch_policy_versions","cinema_qualified_watches"))
    creator_economy_ready = checks["cinema_creator_earnings"] and checks["cinema_creator_earning_policy_versions"]
    return {
        "catalog":"available","project_drafts":"available","media":"existing_content_media_pipeline",
        "generation":"configured" if generation_ready else "blocked_until_job_schema_moderation_policy_and_model_router_are_ready",
        "generation_jobs":"available" if checks["generation_jobs"] else "source_only_not_applied",
        "billing":"available" if billing_ready else "billing_schema_not_applied",
        "playback_entitlement":"available" if entitlement_ready else "entitlement_or_access_policy_not_configured",
        "qualified_watch":"available" if qualified_watch_ready else "watch_policy_schema_not_applied",
        "creator_earnings":"available" if creator_economy_ready else "creator_earning_schema_not_applied",
        "creator_collaboration":"available" if checks["cinema_collaborators"] else "collaboration_schema_not_applied",
        "film_versioning":"available" if checks["cinema_film_versions"] else "film_version_schema_not_applied",
        "generation_reason":None if generation_ready else "GENERATION_JOB_OR_MODERATION_OR_MODEL_ROUTER_NOT_READY",
        "billing_reason":None if billing_ready else "BILLING_SCHEMA_NOT_APPLIED",
        "entitlement_reason":None if entitlement_ready else "CINEMA_ENTITLEMENT_POLICY_NOT_CONFIGURED",
        "qualified_watch_reason":None if qualified_watch_ready else "QUALIFIED_WATCH_POLICY_NOT_CONFIGURED",
        "creator_economy_reason":None if creator_economy_ready else "CREATOR_EARNING_POLICY_NOT_CONFIGURED",
    }




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


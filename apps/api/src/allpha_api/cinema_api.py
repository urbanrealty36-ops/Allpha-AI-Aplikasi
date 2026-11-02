"""AI Cinema catalogue and creator project API (ENG-P13).

Uses canonical Supabase Postgres and the existing private content-media records.
No generation provider, billing policy, playback entitlement or moderation decision
is fabricated here; publication remains gated until those canonical owners act.
"""
from __future__ import annotations

import os
import uuid
from typing import Any, Literal

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from allpha_api.auth import current_user

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
        media = await _db("GET","content_media",params={"select":"id","id":f"eq.{payload.media_id}","owner_id":f"eq.{user['id']}","status":"eq.uploaded","limit":"1"})
        if not media: raise HTTPException(404,detail={"code":"CINEMA_MEDIA_NOT_OWNED","message":"Media tidak ditemukan atau bukan milik Anda."})
    rows = await _db("POST","cinema_episodes",payload={**payload.model_dump(),"title_id":str(title_id),"owner_id":user["id"],"status":"draft"},prefer="return=representation")
    if not rows: raise HTTPException(503,detail={"code":"CINEMA_EPISODE_CREATE_UNCONFIRMED","message":"Episode belum dapat dikonfirmasi."})
    return {"item":rows[0]}


@router.get("/creator/status")
async def creator_capability_status(user: dict[str,Any] = Depends(current_user)) -> dict[str,Any]:
    # The endpoint reports configuration only; it never exposes balances or estimates.
    policies = await _db("GET","credit_policy_versions",params={"select":"policy_version,status","status":"eq.approved","limit":"1"})
    return {"catalog":"available","project_drafts":"available","media":"existing_content_media_pipeline","generation":"unavailable" if not policies else "policy_present_runtime_unverified","generation_reason":None if policies else "APPROVED_CREDIT_POLICY_MISSING"}

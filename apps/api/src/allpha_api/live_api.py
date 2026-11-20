"""Provider-neutral Live control plane.

This API owns session/participant/stage metadata only. It never issues media
publish/subscribe tokens or claims a stream/recording is live while ADR-WP10-001
has not approved a media provider.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime
from typing import Any, Literal

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from allpha_api.auth import current_user

router = APIRouter(prefix="/v1/live", tags=["live-experience"])
_TIMEOUT = httpx.Timeout(10.0, connect=3.0)


class LiveSessionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=4000)
    visibility: Literal["public", "followers", "private"] = "public"
    scheduled_at: datetime | None = None
    idempotency_key: str = Field(min_length=8, max_length=160)


class LiveParticipantInvite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_id: uuid.UUID
    role: Literal["cohost", "speaker", "viewer"]
    idempotency_key: str = Field(min_length=8, max_length=160)


class LiveSessionTransition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)
    next_status: Literal["preparing", "live", "paused", "reconnecting", "ended", "cancelled", "failed", "moderation_stopped"]
    reason: str = Field(default="", max_length=500)


class LiveRecordingConsent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    consent: bool
    idempotency_key: str = Field(min_length=8, max_length=160)


class LiveStageEventCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_type: Literal["stage_slide_changed", "stage_annotation_added", "stage_poll_created", "stage_qa_submitted"]
    payload: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str = Field(min_length=8, max_length=160)


class LiveParticipantRemoval(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(default="host_removed_participant", min_length=3, max_length=500)
    idempotency_key: str = Field(min_length=8, max_length=160)


class LiveIdempotency(BaseModel):
    model_config = ConfigDict(extra="forbid")
    idempotency_key: str = Field(min_length=8, max_length=160)


def _credentials() -> tuple[str, str]:
    base = os.getenv("SUPABASE_URL", "").rstrip("/")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "") or os.getenv("SUPABASE_SECRET_KEY", "")
    if not base or not key:
        raise HTTPException(503, detail={"code": "LIVE_DATABASE_NOT_CONFIGURED", "message": "Live control plane belum terhubung ke database kanonis."})
    return base, key


async def _db(method: str, path: str, *, params: dict[str, str] | None = None,
              payload: Any = None, prefer: str | None = None) -> Any:
    base, key = _credentials()
    headers = {"apikey": key, "Authorization": f"Bearer {key}", "Accept": "application/json"}
    if payload is not None:
        headers["Content-Type"] = "application/json"
    if prefer:
        headers["Prefer"] = prefer
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            response = await client.request(
                method, f"{base}/rest/v1/{path}", params=params, json=payload, headers=headers,
            )
    except httpx.HTTPError as exc:
        raise HTTPException(503, detail={"code": "LIVE_DATABASE_UNAVAILABLE", "message": "Live control plane sementara tidak tersedia."}) from exc
    if response.status_code >= 400:
        raw = response.text
        known = {
            "LIVE_MEDIA_PROVIDER_NOT_APPROVED": (409, "LIVE_MEDIA_PROVIDER_NOT_APPROVED", "Live belum dapat dimulai sebelum provider media disetujui melalui ADR."),
            "LIVE_SESSION_HOST_REQUIRED": (403, "LIVE_SESSION_HOST_REQUIRED", "Tindakan ini hanya tersedia bagi host sesi."),
            "LIVE_SESSION_NOT_JOINABLE": (409, "LIVE_SESSION_NOT_JOINABLE", "Sesi tidak sedang menerima peserta."),
            "LIVE_SESSION_INVITE_REQUIRED": (403, "LIVE_SESSION_INVITE_REQUIRED", "Sesi privat memerlukan undangan host."),
            "LIVE_SESSION_FOLLOW_REQUIRED": (403, "LIVE_SESSION_FOLLOW_REQUIRED", "Ikuti host terlebih dahulu untuk bergabung ke sesi ini."),
            "LIVE_SESSION_VERSION_CONFLICT": (409, "LIVE_SESSION_VERSION_CONFLICT", "Status sesi berubah; muat ulang sebelum mencoba lagi."),
            "LIVE_SESSION_TRANSITION_INVALID": (409, "LIVE_SESSION_TRANSITION_INVALID", "Transisi status sesi tidak diizinkan."),
            "LIVE_PARTICIPANT_REMOVED": (403, "LIVE_PARTICIPANT_REMOVED", "Akses ke sesi telah dicabut host."),
            "LIVE_STAGE_PARTICIPANT_REQUIRED": (403, "LIVE_STAGE_PARTICIPANT_REQUIRED", "Hanya peserta aktif yang dapat mengubah stage."),
            "LIVE_PARTICIPANT_NOT_FOUND": (404, "LIVE_PARTICIPANT_NOT_FOUND", "Peserta tidak ditemukan."),
        }
        for marker, (status, code, message) in known.items():
            if marker in raw:
                raise HTTPException(status, detail={"code": code, "message": message})
        raise HTTPException(503 if response.status_code >= 500 or response.status_code == 404 else 409,
            detail={"code": "LIVE_PERSISTENCE_FAILED", "message": "Perubahan Live belum dapat dikonfirmasi."})
    if not response.content:
        return []
    try:
        return response.json()
    except ValueError as exc:
        raise HTTPException(503, detail={"code": "LIVE_DATABASE_RESPONSE_INVALID", "message": "Respons database Live tidak valid."}) from exc


async def _rpc(name: str, payload: dict[str, Any]) -> dict[str, Any]:
    result = await _db("POST", f"rpc/{name}", payload=payload)
    if isinstance(result, list):
        result = result[0] if result else None
    if not isinstance(result, dict):
        raise HTTPException(503, detail={"code": "LIVE_RPC_OUTCOME_UNCONFIRMED", "message": "Hasil transaksi Live belum dapat dikonfirmasi."})
    return result


async def _session_access(session_id: uuid.UUID, user_id: str) -> tuple[dict[str, Any], bool]:
    rows = await _db("GET", "live_sessions", params={
        "select": "id,host_user_id,conversation_id,title,description,visibility,status,recording_state,scheduled_at,started_at,ended_at,version,created_at,updated_at",
        "id": f"eq.{session_id}", "limit": "1",
    })
    if not rows:
        raise HTTPException(404, detail={"code": "LIVE_SESSION_NOT_FOUND", "message": "Sesi Live tidak ditemukan."})
    session = rows[0]
    is_host = str(session.get("host_user_id")) == user_id
    participants = await _db("GET", "live_participants", params={
        "select": "id,participant_role,status", "session_id": f"eq.{session_id}",
        "user_id": f"eq.{user_id}", "status": "in.(invited,joined)", "limit": "1",
    })
    if not is_host and not participants:
        raise HTTPException(404, detail={"code": "LIVE_SESSION_NOT_FOUND", "message": "Sesi Live tidak ditemukan."})
    return session, is_host


def _media_plane(session: dict[str, Any]) -> dict[str, Any]:
    configured = bool(session.get("provider_key") and session.get("provider_session_ref"))
    return {
        "status": "configured" if configured else "not_configured",
        "provider_approved": False,
        "publish_subscribe_tokens_available": False,
        "reason": "ADR_WP10_001_PROVIDER_APPROVAL_REQUIRED",
    }


@router.post("/sessions", status_code=201)
async def create_live_session(payload: LiveSessionCreate, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    result = await _rpc("create_live_session", {
        "p_host_user_id": str(user["id"]), "p_title": payload.title.strip(),
        "p_description": payload.description, "p_visibility": payload.visibility,
        "p_scheduled_at": payload.scheduled_at.isoformat() if payload.scheduled_at else None,
        "p_idempotency_key": payload.idempotency_key,
    })
    session = result.get("session") or {}
    return {"outcome": result.get("outcome"), "session": session,
            "media_plane": _media_plane(session), "recording_provider_enabled": False}


@router.get("/sessions")
async def list_live_sessions(limit: int = Query(default=30, ge=1, le=100),
                             user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    user_id = str(user["id"])
    hosted = await _db("GET", "live_sessions", params={
        "select": "id,host_user_id,conversation_id,title,description,visibility,status,recording_state,scheduled_at,started_at,ended_at,version,created_at,updated_at",
        "host_user_id": f"eq.{user_id}", "order": "updated_at.desc", "limit": str(limit),
    })
    memberships = await _db("GET", "live_participants", params={
        "select": "session_id", "user_id": f"eq.{user_id}",
        "status": "in.(invited,joined)", "limit": str(limit),
    })
    ids = sorted({str(row.get("session_id")) for row in memberships or [] if row.get("session_id")})
    participant_sessions = []
    if ids:
        participant_sessions = await _db("GET", "live_sessions", params={
            "select": "id,host_user_id,conversation_id,title,description,visibility,status,recording_state,scheduled_at,started_at,ended_at,version,created_at,updated_at",
            "id": "in.(" + ",".join(ids) + ")", "order": "updated_at.desc", "limit": str(limit),
        })
    by_id = {str(row["id"]): row for row in [*(hosted or []), *(participant_sessions or [])]}
    items = sorted(by_id.values(), key=lambda row: str(row.get("updated_at") or ""), reverse=True)[:limit]
    return {"items": [{**item, "media_plane": _media_plane(item), "recording_provider_enabled": False} for item in items]}


@router.get("/sessions/{session_id}")
async def get_live_session(session_id: uuid.UUID, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    session, is_host = await _session_access(session_id, str(user["id"]))
    participants = await _db("GET", "live_participants", params={
        "select": "id,user_id,participant_role,status,recording_consent,recording_consent_at,joined_at,left_at,created_at",
        "session_id": f"eq.{session_id}", "order": "created_at.asc", "limit": "500",
    })
    return {"session": session, "participants": participants or [],
            "is_host": is_host, "media_plane": _media_plane(session),
            "chat": {"conversation_id": session.get("conversation_id"),
                     "api_path": f"/v1/messages/conversations/{session.get('conversation_id')}/messages"},
            "recording_provider_enabled": False}


@router.post("/sessions/{session_id}/participants", status_code=201)
async def invite_live_participant(session_id: uuid.UUID, payload: LiveParticipantInvite,
                                  user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    session, is_host = await _session_access(session_id, str(user["id"]))
    if not is_host:
        raise HTTPException(403, detail={"code": "LIVE_SESSION_HOST_REQUIRED", "message": "Hanya host yang dapat mengundang peserta."})
    result = await _rpc("invite_live_participant", {
        "p_session_id": str(session_id), "p_host_user_id": str(user["id"]),
        "p_user_id": str(payload.user_id), "p_role": payload.role,
        "p_idempotency_key": payload.idempotency_key,
    })
    return {"outcome": result.get("outcome"), "participant": result.get("participant")}


@router.post("/sessions/{session_id}/participants/{participant_user_id}/remove")
async def remove_live_participant(session_id: uuid.UUID, participant_user_id: uuid.UUID,
                                 payload: LiveParticipantRemoval,
                                 user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    _, is_host = await _session_access(session_id, str(user["id"]))
    if not is_host:
        raise HTTPException(403, detail={"code": "LIVE_SESSION_HOST_REQUIRED", "message": "Hanya host yang dapat mencabut peserta."})
    result = await _rpc("remove_live_participant", {
        "p_session_id": str(session_id), "p_host_user_id": str(user["id"]),
        "p_user_id": str(participant_user_id), "p_reason": payload.reason,
        "p_idempotency_key": payload.idempotency_key,
    })
    return {"outcome": result.get("outcome"), "participant": result.get("participant")}


@router.post("/sessions/{session_id}/join")
async def join_live_session(session_id: uuid.UUID, payload: LiveIdempotency,
                            user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    key = payload.idempotency_key
    result = await _rpc("join_live_session", {
        "p_session_id": str(session_id), "p_user_id": str(user["id"]),
        "p_idempotency_key": key,
    })
    return {"outcome": result.get("outcome"), "participant": result.get("participant"),
            "media_plane": {"status": "not_configured", "publish_subscribe_tokens_available": False}}


@router.post("/sessions/{session_id}/leave")
async def leave_live_session(session_id: uuid.UUID, payload: LiveIdempotency,
                             user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    key = payload.get("idempotency_key", "")
    if not 8 <= len(key) <= 160:
        raise HTTPException(422, detail={"code": "LIVE_IDEMPOTENCY_KEY_INVALID", "message": "Idempotency key wajib 8–160 karakter."})
    result = await _rpc("leave_live_session", {
        "p_session_id": str(session_id), "p_user_id": str(user["id"]),
        "p_idempotency_key": key,
    })
    return {"outcome": result.get("outcome"), "participant": result.get("participant")}


@router.post("/sessions/{session_id}/transition")
async def transition_live_session(session_id: uuid.UUID, payload: LiveSessionTransition,
                                  user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    _, is_host = await _session_access(session_id, str(user["id"]))
    if not is_host:
        raise HTTPException(403, detail={"code": "LIVE_SESSION_HOST_REQUIRED", "message": "Hanya host yang dapat mengubah status sesi."})
    result = await _rpc("transition_live_session", {
        "p_session_id": str(session_id), "p_host_user_id": str(user["id"]),
        "p_expected_version": payload.expected_version,
        "p_next_status": payload.next_status, "p_reason": payload.reason,
    })
    session = result.get("session") or {}
    return {"outcome": result.get("outcome"), "session": session, "media_plane": _media_plane(session)}


@router.post("/sessions/{session_id}/recording-consent")
async def set_live_recording_consent(session_id: uuid.UUID, payload: LiveRecordingConsent,
                                     user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    await _session_access(session_id, str(user["id"]))
    result = await _rpc("set_live_recording_consent", {
        "p_session_id": str(session_id), "p_user_id": str(user["id"]),
        "p_consent": payload.consent, "p_idempotency_key": payload.idempotency_key,
    })
    return {"outcome": result.get("outcome"), "participant": result.get("participant"),
            "recording_provider_enabled": False}


@router.post("/sessions/{session_id}/stage-events", status_code=201)
async def append_live_stage_event(session_id: uuid.UUID, payload: LiveStageEventCreate,
                                  user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    await _session_access(session_id, str(user["id"]))
    result = await _rpc("append_live_stage_event", {
        "p_session_id": str(session_id), "p_actor_user_id": str(user["id"]),
        "p_event_type": payload.event_type, "p_payload": payload.payload,
        "p_idempotency_key": payload.idempotency_key,
    })
    return {"outcome": result.get("outcome"), "event": result.get("event")}


@router.get("/sessions/{session_id}/stage-events")
async def list_live_stage_events(session_id: uuid.UUID, after_seq: int = Query(default=0, ge=0),
                                 limit: int = Query(default=100, ge=1, le=500),
                                 user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    await _session_access(session_id, str(user["id"]))
    rows = await _db("GET", "live_stage_events", params={
        "select": "id,event_seq,actor_user_id,event_type,payload,created_at",
        "session_id": f"eq.{session_id}", "event_seq": f"gt.{after_seq}",
        "order": "event_seq.asc", "limit": str(limit),
    })
    return {"items": rows or [], "next_after_seq": max((int(row.get("event_seq") or 0) for row in rows or []), default=after_seq)}

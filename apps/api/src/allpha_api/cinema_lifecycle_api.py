"""AI Cinema playback, subscription and creator-economy lifecycle contracts.

All policy and entitlement decisions are server-owned. This module deliberately fails
closed until the approved access/watch/economy policy records and source-only migrations
are promoted through the project's migration gate.
"""
from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from allpha_api.auth import current_user
from allpha_api.cinema_api import _db, _signed_media_preview_url

router = APIRouter(prefix="/v1/cinema", tags=["cinema-lifecycle"])


class PlaybackSessionStart(BaseModel):
    model_config = ConfigDict(extra="forbid")
    idempotency_key: str = Field(min_length=8, max_length=160, pattern=r"^[A-Za-z0-9._:-]+$")


class PlaybackHeartbeat(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_id: uuid.UUID
    position_seconds: int = Field(ge=0, le=86400)


def _parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _media_ready(row: dict[str, Any] | None) -> bool:
    return bool(
        row and row.get("status") == "ready" and row.get("scan_status") == "clean"
        and row.get("processed_at") and isinstance(row.get("derivatives"), list)
        and row.get("derivatives")
    )


async def _approved_access_policy() -> dict[str, Any] | None:
    now = datetime.now(timezone.utc)
    try:
        rows = await _db("GET", "cinema_access_policy_versions", params={
            "select": "policy_version,approval_reference,configuration,effective_at,expires_at",
            "status": "eq.approved", "effective_at": "lte." + now.isoformat(),
            "order": "effective_at.desc", "limit": "20",
        })
    except HTTPException:
        return None
    for row in rows or []:
        expiry = _parse_time(row.get("expires_at"))
        if expiry is not None and expiry <= now:
            continue
        if isinstance(row.get("configuration"), dict) and row.get("policy_version") and row.get("approval_reference"):
            return row
    return None


async def _premium_entitlement(owner_id: str, entitlement_key: str) -> tuple[bool, str | None]:
    now = datetime.now(timezone.utc)
    try:
        plans = await _db("GET", "cinema_subscription_plans", params={
            "select": "plan_key,entitlement_key,entitlement_version",
            "entitlement_key": "eq." + entitlement_key, "status": "eq.active", "limit": "50",
        })
        plan_map = {str(p["plan_key"]): p for p in plans or [] if p.get("plan_key")}
        if not plan_map:
            return False, None
        subscriptions = await _db("GET", "billing_subscriptions", params={
            "select": "id,plan_key,entitlement_version,status,current_period_end",
            "owner_user_id": "eq." + owner_id, "status": "eq.active",
            "current_period_end": "gt." + now.isoformat(), "limit": "50",
        })
        active = [
            row for row in subscriptions or []
            if row.get("plan_key") in plan_map
            and row.get("entitlement_version") == plan_map[row["plan_key"]].get("entitlement_version")
        ]
        source_ids = [str(row["id"]) for row in active if row.get("id")]
        if not source_ids:
            return False, None
        entitlements = await _db("GET", "playback_entitlements", params={
            "select": "id,source_subscription_id,entitlement_version,valid_from,valid_until",
            "owner_user_id": "eq." + owner_id, "entitlement_key": "eq." + entitlement_key,
            "source_subscription_id": "in.(" + ",".join(source_ids) + ")",
            "status": "eq.active", "valid_from": "lte." + now.isoformat(), "limit": "100",
        })
        for entitlement in entitlements or []:
            expiry = _parse_time(entitlement.get("valid_until"))
            if expiry is not None and expiry <= now:
                continue
            subscription = next((s for s in active if str(s["id"]) == str(entitlement.get("source_subscription_id"))), None)
            if subscription and entitlement.get("entitlement_version") == subscription.get("entitlement_version"):
                return True, str(entitlement["id"])
        return False, None
    except HTTPException:
        # Absent/unapplied billing schema never grants Premium.
        return False, None


async def _title_and_episode(title_id: uuid.UUID, episode_id: uuid.UUID) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    titles = await _db("GET", "cinema_titles", params={
        "select": "id,owner_id,title,maturity_rating,entitlement_key,status,moderation_status,rights_status",
        "id": "eq." + str(title_id), "status": "eq.published",
        "moderation_status": "eq.approved", "rights_status": "eq.cleared", "limit": "1",
    })
    if not titles:
        raise HTTPException(404, detail={"code": "CINEMA_TITLE_NOT_AVAILABLE", "message": "Judul belum tersedia."})
    title = titles[0]
    episodes = await _db("GET", "cinema_episodes", params={
        "select": "id,title_id,owner_id,title,media_id,duration_seconds,is_free_preview,status",
        "id": "eq." + str(episode_id), "title_id": "eq." + str(title_id),
        "owner_id": "eq." + str(title["owner_id"]), "status": "eq.ready", "limit": "1",
    })
    if not episodes or not episodes[0].get("media_id"):
        raise HTTPException(404, detail={"code": "CINEMA_EPISODE_NOT_AVAILABLE", "message": "Episode belum siap."})
    episode = episodes[0]
    media_rows = await _db("GET", "content_media", params={
        "select": "id,owner_id,storage_path,status,scan_status,processed_at,derivatives",
        "id": "eq." + str(episode["media_id"]), "owner_id": "eq." + str(title["owner_id"]),
        "status": "eq.ready", "scan_status": "eq.clean", "limit": "1",
    })
    if not media_rows or not _media_ready(media_rows[0]):
        raise HTTPException(409, detail={"code": "CINEMA_MEDIA_NOT_READY", "message": "Media belum diproses lengkap atau belum lolos scan."})
    return title, episode, media_rows[0]


@router.post("/titles/{title_id}/episodes/{episode_id}/playback-session", status_code=201)
async def start_playback_session(
    title_id: uuid.UUID,
    episode_id: uuid.UUID,
    payload: PlaybackSessionStart,
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    title, episode, media = await _title_and_episode(title_id, episode_id)
    policy = await _approved_access_policy()
    config = policy.get("configuration") if policy and isinstance(policy.get("configuration"), dict) else {}
    if not policy:
        raise HTTPException(503, detail={"code": "CINEMA_ACCESS_POLICY_NOT_CONFIGURED", "message": "Kebijakan akses AI Cinema belum disetujui."})
    if config.get("territory_mode") != "global":
        raise HTTPException(503, detail={"code": "CINEMA_TERRITORY_POLICY_NOT_CONFIGURED", "message": "Kebijakan wilayah belum tersedia."})
    if config.get("maturity_mode") != "all_ages_only" or title.get("maturity_rating") != "all_ages":
        raise HTTPException(403, detail={"code": "CINEMA_MATURITY_POLICY_NOT_SATISFIED", "message": "Judul memerlukan kebijakan verifikasi usia yang belum tersedia."})
    entitlement_id = None
    if episode.get("is_free_preview") is True:
        if config.get("free_preview_enabled") is not True:
            raise HTTPException(403, detail={"code": "CINEMA_FREE_PREVIEW_DISABLED", "message": "Free preview belum diaktifkan."})
    else:
        if config.get("premium_playback_enabled") is not True:
            raise HTTPException(403, detail={"code": "CINEMA_PREMIUM_PLAYBACK_DISABLED", "message": "Premium playback belum diaktifkan."})
        entitlement_key = str(title.get("entitlement_key") or "").strip()
        if not entitlement_key:
            raise HTTPException(403, detail={"code": "CINEMA_ENTITLEMENT_KEY_MISSING", "message": "Judul belum dipetakan ke entitlement Cinema."})
        entitled, entitlement_id = await _premium_entitlement(str(user["id"]), entitlement_key)
        if not entitled:
            raise HTTPException(403, detail={"code": "CINEMA_PREMIUM_ENTITLEMENT_REQUIRED", "message": "Entitlement Premium AI Cinema tidak aktif."})

    max_streams = config.get("max_concurrent_streams")
    if not isinstance(max_streams, int) or max_streams < 1:
        raise HTTPException(503, detail={"code": "CINEMA_CONCURRENT_STREAM_POLICY_MISSING", "message": "Batas concurrent stream belum disetujui."})
    now = datetime.now(timezone.utc)
    active = await _db("GET", "cinema_playback_sessions", params={
        "select": "id", "owner_user_id": "eq." + str(user["id"]),
        "status": "eq.active", "expires_at": "gt." + now.isoformat(), "limit": str(max_streams + 1),
    })
    if len(active or []) >= max_streams:
        raise HTTPException(429, detail={"code": "CINEMA_CONCURRENT_STREAM_LIMIT", "message": "Batas pemutaran bersamaan tercapai."})

    existing = await _db("GET", "cinema_playback_sessions", params={
        "select": "id,episode_id,media_id,status,expires_at",
        "owner_user_id": "eq." + str(user["id"]),
        "idempotency_key": "eq." + payload.idempotency_key, "limit": "1",
    })
    if existing:
        prior = existing[0]
        if str(prior.get("episode_id")) != str(episode_id) or str(prior.get("media_id")) != str(media["id"]):
            raise HTTPException(409, detail={"code": "CINEMA_PLAYBACK_IDEMPOTENCY_CONFLICT", "message": "Idempotency-Key dipakai untuk sesi berbeda."})
        raise HTTPException(409, detail={"code": "CINEMA_PLAYBACK_SESSION_REPLAY", "message": "Sesi lama tidak dapat mengembalikan token rahasia. Buat Idempotency-Key baru."})

    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    expires_at = (now + timedelta(hours=1)).isoformat()
    rows = await _db("POST", "cinema_playback_sessions", payload={
        "owner_user_id": str(user["id"]), "title_id": str(title_id), "episode_id": str(episode_id),
        "media_id": str(media["id"]), "entitlement_id": entitlement_id,
        "access_policy_version": policy["policy_version"], "session_token_hash": token_hash,
        "status": "active", "duration_seconds": episode.get("duration_seconds"),
        "expires_at": expires_at, "idempotency_key": payload.idempotency_key,
    }, prefer="return=representation")
    if not rows:
        raise HTTPException(503, detail={"code": "CINEMA_PLAYBACK_SESSION_UNCONFIRMED", "message": "Sesi belum dapat dikonfirmasi."})
    url = await _signed_media_preview_url(str(media["storage_path"]), expires_in=300)
    return {
        "session": {"id": rows[0]["id"], "expires_at": expires_at, "heartbeat_interval_seconds": 15},
        "session_token": token, "playback_url": url,
        "episode": {"id": episode["id"], "title": episode["title"], "duration_seconds": episode.get("duration_seconds")},
        "qualified_watch": "pending_policy",
    }


@router.post("/playback-sessions/{session_id}/heartbeat")
async def playback_heartbeat(
    session_id: uuid.UUID,
    payload: PlaybackHeartbeat,
    session_token: str = Header(default="", alias="X-Cinema-Session-Token"),
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    if len(session_token) < 32:
        raise HTTPException(401, detail={"code": "CINEMA_SESSION_TOKEN_REQUIRED", "message": "Token sesi pemutaran diperlukan."})
    token_hash = hashlib.sha256(session_token.encode("utf-8")).hexdigest()
    result = await _db("POST", "rpc/cinema_record_playback_heartbeat", payload={
        "p_session_id": str(session_id), "p_owner_user_id": str(user["id"]),
        "p_session_token_hash": token_hash, "p_event_id": str(payload.event_id),
        "p_position_seconds": payload.position_seconds,
    })
    if not isinstance(result, dict):
        raise HTTPException(503, detail={"code": "CINEMA_HEARTBEAT_UNCONFIRMED", "message": "Heartbeat belum dikonfirmasi."})
    return result


@router.post("/playback-sessions/{session_id}/finish")
async def finish_playback_session(
    session_id: uuid.UUID,
    payload: PlaybackHeartbeat,
    session_token: str = Header(default="", alias="X-Cinema-Session-Token"),
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    if len(session_token) < 32:
        raise HTTPException(401, detail={"code": "CINEMA_SESSION_TOKEN_REQUIRED", "message": "Token sesi pemutaran diperlukan."})
    token_hash = hashlib.sha256(session_token.encode("utf-8")).hexdigest()
    result = await _db("POST", "rpc/cinema_finish_playback_session", payload={
        "p_session_id": str(session_id), "p_owner_user_id": str(user["id"]),
        "p_session_token_hash": token_hash, "p_event_id": str(payload.event_id),
        "p_position_seconds": payload.position_seconds,
    })
    if not isinstance(result, dict):
        raise HTTPException(503, detail={"code": "CINEMA_FINISH_UNCONFIRMED", "message": "Penyelesaian sesi belum dikonfirmasi."})
    return result


@router.get("/subscription/plans")
async def cinema_subscription_plans() -> dict[str, Any]:
    try:
        rows = await _db("GET", "cinema_subscription_plans", params={
            "select": "plan_key,product_key,entitlement_key,entitlement_version,configuration",
            "status": "eq.active", "order": "plan_key.asc", "limit": "50",
        })
        items = []
        for plan in rows or []:
            products = await _db("GET", "billing_products", params={
                "select": "product_key,name,description,amount_minor,currency,billing_interval",
                "product_key": "eq." + str(plan["product_key"]), "status": "eq.active",
                "purpose": "eq.premium_subscription", "limit": "1",
            })
            if products:
                items.append({"plan_key": plan["plan_key"], "product": products[0], "configuration": plan.get("configuration") or {}})
        return {"items": items, "configured": bool(items), "checkout_endpoint": "/v1/billing/checkout"}
    except HTTPException:
        return {"items": [], "configured": False, "reason": "CINEMA_PLAN_OR_BILLING_SCHEMA_NOT_READY"}


@router.get("/subscription")
async def my_cinema_subscription(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    try:
        rows = await _db("GET", "cinema_subscriptions", params={
            "select": "id,plan_key,entitlement_version,status,valid_from,valid_until",
            "owner_user_id": "eq." + str(user["id"]), "status": "eq.active",
            "order": "valid_until.desc.nullslast", "limit": "10",
        })
        return {"items": rows or [], "configured": True}
    except HTTPException:
        return {"items": [], "configured": False, "reason": "CINEMA_SUBSCRIPTION_NOT_CONFIGURED"}


@router.get("/creator/earnings")
async def creator_earnings(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    try:
        rows = await _db("GET", "cinema_creator_earnings", params={
            "select": "id,title_id,qualified_watch_id,creator_type,creator_user_id,creator_agent_id,policy_version,earning_credits,status,created_at,settled_at",
            "owner_user_id": "eq." + str(user["id"]), "order": "created_at.desc", "limit": "100",
        })
        return {"items": rows or [], "withdrawals_enabled": False, "cash_conversion_enabled": False,
                "reason": "CREATOR_ECONOMY_POLICY_NOT_APPROVED"}
    except HTTPException:
        return {"items": [], "withdrawals_enabled": False, "cash_conversion_enabled": False,
                "reason": "CINEMA_EARNINGS_SCHEMA_NOT_CONFIGURED"}

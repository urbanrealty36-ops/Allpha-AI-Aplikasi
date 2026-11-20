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

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from allpha_api.auth import current_user
from allpha_api.operator_security import require_operator_scope, write_operator_audit
from allpha_api.cinema_api import _db, _signed_media_preview_url

router = APIRouter(prefix="/v1/cinema", tags=["cinema-lifecycle"])



class CinemaFraudReview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: str = Field(pattern="^(clear|reject)$")
    evidence_reference: str = Field(min_length=8,max_length=500)
    reason: str = Field(min_length=8,max_length=500)


class CinemaPolicyDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")
    policy_version: str = Field(min_length=1,max_length=80,pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,79}$")
    approval_reference: str = Field(min_length=3,max_length=160)
    configuration: dict[str,Any]
    effective_at: str
    expires_at: str | None = None


class CinemaPolicyApproval(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=8,max_length=500)


class CinemaPlanDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")
    plan_key: str = Field(min_length=2,max_length=80,pattern=r"^[a-z0-9][a-z0-9._-]{1,79}$")
    product_key: str = Field(min_length=1,max_length=120)
    entitlement_key: str = Field(min_length=3,max_length=120)
    entitlement_version: str = Field(min_length=1,max_length=80)
    approval_reference: str = Field(min_length=3,max_length=160)
    configuration: dict[str,Any] = Field(default_factory=dict)


class CreatorCreditCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    contributor_type: str = Field(pattern="^(human|agent)$")
    contributor_user_id: uuid.UUID | None = None
    contributor_agent_id: uuid.UUID | None = None
    role: str = Field(min_length=2, max_length=80)
    attribution_label: str = Field(min_length=1, max_length=160)
    disclosure: str = Field(default="AI-assisted contribution", max_length=500)
    provenance: dict[str, Any] = Field(default_factory=dict)


class CinemaCollaboratorCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    collaborator_user_id: uuid.UUID | None = None
    collaborator_agent_id: uuid.UUID | None = None
    role: str = Field(min_length=2, max_length=80)
    permissions: list[str] = Field(default_factory=list, max_length=4)
    expires_at: str | None = None


class CinemaCollaboratorDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: str = Field(pattern="^(accept|revoke)$")


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

async def _owned_cinema_title(title_id: uuid.UUID, owner_id: str) -> dict[str, Any]:
    rows = await _db("GET","cinema_titles",params={
        "select":"id,owner_id,title,original_title,synopsis,genre,language_code,maturity_rating,ai_disclosure,credits,status,moderation_status,rights_status,version,cover_media_id,trailer_media_id,created_at,updated_at,published_at",
        "id":"eq."+str(title_id),"owner_id":"eq."+owner_id,"limit":"1",
    })
    if not rows:
        raise HTTPException(404,detail={"code":"CINEMA_TITLE_NOT_FOUND","message":"Judul Cinema tidak ditemukan atau bukan milik akun ini."})
    return rows[0]


async def _cinema_title_access(title_id: uuid.UUID, user_id: str, scopes: set[str]) -> dict[str,Any]:
    titles=await _db("GET","cinema_titles",params={
        "select":"id,owner_id,title,version","id":"eq."+str(title_id),"limit":"1",
    })
    if not titles:
        raise HTTPException(404,detail={"code":"CINEMA_TITLE_NOT_FOUND","message":"Judul Cinema tidak ditemukan."})
    title=titles[0]
    if str(title["owner_id"])==user_id:
        return title
    grants=await _db("GET","cinema_collaborators",params={
        "select":"permissions,expires_at","title_id":"eq."+str(title_id),
        "owner_id":"eq."+str(title["owner_id"]),"collaborator_user_id":"eq."+user_id,
        "status":"eq.active","limit":"20",
    })
    now=datetime.now(timezone.utc)
    for grant in grants or []:
        expiry=_parse_time(grant.get("expires_at"))
        if expiry and expiry<=now:
            continue
        if scopes.intersection(set(grant.get("permissions") or [])):
            return title
    raise HTTPException(403,detail={"code":"CINEMA_COLLABORATOR_PERMISSION_REQUIRED","message":"Izin collaborator untuk tindakan ini belum diberikan."})


@router.get("/creator/titles/{title_id}/credits")
async def list_creator_credits(title_id: uuid.UUID,user: dict[str,Any]=Depends(current_user))->dict[str,Any]:
    await _cinema_title_access(title_id,str(user["id"]),{"manage_credits"})
    rows=await _db("GET","cinema_creator_credits",params={
        "select":"id,title_id,contributor_type,contributor_user_id,contributor_agent_id,role,attribution_label,disclosure,provenance,created_at",
        "title_id":"eq."+str(title_id),"owner_id":"eq."+str(user["id"]),"order":"created_at.asc","limit":"200",
    })
    return {"items":rows or []}


@router.post("/creator/titles/{title_id}/credits",status_code=201)
async def create_creator_credit(title_id: uuid.UUID,payload: CreatorCreditCreate,
                                user: dict[str,Any]=Depends(current_user))->dict[str,Any]:
    owner_id=str(user["id"])
    title=await _cinema_title_access(title_id,owner_id,{"manage_credits"})
    owner_id=str(title["owner_id"])
    if payload.contributor_type=="human":
        if payload.contributor_agent_id is not None:
            raise HTTPException(422,detail={"code":"CINEMA_CREDIT_CONTRIBUTOR_INVALID","message":"Kredit Human tidak boleh menunjuk AI Agent."})
        contributor_id=str(payload.contributor_user_id or user["id"])
        if contributor_id!=owner_id:
            grants=await _db("GET","cinema_collaborators",params={
                "select":"id","title_id":"eq."+str(title_id),"owner_id":"eq."+owner_id,
                "collaborator_user_id":"eq."+contributor_id,"status":"eq.active","permissions":"cs.{manage_credits}",
                "or":"(expires_at.is.null,expires_at.gt."+datetime.now(timezone.utc).isoformat()+")","limit":"1",
            })
            if not grants:
                raise HTTPException(403,detail={"code":"CINEMA_CREDIT_PERMISSION_REQUIRED","message":"Kontributor Human harus menerima undangan dengan izin pengelolaan kredit."})
    else:
        if payload.contributor_agent_id is None or payload.contributor_user_id is not None:
            raise HTTPException(422,detail={"code":"CINEMA_CREDIT_CONTRIBUTOR_INVALID","message":"Kredit Agent harus menunjuk satu AI Agent."})
        agent_id=str(payload.contributor_agent_id)
        agents=await _db("GET","ai_agents",params={"select":"id,status","id":"eq."+agent_id,"status":"eq.active","limit":"1"})
        ownerships=await _db("GET","agent_ownerships",params={
            "select":"agent_id","agent_id":"eq."+agent_id,"owner_user_id":"eq."+owner_id,
            "ownership_role":"eq.owner","status":"eq.active","limit":"1",
        })
        if not agents or not ownerships:
            raise HTTPException(403,detail={"code":"CINEMA_AGENT_CREDIT_PERMISSION_REQUIRED","message":"AI Agent kontributor harus aktif dan dimiliki oleh pemilik film."})
    rows=await _db("POST","cinema_creator_credits",payload={
        "title_id":str(title_id),"owner_id":owner_id,"contributor_type":payload.contributor_type,
        "contributor_user_id":str(payload.contributor_user_id) if payload.contributor_user_id else None,
        "contributor_agent_id":str(payload.contributor_agent_id) if payload.contributor_agent_id else None,
        "role":payload.role.strip(),"attribution_label":payload.attribution_label.strip(),
        "disclosure":payload.disclosure.strip(),"provenance":payload.provenance,
    },prefer="return=representation")
    if not rows:
        raise HTTPException(503,detail={"code":"CINEMA_CREDIT_NOT_CONFIRMED","message":"Kredit kreator belum tersimpan."})
    return {"credit":rows[0]}


@router.get("/creator/titles/{title_id}/collaborators")
async def list_cinema_collaborators(title_id: uuid.UUID,user: dict[str,Any]=Depends(current_user))->dict[str,Any]:
    owner_id=str(user["id"])
    await _owned_cinema_title(title_id,owner_id)
    rows=await _db("GET","cinema_collaborators",params={
        "select":"id,title_id,collaborator_user_id,collaborator_agent_id,role,permissions,status,accepted_at,expires_at,created_at",
        "title_id":"eq."+str(title_id),"owner_id":"eq."+owner_id,"order":"created_at.desc","limit":"200",
    })
    return {"items":rows or []}


@router.post("/creator/titles/{title_id}/collaborators",status_code=201)
async def invite_cinema_collaborator(title_id: uuid.UUID,payload: CinemaCollaboratorCreate,
                                     user: dict[str,Any]=Depends(current_user))->dict[str,Any]:
    owner_id=str(user["id"])
    await _owned_cinema_title(title_id,owner_id)
    if (payload.collaborator_user_id is None)==(payload.collaborator_agent_id is None):
        raise HTTPException(422,detail={"code":"CINEMA_COLLABORATOR_TARGET_INVALID","message":"Undangan harus menunjuk satu Human atau satu AI Agent."})
    allowed={"edit_metadata","upload_episodes","manage_credits","submit_review"}
    if not set(payload.permissions).issubset(allowed):
        raise HTTPException(422,detail={"code":"CINEMA_COLLABORATOR_SCOPE_INVALID","message":"Permission collaborator tidak dikenal."})
    if payload.collaborator_user_id and str(payload.collaborator_user_id)==owner_id:
        raise HTTPException(422,detail={"code":"CINEMA_COLLABORATOR_SELF_INVITE","message":"Pemilik tidak perlu mengundang dirinya sendiri."})
    if payload.collaborator_agent_id:
        agent_id=str(payload.collaborator_agent_id)
        agents=await _db("GET","ai_agents",params={"select":"id,status","id":"eq."+agent_id,"status":"eq.active","limit":"1"})
        ownerships=await _db("GET","agent_ownerships",params={
            "select":"agent_id","agent_id":"eq."+agent_id,"owner_user_id":"eq."+owner_id,
            "ownership_role":"eq.owner","status":"eq.active","limit":"1",
        })
        if not agents or not ownerships:
            raise HTTPException(403,detail={"code":"CINEMA_AGENT_COLLABORATOR_NOT_OWNED","message":"AI Agent collaborator harus aktif dan dimiliki oleh akun ini."})
    expires=_parse_time(payload.expires_at)
    if payload.expires_at and (expires is None or expires<=datetime.now(timezone.utc)):
        raise HTTPException(422,detail={"code":"CINEMA_COLLABORATOR_EXPIRY_INVALID","message":"Masa undangan tidak valid."})
    is_agent=payload.collaborator_agent_id is not None
    now=datetime.now(timezone.utc).isoformat()
    rows=await _db("POST","cinema_collaborators",payload={
        "title_id":str(title_id),"owner_id":owner_id,
        "collaborator_user_id":str(payload.collaborator_user_id) if payload.collaborator_user_id else None,
        "collaborator_agent_id":str(payload.collaborator_agent_id) if payload.collaborator_agent_id else None,
        "role":payload.role.strip(),"permissions":payload.permissions,
        "status":"active" if is_agent else "invited","invited_by":owner_id,
        "accepted_by":owner_id if is_agent else None,"accepted_at":now if is_agent else None,
        "expires_at":expires.isoformat() if expires else None,
    },prefer="return=representation")
    if not rows:
        raise HTTPException(503,detail={"code":"CINEMA_COLLABORATOR_INVITE_NOT_CONFIRMED","message":"Undangan collaborator belum tersimpan."})
    return {"collaborator":rows[0]}



@router.get("/creator/collaborations")
async def my_cinema_collaborations(user: dict[str,Any]=Depends(current_user))->dict[str,Any]:
    user_id=str(user["id"])
    rows=await _db("GET","cinema_collaborators",params={
        "select":"id,title_id,owner_id,role,permissions,status,expires_at,created_at",
        "collaborator_user_id":"eq."+user_id,"status":"in.(invited,active)",
        "order":"created_at.desc","limit":"100",
    })
    items=[]
    for row in rows or []:
        titles=await _db("GET","cinema_titles",params={
            "select":"id,title,status,version","id":"eq."+str(row["title_id"]),
            "owner_id":"eq."+str(row["owner_id"]),"limit":"1",
        })
        items.append({**row,"title":titles[0] if titles else None})
    return {"items":items}


@router.post("/creator/collaborations/{collaboration_id}/decision")
async def decide_cinema_collaboration(collaboration_id: uuid.UUID,payload: CinemaCollaboratorDecision,
                                      user: dict[str,Any]=Depends(current_user))->dict[str,Any]:
    user_id=str(user["id"])
    rows=await _db("GET","cinema_collaborators",params={
        "select":"id,title_id,owner_id,collaborator_user_id,collaborator_agent_id,status,expires_at",
        "id":"eq."+str(collaboration_id),"limit":"1",
    })
    if not rows:
        raise HTTPException(404,detail={"code":"CINEMA_COLLABORATION_NOT_FOUND","message":"Undangan collaborator tidak ditemukan."})
    row=rows[0]
    if payload.decision=="accept":
        if row.get("collaborator_user_id")!=user_id:
            raise HTTPException(403,detail={"code":"CINEMA_COLLABORATION_ACCEPT_FORBIDDEN","message":"Hanya akun yang diundang yang dapat menerima undangan."})
        expiry=_parse_time(row.get("expires_at"))
        if row.get("status")!="invited" or (expiry and expiry<=datetime.now(timezone.utc)):
            raise HTTPException(409,detail={"code":"CINEMA_COLLABORATION_NOT_ACTIVE","message":"Undangan sudah tidak aktif."})
        changed=await _db("PATCH","cinema_collaborators",params={"id":"eq."+str(collaboration_id),"status":"eq.invited"},payload={
            "status":"active","accepted_by":user_id,"accepted_at":datetime.now(timezone.utc).isoformat(),"updated_at":datetime.now(timezone.utc).isoformat(),
        },prefer="return=representation")
    else:
        if row.get("owner_id")!=user_id:
            raise HTTPException(403,detail={"code":"CINEMA_COLLABORATION_REVOKE_FORBIDDEN","message":"Hanya pemilik film yang dapat mencabut undangan."})
        changed=await _db("PATCH","cinema_collaborators",params={"id":"eq."+str(collaboration_id),"owner_id":"eq."+user_id,"status":"in.(invited,active)"},payload={
            "status":"revoked","updated_at":datetime.now(timezone.utc).isoformat(),
        },prefer="return=representation")
    if not changed:
        raise HTTPException(409,detail={"code":"CINEMA_COLLABORATION_DECISION_CONFLICT","message":"Status undangan berubah; muat ulang sebelum mencoba lagi."})
    return {"collaborator":changed[0]}


@router.get("/creator/titles/{title_id}/versions")
async def list_cinema_versions(title_id: uuid.UUID,user: dict[str,Any]=Depends(current_user))->dict[str,Any]:
    await _owned_cinema_title(title_id,str(user["id"]))
    rows=await _db("GET","cinema_film_versions",params={
        "select":"id,title_id,version,created_at","title_id":"eq."+str(title_id),
        "owner_id":"eq."+str(user["id"]),"order":"version.desc","limit":"100",
    })
    return {"items":rows or []}


@router.post("/creator/titles/{title_id}/versions",status_code=201)
async def snapshot_cinema_version(title_id: uuid.UUID,user: dict[str,Any]=Depends(current_user))->dict[str,Any]:
    owner_id=str(user["id"])
    title=await _owned_cinema_title(title_id,owner_id)
    episodes=await _db("GET","cinema_episodes",params={
        "select":"id,episode_number,title,synopsis,media_id,duration_seconds,is_free_preview,status,updated_at",
        "title_id":"eq."+str(title_id),"owner_id":"eq."+owner_id,"order":"episode_number.asc","limit":"500",
    })
    credits=await _db("GET","cinema_creator_credits",params={
        "select":"id,contributor_type,contributor_user_id,contributor_agent_id,role,attribution_label,disclosure,provenance",
        "title_id":"eq."+str(title_id),"owner_id":"eq."+owner_id,"order":"created_at.asc","limit":"200",
    })
    collaborators=await _db("GET","cinema_collaborators",params={
        "select":"id,collaborator_user_id,collaborator_agent_id,role,permissions,status,accepted_at",
        "title_id":"eq."+str(title_id),"owner_id":"eq."+owner_id,"order":"created_at.asc","limit":"200",
    })
    production_rows=await _db("GET","cinema_titles",params={
        "select":"production_document","id":"eq."+str(title_id),"owner_id":"eq."+owner_id,"limit":"1",
    })
    asset_rows=await _db("GET","cinema_assets",params={
        "select":"id,media_id,asset_role,display_name,metadata,created_at",
        "title_id":"eq."+str(title_id),"owner_id":"eq."+owner_id,
        "order":"created_at.asc","limit":"1000",
    })
    snapshot={"title":title,"episodes":episodes or [],"credits":credits or [],
              "collaborators":collaborators or [],
              "production_document":(production_rows[0].get("production_document") if production_rows else None),
              "assets":asset_rows or [],"snapshot_schema":"cinema-film-v2"}
    version=int(title.get("version") or 1)
    existing=await _db("GET","cinema_film_versions",params={
        "select":"id,title_id,version,created_at","title_id":"eq."+str(title_id),"version":"eq."+str(version),"limit":"1",
    })
    if existing:
        return {"version":existing[0],"created":False}
    rows=await _db("POST","cinema_film_versions",payload={
        "title_id":str(title_id),"owner_id":owner_id,"version":version,"snapshot":snapshot,
        "created_by":owner_id,
    },prefer="return=representation")
    if not rows:
        raise HTTPException(503,detail={"code":"CINEMA_VERSION_SNAPSHOT_NOT_CONFIRMED","message":"Snapshot versi belum tersimpan."})
    return {"version":rows[0],"created":True}



_POLICY_TABLES={"access":"cinema_access_policy_versions","watch":"cinema_watch_policy_versions","earning":"cinema_creator_earning_policy_versions"}


def _validate_cinema_policy(kind:str,configuration:dict[str,Any])->None:
    if kind=="access":
        if configuration.get("territory_mode") not in {"global","allowlist","denylist"}:
            raise HTTPException(422,detail={"code":"CINEMA_TERRITORY_POLICY_INVALID","message":"territory_mode harus global, allowlist, atau denylist."})
        if configuration.get("maturity_mode") not in {"all_ages_only","age_verification"}:
            raise HTTPException(422,detail={"code":"CINEMA_MATURITY_POLICY_INVALID","message":"maturity_mode belum valid."})
        if not isinstance(configuration.get("free_preview_enabled"),bool) or not isinstance(configuration.get("premium_playback_enabled"),bool):
            raise HTTPException(422,detail={"code":"CINEMA_ACCESS_FLAGS_REQUIRED","message":"Flag free preview dan premium playback wajib eksplisit."})
        streams=configuration.get("max_concurrent_streams")
        if not isinstance(streams,int) or not 1<=streams<=10:
            raise HTTPException(422,detail={"code":"CINEMA_STREAM_LIMIT_INVALID","message":"max_concurrent_streams harus 1–10."})
    elif kind=="watch":
        seconds=configuration.get("minimum_watched_seconds")
        ratio=configuration.get("minimum_completion_ratio")
        window=configuration.get("unique_viewer_window_hours")
        if not isinstance(seconds,int) or seconds<1 or not isinstance(ratio,(int,float)) or not 0<ratio<=1 or not isinstance(window,int) or not 1<=window<=8760:
            raise HTTPException(422,detail={"code":"CINEMA_WATCH_POLICY_INVALID","message":"Ambang Qualified Watch, rasio completion dan unique-viewer window harus eksplisit."})
        if configuration.get("fraud_review_required") is not True:
            raise HTTPException(422,detail={"code":"CINEMA_FRAUD_REVIEW_REQUIRED","message":"Fraud review wajib diaktifkan untuk Qualified Watch."})
    elif kind=="earning":
        reward=configuration.get("creator_reward_credits_per_qualified_watch")
        if not isinstance(reward,int) or reward<0:
            raise HTTPException(422,detail={"code":"CINEMA_EARNING_POLICY_INVALID","message":"Nilai reward credits harus berupa integer non-negatif yang disetujui."})
        if configuration.get("cash_payout_enabled") is not False:
            raise HTTPException(422,detail={"code":"CINEMA_CASH_PAYOUT_DISABLED","message":"Cash payout belum dapat diaktifkan melalui policy ini."})
    else:
        raise HTTPException(404,detail={"code":"CINEMA_POLICY_KIND_UNKNOWN","message":"Jenis policy Cinema tidak dikenal."})


@router.post("/admin/playback-sessions/{session_id}/fraud-review")
async def review_cinema_playback_fraud(session_id:uuid.UUID,payload:CinemaFraudReview,request:Request,
                                       operator:dict[str,Any]=Depends(require_operator_scope("platform:billing.manage")))->dict[str,Any]:
    sessions=await _db("GET","cinema_playback_sessions",params={
        "select":"id,status,fraud_status,owner_user_id,title_id,episode_id",
        "id":"eq."+str(session_id),"limit":"1",
    })
    if not sessions: raise HTTPException(404,detail={"code":"CINEMA_PLAYBACK_SESSION_NOT_FOUND","message":"Sesi playback tidak ditemukan."})
    if sessions[0].get("status")!="finished":
        raise HTTPException(409,detail={"code":"CINEMA_PLAYBACK_NOT_FINISHED","message":"Fraud review hanya dilakukan setelah sesi selesai."})
    await write_operator_audit(request,actor_user_id=str(operator["id"]),action="cinema.playback.fraud_review",outcome="attempted",resource_type="cinema_playback_session",resource_id=str(session_id),metadata={"decision":payload.decision,"evidence_reference":payload.evidence_reference,"reason":payload.reason})
    changed=await _db("PATCH","cinema_playback_sessions",params={"id":"eq."+str(session_id),"status":"eq.finished","fraud_status":"eq.pending"},payload={
        "fraud_status":"cleared" if payload.decision=="clear" else "rejected",
        "fraud_reviewed_by":str(operator["id"]),"fraud_reviewed_at":datetime.now(timezone.utc).isoformat(),
        "fraud_evidence_reference":payload.evidence_reference,
    },prefer="return=representation")
    if not changed: raise HTTPException(409,detail={"code":"CINEMA_FRAUD_REVIEW_CONFLICT","message":"Status fraud berubah; periksa ulang sebelum memutuskan."})
    evaluation=await _db("POST","rpc/cinema_evaluate_qualified_watch",payload={"p_session_id":str(session_id)})
    await write_operator_audit(request,actor_user_id=str(operator["id"]),action="cinema.playback.fraud_review",outcome="allowed",resource_type="cinema_playback_session",resource_id=str(session_id),metadata={"decision":payload.decision,"evaluation":evaluation})
    return {"session":changed[0],"qualified_watch":evaluation}


@router.get("/admin/policies")
async def admin_cinema_policies(request:Request,operator:dict[str,Any]=Depends(require_operator_scope("platform:billing.manage")))->dict[str,Any]:
    result={}
    for kind,table in _POLICY_TABLES.items():
        rows=await _db("GET",table,params={"select":"*","order":"created_at.desc","limit":"100"})
        result[kind]=rows or []
    plans=await _db("GET","cinema_subscription_plans",params={"select":"*","order":"created_at.desc","limit":"100"})
    await write_operator_audit(request,actor_user_id=str(operator["id"]),action="cinema.policy_registry.read",outcome="allowed",resource_type="cinema_policy_registry",metadata={"counts":{k:len(v) for k,v in result.items()},"plans":len(plans or [])})
    return {"policies":result,"subscription_plans":plans or []}


@router.post("/admin/policies/{kind}",status_code=201)
async def create_cinema_policy(kind:str,payload:CinemaPolicyDraft,request:Request,
                               operator:dict[str,Any]=Depends(require_operator_scope("platform:billing.manage")))->dict[str,Any]:
    table=_POLICY_TABLES.get(kind)
    if not table: raise HTTPException(404,detail={"code":"CINEMA_POLICY_KIND_UNKNOWN","message":"Jenis policy Cinema tidak dikenal."})
    _validate_cinema_policy(kind,payload.configuration)
    effective=_parse_time(payload.effective_at)
    expiry=_parse_time(payload.expires_at)
    if not effective or (expiry and expiry<=effective):
        raise HTTPException(422,detail={"code":"CINEMA_POLICY_WINDOW_INVALID","message":"Periode efektif policy tidak valid."})
    await write_operator_audit(request,actor_user_id=str(operator["id"]),action="cinema.policy.create",outcome="attempted",resource_type="cinema_policy",resource_id=payload.policy_version,metadata={"kind":kind,"approval_reference":payload.approval_reference})
    rows=await _db("POST",table,payload={
        "policy_version":payload.policy_version,"approval_reference":payload.approval_reference,
        "configuration":payload.configuration,"status":"draft","effective_at":effective.isoformat(),
        "expires_at":expiry.isoformat() if expiry else None,"created_by":str(operator["id"]),
    },prefer="return=representation")
    if not rows: raise HTTPException(503,detail={"code":"CINEMA_POLICY_CREATE_UNCONFIRMED","message":"Draft policy belum tersimpan."})
    await write_operator_audit(request,actor_user_id=str(operator["id"]),action="cinema.policy.create",outcome="allowed",resource_type="cinema_policy",resource_id=payload.policy_version,metadata={"kind":kind})
    return {"policy":rows[0]}


@router.post("/admin/policies/{kind}/{policy_version}/approve")
async def approve_cinema_policy(kind:str,policy_version:str,payload:CinemaPolicyApproval,request:Request,
                                operator:dict[str,Any]=Depends(require_operator_scope("platform:billing.manage")))->dict[str,Any]:
    table=_POLICY_TABLES.get(kind)
    if not table: raise HTTPException(404,detail={"code":"CINEMA_POLICY_KIND_UNKNOWN","message":"Jenis policy Cinema tidak dikenal."})
    rows=await _db("GET",table,params={"select":"policy_version,approval_reference,configuration,status,effective_at,expires_at,created_by","policy_version":"eq."+policy_version,"limit":"1"})
    if not rows: raise HTTPException(404,detail={"code":"CINEMA_POLICY_NOT_FOUND","message":"Draft policy tidak ditemukan."})
    row=rows[0]
    if row.get("status")!="draft" or row.get("created_by")==str(operator["id"]):
        raise HTTPException(409,detail={"code":"CINEMA_POLICY_FOUR_EYES_REQUIRED","message":"Policy harus disetujui operator berbeda dari pembuatnya dan masih berstatus draft."})
    _validate_cinema_policy(kind,row.get("configuration") or {})
    await write_operator_audit(request,actor_user_id=str(operator["id"]),action="cinema.policy.approve",outcome="attempted",resource_type="cinema_policy",resource_id=policy_version,metadata={"kind":kind,"reason":payload.reason})
    changed=await _db("PATCH",table,params={"policy_version":"eq."+policy_version,"status":"eq.draft","created_by":"neq."+str(operator["id"])},payload={
        "status":"approved","approved_by":str(operator["id"]),
    },prefer="return=representation")
    if not changed: raise HTTPException(409,detail={"code":"CINEMA_POLICY_APPROVAL_CONFLICT","message":"Policy berubah saat persetujuan."})
    await write_operator_audit(request,actor_user_id=str(operator["id"]),action="cinema.policy.approve",outcome="allowed",resource_type="cinema_policy",resource_id=policy_version,metadata={"kind":kind,"reason":payload.reason})
    return {"policy":changed[0]}


@router.post("/admin/subscription-plans",status_code=201)
async def create_cinema_subscription_plan(payload:CinemaPlanDraft,request:Request,
                                          operator:dict[str,Any]=Depends(require_operator_scope("platform:billing.manage")))->dict[str,Any]:
    products=await _db("GET","billing_products",params={"select":"product_key,status,purpose","product_key":"eq."+payload.product_key,"status":"eq.active","purpose":"eq.premium_subscription","limit":"1"})
    if not products:
        raise HTTPException(409,detail={"code":"CINEMA_BILLING_PRODUCT_NOT_ACTIVE","message":"Plan harus menunjuk billing product premium yang aktif dan telah disetujui."})
    rows=await _db("POST","cinema_subscription_plans",payload={
        "plan_key":payload.plan_key,"product_key":payload.product_key,"entitlement_key":payload.entitlement_key,
        "entitlement_version":payload.entitlement_version,"approval_reference":payload.approval_reference,
        "configuration":payload.configuration,"status":"draft","created_by":str(operator["id"]),
    },prefer="return=representation")
    if not rows: raise HTTPException(503,detail={"code":"CINEMA_PLAN_CREATE_UNCONFIRMED","message":"Draft subscription plan belum tersimpan."})
    await write_operator_audit(request,actor_user_id=str(operator["id"]),action="cinema.subscription_plan.create",outcome="allowed",resource_type="cinema_subscription_plan",resource_id=payload.plan_key,metadata={"product_key":payload.product_key,"approval_reference":payload.approval_reference})
    return {"plan":rows[0]}


@router.post("/admin/subscription-plans/{plan_key}/activate")
async def activate_cinema_subscription_plan(plan_key:str,payload:CinemaPolicyApproval,request:Request,
                                            operator:dict[str,Any]=Depends(require_operator_scope("platform:billing.manage")))->dict[str,Any]:
    plans=await _db("GET","cinema_subscription_plans",params={"select":"plan_key,product_key,approval_reference,status,created_by","plan_key":"eq."+plan_key,"limit":"1"})
    if not plans: raise HTTPException(404,detail={"code":"CINEMA_PLAN_NOT_FOUND","message":"Plan tidak ditemukan."})
    plan=plans[0]
    if plan.get("status")!="draft" or plan.get("created_by")==str(operator["id"]):
        raise HTTPException(409,detail={"code":"CINEMA_PLAN_FOUR_EYES_REQUIRED","message":"Plan harus disetujui operator berbeda dari pembuatnya."})
    products=await _db("GET","billing_products",params={"select":"product_key,status,purpose","product_key":"eq."+str(plan["product_key"]),"status":"eq.active","purpose":"eq.premium_subscription","limit":"1"})
    if not products or not plan.get("approval_reference"):
        raise HTTPException(409,detail={"code":"CINEMA_PLAN_NOT_APPROVED","message":"Product billing atau approval reference belum valid."})
    changed=await _db("PATCH","cinema_subscription_plans",params={"plan_key":"eq."+plan_key,"status":"eq.draft","created_by":"neq."+str(operator["id"])},payload={"status":"active","updated_at":datetime.now(timezone.utc).isoformat()},prefer="return=representation")
    if not changed: raise HTTPException(409,detail={"code":"CINEMA_PLAN_ACTIVATION_CONFLICT","message":"Plan berubah saat aktivasi."})
    await write_operator_audit(request,actor_user_id=str(operator["id"]),action="cinema.subscription_plan.activate",outcome="allowed",resource_type="cinema_subscription_plan",resource_id=plan_key,metadata={"reason":payload.reason,"product_key":plan["product_key"]})
    return {"plan":changed[0]}



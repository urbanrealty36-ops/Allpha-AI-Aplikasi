"""ENG-P14 social feed, interactions and user controls."""
from __future__ import annotations
import base64, json, re, uuid
from datetime import datetime, timezone
from typing import Any, Literal
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from allpha_api.auth import current_user, optional_current_user
from allpha_api.content_api import _server_db, _signed_media_preview_url
from allpha_api.operator_security import require_operator_scope, write_operator_audit

router = APIRouter(tags=["social-feed"])
FIELDS = "id,owner_id,content_type,body,visibility,status,moderation_status,version,created_at,updated_at,published_at"
MEDIA_FIELDS = "id,content_id,owner_id,bucket_id,storage_path,filename,media_type,size_bytes,sha256,status,created_at"
CANDIDATES = 1000

class ReactionWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reaction: Literal["like"] = "like"

class CommentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    body: str = Field(min_length=1, max_length=2000)

class ReportCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: Literal["spam", "harassment", "privacy", "misinformation", "other"]
    details: str | None = Field(default=None, max_length=1000)

class ShareCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    share_target: Literal["copy_link", "native_share", "external"] = "copy_link"

class PreferencesWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    personalization_enabled: bool
    ranking_mode: Literal["for_you", "recent"]

class ReportReview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Literal["dismiss", "hide_content"]
    reason: str = Field(min_length=8, max_length=500)

def _now() -> datetime:
    return datetime.now(timezone.utc)

def _cursor_encode(offset: int, as_of: datetime) -> str:
    raw = json.dumps({"v": 1, "offset": offset, "as_of": as_of.isoformat()}, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")

def _cursor_decode(cursor: str | None) -> tuple[int, datetime]:
    if not cursor:
        return 0, _now()
    try:
        raw = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4))
        data = json.loads(raw)
        offset = data["offset"]
        as_of = datetime.fromisoformat(str(data["as_of"]).replace("Z", "+00:00"))
        if data.get("v") != 1 or not isinstance(offset, int) or isinstance(offset, bool) or not 0 <= offset < 5000 or as_of.tzinfo is None:
            raise ValueError("cursor")
        return offset, as_of.astimezone(timezone.utc)
    except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        raise HTTPException(422, detail={"code": "FEED_CURSOR_INVALID", "message": "Cursor feed tidak valid; muat ulang feed."}) from exc

async def _visible_content(content_id: uuid.UUID, viewer_id: str) -> dict[str, Any]:
    rows = await _server_db("GET", "content_items", params={
        "select": FIELDS, "id": f"eq.{content_id}", "status": "eq.published",
        "moderation_status": "eq.approved", "visibility": "in.(public,followers)", "limit": "1",
    })
    if not rows:
        raise HTTPException(404, detail={"code": "FEED_CONTENT_NOT_FOUND", "message": "Konten tidak ditemukan atau tidak dapat diakses."})
    item = rows[0]
    followed, hidden = await _edges(viewer_id)
    owner_id = str(item.get("owner_id"))
    owner_profile = (await _profiles_for({owner_id})).get(owner_id)
    if (
        not owner_profile
        or owner_profile.get("account_status", "active") != "active"
        or owner_id in hidden
        or (item.get("visibility") == "followers" and owner_id not in followed)
        or (owner_profile.get("visibility") != "public" and owner_id not in followed and owner_id != viewer_id)
    ):
        raise HTTPException(404, detail={"code": "FEED_CONTENT_NOT_FOUND", "message": "Konten tidak ditemukan atau tidak dapat diakses."})
    return item

async def _edges(user_id: str) -> tuple[set[str], set[str]]:
    outgoing = await _server_db("GET", "social_edges", params={
        "select": "target_user_id,edge_type,status", "actor_user_id": f"eq.{user_id}",
        "edge_type": "in.(follow,block,mute)", "limit": "1500",
    })
    incoming = await _server_db("GET", "social_edges", params={
        "select": "actor_user_id,status", "target_user_id": f"eq.{user_id}",
        "edge_type": "eq.block", "status": "eq.active", "limit": "500",
    })
    followed = {str(x["target_user_id"]) for x in (outgoing or []) if x.get("edge_type") == "follow" and x.get("status") == "active"}
    hidden = {
        str(x["target_user_id"]) for x in (outgoing or [])
        if x.get("edge_type") in {"block", "mute"} and x.get("status") == "active"
    }
    hidden.update(str(x["actor_user_id"]) for x in (incoming or []) if x.get("status") == "active")
    return followed, hidden

async def _profiles_for(user_ids: set[str]) -> dict[str, dict[str, Any]]:
    ids = sorted(value for value in user_ids if value)
    if not ids:
        return {}
    rows = await _server_db("GET", "profiles", params={
        "select": "id,username,display_name,avatar_url,bio,visibility,account_status",
        "id": f"in.({','.join(ids)})", "limit": str(min(1000, len(ids))),
    })
    return {str(row.get("id")): row for row in (rows or [])}


def _published(row: dict[str, Any]) -> datetime:
    try:
        value = datetime.fromisoformat(str(row.get("published_at") or row.get("created_at")).replace("Z", "+00:00"))
        return (value if value.tzinfo else value.replace(tzinfo=timezone.utc)).astimezone(timezone.utc)
    except (ValueError, TypeError):
        return datetime.fromtimestamp(0, tz=timezone.utc)

@router.get("/v1/feed")
async def get_feed(request: Request, mode: Literal["for_you", "recent"] = "for_you",
                   limit: int = Query(default=20, ge=1, le=50), cursor: str | None = None,
                   user: dict[str, Any] | None = Depends(optional_current_user)) -> dict[str, Any]:
    # Guest reads are public-only and chronological. Personalization and relationship filters require identity.
    owner = str(user["id"]) if user else None
    offset, as_of = _cursor_decode(cursor)
    if owner:
        prefs_rows = await _server_db("GET", "feed_preferences", params={
            "select": "personalization_enabled,ranking_mode", "user_id": f"eq.{owner}", "limit": "1"})
        prefs = prefs_rows[0] if prefs_rows else {"personalization_enabled": True, "ranking_mode": "for_you"}
        enabled = bool(prefs.get("personalization_enabled", True))
        effective_mode = "recent" if not enabled else (prefs.get("ranking_mode", "for_you") if mode == "for_you" else "recent")
        visibility_filter = "in.(public,followers)"
    else:
        prefs = {"personalization_enabled": False, "ranking_mode": "recent"}
        enabled = False
        effective_mode = "recent"
        visibility_filter = "eq.public"
    rows = await _server_db("GET", "content_items", params={
        "select": FIELDS, "content_type": "not.eq.story", "status": "eq.published", "moderation_status": "eq.approved",
        "visibility": visibility_filter, "published_at": f"lte.{as_of.isoformat()}",
        "order": "published_at.desc,id.desc", "limit": str(CANDIDATES)})
    candidates = rows or []
    followed, hidden = await _edges(owner) if owner else (set(), set())
    profile_by_id = await _profiles_for({str(row.get("owner_id") or "") for row in candidates})
    candidates = [
        row for row in candidates
        if str(row.get("owner_id")) not in hidden
        and str(row.get("owner_id")) in profile_by_id
        and profile_by_id[str(row.get("owner_id"))].get("account_status", "active") == "active"
        and (
            (row.get("visibility") == "public" and (
                profile_by_id[str(row.get("owner_id"))].get("visibility") == "public"
                or (owner and str(row.get("owner_id")) in followed)
            ))
            or (owner and row.get("visibility") == "followers" and str(row.get("owner_id")) in followed)
        )
    ]
    interest_keys: list[str] = []
    not_interested_keys: list[str] = []
    if owner and effective_mode == "for_you" and enabled:
        interest_rows = await _server_db("GET", "user_interests", params={
            "select": "interest_key,preference", "user_id": f"eq.{owner}", "limit": "500",
        })
        interest_keys = [str(row["interest_key"]).casefold() for row in (interest_rows or [])
                         if row.get("interest_key") and row.get("preference") == "interested"]
        not_interested_keys = [str(row["interest_key"]).casefold() for row in (interest_rows or [])
                               if row.get("interest_key") and row.get("preference") == "not_interested"]
    if not_interested_keys:
        def matches_interest(body: str, key: str) -> bool:
            terms = set(re.findall(r"[a-z0-9]+", key))
            tokens = set(re.findall(r"[a-z0-9]+", body.casefold()))
            return bool(terms) and terms.issubset(tokens)
        candidates = [row for row in candidates if not any(matches_interest(str(row.get("body") or ""), key) for key in not_interested_keys)]
    ids = [str(r["id"]) for r in candidates]
    if not ids:
        return {"items": [], "next_cursor": None, "mode": effective_mode, "personalization_enabled": enabled, "as_of": as_of.isoformat()}
    in_ids = f"in.({','.join(ids)})"
    reactions = await _server_db("GET", "content_reactions", params={"select": "content_id,actor_user_id,reaction", "content_id": in_ids, "limit": "5000"})
    comments = await _server_db("GET", "content_comments", params={"select": "content_id", "content_id": in_ids, "status": "eq.visible", "limit": "5000"})
    saves = await _server_db("GET", "content_saves", params={"select": "content_id,actor_user_id", "content_id": in_ids, "limit": "5000"})
    shares = await _server_db("GET", "content_shares", params={"select": "content_id", "content_id": in_ids, "limit": "5000"})
    likes: dict[str, int] = {}; comment_counts: dict[str, int] = {}; save_counts: dict[str, int] = {}; share_counts: dict[str, int] = {}
    viewer_reactions: dict[str, str] = {}; viewer_saves: set[str] = set()
    for row in reactions or []:
        cid = str(row["content_id"]); likes[cid] = likes.get(cid, 0) + 1
        if owner and str(row.get("actor_user_id")) == owner: viewer_reactions[cid] = str(row.get("reaction") or "like")
    for row in comments or []:
        cid = str(row["content_id"]); comment_counts[cid] = comment_counts.get(cid, 0) + 1
    for row in saves or []:
        cid = str(row["content_id"]); save_counts[cid] = save_counts.get(cid, 0) + 1
        if owner and str(row.get("actor_user_id")) == owner: viewer_saves.add(cid)
    for row in shares or []:
        cid = str(row["content_id"]); share_counts[cid] = share_counts.get(cid, 0) + 1
    ranked = []
    for row in candidates:
        cid = str(row["id"])
        like_count, comment_count, save_count, share_count = likes.get(cid, 0), comment_counts.get(cid, 0), save_counts.get(cid, 0), share_counts.get(cid, 0)
        followed_creator = bool(owner and str(row.get("owner_id")) in followed)
        body_tokens = set(re.findall(r"[a-z0-9]+", str(row.get("body") or "").casefold()))
        interest_matches = sum(
            1 for key in interest_keys
            if (terms := set(re.findall(r"[a-z0-9]+", key))) and terms.issubset(body_tokens)
        )
        engagement_total = like_count + comment_count + save_count + share_count
        signals = ["recency"]
        if followed_creator:
            signals.append("followed_creator")
        if interest_matches:
            signals.append("explicit_interest_match")
        if engagement_total:
            signals.append("engagement")
        # Version 1 is lexicographic, not a fabricated weighted score: followed creator,
        # explicit user-interest match count, observed engagement, then publish time.
        rank_key = (int(followed_creator), interest_matches, engagement_total, _published(row), str(row["id"]))
        ranked.append({**row, "engagement": {"likes": like_count, "comments": comment_count, "saves": save_count, "shares": share_count},
                       "viewer_reaction": viewer_reactions.get(cid), "saved": cid in viewer_saves,
                       "ranking_signals": signals, "_rank": rank_key})
    ranked.sort(key=(lambda r: r["_rank"]) if effective_mode == "for_you"
                else (lambda r: (_published(r), str(r["id"]))), reverse=True)
    # Apply creator diversity before offset pagination so page boundaries remain stable.
    diverse: list[dict[str, Any]] = []
    creator_counts: dict[str, int] = {}
    for row in ranked:
        creator_id = str(row.get("owner_id"))
        if creator_counts.get(creator_id, 0) >= 3:
            continue
        creator_counts[creator_id] = creator_counts.get(creator_id, 0) + 1
        diverse.append(row)
    ranked = diverse
    page = ranked[offset:offset + limit]
    selected = [str(r["id"]) for r in page]
    media_by_id: dict[str, list[dict[str, Any]]] = {}
    if selected:
        media = await _server_db("GET", "content_media", params={
            "select": MEDIA_FIELDS, "content_id": f"in.({','.join(selected)})",
            "status": "in.(uploaded,ready)", "order": "created_at.asc", "limit": str(min(250, limit * 5))})
        for row in media or []:
            item = {k: v for k, v in row.items() if k != "storage_path"}
            item["preview_url"] = await _signed_media_preview_url(str(row["storage_path"]))
            media_by_id.setdefault(str(row["content_id"]), []).append(item)
    items = []
    for row in page:
        cid = str(row["id"]); item = {k: v for k, v in row.items() if k != "_rank"}
        item["media"] = media_by_id.get(cid, [])
        creator = profile_by_id.get(str(row.get("owner_id")), {})
        item["creator"] = {"username": creator.get("username"), "display_name": creator.get("display_name") or creator.get("username") or "Kreator", "avatar_url": creator.get("avatar_url")}
        items.append(item)
    next_offset = offset + len(page)
    return {"items": items, "next_cursor": _cursor_encode(next_offset, as_of) if next_offset < len(ranked) and next_offset < CANDIDATES else None,
            "mode": effective_mode, "personalization_enabled": enabled, "as_of": as_of.isoformat()}


@router.get("/v1/me/profile-feed", tags=["social-feed"])
async def get_my_profile_feed(
    limit: int = Query(default=50, ge=1, le=100),
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    """Return the authenticated owner's published, approved content with canonical engagement/media metadata."""
    owner = str(user["id"])
    rows = await _server_db("GET", "content_items", params={
        "select": FIELDS, "owner_id": f"eq.{owner}", "content_type": "not.eq.story",
        "status": "eq.published", "moderation_status": "eq.approved",
        "order": "published_at.desc,id.desc", "limit": str(limit),
    })
    page = rows or []
    if not page:
        return {"items": [], "count": 0, "source": "authenticated_owner_content"}
    ids = [str(row["id"]) for row in page]
    in_ids = f"in.({','.join(ids)})"
    reactions = await _server_db("GET", "content_reactions", params={
        "select": "content_id,actor_user_id,reaction", "content_id": in_ids, "limit": "5000",
    })
    comments = await _server_db("GET", "content_comments", params={
        "select": "content_id", "content_id": in_ids, "status": "eq.visible", "limit": "5000",
    })
    saves = await _server_db("GET", "content_saves", params={
        "select": "content_id,actor_user_id", "content_id": in_ids, "limit": "5000",
    })
    shares = await _server_db("GET", "content_shares", params={
        "select": "content_id", "content_id": in_ids, "limit": "5000",
    })
    likes_by_id: dict[str, int] = {}
    comments_by_id: dict[str, int] = {}
    shares_by_id: dict[str, int] = {}
    viewer_reactions: dict[str, str] = {}
    viewer_saves: set[str] = set()
    for row in reactions or []:
        content_id = str(row["content_id"])
        likes_by_id[content_id] = likes_by_id.get(content_id, 0) + 1
        if str(row.get("actor_user_id")) == owner:
            viewer_reactions[content_id] = str(row.get("reaction") or "like")
    for row in comments or []:
        content_id = str(row["content_id"])
        comments_by_id[content_id] = comments_by_id.get(content_id, 0) + 1
    for row in saves or []:
        content_id = str(row["content_id"])
        if str(row.get("actor_user_id")) == owner:
            viewer_saves.add(content_id)
    for row in shares or []:
        content_id = str(row["content_id"])
        shares_by_id[content_id] = shares_by_id.get(content_id, 0) + 1
    media_by_id: dict[str, list[dict[str, Any]]] = {}
    media = await _server_db("GET", "content_media", params={
        "select": MEDIA_FIELDS, "content_id": in_ids, "owner_id": f"eq.{owner}",
        "status": "in.(uploaded,ready)", "order": "created_at.asc", "limit": str(min(500, limit * 5)),
    })
    for row in media or []:
        item = {key: value for key, value in row.items() if key != "storage_path"}
        item["preview_url"] = await _signed_media_preview_url(str(row["storage_path"]))
        media_by_id.setdefault(str(row["content_id"]), []).append(item)
    profile_rows = await _profiles_for({owner})
    creator = profile_rows.get(owner, {})
    items = []
    for row in page:
        content_id = str(row["id"])
        items.append({
            **row,
            "media": media_by_id.get(content_id, []),
            "creator": {
                "username": creator.get("username"),
                "display_name": creator.get("display_name") or creator.get("username") or "Kreator",
                "avatar_url": creator.get("avatar_url"),
            },
            "engagement": {
                "likes": likes_by_id.get(content_id, 0),
                "comments": comments_by_id.get(content_id, 0),
                "saves": sum(1 for saved in saves or [] if str(saved.get("content_id")) == content_id),
                "shares": shares_by_id.get(content_id, 0),
            },
            "viewer_reaction": viewer_reactions.get(content_id),
            "saved": content_id in viewer_saves,
        })
    return {"items": items, "count": len(items), "source": "authenticated_owner_content"}


@router.get("/v1/recommendations/creators", tags=["search-discovery"])
async def get_public_creator_recommendations(
    limit: int = Query(default=12, ge=1, le=30),
    user: dict[str, Any] | None = Depends(optional_current_user),
) -> dict[str, Any]:
    """Recommend only public profile owners with real eligible public content; never invent verification or contact signals."""
    content_rows = await _server_db("GET", "content_items", params={
        "select": "owner_id,published_at", "content_type": "not.eq.story",
        "status": "eq.published", "moderation_status": "eq.approved", "visibility": "eq.public",
        "order": "published_at.desc,id.desc", "limit": "1000",
    })
    counts: dict[str, int] = {}
    latest: dict[str, str] = {}
    for row in content_rows or []:
        creator_id = str(row.get("owner_id") or "")
        if not creator_id:
            continue
        counts[creator_id] = counts.get(creator_id, 0) + 1
        published_at = str(row.get("published_at") or "")
        if creator_id not in latest or published_at > latest[creator_id]:
            latest[creator_id] = published_at
    if not counts:
        return {"items": [], "count": 0, "source": "eligible_public_content"}
    owner = str(user["id"]) if user else None
    followed, hidden = await _edges(owner) if owner else (set(), set())
    excluded = hidden | followed
    if owner:
        excluded.add(owner)
    candidate_ids = [creator_id for creator_id in counts if creator_id not in excluded]
    if not candidate_ids:
        return {"items": [], "count": 0, "source": "eligible_public_content"}
    profiles = await _server_db("GET", "profiles", params={
        "select": "id,username,display_name,avatar_url,bio,visibility,account_status,created_at",
        "id": f"in.({','.join(candidate_ids)})", "visibility": "eq.public", "account_status": "eq.active",
        "limit": str(min(100, max(limit * 5, limit))),
    })
    by_id = {str(row.get("id")): row for row in (profiles or [])}
    ranked = sorted((creator_id for creator_id in candidate_ids if creator_id in by_id),
                    key=lambda creator_id: (counts[creator_id], latest.get(creator_id, "")), reverse=True)
    items = []
    for creator_id in ranked[:limit]:
        profile = by_id[creator_id]
        items.append({
            "id": creator_id,
            "username": profile.get("username"),
            "display_name": profile.get("display_name") or profile.get("username") or "Kreator",
            "avatar_url": profile.get("avatar_url"),
            "bio": profile.get("bio") or "",
            "public_post_count": counts[creator_id],
            "last_public_post_at": latest.get(creator_id),
            "is_ai": False,
        })
    return {"items": items, "count": len(items), "source": "eligible_public_content"}


@router.put("/v1/social/follow/{target_user_id}", tags=["social-graph"])
async def follow_public_profile(
    target_user_id: uuid.UUID,
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    actor_id = str(user["id"])
    target_id = str(target_user_id)
    if actor_id == target_id:
        raise HTTPException(status_code=422, detail={"code": "SOCIAL_EDGE_SELF_TARGET", "message": "Akun tidak dapat mengikuti dirinya sendiri."})
    target_rows = await _server_db("GET", "profiles", params={
        "select": "id,visibility,account_status", "id": f"eq.{target_id}", "limit": "1",
    })
    target_profile = target_rows[0] if target_rows else None
    if (
        not target_profile
        or target_profile.get("visibility") not in {"public", "private"}
        or target_profile.get("account_status", "active") != "active"
    ):
        raise HTTPException(status_code=404, detail={"code": "PUBLIC_PROFILE_NOT_FOUND", "message": "Akun tidak ditemukan."})
    for source, target in ((actor_id, target_id), (target_id, actor_id)):
        blocks = await _server_db("GET", "social_edges", params={
            "select": "id", "actor_user_id": f"eq.{source}", "target_user_id": f"eq.{target}",
            "edge_type": "eq.block", "status": "eq.active", "limit": "1",
        })
        if blocks:
            raise HTTPException(status_code=403, detail={"code": "SOCIAL_EDGE_BLOCKED", "message": "Tindakan ini tidak tersedia karena pembatasan akun."})
    existing = await _server_db("GET", "social_edges", params={
        "select": "id,status", "actor_user_id": f"eq.{actor_id}", "target_user_id": f"eq.{target_id}",
        "edge_type": "eq.follow", "limit": "1",
    })
    if existing:
        return {"target_user_id": target_id, "status": existing[0].get("status"), "created": False}
    rows = await _server_db("POST", "social_edges", params={"select": "id,target_user_id,status,created_at"},
        body={"actor_user_id": actor_id, "target_user_id": target_id, "edge_type": "follow", "status": "active"},
        prefer="return=representation")
    if not rows:
        raise HTTPException(status_code=409, detail={"code": "SOCIAL_FOLLOW_NOT_RECORDED", "message": "Permintaan mengikuti akun tidak dapat disimpan."})
    return {"target_user_id": target_id, "status": rows[0].get("status"), "created": True}


@router.delete("/v1/social/follow/{target_user_id}", tags=["social-graph"])
async def unfollow_profile(
    target_user_id: uuid.UUID,
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    actor_id = str(user["id"])
    target_id = str(target_user_id)
    if actor_id == target_id:
        raise HTTPException(status_code=422, detail={"code": "SOCIAL_EDGE_SELF_TARGET", "message": "Akun tidak dapat mengikuti dirinya sendiri."})
    await _server_db("DELETE", "social_edges", params={
        "actor_user_id": f"eq.{actor_id}", "target_user_id": f"eq.{target_id}", "edge_type": "eq.follow",
    }, prefer="return=minimal")
    return {"target_user_id": target_id, "status": "not_following"}


@router.get("/v1/search", tags=["search-discovery"])
async def search_content(
    q: str = Query(min_length=2, max_length=100),
    limit: int = Query(default=20, ge=1, le=50),
    user: dict[str, Any] | None = Depends(optional_current_user),
) -> dict[str, Any]:
    """Search only published, approved content and re-apply social visibility controls."""
    query = " ".join(re.findall(r"[a-zA-Z0-9À-ÿ -]+", q)).strip()
    terms = [part for part in query.split() if len(part) >= 2][:8]
    if not terms:
        raise HTTPException(422, detail={"code": "SEARCH_QUERY_INVALID", "message": "Masukkan kata kunci yang valid."})
    owner = str(user["id"]) if user else None
    # Each term is sanitized before it is sent to PostgREST; database filters remain authoritative.
    clauses = [f"body.ilike.*{term.replace('*', '').replace('%', '').replace('_', '')}*" for term in terms]
    rows = await _server_db("GET", "content_items", params={
        "select": FIELDS, "content_type": "not.eq.story", "status": "eq.published", "moderation_status": "eq.approved",
        "visibility": "in.(public,followers)" if owner else "eq.public", "or": f"({','.join(clauses)})",
        "order": "published_at.desc,id.desc", "limit": "500",
    })
    followed, hidden = await _edges(owner) if owner else (set(), set())
    eligible = [
        row for row in (rows or [])
        if str(row.get("owner_id")) not in hidden
        and (row.get("visibility") == "public" or (owner and row.get("visibility") == "followers" and str(row.get("owner_id")) in followed))
    ]
    profile_by_id = await _profiles_for({str(row.get("owner_id") or "") for row in eligible})
    eligible = [
        row for row in eligible
        if str(row.get("owner_id")) in profile_by_id
        and profile_by_id[str(row.get("owner_id"))].get("account_status", "active") == "active"
        and (profile_by_id[str(row.get("owner_id"))].get("visibility") == "public"
             or (owner and str(row.get("owner_id")) in followed))
    ]
    needle = query.casefold()
    eligible.sort(key=lambda row: (
        0 if needle in str(row.get("body") or "").casefold() else 1,
        -sum(1 for term in terms if term.casefold() in str(row.get("body") or "").casefold()),
        -_published(row).timestamp(),
        str(row.get("id")),
    ))
    page = eligible[:limit]
    ids = [str(row["id"]) for row in page]
    media_by_id: dict[str, list[dict[str, Any]]] = {}
    if ids:
        media = await _server_db("GET", "content_media", params={
            "select": MEDIA_FIELDS, "content_id": f"in.({','.join(ids)})",
            "status": "in.(uploaded,ready)", "order": "created_at.asc", "limit": str(min(200, limit * 5)),
        })
        for row in media or []:
            safe = {key: value for key, value in row.items() if key != "storage_path"}
            safe["preview_url"] = await _signed_media_preview_url(str(row["storage_path"]))
            media_by_id.setdefault(str(row["content_id"]), []).append(safe)
    reactions = await _server_db("GET", "content_reactions", params={"select": "content_id", "content_id": f"in.({','.join(ids)})", "limit": "5000"}) if ids else []
    comments = await _server_db("GET", "content_comments", params={"select": "content_id", "content_id": f"in.({','.join(ids)})", "status": "eq.visible", "limit": "5000"}) if ids else []
    shares = await _server_db("GET", "content_shares", params={"select": "content_id", "content_id": f"in.({','.join(ids)})", "limit": "5000"}) if ids else []
    counts: dict[str, dict[str, int]] = {}
    for row in page:
        counts[str(row["id"])] = {"likes": 0, "comments": 0, "saves": 0, "shares": 0}
    for row in reactions or []:
        cid = str(row["content_id"])
        if cid in counts: counts[cid]["likes"] += 1
    for row in comments or []:
        cid = str(row["content_id"])
        if cid in counts: counts[cid]["comments"] += 1
    for row in shares or []:
        cid = str(row["content_id"])
        if cid in counts: counts[cid]["shares"] += 1
    items = [{
        **row, "media": media_by_id.get(str(row["id"]), []), "engagement": counts[str(row["id"])],
        "creator": {"username": profile_by_id.get(str(row.get("owner_id")), {}).get("username"),
                    "display_name": profile_by_id.get(str(row.get("owner_id")), {}).get("display_name") or profile_by_id.get(str(row.get("owner_id")), {}).get("username") or "Kreator",
                    "avatar_url": profile_by_id.get(str(row.get("owner_id")), {}).get("avatar_url")},
    } for row in page]
    return {"query": query, "items": items, "count": len(items), "has_more": len(eligible) > limit}


@router.get("/v1/trends", tags=["search-discovery"])
async def get_trends(
    limit: int = Query(default=10, ge=1, le=30),
    user: dict[str, Any] | None = Depends(optional_current_user),
) -> dict[str, Any]:
    """Derive trends from actual public content for guests and eligible content for signed-in users."""
    owner = str(user["id"]) if user else None
    rows = await _server_db("GET", "content_items", params={
        "select": FIELDS, "content_type": "not.eq.story", "status": "eq.published", "moderation_status": "eq.approved",
        "visibility": "in.(public,followers)" if owner else "eq.public", "order": "published_at.desc,id.desc", "limit": "500",
    })
    followed, hidden = await _edges(owner) if owner else (set(), set())
    visible = [
        row for row in (rows or [])
        if str(row.get("owner_id")) not in hidden
        and (row.get("visibility") == "public" or (owner and row.get("visibility") == "followers" and str(row.get("owner_id")) in followed))
    ]
    profile_by_id = await _profiles_for({str(row.get("owner_id") or "") for row in visible})
    visible = [
        row for row in visible
        if str(row.get("owner_id")) in profile_by_id
        and profile_by_id[str(row.get("owner_id"))].get("account_status", "active") == "active"
        and (profile_by_id[str(row.get("owner_id"))].get("visibility") == "public"
             or (owner and str(row.get("owner_id")) in followed))
    ]
    stopwords = {
        "yang", "dan", "atau", "untuk", "dari", "dengan", "pada", "ini", "itu", "akan",
        "tidak", "ada", "saya", "kami", "kamu", "bisa", "juga", "dalam", "karena",
        "the", "and", "for", "from", "with", "this", "that", "you", "your", "are",
        "was", "have", "has", "will", "not", "but", "our", "all", "about", "into",
    }
    counts: dict[str, int] = {}
    examples: dict[str, dict[str, Any]] = {}
    for row in visible:
        tokens = set(re.findall(r"[a-zA-ZÀ-ÿ][a-zA-ZÀ-ÿ0-9_]{2,}", str(row.get("body") or "").casefold()))
        for token in tokens - stopwords:
            counts[token] = counts.get(token, 0) + 1
            examples.setdefault(token, {"content_id": str(row["id"]), "published_at": row.get("published_at")})
    trends = [
        {"topic": topic, "content_count": count, "example_content_id": examples[topic]["content_id"]}
        for topic, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:limit]
    ]
    return {"items": trends, "source": "eligible_published_content", "window": "latest_500_candidates"}


@router.get("/v1/recommendations", tags=["search-discovery"])
async def get_recommendations(
    limit: int = Query(default=10, ge=1, le=30),
    user: dict[str, Any] | None = Depends(optional_current_user),
    request: Request = None,
) -> dict[str, Any]:
    """Reuse canonical feed ranking and preference controls for recommendations."""
    page = await get_feed(request=request, mode="for_you", limit=limit, cursor=None, user=user)
    return {"items": page["items"], "mode": page["mode"], "personalization_enabled": page["personalization_enabled"]}


@router.get("/v1/reels", tags=["reels"])
async def get_reels(request: Request, mode: Literal["for_you", "recent"] = "for_you",
                    limit: int = Query(default=20, ge=1, le=50), cursor: str | None = None,
                    user: dict[str, Any] | None = Depends(optional_current_user)) -> dict[str, Any]:
    """Reuse the canonical feed's visibility, ranking, signed media URLs and cursor."""
    page = await get_feed(request=request, mode=mode, limit=limit, cursor=cursor, user=user)
    items = []
    for item in page["items"]:
        media = [m for m in item.get("media", [])
                 if str(m.get("media_type", "")).startswith(("video/", "audio/"))]
        if media:
            items.append({**item, "media": media})
    return {**page, "items": items, "media_kinds": ["video", "audio"]}


@router.put("/v1/feed/{content_id}/reaction")
async def set_reaction(content_id: uuid.UUID, payload: ReactionWrite, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    content = await _visible_content(content_id, str(user["id"]))
    if str(content["owner_id"]) == str(user["id"]):
        raise HTTPException(422, detail={"code": "SELF_REACTION_NOT_ALLOWED", "message": "Konten sendiri tidak dapat diberi reaksi."})
    rows = await _server_db("POST", "content_reactions", params={"on_conflict": "content_id,actor_user_id", "select": "content_id,actor_user_id,reaction,created_at"},
        body={"content_id": str(content_id), "actor_user_id": str(user["id"]), "reaction": payload.reaction}, prefer="resolution=merge-duplicates,return=representation")
    if not rows: raise HTTPException(409, detail={"code": "REACTION_NOT_RECORDED", "message": "Reaksi tidak dapat disimpan."})
    return {"reaction": rows[0]}

@router.delete("/v1/feed/{content_id}/reaction")
async def remove_reaction(content_id: uuid.UUID, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    await _visible_content(content_id, str(user["id"]))
    rows = await _server_db("DELETE", "content_reactions", params={"content_id": f"eq.{content_id}", "actor_user_id": f"eq.{user['id']}", "select": "id"}, prefer="return=representation")
    return {"removed": bool(rows)}

@router.put("/v1/feed/{content_id}/save")
async def save_content(content_id: uuid.UUID, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    await _visible_content(content_id, str(user["id"]))
    rows = await _server_db("POST", "content_saves", params={"on_conflict": "content_id,actor_user_id", "select": "content_id,actor_user_id,created_at"},
        body={"content_id": str(content_id), "actor_user_id": str(user["id"])}, prefer="resolution=ignore-duplicates,return=representation")
    return {"saved": True, "item": rows[0] if rows else None}

@router.delete("/v1/feed/{content_id}/save")
async def unsave_content(content_id: uuid.UUID, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    await _visible_content(content_id, str(user["id"]))
    rows = await _server_db("DELETE", "content_saves", params={"content_id": f"eq.{content_id}", "actor_user_id": f"eq.{user['id']}", "select": "id"}, prefer="return=representation")
    return {"saved": False, "removed": bool(rows)}

@router.get("/v1/feed/{content_id}/comments")
async def list_comments(
    content_id: uuid.UUID,
    limit: int = Query(default=30, ge=1, le=100),
    user: dict[str, Any] | None = Depends(optional_current_user),
) -> dict[str, Any]:
    if user:
        await _visible_content(content_id, str(user["id"]))
        select_fields = "id,content_id,actor_user_id,body,status,created_at,updated_at"
    else:
        # Public comment reads are allowed only for a published, approved public post
        # owned by a public profile. Never expose actor IDs or mention targets to guests.
        public_items = await _server_db("GET", "content_items", params={
            "select": "id,owner_id,visibility,status,moderation_status,published_at",
            "id": f"eq.{content_id}", "content_type": "not.eq.story",
            "status": "eq.published", "moderation_status": "eq.approved",
            "visibility": "eq.public", "published_at": f"lte.{_now().isoformat()}", "limit": "1",
        })
        if not public_items:
            raise HTTPException(404, detail={"code": "FEED_CONTENT_NOT_FOUND", "message": "Konten publik tidak ditemukan atau tidak dapat diakses."})
        owner_id = str(public_items[0].get("owner_id") or "")
        profile = (await _profiles_for({owner_id})).get(owner_id)
        if not profile or profile.get("visibility") != "public":
            raise HTTPException(404, detail={"code": "FEED_CONTENT_NOT_FOUND", "message": "Konten publik tidak ditemukan atau tidak dapat diakses."})
        select_fields = "id,content_id,body,status,created_at,updated_at"
    rows = await _server_db("GET", "content_comments", params={"select": select_fields,
        "content_id": f"eq.{content_id}", "status": "eq.visible", "order": "created_at.asc", "limit": str(limit)})
    items = rows or []
    if user and items:
        mention_rows = await _server_db("GET", "content_mentions", params={
            "select": "comment_id,mentioned_user_id", "comment_id": f"in.({','.join(str(x['id']) for x in items)})", "limit": str(min(500, len(items) * 20)),
        })
        mentions_by_comment: dict[str, list[str]] = {}
        for mention in mention_rows or []:
            mentions_by_comment.setdefault(str(mention["comment_id"]), []).append(str(mention["mentioned_user_id"]))
        items = [{**item, "mentions": mentions_by_comment.get(str(item["id"]), [])} for item in items]
    return {"items": items}

@router.post("/v1/feed/{content_id}/comments", status_code=201)
async def create_comment(content_id: uuid.UUID, payload: CommentCreate, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    content = await _visible_content(content_id, str(user["id"])); body = payload.body.strip()
    if not body: raise HTTPException(422, detail={"code": "COMMENT_EMPTY", "message": "Komentar tidak boleh kosong."})
    rows = await _server_db("POST", "content_comments", params={"select": "id,content_id,actor_user_id,body,status,created_at,updated_at"},
        body={"content_id": str(content_id), "actor_user_id": str(user["id"]), "body": body, "status": "visible"}, prefer="return=representation")
    if not rows: raise HTTPException(409, detail={"code": "COMMENT_NOT_RECORDED", "message": "Komentar tidak dapat disimpan."})
    mentions = await _server_db("GET", "content_mentions", params={"select": "mentioned_user_id", "comment_id": f"eq.{rows[0]['id']}", "limit": "100"})
    return {"comment": rows[0], "mentions": mentions or []}

@router.delete("/v1/feed/comments/{comment_id}")
async def delete_comment(comment_id: uuid.UUID, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    rows = await _server_db("DELETE", "content_comments", params={"id": f"eq.{comment_id}", "actor_user_id": f"eq.{user['id']}", "select": "id"}, prefer="return=representation")
    if not rows: raise HTTPException(404, detail={"code": "COMMENT_NOT_FOUND", "message": "Komentar tidak ditemukan atau bukan milik Anda."})
    return {"removed": True}

@router.post("/v1/feed/{content_id}/share", status_code=201)
async def share_content(content_id: uuid.UUID, payload: ShareCreate,
                        user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    await _visible_content(content_id, str(user["id"]))
    rows = await _server_db("POST", "content_shares", params={"select": "id,content_id,actor_user_id,share_target,created_at"},
        body={"content_id": str(content_id), "actor_user_id": str(user["id"]), "share_target": payload.share_target},
        prefer="return=representation")
    if not rows:
        raise HTTPException(409, detail={"code": "SHARE_NOT_RECORDED", "message": "Aktivitas berbagi tidak dapat dicatat."})
    return {"share": rows[0], "share_url": "https://allpha.web.id/feed?content=" + str(content_id)}

@router.get("/v1/feed/item/{content_id}")
async def get_shared_feed_item(content_id: uuid.UUID, user: dict[str, Any] | None = Depends(optional_current_user)) -> dict[str, Any]:
    owner = str(user["id"]) if user else None
    if owner:
        item = await _visible_content(content_id, owner)
    else:
        rows = await _server_db("GET", "content_items", params={
            "select": FIELDS, "id": f"eq.{content_id}", "content_type": "not.eq.story",
            "status": "eq.published", "moderation_status": "eq.approved",
            "visibility": "eq.public", "published_at": f"lte.{_now().isoformat()}", "limit": "1",
        })
        if not rows:
            raise HTTPException(404, detail={"code": "FEED_CONTENT_NOT_FOUND", "message": "Konten publik tidak ditemukan atau tidak dapat diakses."})
        item = rows[0]
        public_profile = (await _profiles_for({str(item.get("owner_id") or "")})).get(str(item.get("owner_id")))
        if not public_profile or public_profile.get("visibility") != "public":
            raise HTTPException(404, detail={"code": "FEED_CONTENT_NOT_FOUND", "message": "Konten publik tidak ditemukan atau tidak dapat diakses."})
        item["creator"] = {"username": public_profile.get("username"), "display_name": public_profile.get("display_name") or public_profile.get("username") or "Kreator", "avatar_url": public_profile.get("avatar_url")}
    cid = str(content_id)
    reactions = await _server_db("GET", "content_reactions", params={"select": "actor_user_id,reaction", "content_id": f"eq.{cid}", "limit": "5000"})
    comments = await _server_db("GET", "content_comments", params={"select": "id", "content_id": f"eq.{cid}", "status": "eq.visible", "limit": "5000"})
    saves = await _server_db("GET", "content_saves", params={"select": "actor_user_id", "content_id": f"eq.{cid}", "limit": "5000"})
    shares = await _server_db("GET", "content_shares", params={"select": "id", "content_id": f"eq.{cid}", "limit": "5000"})
    media = await _server_db("GET", "content_media", params={"select": MEDIA_FIELDS, "content_id": f"eq.{cid}",
        "status": "in.(uploaded,ready)", "order": "created_at.asc", "limit": "50"})
    media_items = []
    for row in media or []:
        media_item = {key: value for key, value in row.items() if key != "storage_path"}
        media_item["preview_url"] = await _signed_media_preview_url(str(row["storage_path"]))
        media_items.append(media_item)
    viewer_reaction = next((str(row.get("reaction") or "like") for row in reactions or [] if owner and str(row.get("actor_user_id")) == owner), None)
    item["engagement"] = {"likes": len(reactions or []), "comments": len(comments or []), "saves": len(saves or []), "shares": len(shares or [])}
    item["viewer_reaction"] = viewer_reaction
    item["saved"] = bool(owner and any(str(row.get("actor_user_id")) == owner for row in saves or []))
    item["media"] = media_items
    item["ranking_signals"] = ["shared_link"]
    return {"item": item}

@router.post("/v1/feed/{content_id}/report", status_code=201)
async def report_content(content_id: uuid.UUID, payload: ReportCreate, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    await _visible_content(content_id, str(user["id"]))
    existing = await _server_db("GET", "content_reports", params={"select": "id", "content_id": f"eq.{content_id}",
        "reporter_user_id": f"eq.{user['id']}", "status": "eq.pending", "limit": "1"})
    if existing: raise HTTPException(409, detail={"code": "REPORT_ALREADY_PENDING", "message": "Laporan konten ini masih menunggu peninjauan."})
    rows = await _server_db("POST", "content_reports", params={"select": "id,content_id,reporter_user_id,reason,status,created_at"},
        body={"content_id": str(content_id), "reporter_user_id": str(user["id"]), "reason": payload.reason,
              "details": (payload.details or "").strip() or None, "status": "pending"}, prefer="return=representation")
    if not rows: raise HTTPException(409, detail={"code": "REPORT_NOT_RECORDED", "message": "Laporan tidak dapat disimpan."})
    return {"report": rows[0]}

@router.get("/v1/feed/preferences")
async def get_preferences(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    rows = await _server_db("GET", "feed_preferences", params={"select": "personalization_enabled,ranking_mode,updated_at", "user_id": f"eq.{user['id']}", "limit": "1"})
    return {"preferences": rows[0] if rows else {"personalization_enabled": True, "ranking_mode": "for_you"}}

@router.put("/v1/feed/preferences")
async def set_preferences(payload: PreferencesWrite, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    rows = await _server_db("POST", "feed_preferences", params={"on_conflict": "user_id", "select": "user_id,personalization_enabled,ranking_mode,updated_at"},
        body={"user_id": str(user["id"]), "personalization_enabled": payload.personalization_enabled, "ranking_mode": payload.ranking_mode},
        prefer="resolution=merge-duplicates,return=representation")
    if not rows: raise HTTPException(409, detail={"code": "FEED_PREFERENCES_NOT_SAVED", "message": "Preferensi feed tidak dapat disimpan."})
    return {"preferences": rows[0]}

@router.get("/v1/admin/content-reports", tags=["content-moderation"])
async def list_content_reports(user: dict[str, Any] = Depends(require_operator_scope("platform:content.moderate"))) -> dict[str, Any]:
    rows = await _server_db("GET", "content_reports", params={"select": "id,content_id,reporter_user_id,reason,details,status,created_at",
        "status": "eq.pending", "order": "created_at.asc", "limit": "100"})
    reports = rows or []; ids = list(dict.fromkeys(str(r["content_id"]) for r in reports)); by_id = {}
    if ids:
        content = await _server_db("GET", "content_items", params={"select": FIELDS, "id": f"in.({','.join(ids)})", "limit": str(len(ids))})
        by_id = {str(r["id"]): r for r in (content or [])}
        media_rows = await _server_db("GET", "content_media", params={
            "select": MEDIA_FIELDS, "content_id": f"in.({','.join(ids)})",
            "status": "in.(uploaded,ready)", "order": "created_at.asc", "limit": str(min(500, len(ids) * 5)),
        })
        media_by_id: dict[str, list[dict[str, Any]]] = {}
        for media_row in media_rows or []:
            media_item = {key: value for key, value in media_row.items() if key != "storage_path"}
            media_item["preview_url"] = await _signed_media_preview_url(str(media_row["storage_path"]))
            media_by_id.setdefault(str(media_row["content_id"]), []).append(media_item)
        for content_id, item in by_id.items():
            item["media"] = media_by_id.get(content_id, [])
    return {"items": [{**r, "content": by_id.get(str(r["content_id"]))} for r in reports]}

@router.post("/v1/admin/content-reports/{report_id}/review")
async def review_content_report(report_id: uuid.UUID, payload: ReportReview, request: Request,
    user: dict[str, Any] = Depends(require_operator_scope("platform:content.moderate"))) -> dict[str, Any]:
    reports = await _server_db("GET", "content_reports", params={"select": "id,content_id,status", "id": f"eq.{report_id}", "status": "eq.pending", "limit": "1"})
    if not reports: raise HTTPException(404, detail={"code": "CONTENT_REPORT_NOT_FOUND", "message": "Laporan tidak ditemukan atau sudah ditinjau."})
    report = reports[0]
    await write_operator_audit(request, actor_user_id=str(user["id"]), action="content.report.review", outcome="attempted",
        resource_type="content_report", resource_id=str(report_id), metadata={"decision": payload.decision, "reason": payload.reason, "content_id": str(report["content_id"])})
    if payload.decision == "hide_content":
        content_rows = await _server_db("GET", "content_items", params={"select": FIELDS, "id": f"eq.{report['content_id']}",
            "status": "eq.published", "moderation_status": "eq.approved", "visibility": "in.(public,followers)", "limit": "1"})
        if content_rows:
            item = content_rows[0]
            changed = await _server_db("PATCH", "content_items", params={"id": f"eq.{item['id']}", "version": f"eq.{item['version']}",
                "status": "eq.published", "moderation_status": "eq.approved", "select": FIELDS},
                body={"status": "archived", "moderation_status": "removed", "version": int(item["version"]) + 1}, prefer="return=representation")
            if not changed: raise HTTPException(409, detail={"code": "CONTENT_CHANGED_DURING_REVIEW", "message": "Konten berubah; muat ulang antrean laporan."})
    reviewed = await _server_db("PATCH", "content_reports", params={"id": f"eq.{report_id}", "status": "eq.pending", "select": "id,status"},
        body={"status": "actioned" if payload.decision == "hide_content" else "dismissed", "reviewed_by": str(user["id"]),
              "review_reason": payload.reason, "reviewed_at": _now().isoformat()}, prefer="return=representation")
    if not reviewed: raise HTTPException(409, detail={"code": "REPORT_REVIEW_CONFLICT", "message": "Laporan sudah ditinjau oleh operator lain."})
    await write_operator_audit(request, actor_user_id=str(user["id"]), action="content.report.review", outcome="succeeded",
        resource_type="content_report", resource_id=str(report_id), metadata={"decision": payload.decision, "reason": payload.reason, "content_id": str(report["content_id"])})
    return {"report": reviewed[0], "content_hidden": payload.decision == "hide_content"}

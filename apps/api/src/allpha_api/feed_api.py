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
    if owner_id in hidden or (item.get("visibility") == "followers" and owner_id not in followed):
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
    # Guest reads are public-only, chronological, and never depend on a personal feed.
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
    if not owner and candidates:
        profiles = await _server_db("GET", "profiles", params={
            "select": "id,visibility", "id": f"in.({','.join(str(row.get('owner_id')) for row in candidates if row.get('owner_id'))})",
            "visibility": "eq.public", "limit": str(min(CANDIDATES, len(candidates)))})
        public_profile_ids = {str(row.get("id")) for row in profiles or []}
        candidates = [row for row in candidates if str(row.get("owner_id")) in public_profile_ids]
    candidates = [r for r in candidates if str(r.get("owner_id")) not in hidden and
                  (r.get("visibility") == "public" or (owner and r.get("visibility") == "followers" and str(r.get("owner_id")) in followed))]
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
        item["media"] = media_by_id.get(cid, []); items.append(item)
    next_offset = offset + len(page)
    return {"items": items, "next_cursor": _cursor_encode(next_offset, as_of) if next_offset < len(ranked) and next_offset < CANDIDATES else None,
            "mode": effective_mode, "personalization_enabled": enabled, "as_of": as_of.isoformat()}


@router.get("/v1/search", tags=["search-discovery"])
async def search_content(
    q: str = Query(min_length=2, max_length=100),
    limit: int = Query(default=20, ge=1, le=50),
    user: dict[str, Any] | None = Depends(optional_current_user),
) -> dict[str, Any]:
    """Search published approved public content for guests; apply relationship filters when authenticated."""
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
    if not owner and eligible:
        profiles = await _server_db("GET", "profiles", params={
            "select": "id,visibility", "id": f"in.({','.join(str(row.get('owner_id')) for row in eligible if row.get('owner_id'))})",
            "visibility": "eq.public", "limit": str(min(500, len(eligible))),
        })
        public_profile_ids = {str(row.get("id")) for row in profiles or []}
        eligible = [row for row in eligible if str(row.get("owner_id")) in public_profile_ids]
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
    items = [{**row, "media": media_by_id.get(str(row["id"]), [])} for row in page]
    return {"query": query, "items": items, "count": len(items), "has_more": len(eligible) > limit}


@router.get("/v1/trends", tags=["search-discovery"])
async def get_trends(
    limit: int = Query(default=10, ge=1, le=30),
    user: dict[str, Any] | None = Depends(optional_current_user),
) -> dict[str, Any]:
    """Derive trends from real eligible content; guest trends include public resources only."""
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
    if not owner and visible:
        profiles = await _server_db("GET", "profiles", params={
            "select": "id,visibility", "id": f"in.({','.join(str(row.get('owner_id')) for row in visible if row.get('owner_id'))})",
            "visibility": "eq.public", "limit": str(min(500, len(visible))),
        })
        public_profile_ids = {str(row.get("id")) for row in profiles or []}
        visible = [row for row in visible if str(row.get("owner_id")) in public_profile_ids]
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
    """Reuse canonical feed ranking; guest recommendations are public-only and chronological."""
    page = await get_feed(request=request, mode="for_you", limit=limit, cursor=None, user=user)
    return {"items": page["items"], "mode": page["mode"], "personalization_enabled": page["personalization_enabled"]}


@router.get("/v1/reels", tags=["reels"])
async def get_reels(request: Request, mode: Literal["for_you", "recent"] = "for_you",
                    limit: int = Query(default=20, ge=1, le=50), cursor: str | None = None,
                    user: dict[str, Any] | None = Depends(optional_current_user)) -> dict[str, Any]:
    """Reuse the canonical feed's guest/auth visibility, ranking, signed media URLs and cursor."""
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
async def list_comments(content_id: uuid.UUID, limit: int = Query(default=30, ge=1, le=100), user: dict[str, Any] | None = Depends(optional_current_user)) -> dict[str, Any]:
    if user:
        await _visible_content(content_id, str(user["id"]))
    else:
        public_item = await _server_db("GET", "content_items", params={
            "select": "id,owner_id,visibility,status,moderation_status",
            "id": f"eq.{content_id}", "visibility": "eq.public", "status": "eq.published",
            "moderation_status": "eq.approved", "content_type": "neq.story", "limit": "1",
        })
        if not public_item:
            raise HTTPException(404, detail={"code": "FEED_CONTENT_NOT_FOUND", "message": "Konten tidak ditemukan atau tidak dapat diakses."})
        profile = await _server_db("GET", "profiles", params={
            "select": "id", "id": f"eq.{public_item[0]['owner_id']}", "visibility": "eq.public", "limit": "1",
        })
        if not profile:
            raise HTTPException(404, detail={"code": "FEED_CONTENT_NOT_FOUND", "message": "Konten tidak ditemukan atau tidak dapat diakses."})
    rows = await _server_db("GET", "content_comments", params={"select": "id,content_id,actor_user_id,body,status,created_at,updated_at",
        "content_id": f"eq.{content_id}", "status": "eq.visible", "order": "created_at.asc", "limit": str(limit)})
    items = rows or []
    if items:
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
            "select": FIELDS, "id": f"eq.{content_id}", "content_type": "neq.story",
            "status": "eq.published", "moderation_status": "eq.approved", "visibility": "eq.public", "limit": "1",
        })
        if not rows:
            raise HTTPException(404, detail={"code": "FEED_CONTENT_NOT_FOUND", "message": "Konten tidak ditemukan atau tidak dapat diakses."})
        item = rows[0]
        profiles = await _server_db("GET", "profiles", params={
            "select": "id", "id": f"eq.{item['owner_id']}", "visibility": "eq.public", "limit": "1",
        })
        if not profiles:
            raise HTTPException(404, detail={"code": "FEED_CONTENT_NOT_FOUND", "message": "Konten tidak ditemukan atau tidak dapat diakses."})
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

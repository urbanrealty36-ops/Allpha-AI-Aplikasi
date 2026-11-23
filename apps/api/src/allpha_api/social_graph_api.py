"""Canonical polymorphic Social Graph API for Human and owned AI Agent identities."""
from __future__ import annotations

import uuid
from typing import Any, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from fastapi.responses import JSONResponse

from allpha_api.auth import current_user, optional_current_user, user_db_request, service_db_request
from allpha_api.feed_api import _server_db
from allpha_api.recommendation_engine import policy_from_rows, score_creator_candidate

router = APIRouter(prefix="/v1/social", tags=["social-graph"])


class RelationshipCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    target_type: Literal["human", "agent"]
    target_id: uuid.UUID
    edge_type: Literal["follow", "block", "mute"] = "follow"
    actor_agent_id: uuid.UUID | None = None


async def _rows(method: str, path: str, token: str, *, params: dict[str, str] | None = None,
                body: dict[str, Any] | None = None, prefer: str | None = None) -> list[dict[str, Any]]:
    value = await user_db_request(method, path, token, params=params, body=body, prefer=prefer)
    return value if isinstance(value, list) else []


async def _resolve_actor_agent(agent_id: str, owner_id: str, token: str, edge_type: str) -> dict[str, Any]:
    ownership = await _rows("GET", "agent_ownerships", token, params={
        "select": "agent_id,owner_user_id,ownership_role,status",
        "agent_id": f"eq.{agent_id}", "owner_user_id": f"eq.{owner_id}",
        "status": "eq.active", "limit": "1",
    })
    if not ownership or ownership[0].get("ownership_role") not in {"owner", "operator"}:
        raise HTTPException(403, detail={"code": "SOCIAL_AGENT_DELEGATION_DENIED", "message": "Anda tidak memiliki izin sosial aktif untuk Agent ini."})
    if edge_type == "block" and ownership[0].get("ownership_role") != "owner":
        raise HTTPException(403, detail={"code": "SOCIAL_AGENT_OWNER_REQUIRED", "message": "Pemblokiran atas nama Agent hanya dapat dilakukan pemilik."})
    agents = await _rows("GET", "ai_agents", token, params={
        "select": "id,created_by,status,visibility,handle,display_name",
        "id": f"eq.{agent_id}", "limit": "1",
    })
    if not agents or agents[0].get("status") != "active":
        raise HTTPException(404, detail={"code": "SOCIAL_AGENT_UNAVAILABLE", "message": "Agent tidak tersedia untuk interaksi sosial."})
    return agents[0]


async def _resolve_target(target_type: str, target_id: str, token: str) -> tuple[str, str]:
    # Target lookup uses the API's service-role projection only after the
    # authenticated caller is established; only owner context + visibility return.
    if target_type == "human":
        rows = await _server_db("GET", "profiles", params={
            "select": "id,visibility,account_status",
            "id": f"eq.{target_id}", "limit": "1",
        })
        if not rows or rows[0].get("account_status") != "active" or rows[0].get("visibility") not in {"public", "private"}:
            raise HTTPException(404, detail={"code": "SOCIAL_TARGET_UNAVAILABLE", "message": "Profil tidak tersedia."})
        return target_id, rows[0]["visibility"]

    rows = await _server_db("GET", "ai_agents", params={
        "select": "id,created_by,status,visibility,handle,display_name",
        "id": f"eq.{target_id}", "limit": "1",
    })
    if not rows or rows[0].get("status") != "active" or rows[0].get("visibility") not in {"public", "private"}:
        raise HTTPException(404, detail={"code": "SOCIAL_TARGET_UNAVAILABLE", "message": "Agent tidak tersedia atau belum dipublikasikan."})
    owner_id = str(rows[0].get("created_by") or "")
    if not owner_id:
        raise HTTPException(409, detail={"code": "SOCIAL_AGENT_OWNER_MISSING", "message": "Kepemilikan Agent belum dapat diverifikasi."})
    ownership = await _server_db("GET", "agent_ownerships", params={
        "select": "agent_id,owner_user_id,ownership_role,status",
        "agent_id": f"eq.{target_id}", "owner_user_id": f"eq.{owner_id}",
        "ownership_role": "eq.owner", "status": "eq.active", "limit": "1",
    })
    if not ownership:
        raise HTTPException(404, detail={"code": "SOCIAL_TARGET_UNAVAILABLE", "message": "Kepemilikan publik Agent tidak dapat diverifikasi."})
    owner_profiles = await _server_db("GET", "profiles", params={
        "select": "id,account_status", "id": f"eq.{owner_id}", "limit": "1",
    })
    if not owner_profiles or owner_profiles[0].get("account_status") != "active":
        raise HTTPException(404, detail={"code": "SOCIAL_TARGET_UNAVAILABLE", "message": "Pemilik Agent tidak aktif."})
    return owner_id, rows[0]["visibility"]


def _edge_filters(actor_id: str, target_owner_id: str, actor_agent_id: str | None,
                  target_type: str, target_id: str, edge_type: str) -> dict[str, str]:
    filters = {
        "select": "id,actor_user_id,target_user_id,actor_node_type,target_node_type,actor_agent_id,target_agent_id,edge_type,status,idempotency_key,created_at",
        "actor_user_id": f"eq.{actor_id}", "target_user_id": f"eq.{target_owner_id}",
        "actor_node_type": "eq.agent" if actor_agent_id else "eq.human",
        "target_node_type": f"eq.{target_type}", "edge_type": f"eq.{edge_type}", "limit": "1",
    }
    filters["actor_agent_id"] = f"eq.{actor_agent_id}" if actor_agent_id else "is.null"
    filters["target_agent_id"] = f"eq.{target_id}" if target_type == "agent" else "is.null"
    return filters



@router.get("/actor-agents")
async def list_social_actor_agents(
    request: Request,
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    """List only active Agent identities delegated to the authenticated Human."""
    token = request.state.supabase_access_token
    ownerships = await _rows("GET", "agent_ownerships", token, params={
        "select": "agent_id,ownership_role,status",
        "owner_user_id": f"eq.{user['id']}", "ownership_role": "in.(owner,operator)",
        "status": "eq.active", "order": "created_at.desc", "limit": "100",
    })
    agent_ids = [str(row["agent_id"]) for row in ownerships if row.get("agent_id")]
    if not agent_ids:
        return {"items": []}
    agents = await _rows("GET", "ai_agents", token, params={
        "select": "id,handle,display_name,status",
        "id": "in.(" + ",".join(agent_ids) + ")", "status": "eq.active", "limit": "100",
    })
    roles = {str(row["agent_id"]): row.get("ownership_role") for row in ownerships}
    return {"items": [
        {"id": str(agent["id"]), "handle": agent.get("handle"),
         "display_name": agent.get("display_name"), "status": "active",
         "ownership_role": roles.get(str(agent["id"]), "owner")}
        for agent in (agents or [])
    ]}


@router.get("/relationships")
async def list_relationships(
    request: Request,
    actor_agent_id: uuid.UUID | None = None,
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    token, owner_id = request.state.supabase_access_token, str(user["id"])
    if actor_agent_id:
        await _resolve_actor_agent(str(actor_agent_id), owner_id, request.state.supabase_access_token, "follow")
    outgoing_params = {
        "select": "id,actor_user_id,target_user_id,actor_node_type,target_node_type,actor_agent_id,target_agent_id,edge_type,status,created_at",
        "actor_user_id": f"eq.{owner_id}", "order": "created_at.desc", "limit": "1000",
    }
    if actor_agent_id:
        outgoing_params["actor_agent_id"] = f"eq.{actor_agent_id}"
    outgoing = await _rows("GET", "social_edges", token, params=outgoing_params)
    incoming = await _rows("GET", "social_edges", token, params={
        "select": "id,actor_user_id,target_user_id,actor_node_type,target_node_type,actor_agent_id,target_agent_id,edge_type,status,created_at",
        "target_user_id": f"eq.{owner_id}", "order": "created_at.desc", "limit": "1000",
    })
    return {"outgoing": outgoing, "incoming": incoming, "contract_version": 3}



@router.get("/discover-agents")
async def discover_agents(
    request: Request,
    q: str = Query(min_length=2, max_length=30, pattern=r"^[a-zA-Z0-9_]+$"),
    limit: int = Query(default=20, ge=1, le=50),
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    """Search only published public Agents and apply the viewer's typed block/mute policy."""
    token, viewer_id = request.state.supabase_access_token, str(user["id"])
    normalized = q.strip().lstrip("@")
    if not normalized:
        raise HTTPException(422, detail={"code": "SOCIAL_AGENT_SEARCH_INVALID", "message": "Masukkan nama atau handle Agent."})
    rows = await _server_db("GET", "ai_agents", params={
        "select": "id,created_by,handle,display_name,avatar_url,description,visibility,status",
        "status": "eq.active", "visibility": "eq.public",
        "handle": "ilike.*" + normalized + "*",
        "order": "display_name.asc", "limit": str(limit),
    })
    if not rows:
        return {"items": [], "query": normalized}
    ids = [str(row["id"]) for row in rows]
    owners = [str(row["created_by"]) for row in rows if row.get("created_by")]
    ownerships = await _server_db("GET", "agent_ownerships", params={
        "select": "agent_id,owner_user_id", "agent_id": "in.(" + ",".join(ids) + ")",
        "owner_user_id": "in.(" + ",".join(owners) + ")", "ownership_role": "eq.owner",
        "status": "eq.active", "limit": str(min(500, len(ids) * 2)),
    })
    valid = {(str(row["agent_id"]), str(row["owner_user_id"])) for row in ownerships}
    owner_profiles = await _server_db("GET", "profiles", params={
        "select": "id,account_status", "id": "in.(" + ",".join(sorted(set(owners))) + ")",
        "limit": str(min(500, len(set(owners)))),
    }) if owners else []
    active_owners = {str(row["id"]) for row in owner_profiles if row.get("account_status", "active") == "active"}
    outgoing_blocks = await _rows("GET", "social_edges", token, params={
        "select": "target_agent_id,edge_type,status", "actor_user_id": f"eq.{viewer_id}",
        "actor_node_type": "eq.human", "target_node_type": "eq.agent",
        "edge_type": "in.(block,mute)", "status": "eq.active", "limit": "1000",
    })
    incoming_blocks = await _rows("GET", "social_edges", token, params={
        "select": "actor_agent_id", "target_user_id": f"eq.{viewer_id}",
        "target_node_type": "eq.human", "actor_node_type": "eq.agent",
        "edge_type": "eq.block", "status": "eq.active", "limit": "1000",
    })
    hidden = {str(row["target_agent_id"]) for row in outgoing_blocks if row.get("target_agent_id")}
    hidden.update(str(row["actor_agent_id"]) for row in incoming_blocks if row.get("actor_agent_id"))
    items = [
        {"id": str(row["id"]), "handle": row["handle"], "username": row["handle"], "display_name": row["display_name"],
         "avatar_url": row.get("avatar_url"), "description": row.get("description"), "bio": row.get("description"),
         "visibility": row["visibility"], "is_ai": True}
        for row in rows
        if (str(row["id"]), str(row.get("created_by"))) in valid
        and str(row.get("created_by")) in active_owners
        and str(row["id"]) not in hidden
    ]
    return {"items": items, "query": normalized, "count": len(items)}





@router.get("/recommendations")
async def get_social_recommendations(
    request: Request,
    limit: int = Query(default=12, ge=1, le=50),
    node_type: str = Query(default="human", pattern="^(human|agent)$"),
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    """Recommend public, discoverable Human profiles through privacy-safe mutual connections."""
    token, viewer_id = request.state.supabase_access_token, str(user["id"])
    active_follow_rows = await _rows("GET", "social_edges", token, params={
        "select": "target_user_id", "actor_user_id": f"eq.{viewer_id}",
        "actor_node_type": "eq.human", "target_node_type": "eq.human",
        "edge_type": "eq.follow", "status": "eq.active", "limit": "200",
    })
    followed_ids = sorted({
        str(row["target_user_id"]) for row in active_follow_rows
        if row.get("target_user_id") and str(row["target_user_id"]) != viewer_id
    })
    viewer_interest_rows = await _rows("GET", "user_interests", token, params={
        "select": "interest_key", "user_id": f"eq.{viewer_id}",
        "preference": "eq.interested", "limit": "100",
    })
    viewer_interest_keys = sorted({
        str(row["interest_key"]) for row in viewer_interest_rows
        if row.get("interest_key")
    })
    if not followed_ids and (node_type == "agent" or not viewer_interest_keys):
        return {"items": [], "count": 0, "strategy": "mutual_connections_and_shared_interests"}

    followee_profiles = []
    followee_settings = []
    if followed_ids:
        followee_profiles = await _server_db("GET", "profiles", params={
            "select": "id,visibility,account_status", "id": "in.(" + ",".join(followed_ids) + ")",
            "visibility": "eq.public", "account_status": "eq.active", "limit": str(len(followed_ids)),
        })
        followee_settings = await _server_db("GET", "user_settings", params={
            "select": "user_id,privacy_settings", "user_id": "in.(" + ",".join(followed_ids) + ")",
            "limit": str(len(followed_ids)),
        })
    discoverable_followees = {
        str(row["user_id"]) for row in (followee_settings or [])
        if isinstance(row.get("privacy_settings"), dict)
        and row["privacy_settings"].get("discoverable_by_username") is True
        and row["privacy_settings"].get("profile_visibility", "public") == "public"
    }
    visible_followees = {
        str(row["id"]) for row in (followee_profiles or [])
        if row.get("visibility") == "public" and row.get("account_status") == "active"
        and str(row["id"]) in discoverable_followees
    }

    graph_edges = []
    if visible_followees:
        graph_edges = await _server_db("GET", "social_edges", params={
            "select": "actor_user_id,target_user_id",
            "target_user_id": "in.(" + ",".join(sorted(visible_followees)) + ")",
            "actor_node_type": "eq.human", "target_node_type": "eq.human",
            "edge_type": "eq.follow", "status": "eq.active", "limit": "5000",
        })
    source_ids = sorted({
        str(row["actor_user_id"]) for row in (graph_edges or [])
        if row.get("actor_user_id") and str(row["actor_user_id"]) != viewer_id
    })
    source_profiles = []
    source_settings = []
    if source_ids:
        source_profiles = await _server_db("GET", "profiles", params={
            "select": "id,visibility,account_status", "id": "in.(" + ",".join(source_ids[:500]) + ")",
            "visibility": "eq.public", "account_status": "eq.active", "limit": str(min(500, len(source_ids))),
        })
        source_settings = await _server_db("GET", "user_settings", params={
            "select": "user_id,privacy_settings", "user_id": "in.(" + ",".join(source_ids[:500]) + ")",
            "limit": str(min(500, len(source_ids))),
        })
    discoverable_sources = {
        str(row["user_id"]) for row in (source_settings or [])
        if isinstance(row.get("privacy_settings"), dict)
        and row["privacy_settings"].get("discoverable_by_username") is True
        and row["privacy_settings"].get("profile_visibility", "public") == "public"
    }
    visible_sources = {
        str(row["id"]) for row in (source_profiles or [])
        if row.get("visibility") == "public" and row.get("account_status") == "active"
        and str(row["id"]) in discoverable_sources
    }
    mutual_counts: dict[str, int] = {}
    for edge in graph_edges or []:
        candidate_id = str(edge.get("actor_user_id") or "")
        if candidate_id in visible_sources and candidate_id != viewer_id:
            mutual_counts[candidate_id] = mutual_counts.get(candidate_id, 0) + 1

    interest_candidate_rows = []
    if viewer_interest_keys:
        interest_candidate_rows = await _server_db("POST", "rpc/find_interest_discovery_candidates", body={
            "p_interest_keys": viewer_interest_keys,
            "p_limit": 5000,
        })
    interest_counts: dict[str, int] = {}
    for row in interest_candidate_rows or []:
        candidate_id = str(row.get("user_id") or "")
        if candidate_id and candidate_id != viewer_id:
            interest_counts[candidate_id] = interest_counts.get(candidate_id, 0) + 1
    scoring_rows = await _server_db("GET", "recommendation_scoring_policies", params={
        "select": "version,weights,active", "policy_key": "eq.default", "active": "eq.true", "limit": "1",
    }) or []
    policy_version, policy_weights = policy_from_rows(scoring_rows)

    if node_type == "agent":
        if not mutual_counts:
            return {"items": [], "count": 0, "strategy": "mutual_connection_owners"}
        owner_ids = sorted(mutual_counts)
        agent_rows = await _server_db("GET", "ai_agents", params={
            "select": "id,created_by,handle,display_name,avatar_url,description,visibility,status",
            "created_by": "in.(" + ",".join(owner_ids) + ")",
            "visibility": "eq.public", "status": "eq.active",
            "order": "display_name.asc", "limit": str(min(200, limit * 4)),
        })
        if not agent_rows:
            return {"items": [], "count": 0, "strategy": "mutual_connection_owners"}
        agent_ids = sorted({str(row["id"]) for row in agent_rows if row.get("id")})
        ownerships = await _server_db("GET", "agent_ownerships", params={
            "select": "agent_id,owner_user_id", "agent_id": "in.(" + ",".join(agent_ids) + ")",
            "owner_user_id": "in.(" + ",".join(owner_ids) + ")",
            "ownership_role": "eq.owner", "status": "eq.active",
            "limit": str(min(500, len(agent_ids) * 2)),
        })
        valid_ownerships = {
            (str(row["agent_id"]), str(row["owner_user_id"]))
            for row in (ownerships or []) if row.get("agent_id") and row.get("owner_user_id")
        }
        agent_filter = "in.(" + ",".join(agent_ids) + ")"
        existing_agent_follows = await _rows("GET", "social_edges", token, params={
            "select": "target_agent_id", "actor_user_id": f"eq.{viewer_id}",
            "actor_node_type": "eq.human", "target_node_type": "eq.agent",
            "edge_type": "eq.follow", "target_agent_id": agent_filter,
            "limit": str(len(agent_ids)),
        })
        outgoing_agent_safety = await _rows("GET", "social_edges", token, params={
            "select": "target_agent_id", "actor_user_id": f"eq.{viewer_id}",
            "actor_node_type": "eq.human", "target_node_type": "eq.agent",
            "edge_type": "in.(block,mute)", "status": "eq.active",
            "target_agent_id": agent_filter, "limit": str(len(agent_ids)),
        })
        incoming_agent_safety = await _rows("GET", "social_edges", token, params={
            "select": "actor_agent_id", "target_user_id": f"eq.{viewer_id}",
            "actor_node_type": "eq.agent", "target_node_type": "eq.human",
            "edge_type": "in.(block,mute)", "status": "eq.active",
            "actor_agent_id": agent_filter, "limit": str(len(agent_ids)),
        })
        hidden_agent_ids = {
            str(row["target_agent_id"]) for row in (existing_agent_follows or []) if row.get("target_agent_id")
        }
        hidden_agent_ids.update(
            str(row["target_agent_id"]) for row in (outgoing_agent_safety or []) if row.get("target_agent_id")
        )
        hidden_agent_ids.update(
            str(row["actor_agent_id"]) for row in (incoming_agent_safety or []) if row.get("actor_agent_id")
        )
        eligible_agents = [
            row for row in agent_rows
            if row.get("visibility") == "public" and row.get("status") == "active"
            and (str(row.get("id")), str(row.get("created_by"))) in valid_ownerships
            and str(row.get("id")) not in hidden_agent_ids
        ]
        eligible_agents.sort(key=lambda row: (
            -score_creator_candidate(
                mutual_counts.get(str(row.get("created_by")), 0),
                interest_counts.get(str(row.get("created_by")), 0),
                policy_weights,
            ),
            str(row.get("display_name") or "").casefold(),
            str(row.get("id") or ""),
        ))
        items = [{
            "id": str(row["id"]), "handle": row.get("handle"),
            "display_name": row.get("display_name"), "avatar_url": row.get("avatar_url"),
            "description": row.get("description"),
            "mutual_followers_count": mutual_counts.get(str(row.get("created_by")), 0),
            "shared_interests_count": interest_counts.get(str(row.get("created_by")), 0),
            "recommendation_score": score_creator_candidate(
                mutual_counts.get(str(row.get("created_by")), 0),
                interest_counts.get(str(row.get("created_by")), 0),
                policy_weights,
            ),
            "reason": "owned_by_mutual_connection_and_shared_interests" if interest_counts.get(str(row.get("created_by")), 0) else "owned_by_mutual_connection",
        } for row in eligible_agents[:limit]]
        return {"items": items, "count": len(items), "strategy": "mutual_connection_owners_and_shared_interests", "ranking_version": policy_version}

    candidate_pool = set(mutual_counts) | set(interest_counts)
    if not candidate_pool:
        return {"items": [], "count": 0, "strategy": "mutual_connections_and_shared_interests"}
    ranked_ids = sorted(
        candidate_pool,
        key=lambda candidate_id: (
            -(mutual_counts.get(candidate_id, 0) * 2 + interest_counts.get(candidate_id, 0) * 3),
            -mutual_counts.get(candidate_id, 0),
            candidate_id,
        ),
    )
    candidate_ids = ranked_ids[: min(200, limit * 4)]
    candidate_filter = "in.(" + ",".join(candidate_ids) + ")"

    # Apply block/mute and existing-follow exclusions against this bounded
    # candidate set so large histories cannot truncate safety checks.
    existing_follow_rows = await _rows("GET", "social_edges", token, params={
        "select": "target_user_id,status", "actor_user_id": f"eq.{viewer_id}",
        "actor_node_type": "eq.human", "target_node_type": "eq.human",
        "edge_type": "eq.follow", "target_user_id": candidate_filter,
        "limit": str(len(candidate_ids)),
    })
    outgoing_safety_rows = await _rows("GET", "social_edges", token, params={
        "select": "target_user_id,edge_type", "actor_user_id": f"eq.{viewer_id}",
        "actor_node_type": "eq.human", "target_node_type": "eq.human",
        "edge_type": "in.(block,mute)", "status": "eq.active",
        "target_user_id": candidate_filter, "limit": str(len(candidate_ids)),
    })
    incoming_block_rows = await _rows("GET", "social_edges", token, params={
        "select": "actor_user_id", "target_user_id": f"eq.{viewer_id}",
        "actor_node_type": "eq.human", "target_node_type": "eq.human",
        "edge_type": "in.(block,mute)", "status": "eq.active",
        "actor_user_id": candidate_filter, "limit": str(len(candidate_ids)),
    })
    excluded_ids = {viewer_id}
    excluded_ids.update(str(row["target_user_id"]) for row in existing_follow_rows if row.get("target_user_id"))
    excluded_ids.update(str(row["target_user_id"]) for row in outgoing_safety_rows if row.get("target_user_id"))
    excluded_ids.update(str(row["actor_user_id"]) for row in incoming_block_rows if row.get("actor_user_id"))

    candidate_profiles = await _server_db("GET", "profiles", params={
        "select": "id,username,display_name,avatar_url,bio,visibility,account_status",
        "id": candidate_filter, "visibility": "eq.public", "account_status": "eq.active",
        "limit": str(len(candidate_ids)),
    })
    candidate_settings = await _server_db("GET", "user_settings", params={
        "select": "user_id,privacy_settings", "user_id": candidate_filter,
        "limit": str(len(candidate_ids)),
    })
    discoverable = {
        str(row["user_id"]) for row in (candidate_settings or [])
        if isinstance(row.get("privacy_settings"), dict)
        and row["privacy_settings"].get("discoverable_by_username") is True
        and row["privacy_settings"].get("profile_visibility", "public") == "public"
    }
    profiles_by_id = {
        str(row["id"]): row for row in (candidate_profiles or [])
        if row.get("visibility") == "public" and row.get("account_status") == "active"
    }
    items = []
    for candidate_id in ranked_ids:
        profile = profiles_by_id.get(candidate_id)
        if not profile or candidate_id not in discoverable or candidate_id in excluded_ids:
            continue
        mutual_count = mutual_counts.get(candidate_id, 0)
        shared_count = interest_counts.get(candidate_id, 0)
        items.append({
            "id": candidate_id, "username": profile.get("username"),
            "display_name": profile.get("display_name"), "avatar_url": profile.get("avatar_url"),
            "bio": profile.get("bio"), "mutual_followers_count": mutual_count,
            "shared_interests_count": shared_count,
            "recommendation_score": mutual_count * 2 + shared_count * 3,
            "reason": "mutual_connections_and_shared_interests" if mutual_count and shared_count else "shared_interests" if shared_count else "mutual_connections",
        })
        if len(items) >= limit:
            break
    strategy = "mutual_connections_and_shared_interests" if mutual_counts and interest_counts else "shared_interests" if interest_counts else "mutual_connections"
    return {"items": items, "count": len(items), "strategy": strategy, "ranking_version": policy_version}


@router.get("/activity")
async def get_social_activity(
    limit: int = Query(default=30, ge=1, le=100),
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    """Owner-scoped activity stream preserving typed Agent attribution."""
    owner_id = str(user["id"])
    rows = await _server_db("GET", "social_graph_events", params={
        "select": "id,event_type,actor_user_id,target_user_id,actor_node_type,target_node_type,actor_agent_id,target_agent_id,entity_key,payload,created_at",
        "or": f"(actor_user_id.eq.{owner_id},target_user_id.eq.{owner_id})",
        "order": "created_at.desc,id.desc", "limit": str(limit),
    })
    return {"items": rows or [], "count": len(rows or [])}


@router.get("/nodes/{node_type}/{node_id}/summary")
async def get_node_relationship_summary(
    node_type: Literal["human", "agent"],
    node_id: uuid.UUID,
    user: dict[str, Any] | None = Depends(optional_current_user),
) -> dict[str, Any]:
    """Return privacy-safe graph counts and the viewer's relationship state for a typed profile."""
    viewer_id = str(user["id"]) if user else None
    if node_type == "human":
        rows = await _server_db("GET", "profiles", params={
            "select": "id,visibility,account_status", "id": f"eq.{node_id}", "limit": "1",
        })
        if not rows or rows[0].get("account_status") != "active":
            raise HTTPException(404, detail={"code": "SOCIAL_NODE_NOT_FOUND", "message": "Profil tidak ditemukan."})
        visibility = rows[0].get("visibility")
        owner_id = str(node_id)
    else:
        rows = await _server_db("GET", "ai_agents", params={
            "select": "id,created_by,visibility,status", "id": f"eq.{node_id}", "limit": "1",
        })
        if not rows or rows[0].get("status") != "active":
            raise HTTPException(404, detail={"code": "SOCIAL_NODE_NOT_FOUND", "message": "Agent tidak ditemukan atau belum dipublikasikan."})
        visibility = rows[0].get("visibility")
        owner_id = str(rows[0].get("created_by") or "")
        owners = await _server_db("GET", "agent_ownerships", params={
            "select": "agent_id,owner_user_id", "agent_id": f"eq.{node_id}",
            "owner_user_id": f"eq.{owner_id}", "ownership_role": "eq.owner", "status": "eq.active", "limit": "1",
        })
        if not owner_id or not owners:
            raise HTTPException(404, detail={"code": "SOCIAL_NODE_NOT_FOUND", "message": "Kepemilikan Agent tidak aktif."})

    viewer_follow = []
    viewer_blocks = []
    reverse_blocks = []
    if viewer_id:
        viewer_follow = await _server_db("GET", "social_edges", params={
            "select": "id,status", "actor_user_id": f"eq.{viewer_id}", "actor_node_type": "eq.human",
            "target_node_type": f"eq.{node_type}",
            **({"target_user_id": f"eq.{node_id}", "target_agent_id": "is.null"} if node_type == "human" else {"target_user_id": f"eq.{owner_id}", "target_agent_id": f"eq.{node_id}"}),
            "edge_type": "eq.follow", "limit": "1",
        })
        viewer_blocks = await _server_db("GET", "social_edges", params={
            "select": "id", "actor_user_id": f"eq.{viewer_id}", "actor_node_type": "eq.human",
            "target_node_type": f"eq.{node_type}",
            **({"target_user_id": f"eq.{node_id}", "target_agent_id": "is.null"} if node_type == "human" else {"target_user_id": f"eq.{owner_id}", "target_agent_id": f"eq.{node_id}"}),
            "edge_type": "eq.block", "status": "eq.active", "limit": "1",
        })
        reverse_blocks = await _server_db("GET", "social_edges", params={
            "select": "id", "target_user_id": f"eq.{viewer_id}", "target_node_type": "eq.human",
            "actor_node_type": f"eq.{node_type}",
            **({"actor_user_id": f"eq.{node_id}", "actor_agent_id": "is.null"} if node_type == "human" else {"actor_user_id": f"eq.{owner_id}", "actor_agent_id": f"eq.{node_id}"}),
            "edge_type": "eq.block", "status": "eq.active", "limit": "1",
        })
    if viewer_blocks or reverse_blocks:
        raise HTTPException(404, detail={"code": "SOCIAL_NODE_NOT_FOUND", "message": "Profil tidak ditemukan."})
    is_following = bool(viewer_follow and viewer_follow[0].get("status") == "active")
    request_pending = bool(viewer_follow and viewer_follow[0].get("status") == "requested")
    if visibility != "public" and viewer_id != owner_id and not is_following:
        raise HTTPException(404, detail={"code": "SOCIAL_NODE_NOT_FOUND", "message": "Profil tidak ditemukan."})

    counts = await _server_db("POST", "rpc/social_graph_node_counts", body={
        "p_node_type": node_type, "p_node_id": str(node_id),
    })
    count_row = counts[0] if counts else {"followers_count": 0, "following_count": 0}
    muted = False
    if viewer_id:
        mute_rows = await _server_db("GET", "social_edges", params={
            "select": "id", "actor_user_id": f"eq.{viewer_id}", "actor_node_type": "eq.human",
            "target_node_type": f"eq.{node_type}",
            **({"target_user_id": f"eq.{node_id}", "target_agent_id": "is.null"} if node_type == "human" else {"target_user_id": f"eq.{owner_id}", "target_agent_id": f"eq.{node_id}"}),
            "edge_type": "eq.mute", "status": "eq.active", "limit": "1",
        })
        muted = bool(mute_rows)
    return {
        "node_type": node_type, "node_id": str(node_id), "visibility": visibility,
        "followers_count": int(count_row.get("followers_count") or 0), "following_count": int(count_row.get("following_count") or 0),
        "viewer_relationship": {"is_following": is_following, "request_pending": request_pending, "muted": muted, "blocked": False},
    }


@router.post("/relationships", status_code=201)
async def create_relationship(
    payload: RelationshipCreate,
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    user: dict[str, Any] = Depends(current_user),
) -> JSONResponse:
    token, owner_id = request.state.supabase_access_token, str(user["id"])
    key = idempotency_key.strip() if idempotency_key else None
    if key and (len(key) < 8 or len(key) > 160 or not all(ch.isalnum() or ch in "._:-" for ch in key)):
        raise HTTPException(422, detail={"code": "SOCIAL_IDEMPOTENCY_KEY_INVALID", "message": "Idempotency-Key tidak valid."})

    actor_agent = await _resolve_actor_agent(str(payload.actor_agent_id), owner_id, token, payload.edge_type) if payload.actor_agent_id else None
    target_owner_id, target_visibility = await _resolve_target(payload.target_type, str(payload.target_id), token)

    actor_type = "agent" if actor_agent else "human"
    actor_agent_id = str(payload.actor_agent_id) if actor_agent else None
    target_agent_id = str(payload.target_id) if payload.target_type == "agent" else None
    if actor_type == payload.target_type and (actor_agent_id or owner_id) == (target_agent_id or str(payload.target_id)):
        if payload.target_type == "human" and owner_id == str(payload.target_id):
            raise HTTPException(422, detail={"code": "SOCIAL_EDGE_SELF_TARGET", "message": "Relasi sosial tidak dapat ditujukan ke identitas sendiri."})
        if payload.target_type == "agent" and actor_agent_id == target_agent_id:
            raise HTTPException(422, detail={"code": "SOCIAL_EDGE_SELF_TARGET", "message": "Agent tidak dapat membuat relasi terhadap dirinya sendiri."})

    filters = _edge_filters(owner_id, target_owner_id, actor_agent_id, payload.target_type, str(payload.target_id), payload.edge_type)
    existing = await _rows("GET", "social_edges", token, params=filters)
    if key:
        replay = await _rows("GET", "social_edges", token, params={
            "select": filters["select"], "actor_user_id": f"eq.{owner_id}",
            "idempotency_key": f"eq.{key}", "limit": "1",
        })
        if replay:
            row = replay[0]
            same = (row.get("target_node_type") == payload.target_type
                    and str(row.get("target_agent_id") or row.get("target_user_id")) == str(payload.target_id)
                    and row.get("edge_type") == payload.edge_type
                    and str(row.get("actor_agent_id") or "") == str(actor_agent_id or ""))
            if not same:
                raise HTTPException(409, detail={"code": "SOCIAL_IDEMPOTENCY_KEY_REUSED", "message": "Idempotency-Key sudah digunakan untuk relasi berbeda."})
            return JSONResponse(status_code=200, content={"edge": row, "outcome": "idempotent_replay", "idempotent_replay": True})
    if existing:
        return JSONResponse(status_code=200, content={"edge": existing[0], "outcome": "idempotent_replay", "idempotent_replay": True})

    body = {
        "p_actor_user_id": owner_id, "p_target_user_id": target_owner_id,
        "p_actor_node_type": actor_type, "p_target_node_type": payload.target_type,
        "p_actor_agent_id": actor_agent_id, "p_target_agent_id": target_agent_id,
        "p_edge_type": payload.edge_type, "p_idempotency_key": key,
    }
    try:
        rows = await service_db_request("create_social_edge_for_actor", body=body)
    except HTTPException as exc:
        if exc.status_code != 409:
            raise
        existing = await _rows("GET", "social_edges", token, params=filters)
        if existing:
            return JSONResponse(status_code=200, content={"edge": existing[0], "outcome": "idempotent_replay", "idempotent_replay": True})
        raise
    if not rows:
        raise HTTPException(409, detail={"code": "SOCIAL_EDGE_NOT_RECORDED", "message": "Relasi tidak dapat disimpan."})
    row = rows[0]
    outcome = "follow_request_created" if row.get("edge_type") == "follow" and row.get("status") == "requested" else f"{payload.edge_type}_active"
    return JSONResponse(status_code=201, content={"edge": row, "outcome": outcome, "idempotent_replay": False})


@router.post("/relationships/{edge_id}/accept")
async def accept_relationship(edge_id: uuid.UUID, request: Request,
                              user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    rows = await service_db_request("accept_social_follow_for_actor", body={
        "p_actor_user_id": str(user["id"]), "p_edge_id": str(edge_id),
    })
    if not rows:
        replay = await _rows("GET", "social_edges", request.state.supabase_access_token, params={
            "id": f"eq.{edge_id}", "target_user_id": f"eq.{user['id']}",
            "edge_type": "eq.follow", "status": "eq.active",
            "select": "id,actor_user_id,target_user_id,actor_node_type,target_node_type,actor_agent_id,target_agent_id,edge_type,status,created_at",
            "limit": "1",
        })
        if replay:
            return {"edge": replay[0], "outcome": "follow_accepted", "idempotent_replay": True}
        raise HTTPException(404, detail={"code": "SOCIAL_FOLLOW_REQUEST_NOT_FOUND", "message": "Permintaan tidak ditemukan atau sudah diproses."})
    return {"edge": rows[0], "outcome": "follow_accepted", "idempotent_replay": False}


@router.post("/relationships/{edge_id}/reject")
async def reject_relationship(edge_id: uuid.UUID, request: Request,
                              user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    rows = await service_db_request("reject_social_follow_for_actor", body={
        "p_actor_user_id": str(user["id"]), "p_edge_id": str(edge_id),
    })
    if not rows:
        return {"removed": None, "outcome": "follow_rejected", "idempotent_replay": True}
    return {"removed": rows[0], "outcome": "follow_rejected", "idempotent_replay": False}


@router.delete("/relationships/{edge_id}")
async def remove_relationship(edge_id: uuid.UUID, request: Request,
                              user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    rows = await service_db_request("remove_social_edge_for_actor", body={
        "p_actor_user_id": str(user["id"]), "p_edge_id": str(edge_id),
    })
    if not rows:
        return {"removed": None, "outcome": "already_removed", "idempotent_replay": True}
    return {"removed": rows[0], "outcome": f"{rows[0]['edge_type']}_removed", "idempotent_replay": False}

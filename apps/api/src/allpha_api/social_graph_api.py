"""Canonical polymorphic Social Graph API for Human and owned AI Agent identities."""
from __future__ import annotations

import uuid
from typing import Any, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from fastapi.responses import JSONResponse

from allpha_api.auth import current_user, user_db_request
from allpha_api.feed_api import _server_db

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
    rows = await _rows("GET", "ai_agents", token, params={
        "select": "id,created_by,handle,display_name,avatar_url,description,visibility,status",
        "status": "eq.active", "visibility": "eq.public",
        "handle": "ilike.*" + normalized + "*",
        "order": "display_name.asc", "limit": str(limit),
    })
    if not rows:
        return {"items": [], "query": normalized}
    ids = [str(row["id"]) for row in rows]
    owners = [str(row["created_by"]) for row in rows if row.get("created_by")]
    ownerships = await _rows("GET", "agent_ownerships", token, params={
        "select": "agent_id,owner_user_id", "agent_id": "in.(" + ",".join(ids) + ")",
        "owner_user_id": "in.(" + ",".join(owners) + ")", "ownership_role": "eq.owner",
        "status": "eq.active", "limit": str(min(500, len(ids) * 2)),
    })
    valid = {(str(row["agent_id"]), str(row["owner_user_id"])) for row in ownerships}
    owner_profiles = await _rows("GET", "profiles", token, params={
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
        "actor_user_id": owner_id, "target_user_id": target_owner_id,
        "actor_node_type": actor_type, "target_node_type": payload.target_type,
        "actor_agent_id": actor_agent_id, "target_agent_id": target_agent_id,
        "edge_type": payload.edge_type, **({"idempotency_key": key} if key else {}),
    }
    try:
        rows = await _rows("POST", "social_edges", token, body=body,
                           params={"select": filters["select"]}, prefer="return=representation")
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
    rows = await _rows("PATCH", "social_edges", request.state.supabase_access_token, params={
        "id": f"eq.{edge_id}", "target_user_id": f"eq.{user['id']}",
        "edge_type": "eq.follow", "status": "eq.requested",
        "select": "id,actor_user_id,target_user_id,actor_node_type,target_node_type,actor_agent_id,target_agent_id,edge_type,status,created_at",
    }, body={"status": "active"}, prefer="return=representation")
    if not rows:
        raise HTTPException(404, detail={"code": "SOCIAL_FOLLOW_REQUEST_NOT_FOUND", "message": "Permintaan tidak ditemukan atau sudah diproses."})
    return {"edge": rows[0], "outcome": "follow_accepted"}


@router.post("/relationships/{edge_id}/reject")
async def reject_relationship(edge_id: uuid.UUID, request: Request,
                              user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    rows = await _rows("DELETE", "social_edges", request.state.supabase_access_token, params={
        "id": f"eq.{edge_id}", "target_user_id": f"eq.{user['id']}",
        "edge_type": "eq.follow", "status": "eq.requested", "select": "id,actor_node_type,target_node_type,actor_agent_id,target_agent_id",
    }, prefer="return=representation")
    if not rows:
        raise HTTPException(404, detail={"code": "SOCIAL_FOLLOW_REQUEST_NOT_FOUND", "message": "Permintaan tidak ditemukan atau sudah diproses."})
    return {"removed": rows[0], "outcome": "follow_rejected"}


@router.delete("/relationships/{edge_id}")
async def remove_relationship(edge_id: uuid.UUID, request: Request,
                              user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    rows = await _rows("DELETE", "social_edges", request.state.supabase_access_token, params={
        "id": f"eq.{edge_id}", "actor_user_id": f"eq.{user['id']}",
        "select": "id,actor_node_type,target_node_type,actor_agent_id,target_agent_id,edge_type,status",
    }, prefer="return=representation")
    if not rows:
        raise HTTPException(404, detail={"code": "SOCIAL_EDGE_NOT_FOUND", "message": "Relasi tidak ditemukan atau bukan milik principal Anda."})
    return {"removed": rows[0], "outcome": f"{rows[0]['edge_type']}_removed"}

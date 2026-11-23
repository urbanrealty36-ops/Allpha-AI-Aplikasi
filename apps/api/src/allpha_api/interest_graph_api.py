"""Owner-controlled Interest, Passion and Habit Graph API."""
from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from allpha_api.auth import current_user, user_db_request, service_db_request

router = APIRouter(prefix="/v1/me", tags=["interest-graph"])


class InterestSignalWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    interest_key: str = Field(min_length=1, max_length=80)
    signal_type: Literal["passion", "habit"]
    strength: float = Field(ge=0, le=1)
    signal_source: Literal["user_selected", "explicit_feedback", "observed_interaction"]
    consent_version: Literal["interest-graph-v1"] = "interest-graph-v1"
    agent_id: UUID | None = None


@router.get("/interest-signals")
async def list_my_interest_signals(
    request: Request, user: dict[str, Any] = Depends(current_user)
) -> dict[str, Any]:
    rows = await user_db_request(
        "GET", "user_interest_graph_signals", request.state.supabase_access_token,
        params={
            "select": "interest_key,agent_id,signal_type,strength,signal_source,consent_version,consent_granted_at,created_at,updated_at",
            "user_id": f"eq.{user['id']}", "order": "signal_type.asc,interest_key.asc", "limit": "500",
        },
    )
    events = await user_db_request(
        "GET", "user_interest_graph_signal_events", request.state.supabase_access_token,
        params={
            "select": "interest_key,agent_id,signal_type,action,signal_source,consent_version,occurred_at",
            "user_id": f"eq.{user['id']}", "order": "occurred_at.desc", "limit": "100",
        },
    )
    return {"items": rows if isinstance(rows, list) else [], "events": events if isinstance(events, list) else []}


@router.put("/interest-signals")
async def set_my_interest_signal(
    payload: InterestSignalWrite,
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    rows = await service_db_request("set_user_interest_graph_signal_for_actor", body={
        "p_actor_user_id": str(user["id"]),
        "p_interest_key": payload.interest_key,
        "p_signal_type": payload.signal_type,
        "p_strength": payload.strength,
        "p_signal_source": payload.signal_source,
        "p_consent_version": payload.consent_version,
        **({"p_agent_id": str(payload.agent_id)} if payload.agent_id else {}),
    })
    if not isinstance(rows, list) or len(rows) != 1:
        raise HTTPException(409, detail={"code": "INTEREST_SIGNAL_NOT_RECORDED", "message": "Sinyal minat tidak dapat disimpan."})
    return {"item": rows[0]}


@router.delete("/interest-signals/{signal_type}/{interest_key}")
async def delete_my_interest_signal(
    signal_type: Literal["passion", "habit"],
    interest_key: str,
    user: dict[str, Any] = Depends(current_user),
    agent_id: UUID | None = None,
) -> dict[str, Any]:
    rows = await service_db_request("delete_user_interest_graph_signal_for_actor", body={
        "p_actor_user_id": str(user["id"]),
        "p_interest_key": interest_key,
        "p_signal_type": signal_type,
        **({"p_agent_id": str(agent_id)} if agent_id else {}),
    })
    if not isinstance(rows, list) or not rows:
        raise HTTPException(404, detail={"code": "INTEREST_SIGNAL_NOT_FOUND", "message": "Sinyal minat tidak ditemukan."})
    return {"removed": rows[0]}


@router.delete("/interest-signals")
async def reset_my_interest_signals(
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    deleted = await service_db_request("clear_user_interest_graph_signals_for_actor", body={
        "p_actor_user_id": str(user["id"]),
    })
    if type(deleted) is not int:
        raise HTTPException(409, detail={"code": "INTEREST_SIGNAL_RESET_UNCONFIRMED", "message": "Reset sinyal minat belum terkonfirmasi."})
    return {"deleted_count": deleted}


catalog_router = APIRouter(tags=["interest-ontology"])


@catalog_router.get("/v1/interests/catalog")
async def list_interest_catalog(
    request: Request,
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    items = await user_db_request(
        "GET",
        "interest_catalog",
        request.state.supabase_access_token,
        params={
            "select": "interest_key,label,label_key,category,aliases,sensitivity,sort_order",
            "active": "eq.true",
            "order": "sort_order.asc,interest_key.asc",
            "limit": "500",
        },
    )
    relationships = await user_db_request(
        "GET",
        "interest_taxonomy_edges",
        request.state.supabase_access_token,
        params={
            "select": "source_interest_key,target_interest_key,relation_type,weight",
            "active": "eq.true",
            "order": "source_interest_key.asc,target_interest_key.asc",
            "limit": "1000",
        },
    )
    return {
        "items": items if isinstance(items, list) else [],
        "relationships": relationships if isinstance(relationships, list) else [],
    }

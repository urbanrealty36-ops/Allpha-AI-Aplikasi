"""ENG-P18 authenticated messaging, delivery and realtime-compatible API."""
from __future__ import annotations
import os, uuid
from datetime import datetime, timezone
from typing import Any
import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from allpha_api.auth import current_user

router = APIRouter(prefix="/v1/messages", tags=["messaging"])
TIMEOUT = httpx.Timeout(12, connect=3)

def _config():
    base = os.getenv("SUPABASE_URL", "").rstrip("/")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "") or os.getenv("SUPABASE_SECRET_KEY", "")
    if not base or not key:
        raise HTTPException(503, detail={"code":"MESSAGING_NOT_CONFIGURED","message":"Layanan pesan belum dikonfigurasi."})
    return base, key

async def _db(method: str, table: str, *, params: dict[str, str] | None = None, body: Any = None, prefer: str | None = None):
    base, key = _config()
    headers = {"apikey":key,"Authorization":f"Bearer {key}","Content-Type":"application/json"}
    if prefer: headers["Prefer"] = prefer
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.request(method, f"{base}/rest/v1/{table}", params=params, json=body, headers=headers)
    except httpx.HTTPError as exc:
        raise HTTPException(503, detail={"code":"MESSAGING_DATABASE_UNAVAILABLE","message":"Data pesan sementara tidak tersedia."}) from exc
    if response.status_code >= 400:
        if response.status_code == 409:
            raise HTTPException(409, detail={"code":"MESSAGE_CONFLICT","message":"Pesan duplikat atau konflik; muat ulang percakapan."})
        raise HTTPException(503, detail={"code":"MESSAGING_DATABASE_ERROR","message":"Data pesan tidak dapat diproses."})
    return response.json() if response.content else None

async def _membership(conversation_id: uuid.UUID, user_id: str):
    rows = await _db("GET","conversation_participants",params={"select":"conversation_id,user_id,agent_id,last_read_at","conversation_id":f"eq.{conversation_id}","user_id":f"eq.{user_id}","limit":"1"})
    if not rows:
        raise HTTPException(404,detail={"code":"CONVERSATION_NOT_FOUND","message":"Percakapan tidak ditemukan."})
    return rows[0]

class ConversationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    recipient_user_id: uuid.UUID | None = None
    agent_id: uuid.UUID | None = None
    title: str | None = Field(default=None,max_length=120)

class MessageCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    body: str = Field(min_length=1,max_length=10000)
    client_message_id: uuid.UUID

@router.get("/conversations")
async def list_conversations(request: Request, user: dict[str,Any] = Depends(current_user), limit: int = Query(30,ge=1,le=100)):
    uid=str(user["id"])
    memberships=await _db("GET","conversation_participants",params={"select":"conversation_id,last_read_at","user_id":f"eq.{uid}","order":"joined_at.desc","limit":str(limit)})
    if not memberships: return {"items":[]}
    ids=[row["conversation_id"] for row in memberships]
    convs=await _db("GET","conversations",params={"select":"id,title,kind,created_by,created_at,updated_at,last_message_at","id":"in.("+",".join(ids)+")","order":"last_message_at.desc.nullslast","limit":str(limit)})
    people=await _db("GET","conversation_participants",params={"select":"conversation_id,user_id,agent_id,participant_type","conversation_id":"in.("+",".join(ids)+")","limit":str(limit*10)})
    latest=await _db("GET","messages",params={"select":"id,conversation_id,sender_type,sender_user_id,sender_agent_id,body,created_at,delivery_status","conversation_id":"in.("+",".join(ids)+")","order":"created_at.desc","limit":str(limit*10)})
    by_id={c["id"]:c for c in convs}
    for row in people:
        if row.get("user_id")==uid: continue
        by_id.get(row["conversation_id"],{}).setdefault("participants",[]).append(row)
    for row in latest:
        conv=by_id.get(row["conversation_id"])
        if conv is not None and "last_message" not in conv: conv["last_message"]=row
    return {"items":[by_id[i] for i in by_id]}

@router.post("/conversations",status_code=201)
async def create_conversation(payload: ConversationCreate, request: Request, user: dict[str,Any] = Depends(current_user)):
    if bool(payload.recipient_user_id) == bool(payload.agent_id):
        raise HTTPException(422,detail={"code":"RECIPIENT_REQUIRED","message":"Tentukan satu penerima manusia atau Agent."})
    uid=str(user["id"])
    if payload.recipient_user_id and str(payload.recipient_user_id)==uid:
        raise HTTPException(422,detail={"code":"SELF_MESSAGE","message":"Tidak dapat memulai percakapan dengan diri sendiri."})
    if payload.recipient_user_id:
        recipient=str(payload.recipient_user_id)
        edges=await _db("GET","social_edges",params={"select":"id","edge_type":"eq.block","status":"eq.active","or":f"(and(actor_user_id.eq.{uid},target_user_id.eq.{recipient}),and(actor_user_id.eq.{recipient},target_user_id.eq.{uid}))","limit":"1"})
        if edges: raise HTTPException(403,detail={"code":"MESSAGING_BLOCKED","message":"Percakapan tidak tersedia karena pembatasan blokir."})
        kind="human"
        participants=[{"user_id":uid,"participant_type":"human"},{"user_id":recipient,"participant_type":"human"}]
    else:
        agents=await _db("GET","ai_agents",params={"select":"id,created_by,status,visibility","id":f"eq.{payload.agent_id}","limit":"1"})
        if not agents or agents[0].get("status")!="active" or agents[0].get("visibility")!="public":
            raise HTTPException(404,detail={"code":"AGENT_NOT_AVAILABLE","message":"Agent tidak tersedia untuk percakapan."})
        kind="agent"
        participants=[{"user_id":uid,"participant_type":"human"},{"agent_id":str(payload.agent_id),"participant_type":"agent"}]
    rows=await _db("POST","conversations",body={"kind":kind,"title":payload.title,"created_by":uid},prefer="return=representation")
    if not rows: raise HTTPException(503,detail={"code":"CONVERSATION_CREATE_FAILED","message":"Percakapan tidak dapat dibuat."})
    conversation=rows[0]
    for participant in participants: participant["conversation_id"]=conversation["id"]
    await _db("POST","conversation_participants",body=participants,prefer="return=minimal")
    return {"conversation":conversation}

@router.get("/conversations/{conversation_id}/messages")
async def list_messages(conversation_id: uuid.UUID, request: Request, user: dict[str,Any] = Depends(current_user), limit: int = Query(50,ge=1,le=100), before: datetime | None = None):
    uid=str(user["id"]); await _membership(conversation_id,uid)
    params={"select":"id,conversation_id,sender_type,sender_user_id,sender_agent_id,body,client_message_id,created_at,delivery_status,delivered_at,read_at","conversation_id":f"eq.{conversation_id}","order":"created_at.desc","limit":str(limit)}
    if before: params["created_at"]=f"lt.{before.astimezone(timezone.utc).isoformat()}"
    rows=await _db("GET","messages",params=params)
    now=datetime.now(timezone.utc).isoformat()
    for row in rows:
        if row.get("sender_user_id") != uid and row.get("delivery_status")=="sent":
            await _db("PATCH","messages",params={"id":f"eq.{row['id']}","delivery_status":"eq.sent"},body={"delivery_status":"delivered","delivered_at":now},prefer="return=minimal")
            row["delivery_status"]="delivered"; row["delivered_at"]=now
    await _db("PATCH","conversation_participants",params={"conversation_id":f"eq.{conversation_id}","user_id":f"eq.{uid}"},body={"last_read_at":now},prefer="return=minimal")
    return {"items":list(reversed(rows)),"has_more":len(rows)==limit}

@router.post("/conversations/{conversation_id}/messages",status_code=201)
async def send_message(conversation_id: uuid.UUID, payload: MessageCreate, request: Request, user: dict[str,Any] = Depends(current_user)):
    uid=str(user["id"]); await _membership(conversation_id,uid)
    # Idempotent client ID prevents duplicate sends after reconnect/retry.
    existing=await _db("GET","messages",params={"select":"id,conversation_id,sender_type,sender_user_id,body,client_message_id,created_at,delivery_status","conversation_id":f"eq.{conversation_id}","sender_user_id":f"eq.{uid}","client_message_id":f"eq.{payload.client_message_id}","limit":"1"})
    if existing: return {"message":existing[0],"replayed":True}
    row={"conversation_id":str(conversation_id),"sender_type":"human","sender_user_id":uid,"body":payload.body.strip(),"client_message_id":str(payload.client_message_id),"delivery_status":"sent"}
    if not row["body"]: raise HTTPException(422,detail={"code":"MESSAGE_EMPTY","message":"Pesan tidak boleh kosong."})
    created=await _db("POST","messages",body=row,prefer="return=representation")
    if not created: raise HTTPException(503,detail={"code":"MESSAGE_SEND_FAILED","message":"Pesan tidak dapat dikirim."})
    await _db("PATCH","conversations",params={"id":f"eq.{conversation_id}"},body={"updated_at":datetime.now(timezone.utc).isoformat(),"last_message_at":created[0]["created_at"]},prefer="return=minimal")
    return {"message":created[0],"replayed":False}

@router.post("/conversations/{conversation_id}/read")
async def mark_read(conversation_id: uuid.UUID, request: Request, user: dict[str,Any] = Depends(current_user)):
    uid=str(user["id"]); await _membership(conversation_id,uid)
    now=datetime.now(timezone.utc).isoformat()
    await _db("PATCH","messages",params={"conversation_id":f"eq.{conversation_id}","sender_user_id":f"neq.{uid}","delivery_status":"in.(sent,delivered)"},body={"delivery_status":"read","read_at":now},prefer="return=minimal")
    await _db("PATCH","conversation_participants",params={"conversation_id":f"eq.{conversation_id}","user_id":f"eq.{uid}"},body={"last_read_at":now},prefer="return=minimal")
    return {"read_at":now}

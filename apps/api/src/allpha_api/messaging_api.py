"""ENG-P18 authenticated messaging, delivery and realtime-compatible API."""
from __future__ import annotations
import os, uuid
from datetime import datetime, timezone
from typing import Any
import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from allpha_api.auth import current_user
from allpha_api.agent_runtime import AgentRuntime, AgentRuntimeBlocked
from allpha_api.agent_runtime_store import AgentRuntimeStore, AgentRuntimePersistenceError
from allpha_api.model_router import TextGenerationRequest, TextGenerationRouterUnavailable

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

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

async def _membership(conversation_id: uuid.UUID, user_id: str):
    rows = await _db("GET","conversation_participants",params={"select":"conversation_id,user_id,agent_id,last_read_at","conversation_id":f"eq.{conversation_id}","user_id":f"eq.{user_id}","limit":"1"})
    if not rows:
        raise HTTPException(404,detail={"code":"CONVERSATION_NOT_FOUND","message":"Percakapan tidak ditemukan."})
    return rows[0]

async def _assert_not_blocked(conversation_id: uuid.UUID, user_id: str):
    participants = await _db("GET","conversation_participants",params={"select":"user_id","conversation_id":f"eq.{conversation_id}","user_id":"not.is.null","limit":"20"})
    other_ids = sorted({str(row["user_id"]) for row in participants if row.get("user_id") and str(row["user_id"]) != user_id})
    if not other_ids:
        return
    edges = await _db("GET","social_edges",params={
        "select":"id","edge_type":"eq.block","status":"eq.active",
        "or":f"(and(actor_user_id.eq.{user_id},target_user_id.in.({','.join(other_ids)})),and(actor_user_id.in.({','.join(other_ids)}),target_user_id.eq.{user_id}))",
        "limit":"1",
    })
    if edges:
        raise HTTPException(403,detail={"code":"MESSAGING_BLOCKED","message":"Percakapan tidak tersedia karena pembatasan blokir."})

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
    visible=[]
    for cid, conv in by_id.items():
        try:
            await _assert_not_blocked(uuid.UUID(cid),uid)
        except HTTPException as exc:
            if exc.status_code==403: continue
            raise
        visible.append(conv)
    return {"items":visible}

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
        profiles=await _db("GET","profiles",params={"select":"id,visibility,account_status","id":f"eq.{recipient}","limit":"1"})
        if not profiles or profiles[0].get("account_status")!="active":
            raise HTTPException(404,detail={"code":"RECIPIENT_NOT_AVAILABLE","message":"Penerima tidak tersedia."})
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
    try:
        await _db("POST","conversation_participants",body=participants,prefer="return=minimal")
    except HTTPException:
        await _db("DELETE","conversations",params={"id":f"eq.{conversation['id']}"})
        raise
    return {"conversation":conversation}

@router.get("/conversations/{conversation_id}/messages")
async def list_messages(conversation_id: uuid.UUID, request: Request, user: dict[str,Any] = Depends(current_user), limit: int = Query(50,ge=1,le=100), before: datetime | None = None):
    uid=str(user["id"]); await _membership(conversation_id,uid); await _assert_not_blocked(conversation_id,uid)
    params={"select":"id,conversation_id,sender_type,sender_user_id,sender_agent_id,body,client_message_id,created_at,delivery_status,delivered_at,read_at","conversation_id":f"eq.{conversation_id}","order":"created_at.desc","limit":str(limit)}
    if before: params["created_at"]=f"lt.{before.astimezone(timezone.utc).isoformat()}"
    rows=await _db("GET","messages",params=params)
    incoming=[row for row in rows if row.get("sender_user_id") != uid and row.get("delivery_status")=="sent"]
    for row in incoming:
        now=_now()
        changed=await _db("PATCH","messages",params={"id":f"eq.{row['id']}","delivery_status":"eq.sent"},body={"delivery_status":"delivered","delivered_at":now},prefer="return=representation")
        if changed:
            row.update(changed[0])
    now=_now()
    await _db("PATCH","conversation_participants",params={"conversation_id":f"eq.{conversation_id}","user_id":f"eq.{uid}"},body={"last_read_at":now},prefer="return=minimal")
    return {"items":list(reversed(rows)),"has_more":len(rows)==limit}

@router.post("/conversations/{conversation_id}/messages",status_code=201)
async def send_message(conversation_id: uuid.UUID, payload: MessageCreate, request: Request, user: dict[str,Any] = Depends(current_user)):
    uid=str(user["id"]); await _membership(conversation_id,uid); await _assert_not_blocked(conversation_id,uid)
    body=payload.body.strip()
    if not body: raise HTTPException(422,detail={"code":"MESSAGE_EMPTY","message":"Pesan tidak boleh kosong."})
    existing=await _db("GET","messages",params={"select":"id,conversation_id,sender_type,sender_user_id,sender_agent_id,body,client_message_id,created_at,delivery_status,delivered_at,read_at","conversation_id":f"eq.{conversation_id}","sender_user_id":f"eq.{uid}","client_message_id":f"eq.{payload.client_message_id}","limit":"1"})
    replayed = bool(existing)
    created = existing
    if not existing:
        row={"conversation_id":str(conversation_id),"sender_type":"human","sender_user_id":uid,"body":body,"client_message_id":str(payload.client_message_id),"delivery_status":"sent"}
        try:
            created=await _db("POST","messages",body=row,prefer="return=representation")
        except HTTPException as exc:
            if exc.status_code==409:
                replay=await _db("GET","messages",params={"select":"id,conversation_id,sender_type,sender_user_id,sender_agent_id,body,client_message_id,created_at,delivery_status,delivered_at,read_at","conversation_id":f"eq.{conversation_id}","sender_user_id":f"eq.{uid}","client_message_id":f"eq.{payload.client_message_id}","limit":"1"})
                if replay:
                    created = replay
                    replayed = True
                else:
                    raise
            else:
                raise
    if not created: raise HTTPException(503,detail={"code":"MESSAGE_SEND_FAILED","message":"Pesan tidak dapat dikirim."})
    if not replayed:
        await _db("PATCH","conversations",params={"id":f"eq.{conversation_id}"},body={"updated_at":_now(),"last_message_at":created[0]["created_at"]},prefer="return=minimal")
    agent_reply = None
    conv = await _db("GET","conversations",params={"select":"id,kind","id":f"eq.{conversation_id}","limit":"1"})
    if conv and conv[0].get("kind") == "agent":
        participants = await _db("GET","conversation_participants",params={"select":"agent_id","conversation_id":f"eq.{conversation_id}","participant_type":"eq.agent","limit":"1"})
        agent_id = str(participants[0]["agent_id"]) if participants else ""
        try:
            runtime_store = AgentRuntimeStore.from_environment()
            if not agent_id or not await runtime_store.owner_has_agent(uid,agent_id):
                agent_reply = {"status":"unavailable","error_code":"PUBLIC_AGENT_RUNTIME_AUTHORIZATION_REQUIRED"}
            else:
                agents = await _db("GET","ai_agents",params={"select":"id,version,status,persona,boundaries","id":f"eq.{agent_id}","limit":"1"})
                skills = await _db("GET","agent_skills",params={"select":"id,version,status,name,instructions","agent_id":f"eq.{agent_id}","status":"eq.published","order":"updated_at.desc","limit":"1"})
                text_router = getattr(request.app.state,"text_generation_router",None)
                if not agents or agents[0].get("status")!="active" or not skills or text_router is None:
                    agent_reply = {"status":"unavailable","error_code":"AGENT_RUNTIME_NOT_READY"}
                else:
                    agent, skill = agents[0], skills[0]
                    text_router.require_runtime_ready("private")
                    policy_version = text_router.policy_version_for("private")
                    prompt = (
                        "Anda adalah AI Agent Allpha milik pengguna yang sedang menguji Agent-nya sendiri. "
                        "Ikuti persona dan instruksi Skill, jangan melampaui boundaries, dan jangan mengklaim tindakan yang belum dilakukan. "
                        "Balas dalam Bahasa Indonesia secara ringkas.\nPERSONA: " + str(agent.get("persona") or {})[:3000] +
                        "\nBOUNDARIES: " + str(agent.get("boundaries") or {})[:1500] +
                        "\nSKILL: " + str(skill.get("name") or "")[:200] +
                        "\nINSTRUKSI SKILL: " + str(skill.get("instructions") or "")[:2500] +
                        "\nPESAN PENGGUNA: " + body
                    )
                    task_id, trace_id = str(uuid.uuid4()), str(uuid.uuid4())
                    generation = TextGenerationRequest(
                        task_id=task_id, trace_id=trace_id,
                        idempotency_key="message-agent-reply:"+str(created[0]["id"]),
                        sensitivity="private", prompt=prompt, max_output_tokens=512, timeout_ms=30000,
                        owner_id=uid, agent_id=agent_id, source_id=str(skill["id"]), source_version=int(skill["version"]),
                    )
                    generated, evidence = await AgentRuntime().execute_skill_generation(
                        requester_id=uid, owner_id=uid, agent_id=agent_id, agent_version=int(agent["version"]),
                        skill_id=str(skill["id"]), skill_version=int(skill["version"]), skill_published=True,
                        policy_version=policy_version, router=text_router, request=generation,
                    )
                    reply_id = str(uuid.uuid5(uuid.NAMESPACE_URL,"allpha-agent-reply:"+str(created[0]["id"])))
                    reply_row = {"conversation_id":str(conversation_id),"sender_type":"agent","sender_agent_id":agent_id,
                                 "body":generated.output_text[:10000],"client_message_id":reply_id,"delivery_status":"sent"}
                    try:
                        reply_created = await _db("POST","messages",body=reply_row,prefer="return=representation")
                    except HTTPException as exc:
                        if exc.status_code != 409: raise
                        reply_created = await _db("GET","messages",params={"select":"id,conversation_id,sender_type,sender_agent_id,body,client_message_id,created_at,delivery_status","conversation_id":f"eq.{conversation_id}","sender_agent_id":f"eq.{agent_id}","client_message_id":f"eq.{reply_id}","limit":"1"})
                    if reply_created:
                        agent_reply = {"status":"sent","message":reply_created[0],"trace_id":evidence.trace_id}
                        await _db("PATCH","conversations",params={"id":f"eq.{conversation_id}"},body={"updated_at":_now(),"last_message_at":reply_created[0]["created_at"]},prefer="return=minimal")
                    else:
                        agent_reply = {"status":"failed","error_code":"AGENT_REPLY_PERSISTENCE_FAILED","trace_id":evidence.trace_id}
        except (AgentRuntimeBlocked, TextGenerationRouterUnavailable, AgentRuntimePersistenceError, ValueError):
            agent_reply = {"status":"unavailable","error_code":"AGENT_RUNTIME_BLOCKED"}
        except Exception:
            # Provider/network/runtime failures must not erase the persisted user message.
            # A retry with the same client_message_id re-enters this recovery path.
            agent_reply = {"status":"failed","error_code":"AGENT_REPLY_RETRYABLE_FAILURE"}
    return {"message":created[0],"replayed":replayed,"agent_reply":agent_reply}

@router.post("/conversations/{conversation_id}/read")
async def mark_read(conversation_id: uuid.UUID, request: Request, user: dict[str,Any] = Depends(current_user)):
    uid=str(user["id"]); await _membership(conversation_id,uid); await _assert_not_blocked(conversation_id,uid)
    now=_now()
    await _db("PATCH","messages",params={"conversation_id":f"eq.{conversation_id}","or":f"(sender_user_id.neq.{uid},sender_user_id.is.null)","delivery_status":"in.(sent,delivered)"},body={"delivery_status":"read","read_at":now},prefer="return=minimal")
    await _db("PATCH","conversation_participants",params={"conversation_id":f"eq.{conversation_id}","user_id":f"eq.{uid}"},body={"last_read_at":now},prefer="return=minimal")
    return {"read_at":now}

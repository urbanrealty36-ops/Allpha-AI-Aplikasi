"""Owner-facing API for the canonical Agent Memory Coordinator."""
from __future__ import annotations
import uuid
from typing import Any
from fastapi import APIRouter,Depends,HTTPException,Query,Request
from pydantic import BaseModel,ConfigDict,Field
from allpha_api.auth import current_user,user_db_request
from allpha_api.memory_coordinator import MEMORY_TYPES,PURPOSES,MemoryCoordinator,MemoryUnavailable,MemoryDenied

router=APIRouter(prefix="/v1/memory",tags=["agent-memory"])
class PolicyInput(BaseModel):
 model_config=ConfigDict(extra="forbid")
 agent_id:uuid.UUID|None=None
 enabled:bool
 consent_version:str|None=Field(default=None,max_length=80)
 allowed_purposes:list[str]=Field(default_factory=list,max_length=8)
 allowed_sensitivities:list[str]=Field(default_factory=list,max_length=4)
 retention_days:int=Field(default=30,ge=1,le=3650)
class ProposalInput(BaseModel):
 model_config=ConfigDict(extra="forbid")
 agent_id:uuid.UUID|None=None
 memory_type:str
 purpose:str
 classification:str
 content:str=Field(min_length=1,max_length=8000)
 source_ref:dict[str,Any]=Field(default_factory=dict)
 provenance:dict[str,Any]=Field(default_factory=dict)
 confidence:float|None=Field(default=None,ge=0,le=1)
 retention_days:int|None=Field(default=None,ge=1,le=3650)
class DecisionInput(BaseModel):
 model_config=ConfigDict(extra="forbid")
 decision:str
class CorrectionInput(BaseModel):
 model_config=ConfigDict(extra="forbid")
 content:str=Field(min_length=1,max_length=8000)
class ContextInput(BaseModel):
 model_config=ConfigDict(extra="forbid")
 agent_id:uuid.UUID
 purpose:str="agent_runtime_context"
 query:str|None=Field(default=None,max_length=300)
 max_sensitivity:str|None=None
 limit:int=Field(default=12,ge=1,le=30)

def _store():return MemoryCoordinator()
def _error(exc):
 if isinstance(exc,MemoryDenied):return HTTPException(409,detail={"code":"MEMORY_POLICY_DENIED","message":"Operasi Memory tidak diizinkan oleh kebijakan pemilik."})
 return HTTPException(503,detail={"code":"MEMORY_UNAVAILABLE","message":"Memory Coordinator sementara tidak tersedia."})
async def _owner(agent_id,request,user):
 if agent_id is None:return
 rows=await user_db_request("GET","agent_ownerships",getattr(request.state,"supabase_access_token",None),
  params={"select":"agent_id","agent_id":f"eq.{agent_id}","owner_user_id":f"eq.{user['id']}","ownership_role":"eq.owner","status":"eq.active","limit":"1"})
 if not rows:raise HTTPException(404,detail={"code":"AGENT_NOT_FOUND","message":"Agent tidak ditemukan."})

@router.get("/classes")
async def classes(user:dict[str,Any]=Depends(current_user)):
 return {"items":[
 {"key":"conversation","label":"Conversation Memory","storage":"conversations/messages","managed":False},
 {"key":"working","label":"Working Memory","storage":"memory_coordinator","managed":True},
 {"key":"episodic","label":"Episodic Memory","storage":"memory_coordinator","managed":True},
 {"key":"semantic","label":"Semantic Memory","storage":"memory_coordinator","managed":True},
 {"key":"procedural","label":"Procedural Memory","storage":"memory_coordinator","managed":True},
 {"key":"long_term","label":"Long-term Memory","storage":"memory_coordinator","managed":True}]}

@router.get("/policies")
async def policies(request:Request,agent_id:uuid.UUID|None=Query(default=None),user:dict[str,Any]=Depends(current_user)):
 await _owner(agent_id,request,user)
 try:return {"items":await _store().policies(str(user["id"]),str(agent_id) if agent_id else None)}
 except (MemoryUnavailable,MemoryDenied) as exc:raise _error(exc) from exc

@router.put("/policies/{memory_type}")
async def save_policy(memory_type:str,payload:PolicyInput,request:Request,user:dict[str,Any]=Depends(current_user)):
 if memory_type not in MEMORY_TYPES:raise HTTPException(422,detail={"code":"MEMORY_TYPE_INVALID","message":"Kelas Memory tidak didukung."})
 await _owner(payload.agent_id,request,user)
 try:
  p=await _store().save_policy(str(user["id"]),str(payload.agent_id) if payload.agent_id else None,memory_type,payload.enabled,payload.consent_version,payload.allowed_purposes,payload.allowed_sensitivities,payload.retention_days)
  return {"policy":p}
 except (MemoryUnavailable,MemoryDenied) as exc:raise _error(exc) from exc

@router.get("/items")
async def items(request:Request,agent_id:uuid.UUID|None=Query(default=None),memory_type:str|None=Query(default=None),status:str|None=Query(default=None),limit:int=Query(default=50,ge=1,le=100),user:dict[str,Any]=Depends(current_user)):
 await _owner(agent_id,request,user)
 if memory_type and memory_type not in MEMORY_TYPES:raise HTTPException(422,detail={"code":"MEMORY_TYPE_INVALID","message":"Kelas Memory tidak didukung."})
 try:
  s=_store();await s.expire(str(user["id"]),str(agent_id) if agent_id else None)
  return {"items":await s.items(str(user["id"]),str(agent_id) if agent_id else None,memory_type=memory_type,status=status,limit=limit)}
 except (MemoryUnavailable,MemoryDenied) as exc:raise _error(exc) from exc

@router.get("/events")
async def events(request:Request,agent_id:uuid.UUID|None=Query(default=None),limit:int=Query(default=100,ge=1,le=200),user:dict[str,Any]=Depends(current_user)):
 await _owner(agent_id,request,user)
 try:return {"items":await _store().events(str(user["id"]),str(agent_id) if agent_id else None,limit)}
 except (MemoryUnavailable,MemoryDenied) as exc:raise _error(exc) from exc

@router.post("/proposals",status_code=201)
async def propose(payload:ProposalInput,request:Request,user:dict[str,Any]=Depends(current_user)):
 await _owner(payload.agent_id,request,user)
 try:return {"proposal":await _store().propose(str(user["id"]),str(payload.agent_id) if payload.agent_id else None,payload.memory_type,payload.purpose,payload.classification,payload.content,payload.source_ref,payload.provenance,payload.confidence,payload.retention_days)}
 except (MemoryUnavailable,MemoryDenied) as exc:raise _error(exc) from exc

@router.post("/items/{item_id}/decision")
async def decide(item_id:uuid.UUID,payload:DecisionInput,user:dict[str,Any]=Depends(current_user)):
 try:
  row=await _store().decide(str(user["id"]),str(item_id),payload.decision)
  if not row:raise HTTPException(404,detail={"code":"MEMORY_PROPOSAL_NOT_FOUND","message":"Proposal tidak ditemukan, kedaluwarsa atau sudah diputuskan."})
  return {"item_id":str(item_id),"status":"active" if payload.decision=="approve" else "rejected"}
 except (MemoryUnavailable,MemoryDenied) as exc:raise _error(exc) from exc

@router.patch("/items/{item_id}")
async def correct(item_id:uuid.UUID,payload:CorrectionInput,user:dict[str,Any]=Depends(current_user)):
 try:
  row=await _store().correct(str(user["id"]),str(item_id),payload.content)
  if not row:raise HTTPException(404,detail={"code":"MEMORY_ITEM_NOT_FOUND","message":"Memori aktif tidak ditemukan."})
  return {"item_id":str(item_id),"status":"corrected"}
 except (MemoryUnavailable,MemoryDenied) as exc:raise _error(exc) from exc

@router.delete("/items/{item_id}")
async def delete(item_id:uuid.UUID,user:dict[str,Any]=Depends(current_user)):
 try:
  row=await _store().delete(str(user["id"]),str(item_id))
  if not row:raise HTTPException(404,detail={"code":"MEMORY_ITEM_NOT_FOUND","message":"Memori tidak ditemukan."})
  return {"item_id":str(item_id),"status":"deleted","retrieval_access":"revoked"}
 except (MemoryUnavailable,MemoryDenied) as exc:raise _error(exc) from exc

@router.post("/context")
async def context(payload:ContextInput,request:Request,user:dict[str,Any]=Depends(current_user)):
 await _owner(payload.agent_id,request,user)
 if payload.purpose not in PURPOSES:raise HTTPException(422,detail={"code":"MEMORY_PURPOSE_INVALID","message":"Tujuan retrieval Memory tidak didukung."})
 if payload.max_sensitivity is not None and payload.max_sensitivity not in {"public","internal","confidential","restricted"}:
  raise HTTPException(422,detail={"code":"MEMORY_SENSITIVITY_INVALID","message":"Batas sensitivitas Memory tidak valid."})
 try:
  items=await _store().retrieve_context(str(user["id"]),str(payload.agent_id),purpose=payload.purpose,query=payload.query,limit=payload.limit,max_sensitivity=payload.max_sensitivity)
  return {"items":items,"retrieval_mode":"keyword_ranked" if payload.query and payload.query.strip() else "metadata_recency","private_scope":"owner_agent"}
 except (MemoryUnavailable,MemoryDenied) as exc:raise _error(exc) from exc

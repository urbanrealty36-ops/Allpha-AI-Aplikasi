"""Single canonical persistence and retrieval boundary for owner-private Agent Memory."""
from __future__ import annotations
import hashlib, os
from datetime import datetime, timedelta, timezone
from typing import Any
import httpx

MEMORY_TYPES=("working","episodic","semantic","procedural","long_term")
PURPOSES=("agent_generation_context","agent_runtime_context","workflow_context","personalization_context")
SENSITIVITIES=("public","internal","confidential","restricted")
CONSENT_VERSION="allpha.memory.v1"
_TIMEOUT=httpx.Timeout(12,connect=3)

class MemoryUnavailable(RuntimeError): pass
class MemoryDenied(RuntimeError): pass

class MemoryCoordinator:
    def _config(self):
        base=os.getenv("SUPABASE_URL","").rstrip("/")
        key=os.getenv("SUPABASE_SERVICE_ROLE_KEY","") or os.getenv("SUPABASE_SECRET_KEY","")
        if not base or not key: raise MemoryUnavailable("Memory server persistence is not configured")
        return base,key

    async def db(self,method,path,*,params=None,body=None,prefer=None):
        base,key=self._config()
        headers={"apikey":key,"Authorization":f"Bearer {key}","Content-Type":"application/json","Accept":"application/json"}
        if prefer: headers["Prefer"]=prefer
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
                r=await c.request(method,f"{base}/rest/v1/{path}",params=params,json=body,headers=headers)
        except httpx.HTTPError as exc: raise MemoryUnavailable("Memory database is unavailable") from exc
        if r.status_code>=400:
            if r.status_code in (401,403,409): raise MemoryDenied("Memory policy rejected or conflicted with the operation")
            raise MemoryUnavailable("Memory persistence operation failed")
        return r.json() if r.content else None

    async def transition(self,action,owner_id,agent_id=None,item_id=None,payload=None):
        return await self.db("POST","rpc/agent_memory_transition",body={
            "p_action":action,"p_owner_user_id":owner_id,"p_agent_id":agent_id,
            "p_item_id":item_id,"p_payload":payload or {}})

    async def policies(self,owner_id,agent_id):
        p={"select":"*","owner_user_id":f"eq.{owner_id}","agent_id":f"eq.{agent_id}" if agent_id else "is.null","order":"memory_type.asc","limit":"20"}
        rows=await self.db("GET","agent_memory_policies",params=p)
        return rows if isinstance(rows,list) else []

    async def save_policy(self,owner_id,agent_id,memory_type,enabled,consent_version,purposes,sensitivities,retention_days):
        if memory_type not in MEMORY_TYPES or not 1<=retention_days<=3650: raise MemoryDenied("Memory type or retention is invalid")
        if enabled:
            if consent_version!=CONSENT_VERSION: raise MemoryDenied("Explicit current Memory consent is required")
            if not purposes or any(x not in PURPOSES for x in purposes): raise MemoryDenied("Memory purposes are invalid")
            if not sensitivities or any(x not in SENSITIVITIES for x in sensitivities): raise MemoryDenied("Memory classifications are invalid")
            if memory_type=="working" and retention_days!=1: raise MemoryDenied("Working Memory is limited to one day")
        current=next((p for p in await self.policies(owner_id,agent_id) if p["memory_type"]==memory_type),None)
        now=datetime.now(timezone.utc).isoformat()
        body={"owner_user_id":owner_id,"agent_id":agent_id,"memory_type":memory_type,"enabled":enabled,
              "consent_version":consent_version if enabled else None,"consent_granted_at":now if enabled else None,
              "consent_revoked_at":None if enabled else now,"allowed_purposes":sorted(set(purposes)) if enabled else [],
              "allowed_sensitivities":sorted(set(sensitivities)) if enabled else [],
              "retention_days":retention_days,"write_mode":"manual_only",
              "policy_version":int((current or {}).get("policy_version",0))+1,"updated_at":now}
        if current:
            rows=await self.db("PATCH","agent_memory_policies",params={"id":f"eq.{current['id']}","owner_user_id":f"eq.{owner_id}","select":"*"},body=body,prefer="return=representation")
        else:
            body["created_at"]=now
            rows=await self.db("POST","agent_memory_policies",params={"select":"*"},body=body,prefer="return=representation")
        if not isinstance(rows,list) or len(rows)!=1: raise MemoryUnavailable("Memory policy was not persisted")
        policy=rows[0]
        await self.transition("policy_event",owner_id,agent_id,payload={"policy_id":policy["id"],"enabled":enabled,
            "memory_type":memory_type,"policy_version":policy["policy_version"],"retention_days":retention_days})
        return policy

    async def event(self,owner_id,agent_id,policy_id,item_id,event_type,details):
        # Lifecycle item events are written atomically by agent_memory_transition.
        return None

    async def expire(self,owner_id,agent_id):
        return await self.transition("expire",owner_id,agent_id)

    async def items(self,owner_id,agent_id,*,memory_type=None,status=None,limit=50):
        p={"select":"id,policy_id,agent_id,memory_type,visibility_scope,purpose,classification,content,content_sha256,source_ref,provenance,confidence,version,policy_version,status,retention_expires_at,approved_at,created_at,updated_at",
           "owner_user_id":f"eq.{owner_id}","agent_id":f"eq.{agent_id}" if agent_id else "is.null","order":"created_at.desc","limit":str(max(1,min(limit,100)))}
        if memory_type:p["memory_type"]=f"eq.{memory_type}"
        if status:p["status"]=f"eq.{status}"
        rows=await self.db("GET","agent_memory_items",params=p)
        return rows if isinstance(rows,list) else []

    async def events(self,owner_id,agent_id,limit=100):
        p={"select":"id,agent_id,policy_id,item_id,actor_user_id,event_type,details,created_at","owner_user_id":f"eq.{owner_id}",
           "agent_id":f"eq.{agent_id}" if agent_id else "is.null","order":"created_at.desc","limit":str(max(1,min(limit,200)))}
        rows=await self.db("GET","agent_memory_events",params=p)
        return rows if isinstance(rows,list) else []

    async def propose(self,owner_id,agent_id,memory_type,purpose,classification,content,source_ref,provenance,confidence,retention_days):
        if os.getenv("ALLPHA_MEMORY_COORDINATOR_ENABLED","false").lower()!="true": raise MemoryUnavailable("Memory proposal writes are not activated")
        if memory_type not in MEMORY_TYPES or purpose not in PURPOSES or classification not in SENSITIVITIES or not content.strip() or len(content)>8000:
            raise MemoryDenied("Memory proposal contract is invalid")
        if len(str(source_ref).encode())>4096 or len(str(provenance).encode())>4096 or (confidence is not None and not 0<=confidence<=1):
            raise MemoryDenied("Memory provenance or confidence is invalid")
        if agent_id:
            owned=await self.db("GET","agent_ownerships",params={"select":"agent_id","owner_user_id":f"eq.{owner_id}","agent_id":f"eq.{agent_id}","status":"eq.active","limit":"1"})
            if not owned: raise MemoryDenied("Agent ownership is no longer active")
        policy=next((p for p in await self.policies(owner_id,agent_id) if p["memory_type"]==memory_type),None)
        if not policy or not policy["enabled"] or policy.get("consent_version")!=CONSENT_VERSION or policy.get("consent_revoked_at"):
            raise MemoryDenied("Memory is disabled until the owner explicitly consents")
        if purpose not in policy["allowed_purposes"] or classification not in policy["allowed_sensitivities"]:
            raise MemoryDenied("Memory purpose or classification is outside the owner policy")
        ttl=int(retention_days or policy["retention_days"])
        if ttl<1 or ttl>int(policy["retention_days"]) or (memory_type=="working" and ttl!=1):
            raise MemoryDenied("Memory retention exceeds the owner policy")
        digest=hashlib.sha256(content.encode()).hexdigest()
        expires=(datetime.now(timezone.utc)+timedelta(days=ttl)).isoformat()
        row=await self.transition("create_proposal",owner_id,agent_id,payload={
            "policy_id":policy["id"],"memory_type":memory_type,"purpose":purpose,"classification":classification,
            "content":content,"content_sha256":digest,"source_ref":source_ref,"provenance":provenance,
            "confidence":confidence,"retention_expires_at":expires})
        if not isinstance(row,dict) or not row.get("id"): raise MemoryUnavailable("Memory proposal was not created")
        return row

    async def decide(self,owner_id,item_id,decision):
        if decision not in ("approve","reject"): raise MemoryDenied("Decision must be approve or reject")
        if decision=="approve" and os.getenv("ALLPHA_MEMORY_COORDINATOR_ENABLED","false").lower()!="true":
            raise MemoryUnavailable("Memory activation is disabled")
        result=await self.transition("decide",owner_id,item_id=item_id,payload={"decision":decision})
        return result if isinstance(result,dict) else None

    async def correct(self,owner_id,item_id,content):
        if not content.strip() or len(content)>8000: raise MemoryDenied("Corrected Memory content is invalid")
        result=await self.transition("correct",owner_id,item_id=item_id,payload={
            "content":content,"content_sha256":hashlib.sha256(content.encode()).hexdigest()})
        return result if isinstance(result,dict) else None

    async def delete(self,owner_id,item_id):
        result=await self.transition("delete",owner_id,item_id=item_id)
        return result if isinstance(result,dict) else None

    async def retrieve_context(self,owner_id,agent_id,purpose="agent_generation_context",limit=12,max_chars=6000,query=None,max_sensitivity=None):
        if os.getenv("ALLPHA_MEMORY_COORDINATOR_ENABLED","false").lower()!="true":return []
        if purpose not in PURPOSES:return []
        ownership=await self.db("GET","agent_ownerships",params={"select":"agent_id","owner_user_id":f"eq.{owner_id}","agent_id":f"eq.{agent_id}","status":"eq.active","limit":"1"})
        if not ownership:return []
        policies=await self.policies(owner_id,agent_id)
        enabled=[p for p in policies if p["enabled"] and not p.get("consent_revoked_at") and purpose in (p.get("allowed_purposes") or [])]
        if not enabled:return []
        await self.expire(owner_id,agent_id)
        policy_ids=[p["id"] for p in enabled]; versions={p["id"]:p["policy_version"] for p in enabled}; sensitivities={p["id"]:set(p.get("allowed_sensitivities") or []) for p in enabled}
        p={"select":"id,memory_type,content,classification,source_ref,provenance,confidence,version,content_sha256,policy_id,policy_version,created_at",
           "owner_user_id":f"eq.{owner_id}","agent_id":f"eq.{agent_id}","policy_id":f"in.({','.join(policy_ids)})",
           "purpose":f"eq.{purpose}","status":"eq.active","retention_expires_at":f"gt.{datetime.now(timezone.utc).isoformat()}",
           "classification":f"in.({','.join(sorted(set().union(*(s for s in sensitivities.values()))))})",
           "order":"created_at.desc","limit":"30"}
        if query:p["search_vector"]="fts.simple."+query
        rows=await self.db("GET","agent_memory_items",params=p)
        if max_sensitivity is not None and max_sensitivity not in SENSITIVITIES:return []
        sensitivity_rank={name:index for index,name in enumerate(SENSITIVITIES)}
        out=[]; used=0
        for row in rows or []:
            if len(out)>=max(1,min(limit,30)):break
            if row["policy_version"]!=versions.get(row["policy_id"]) or row.get("classification") not in sensitivities.get(row["policy_id"],set()):continue
            if max_sensitivity is not None and sensitivity_rank.get(row.get("classification"),99)>sensitivity_rank[max_sensitivity]:continue
            content=str(row["content"]); remaining=max_chars-used
            if remaining<=0:break
            content=content[:remaining]; used+=len(content)
            out.append({**row,"content":content,"retrieval_method":"keyword" if query else "metadata"})
        return out

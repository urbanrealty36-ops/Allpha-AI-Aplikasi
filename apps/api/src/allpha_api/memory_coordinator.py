"""Single canonical persistence and retrieval boundary for owner-private Agent Memory."""
from __future__ import annotations
import hashlib, os, re
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
        if memory_type not in MEMORY_TYPES or not 1<=retention_days<=3650:
            raise MemoryDenied("Memory type or retention is invalid")
        normalized_purposes=sorted(set(purposes)) if enabled else []
        normalized_sensitivities=sorted(set(sensitivities)) if enabled else []
        if enabled:
            if consent_version!=CONSENT_VERSION:
                raise MemoryDenied("Explicit current Memory consent is required")
            if not normalized_purposes or any(x not in PURPOSES for x in normalized_purposes):
                raise MemoryDenied("Memory purposes are invalid")
            if not normalized_sensitivities or any(x not in SENSITIVITIES for x in normalized_sensitivities):
                raise MemoryDenied("Memory classifications are invalid")
            if memory_type=="working" and retention_days!=1:
                raise MemoryDenied("Working Memory is limited to one day")
        result=await self.transition("set_policy",owner_id,agent_id,payload={
            "memory_type":memory_type,"enabled":bool(enabled),
            "consent_version":consent_version if enabled else None,
            "allowed_purposes":normalized_purposes,
            "allowed_sensitivities":normalized_sensitivities,
            "retention_days":retention_days})
        if not isinstance(result,dict) or not result.get("id"):
            raise MemoryUnavailable("Memory policy was not persisted")
        return result

    async def event(self,owner_id,agent_id,policy_id,item_id,event_type,details):
        # Lifecycle item events are written atomically by agent_memory_transition.
        return None

    async def expire(self,owner_id,agent_id):
        return await self.transition("expire",owner_id,agent_id)

    async def expire_all(self):
        if os.getenv("ALLPHA_MEMORY_COORDINATOR_ENABLED","false").lower()!="true":return {"expired_count":0}
        return await self.transition("expire_all",None)

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
            owned=await self.db("GET","agent_ownerships",params={"select":"agent_id","owner_user_id":f"eq.{owner_id}","agent_id":f"eq.{agent_id}","ownership_role":"eq.owner","status":"eq.active","limit":"1"})
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

    async def propose_explicit_intent(self,owner_id,agent_id,text,*,purpose="agent_runtime_context",source_ref=None):
        """Create a pending proposal only when the owner explicitly asks to remember content."""
        if os.getenv("ALLPHA_MEMORY_COORDINATOR_ENABLED","false").lower()!="true":
            return None
        if agent_id:
            owned = await self.db("GET","agent_ownerships",params={
                "select":"agent_id","owner_user_id":f"eq.{owner_id}",
                "agent_id":f"eq.{agent_id}","ownership_role":"eq.owner","status":"eq.active","limit":"1",
            })
            if not owned:
                raise MemoryDenied("Agent ownership is no longer active")
        if purpose not in {"agent_runtime_context","agent_generation_context"}:
            return None
        source=str(text or "").strip()
        if not source or len(source)>8000:
            return None
        lowered=source.lower()
        if re.search(r"\b(?:do not|don't|never|jangan)\s+(?:remember|ingat)\b",lowered):
            return None
        patterns=(
            r"\b(?:please\s+)?(?:remember(?:\s+that)?|keep\s+in\s+mind(?:\s+that)?|save\s+this(?:\s+as)?|note\s+that)\s+(.+)$",
            r"\b(?:tolong\s+)?(?:ingat(?:lah)?(?:\s+bahwa)?|simpan(?:lah)?(?:\s+bahwa)?|catat(?:lah)?(?:\s+bahwa)?)\s+(.+)$",
        )
        match=next((re.search(pattern,source,re.IGNORECASE|re.DOTALL) for pattern in patterns
                    if re.search(pattern,source,re.IGNORECASE|re.DOTALL)),None)
        if not match:
            return None
        content=match.group(1).strip()
        if not content or len(content)>8000:
            return None
        policy=next((p for p in await self.policies(owner_id,agent_id)
                     if p.get("memory_type")=="long_term"),None)
        if (not policy or not policy.get("enabled")
                or policy.get("consent_version")!=CONSENT_VERSION
                or policy.get("consent_revoked_at")
                or purpose not in (policy.get("allowed_purposes") or [])):
            return None
        allowed=set(policy.get("allowed_sensitivities") or [])
        classification=next((level for level in reversed(SENSITIVITIES) if level in allowed),None)
        if classification is None:
            return None
        source_digest=hashlib.sha256(source.encode()).hexdigest()
        resolved_source_ref = source_ref or {"kind":"owner_explicit_memory_intent"}
        generation_job_id = resolved_source_ref.get("generation_job_id") if isinstance(resolved_source_ref,dict) else None

        async def existing_source_proposal():
            if not isinstance(generation_job_id,str) or not generation_job_id:
                return None
            rows = await self.db("GET","agent_memory_items",params={
                "select":"id,status,memory_type,purpose,classification,policy_version,retention_expires_at",
                "owner_user_id":f"eq.{owner_id}",
                "agent_id":f"eq.{agent_id}" if agent_id else "is.null",
                "source_ref->>generation_job_id":f"eq.{generation_job_id}",
                "limit":"1",
            })
            return rows[0] if rows else None

        existing = await existing_source_proposal()
        if existing:
            return existing
        try:
            return await self.propose(
                owner_id,agent_id,"long_term",purpose,classification,content,
                resolved_source_ref,
                {"created_by":"owner","capture_mode":"explicit_intent",
                 "source_text_sha256":source_digest},
                1.0,int(policy.get("retention_days") or 365),
            )
        except MemoryDenied:
            # A concurrent worker may have won the unique source-key insert.
            existing = await existing_source_proposal()
            if existing:
                return existing
            raise

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

    async def pin(self,owner_id,item_id,pinned):
        result=await self.transition("pin",owner_id,item_id=item_id,payload={"pinned":bool(pinned)})
        return result if isinstance(result,dict) else None

    async def expire_item(self,owner_id,item_id):
        result=await self.transition("expire_item",owner_id,item_id=item_id)
        return result if isinstance(result,dict) else None

    async def retrieve_context(self,owner_id,agent_id,purpose="agent_generation_context",limit=12,max_chars=6000,query=None,max_sensitivity=None):
        if os.getenv("ALLPHA_MEMORY_COORDINATOR_ENABLED","false").lower()!="true":return []
        if purpose not in PURPOSES:return []
        # The owner-only API uses "private" as a caller classification; policy
        # allowed_sensitivities remains the authoritative item-level ceiling.
        if max_sensitivity=="private":max_sensitivity=None
        if max_sensitivity is not None and max_sensitivity not in SENSITIVITIES:return []
        if not isinstance(max_chars,int) or isinstance(max_chars,bool) or max_chars<1:return []
        max_chars=min(max_chars,12000)
        ownership=await self.db("GET","agent_ownerships",params={"select":"agent_id","owner_user_id":f"eq.{owner_id}","agent_id":f"eq.{agent_id}","ownership_role":"eq.owner","status":"eq.active","limit":"1"})
        if not ownership:return []
        policies=await self.policies(owner_id,agent_id)
        enabled=[p for p in policies if p["enabled"] and not p.get("consent_revoked_at")
                 and p.get("consent_version")==CONSENT_VERSION and purpose in (p.get("allowed_purposes") or [])]
        if not enabled:return []
        await self.expire(owner_id,agent_id)
        policy_ids=[p["id"] for p in enabled]
        versions={p["id"]:p["policy_version"] for p in enabled}
        sensitivities={p["id"]:set(p.get("allowed_sensitivities") or []) for p in enabled}
        allowed_sensitivities=sorted(set().union(*sensitivities.values()))
        if not allowed_sensitivities:return []
        normalized_query=str(query).strip()[:300] if query is not None else None
        if normalized_query=="":normalized_query=None
        rows=await self.db("POST","rpc/agent_memory_search",body={
            "p_owner_user_id":owner_id,
            "p_agent_id":agent_id,
            "p_policy_ids":policy_ids,
            "p_purpose":purpose,
            "p_allowed_sensitivities":allowed_sensitivities,
            "p_query":normalized_query,
            "p_max_sensitivity":max_sensitivity,
            "p_limit":max(1,min(limit,30)),
        })
        if not isinstance(rows,list):
            raise MemoryUnavailable("Memory retrieval RPC returned an invalid result")
        sensitivity_rank={name:index for index,name in enumerate(SENSITIVITIES)}
        out=[]; used=0
        for row in rows:
            policy_id=row.get("policy_id")
            classification=row.get("classification")
            if policy_id not in versions or row.get("policy_version")!=versions.get(policy_id):
                raise MemoryDenied("Memory policy changed during retrieval")
            if classification not in sensitivities.get(policy_id,set()):
                raise MemoryDenied("Memory classification is outside the current owner policy")
            if max_sensitivity is not None and sensitivity_rank.get(classification,99)>sensitivity_rank[max_sensitivity]:
                raise MemoryDenied("Memory retrieval exceeded the requested sensitivity ceiling")
            content=str(row.get("content") or "")
            digest=hashlib.sha256(content.encode()).hexdigest()
            if not content or digest!=row.get("content_sha256"):
                raise MemoryUnavailable("Memory content digest verification failed")
            remaining=max_chars-used
            if remaining<=0:break
            bounded=content[:remaining]
            retrieved_digest=hashlib.sha256(bounded.encode()).hexdigest()
            used+=len(bounded)
            score=row.get("retrieval_score",0)
            try:score=float(score or 0)
            except (TypeError,ValueError):raise MemoryUnavailable("Memory retrieval score is invalid")
            if not (score==score and abs(score)!=float("inf")):
                raise MemoryUnavailable("Memory retrieval score is not finite")
            out.append({**row,"content":bounded,"retrieved_content_sha256":retrieved_digest,
                        "retrieval_method":"keyword" if normalized_query else "metadata",
                        "retrieval_score":score})
            if used>=max_chars:break
        return out

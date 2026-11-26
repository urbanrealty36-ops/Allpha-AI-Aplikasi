"""Auditable retention executor. Destructive execution is disabled until explicitly approved."""
from __future__ import annotations
import asyncio, logging, os, signal, uuid
from datetime import datetime, timezone
from typing import Any
import httpx
log=logging.getLogger("allpha.content_retention_worker")

class RetentionWorker:
 def __init__(self):
  self.base=os.environ["SUPABASE_URL"].rstrip("/")
  self.key=os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ["SUPABASE_SECRET_KEY"]
  self.worker_id=f"content-retention-{uuid.uuid4()}"
  self.client=httpx.AsyncClient(trust_env=False, follow_redirects=False, timeout=httpx.Timeout(60,connect=5),headers={"apikey":self.key,"Authorization":f"Bearer {self.key}","Content-Type":"application/json"})
  self.enabled = all(
   os.getenv(name, "false").strip().lower() in ("1", "true", "yes")
   for name in (
    "CONTENT_RETENTION_PURGE_ENABLED",
    "CONTENT_RETENTION_BACKUP_VERIFIED",
    "CONTENT_RETENTION_RESTORE_DRILL_VERIFIED",
    "CONTENT_RETENTION_LEGAL_HOLD_VERIFIED",
    "CONTENT_RETENTION_APPROVAL_VERIFIED",
   )
  )
  self.stopping=False
 async def rpc(self,name,payload):
  r=await self.client.post(f"{self.base}/rest/v1/rpc/{name}",json=payload);r.raise_for_status();return r.json() if r.content else None
 async def db(self,method,path,params=None,body=None,prefer=None):
  h={"apikey":self.key,"Authorization":f"Bearer {self.key}","Content-Type":"application/json"}
  if prefer:h["Prefer"]=prefer
  r=await self.client.request(method,f"{self.base}/rest/v1/{path}",params=params,json=body,headers=h);r.raise_for_status();return r.json() if r.content else None
 async def _delete_confirmed_media_metadata(self,item):
  media_id=str(item["id"]);owner_id=str(item["owner_id"])
  rows=await self.db("DELETE","content_media",{
   "id":f"eq.{media_id}","owner_id":f"eq.{owner_id}",
   "status":"eq.deleted","provider_delete_state":"eq.deleted",
  },prefer="return=representation")
  if rows:
   return True
  remaining=await self.db("GET","content_media",{
   "select":"id","id":f"eq.{media_id}","owner_id":f"eq.{owner_id}","limit":"1",
  })
  return not bool(remaining)

 async def _request_provider_cleanup(self,item):
  media_id=str(item["id"]);owner_id=str(item["owner_id"])
  if item.get("status")=="deleted" and item.get("provider_delete_state")=="deleted" and item.get("provider_deleted_at"):
   return "deleted" if await self._delete_confirmed_media_metadata(item) else "pending"
  result=await self.rpc("request_cloudinary_content_media_delete",{
   "p_media_id":media_id,"p_owner_id":owner_id,
  })
  outcome=result.get("outcome") if isinstance(result,dict) else None
  if outcome in ("queued","already_queued"):
   return "pending"
  if outcome=="already_deleted":
   current=await self.db("GET","content_media",{
    "select":"id,owner_id,status,provider_delete_state,provider_deleted_at",
    "id":f"eq.{media_id}","owner_id":f"eq.{owner_id}","limit":"1",
   })
   if current and current[0].get("status")=="deleted" and current[0].get("provider_delete_state")=="deleted" and current[0].get("provider_deleted_at"):
    return "deleted" if await self._delete_confirmed_media_metadata(current[0]) else "pending"
   return "pending"
  if outcome=="media_not_found":
   return "deleted"
  return "pending"

 async def _cleanup_media_rows(self,job,media_rows):
  deleted_objects=[];deleted_rows=[];pending=False
  for item in media_rows or []:
   outcome=await self._request_provider_cleanup(item)
   if outcome=="pending":
    pending=True
    continue
   if outcome=="deleted":
    deleted_rows.append(str(item["id"]))
    provider=str(item.get("storage_provider") or "supabase")
    if provider=="cloudinary" and item.get("provider_public_id"):
     deleted_objects.append("cloudinary:"+str(item["provider_public_id"]))
    elif item.get("bucket_id") and item.get("storage_path"):
     deleted_objects.append("supabase_storage:"+str(item["bucket_id"])+"/"+str(item["storage_path"]))
    for derivative in item.get("derivatives") or []:
     path=derivative.get("storage_path") if isinstance(derivative,dict) else None
     if path:
      deleted_objects.append("supabase_storage:"+str(item.get("bucket_id") or "content-media")+"/"+str(path))
  if pending:
   await self.rpc("defer_content_retention_job",{
    "p_job_id":str(job["id"]),"p_lease_token":str(job["lease_token"]),
    "p_reason":"provider_media_cleanup_pending",
   })
   return False,[],[]
  return True,deleted_objects,deleted_rows

 async def process(self,job):
  jid=str(job["id"]);token=str(job["lease_token"]);payload=job.get("payload") or {}
  try:
   authorization=await self.rpc("begin_content_retention_purge",{"p_job_id":jid,"p_lease_token":token})
   if not isinstance(authorization,dict) or authorization.get("outcome")!="authorized":
    await self.rpc("defer_content_retention_job",{"p_job_id":jid,"p_lease_token":token,"p_reason":(authorization or {}).get("outcome","retention_not_authorized")})
    return
   if payload.get("scope")=="content":
    cid=str(payload["content_id"])
    media=await self.db("GET","content_media",{
     "select":"id,owner_id,status,storage_provider,provider_public_id,provider_delete_state,provider_deleted_at,bucket_id,storage_path,derivatives",
     "content_id":f"eq.{cid}","limit":"200",
    })
    complete,deleted,deleted_rows=await self._cleanup_media_rows(job,media)
    if not complete:
     return
    remaining=await self.db("GET","content_media",{"select":"id","content_id":f"eq.{cid}","limit":"1"})
    if remaining:
     await self.rpc("defer_content_retention_job",{"p_job_id":jid,"p_lease_token":token,"p_reason":"provider_media_registry_not_empty"})
     return
    await self.db("DELETE","content_items",{"id":f"eq.{cid}","status":"eq.deleted","purge_started_at":"not.is.null"})
    content_id=cid
    owner_id=job.get("owner_id")
   elif payload.get("scope")=="abandoned_upload":
    mid=str(payload["media_id"])
    rows=await self.db("GET","content_media",{
     "select":"id,owner_id,content_id,status,storage_provider,provider_public_id,provider_delete_state,provider_deleted_at,bucket_id,storage_path,derivatives",
     "id":f"eq.{mid}","status":"in.(uploading,failed,deleting,deleted)","limit":"1",
    })
    if rows:
     item=rows[0]
     complete,deleted,deleted_rows=await self._cleanup_media_rows(job,rows)
     if not complete:
      return
     remaining=await self.db("GET","content_media",{"select":"id","id":f"eq.{mid}","limit":"1"})
     if remaining:
      await self.rpc("defer_content_retention_job",{"p_job_id":jid,"p_lease_token":token,"p_reason":"provider_media_registry_not_empty"})
      return
     content_id=item.get("content_id") or job.get("content_id")
     owner_id=item.get("owner_id") or job.get("owner_id")
    else:
     deleted=[];deleted_rows=[];content_id=job.get("content_id");owner_id=job.get("owner_id")
   else:raise ValueError("RETENTION_SCOPE_INVALID")
   await self.db("POST","content_retention_receipts",body={
    "job_id":jid,"content_id":content_id,"owner_id":owner_id,"dry_run":False,
    "deleted_objects":deleted,"deleted_rows":deleted_rows,
    "backup_expiry_policy":"provider_managed_expiry_not_verified",
   },prefer="resolution=ignore-duplicates,return=minimal")
   completion=await self.rpc("complete_content_retention_job",{"p_job_id":jid,"p_lease_token":token})
   if completion!="succeeded":raise ValueError("RETENTION_COMPLETION_LEASE_LOST")
  except Exception as exc:
   log.exception("retention job failed job=%s",jid)
   try:await self.rpc("fail_content_lifecycle_job",{"p_job_id":jid,"p_lease_token":token,"p_error_code":type(exc).__name__[:80]})
   except Exception:log.exception("retention failure could not be persisted job=%s",jid)
 async def batch(self):
  if not self.enabled:
   return 0
  readiness=await self.rpc("cloudinary_media_schema_readiness",{})
  if not isinstance(readiness,dict) or readiness.get("ready") is not True:
   raise RuntimeError("CONTENT_RETENTION_MEDIA_SCHEMA_NOT_READY")
  await self.rpc("enqueue_expired_content_retention_jobs",{"p_limit":100})
  jobs=await self.rpc("claim_content_lifecycle_jobs",{"p_worker_id":self.worker_id,"p_limit":1,"p_lease_seconds":300,"p_job_type":"retention_purge"}) or []
  for job in jobs:await self.process(job)
  return len(jobs)
 async def run(self):
  try:
   while not self.stopping:
    try:n=await self.batch()
    except Exception:log.exception("retention worker poll failed");n=0
    if n==0:await asyncio.sleep(max(30,int(os.getenv("CONTENT_RETENTION_POLL_SECONDS","300"))))
  finally:await self.client.aclose()
def enabled():
 raw=os.getenv("ALLPHA_CONTENT_RETENTION_WORKER_ENABLED","false").strip().lower()
 if raw not in {"true","false"}:raise SystemExit("ALLPHA_CONTENT_RETENTION_WORKER_ENABLED must be true or false")
 if raw!="true":return False
 missing=[name for name in ("SUPABASE_URL",) if not os.getenv(name)]
 if not (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SECRET_KEY")):missing.append("SUPABASE_SERVICE_ROLE_KEY or SUPABASE_SECRET_KEY")
 if missing:raise SystemExit("Content retention worker configuration missing: "+", ".join(missing))
 return True
def main():
 logging.basicConfig(level=os.getenv("LOG_LEVEL","INFO"))
 if not enabled():
  log.info("Content retention worker is disabled")
  return
 worker=RetentionWorker();loop=asyncio.new_event_loop();asyncio.set_event_loop(loop)
 for sig in (signal.SIGINT,signal.SIGTERM):loop.add_signal_handler(sig,lambda:setattr(worker,"stopping",True))
 try:loop.run_until_complete(worker.run())
 finally:loop.close()
if __name__=="__main__":main()

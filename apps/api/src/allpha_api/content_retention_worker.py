"""Auditable, idempotent retention executor. Destructive jobs are never run in dry-run mode."""
from __future__ import annotations
import asyncio, logging, os, signal, uuid\nfrom datetime import datetime, timezone
from typing import Any
from urllib.parse import quote
import httpx
log=logging.getLogger("allpha.content_retention_worker")

class RetentionWorker:
 def __init__(self):
  self.base=os.environ["SUPABASE_URL"].rstrip("/")
  self.key=os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ["SUPABASE_SECRET_KEY"]
  self.worker_id=f"content-retention-{uuid.uuid4()}"
  self.client=httpx.AsyncClient(timeout=httpx.Timeout(60,connect=5),headers={"apikey":self.key,"Authorization":f"Bearer {self.key}","Content-Type":"application/json"})
  self.stopping=False
 async def rpc(self,name,payload):
  r=await self.client.post(f"{self.base}/rest/v1/rpc/{name}",json=payload);r.raise_for_status();return r.json() if r.content else None
 async def db(self,method,path,params=None,body=None,prefer=None):
  h={"apikey":self.key,"Authorization":f"Bearer {self.key}","Content-Type":"application/json"}
  if prefer:h["Prefer"]=prefer
  r=await self.client.request(method,f"{self.base}/rest/v1/{path}",params=params,json=body,headers=h);r.raise_for_status();return r.json() if r.content else None
 async def remove_object(self,bucket,path):
  url=f"{self.base}/storage/v1/object/{quote(bucket,safe='')}/{quote(path,safe='/')}"
  response=await self.client.delete(url)
  if response.status_code not in (200,204,404):response.raise_for_status()
 async def process(self,job):
  jid=str(job["id"]);token=str(job["lease_token"]);payload=job.get("payload") or {}
  try:
   authorization=await self.rpc("begin_content_retention_purge",{"p_job_id":jid,"p_lease_token":token})
   if not isinstance(authorization,dict) or authorization.get("outcome")!="authorized":
    await self.rpc("defer_content_retention_job",{"p_job_id":jid,"p_lease_token":token,"p_reason":(authorization or {}).get("outcome","retention_not_authorized")})
    return
   deleted=[];deleted_rows=[]
   if payload.get("scope")=="content":
    cid=str(payload["content_id"])
    media=await self.db("GET","content_media",{"select":"id,bucket_id,storage_path,derivatives","content_id":f"eq.{cid}","limit":"200"})
    for item in media or []:
     await self.remove_object(item["bucket_id"],item["storage_path"]);deleted.append(item["storage_path"])
     for derivative in item.get("derivatives") or []:
      path=derivative.get("storage_path")
      if path:
       await self.remove_object(item["bucket_id"],path);deleted.append(path)
     deleted_rows.append(str(item["id"]))
    await self.db("DELETE","content_media",{"content_id":f"eq.{cid}"})
    await self.db("DELETE","content_items",{"id":f"eq.{cid}","status":"eq.deleted","purge_started_at":"not.is.null"})
    content_id=cid
    owner_id=job.get("owner_id")
   elif payload.get("scope")=="abandoned_upload":
    mid=str(payload["media_id"])
    rows=await self.db("GET","content_media",{"select":"id,bucket_id,storage_path,derivatives,content_id,owner_id","id":f"eq.{mid}","status":"in.(uploading,failed)","limit":"1"})
    if rows:
     item=rows[0];await self.remove_object(item["bucket_id"],item["storage_path"]);deleted.append(item["storage_path"])
     for derivative in item.get("derivatives") or []:
      path=derivative.get("storage_path")
      if path:await self.remove_object(item["bucket_id"],path);deleted.append(path)
     await self.db("DELETE","content_media",{"id":f"eq.{mid}","status":"in.(uploading,failed)"})
     deleted_rows.append(mid);content_id=item["content_id"];owner_id=item["owner_id"]
    else:content_id=job.get("content_id");owner_id=job.get("owner_id")
   else:raise ValueError("RETENTION_SCOPE_INVALID")
   await self.db("POST","content_retention_receipts",body={
    "job_id":jid,"content_id":content_id,"owner_id":owner_id,"dry_run":False,
    "deleted_objects":deleted,"deleted_rows":deleted_rows,
    "backup_expiry_policy":"provider_managed_expiry_not_verified",
   },prefer="resolution=ignore-duplicates,return=minimal")
   await self.db("PATCH","content_lifecycle_jobs",{"id":f"eq.{jid}","status":"eq.processing","lease_token":f"eq.{token}"},{
    "status":"succeeded","lease_token":None,"lease_expires_at":None,"completed_at":datetime.now(timezone.utc).isoformat()
   })
   await self.rpc("release_content_retention_purge_lock",{"p_job_id":jid})
  except Exception as exc:
   log.exception("retention job failed job=%s",jid)
   try:await self.rpc("fail_content_lifecycle_job",{"p_job_id":jid,"p_lease_token":token,"p_error_code":type(exc).__name__[:80]})
   except Exception:log.exception("retention failure could not be persisted job=%s",jid)
 async def batch(self):
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
def main():
 logging.basicConfig(level=os.getenv("LOG_LEVEL","INFO"))
 worker=RetentionWorker();loop=asyncio.new_event_loop();asyncio.set_event_loop(loop)
 for sig in (signal.SIGINT,signal.SIGTERM):loop.add_signal_handler(sig,lambda:setattr(worker,"stopping",True))
 try:loop.run_until_complete(worker.run())
 finally:loop.close()
if __name__=="__main__":main()

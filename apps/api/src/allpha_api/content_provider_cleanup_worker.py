"""Deletes authenticated Cloudinary intermediates after canonical derivatives are persisted in private Supabase Storage."""
from __future__ import annotations
import asyncio,hashlib,logging,os,signal,time,uuid
import httpx
log=logging.getLogger("allpha.cloudinary_cleanup")

class CleanupWorker:
 def __init__(self):
  self.base=os.environ["SUPABASE_URL"].rstrip("/")
  self.key=os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ["SUPABASE_SECRET_KEY"]
  self.cloud=os.environ["CLOUDINARY_CLOUD_NAME"];self.api_key=os.environ["CLOUDINARY_API_KEY"];self.secret=os.environ["CLOUDINARY_API_SECRET"]
  self.worker_id=f"cloudinary-cleanup-{uuid.uuid4()}"
  self.client=httpx.AsyncClient(timeout=httpx.Timeout(30,connect=5),headers={"apikey":self.key,"Authorization":f"Bearer {self.key}","Content-Type":"application/json"})
  self.stopping=False
 async def rpc(self,name,payload):
  r=await self.client.post(f"{self.base}/rest/v1/rpc/{name}",json=payload);r.raise_for_status();return r.json() if r.content else None
 async def delete_asset(self,public_id):
  timestamp=int(time.time())
  params={"invalidate":"true","public_id":public_id,"timestamp":str(timestamp),"type":"authenticated"}
  serialized="&".join(f"{k}={params[k]}" for k in sorted(params))
  signature=hashlib.sha1((serialized+self.secret).encode()).hexdigest()
  form={**params,"api_key":self.api_key,"signature":signature}
  async with httpx.AsyncClient(timeout=httpx.Timeout(30,connect=5)) as provider:
   response=await provider.post(f"https://api.cloudinary.com/v1_1/{self.cloud}/video/destroy",data=form)
  response.raise_for_status();result=response.json().get("result")
  if result not in ("ok","not found"):raise ValueError("CLOUDINARY_DESTROY_UNCONFIRMED")
 async def batch(self):
  jobs=await self.rpc("claim_content_lifecycle_jobs",{"p_worker_id":self.worker_id,"p_limit":5,"p_lease_seconds":120,"p_job_type":"provider_cleanup"}) or []
  for job in jobs:
   try:
    payload=job.get("payload") or {}
    if payload.get("provider")!="cloudinary" or payload.get("resource_type")!="video":raise ValueError("PROVIDER_CLEANUP_PAYLOAD_INVALID")
    await self.delete_asset(str(payload["provider_public_id"]))
    response=await self.client.patch(f"{self.base}/rest/v1/content_lifecycle_jobs",
     params={"id":f"eq.{job['id']}","status":"eq.processing","lease_token":f"eq.{job['lease_token']}"},
     json={"status":"succeeded","lease_token":None,"lease_expires_at":None,"completed_at":__import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()})
    response.raise_for_status()
   except Exception as exc:
    log.exception("provider cleanup failed job=%s",job["id"])
    try:await self.rpc("fail_content_lifecycle_job",{"p_job_id":job["id"],"p_lease_token":job["lease_token"],"p_error_code":type(exc).__name__[:80]})
    except Exception:log.exception("provider cleanup failure could not be recorded")
  return len(jobs)
 async def run(self):
  try:
   while not self.stopping:
    try:n=await self.batch()
    except Exception:log.exception("provider cleanup poll failed");n=0
    if n==0:await asyncio.sleep(15)
  finally:await self.client.aclose()
def main():
 logging.basicConfig(level=os.getenv("LOG_LEVEL","INFO"))
 worker=CleanupWorker();loop=asyncio.new_event_loop();asyncio.set_event_loop(loop)
 for sig in (signal.SIGINT,signal.SIGTERM):loop.add_signal_handler(sig,lambda:setattr(worker,"stopping",True))
 try:loop.run_until_complete(worker.run())
 finally:loop.close()
if __name__=="__main__":main()

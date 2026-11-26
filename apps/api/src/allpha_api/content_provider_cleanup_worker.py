"""Deletes authenticated Cloudinary assets only for an explicit, lease-fenced media deletion request."""
from __future__ import annotations
import asyncio,logging,os,signal,time,uuid
from urllib.parse import quote
import httpx
from allpha_api.cloudinary_provider import sign_api_params
log=logging.getLogger("allpha.cloudinary_cleanup")


def cloudinary_destroy_endpoint(cloud_name: str, resource_type: str) -> str:
 """Return the authenticated Cloudinary destroy endpoint for a validated resource."""
 if resource_type not in {"image", "video", "raw"}:
  raise ValueError("PROVIDER_CLEANUP_RESOURCE_TYPE_INVALID")
 if not cloud_name or any(char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for char in cloud_name):
  raise ValueError("PROVIDER_CLEANUP_CLOUD_INVALID")
 return f"https://api.cloudinary.com/v1_1/{cloud_name}/{resource_type}/destroy"

class CleanupWorker:
 def __init__(self):
  self.base=os.environ["SUPABASE_URL"].rstrip("/")
  self.key=os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ["SUPABASE_SECRET_KEY"]
  self.cloud=os.environ["CLOUDINARY_CLOUD_NAME"];self.api_key=os.environ["CLOUDINARY_API_KEY"];self.secret=os.environ["CLOUDINARY_API_SECRET"]
  self.worker_id=f"cloudinary-cleanup-{uuid.uuid4()}"
  self.client=httpx.AsyncClient(trust_env=False, follow_redirects=False, timeout=httpx.Timeout(30,connect=5),headers={"apikey":self.key,"Authorization":f"Bearer {self.key}","Content-Type":"application/json"})
  self.stopping=False
 async def rpc(self,name,payload):
  r=await self.client.post(f"{self.base}/rest/v1/rpc/{name}",json=payload);r.raise_for_status();return r.json() if r.content else None
 async def delete_asset(self,public_id,resource_type):
  endpoint=cloudinary_destroy_endpoint(self.cloud,resource_type)
  if not isinstance(public_id,str) or not public_id.startswith("allpha/"):
   raise ValueError("PROVIDER_CLEANUP_PUBLIC_ID_INVALID")
  timestamp=int(time.time())
  params={"invalidate":"true","public_id":public_id,"timestamp":str(timestamp),"type":"authenticated"}
  signature=sign_api_params(params,self.secret)
  form={**params,"api_key":self.api_key,"signature":signature}
  async with httpx.AsyncClient(trust_env=False, follow_redirects=False, timeout=httpx.Timeout(30,connect=5)) as provider:
   response=await provider.post(endpoint,data=form)
  response.raise_for_status();result=response.json().get("result")
  if result not in ("ok","not found"):raise ValueError("CLOUDINARY_DESTROY_UNCONFIRMED")
 async def delete_legacy_storage_object(self,legacy_storage,owner_id=None):
  if not isinstance(legacy_storage,dict):raise ValueError("LEGACY_STORAGE_IDENTITY_INVALID")
  bucket=str(legacy_storage.get("bucket_id") or "")
  path=str(legacy_storage.get("storage_path") or "")
  parts=path.split("/") if path else []
  if bucket!="content-media" or not path or path.startswith("/") or ".." in parts or (owner_id and (not parts or parts[0]!=owner_id)):
   raise ValueError("LEGACY_STORAGE_IDENTITY_INVALID")
  url=f"{self.base}/storage/v1/object/{quote(bucket,safe='')}/{quote(path,safe='/')}"
  response=await self.client.delete(url)
  if response.status_code not in (200,204,404):
   response.raise_for_status()
   raise ValueError("LEGACY_STORAGE_DELETE_UNCONFIRMED")

 async def delete_legacy_derivative_objects(self,derivatives,owner_id):
  seen=set()
  for derivative in derivatives or []:
   if not isinstance(derivative,dict):continue
   path=derivative.get("storage_path")
   if not isinstance(path,str) or not path or path in seen:continue
   seen.add(path)
   await self.delete_legacy_storage_object({
    "bucket_id":derivative.get("bucket_id") or "content-media","storage_path":path,
   },owner_id=owner_id)

 async def batch(self):
  jobs=await self.rpc("claim_content_lifecycle_jobs",{"p_worker_id":self.worker_id,"p_limit":1,"p_lease_seconds":300,"p_job_type":"provider_cleanup"}) or []
  for job in jobs:
   try:
    payload=job.get("payload") or {}
    provider=str(payload.get("provider") or "")
    action=str(payload.get("action") or "")
    if provider=="cloudinary":
     resource_type=str(payload.get("resource_type") or "")
     if resource_type not in {"image","video","raw"}:raise ValueError("PROVIDER_CLEANUP_PAYLOAD_INVALID")
     await self.delete_asset(str(payload["provider_public_id"]),resource_type)
     if action=="delete_media" and payload.get("legacy_storage") is not None:
      await self.delete_legacy_storage_object(payload["legacy_storage"],owner_id=str(job.get("owner_id") or ""))
     if action=="delete_media":
      await self.delete_legacy_derivative_objects(payload.get("derivatives"),str(job.get("owner_id") or ""))
     if action=="delete_media":
      completion=await self.rpc("complete_cloudinary_media_delete_job",{
       "p_job_id":job["id"],"p_lease_token":job["lease_token"],"p_media_id":job["media_id"],
      })
     else:
      completion=await self.rpc("complete_content_provider_cleanup_job",{
       "p_job_id":job["id"],"p_lease_token":job["lease_token"],
      })
    elif provider=="supabase_storage" and action=="delete_media":
     await self.delete_legacy_storage_object({
      "bucket_id":payload.get("bucket_id"),"storage_path":payload.get("storage_path"),
     },owner_id=str(job.get("owner_id") or ""))
     await self.delete_legacy_derivative_objects(payload.get("derivatives"),str(job.get("owner_id") or ""))
     completion=await self.rpc("complete_legacy_content_media_delete_job",{
      "p_job_id":job["id"],"p_lease_token":job["lease_token"],"p_media_id":job["media_id"],
     })
    else:
     raise ValueError("PROVIDER_CLEANUP_PROVIDER_INVALID")
    if completion!="succeeded":raise ValueError("PROVIDER_CLEANUP_LEASE_LOST")
   except Exception as exc:
    log.exception("provider cleanup failed job=%s",job["id"])
    try:
     payload=job.get("payload") or {}
     failure_rpc="fail_cloudinary_media_delete_job" if payload.get("provider")=="cloudinary" and payload.get("action")=="delete_media" else "fail_content_lifecycle_job"
     await self.rpc(failure_rpc,{"p_job_id":job["id"],"p_lease_token":job["lease_token"],"p_error_code":type(exc).__name__[:80]})
    except Exception:log.exception("provider cleanup failure could not be recorded")
  return len(jobs)
 async def assert_schema_ready(self):
  result=await self.rpc("cloudinary_media_schema_readiness",{})
  if not isinstance(result,dict) or result.get("ready") is not True:
   raise RuntimeError("MEDIA_SCHEMA_NOT_READY")
 async def run(self):
  try:
   while not self.stopping:
    try:n=await self.batch()
    except Exception:log.exception("provider cleanup poll failed");n=0
    if n==0:await asyncio.sleep(15)
  finally:await self.client.aclose()
def enabled():
 raw=os.getenv("ALLPHA_CONTENT_PROVIDER_CLEANUP_WORKER_ENABLED","false").strip().lower()
 if raw not in {"true","false"}:raise SystemExit("ALLPHA_CONTENT_PROVIDER_CLEANUP_WORKER_ENABLED must be true or false")
 if raw!="true":return False
 missing=[name for name in ("SUPABASE_URL","CLOUDINARY_CLOUD_NAME","CLOUDINARY_API_KEY","CLOUDINARY_API_SECRET") if not os.getenv(name)]
 if not (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SECRET_KEY")):missing.append("SUPABASE_SERVICE_ROLE_KEY or SUPABASE_SECRET_KEY")
 if missing:raise SystemExit("Provider cleanup worker configuration missing: "+", ".join(missing))
 return True
def main():
 logging.basicConfig(level=os.getenv("LOG_LEVEL","INFO"))
 if not enabled():
  log.info("Provider cleanup worker is disabled")
  return
 worker=CleanupWorker();loop=asyncio.new_event_loop();asyncio.set_event_loop(loop)
 for sig in (signal.SIGINT,signal.SIGTERM):loop.add_signal_handler(sig,lambda:setattr(worker,"stopping",True))
 try:
  loop.run_until_complete(worker.assert_schema_ready())
  loop.run_until_complete(worker.run())
 finally:loop.close()
if __name__=="__main__":main()

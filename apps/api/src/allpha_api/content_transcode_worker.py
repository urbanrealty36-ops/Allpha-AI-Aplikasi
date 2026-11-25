"""Cloudinary video/audio transcode dispatcher. Provider callback owns readiness promotion."""
from __future__ import annotations
import asyncio, hashlib, logging, os, signal, time, uuid
from urllib.parse import quote
import httpx

from allpha_api.media_scanner import require_media_scanner_configuration, scan_media_bytes_async
from allpha_api.cloudinary_provider import CloudinaryConfig, build_signed_upload_intent

log=logging.getLogger("allpha.content_transcode_worker")

class TranscodeWorker:
 def __init__(self):
  self.base=os.environ["SUPABASE_URL"].rstrip("/")
  self.key=os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ["SUPABASE_SECRET_KEY"]
  self.cloudinary=CloudinaryConfig.from_environment(require_callback=True)
  self.cloud=self.cloudinary.cloud_name
  self.callback=self.cloudinary.callback_url
  self.scanner_mode=require_media_scanner_configuration()
  self.worker_id=f"content-transcode-{uuid.uuid4()}"
  self.client=httpx.AsyncClient(trust_env=False, follow_redirects=False, timeout=httpx.Timeout(180,connect=10),headers={"apikey":self.key,"Authorization":f"Bearer {self.key}"})
  self.stopping=False
 async def rpc(self,name,payload):
  r=await self.client.post(f"{self.base}/rest/v1/rpc/{name}",json=payload);r.raise_for_status();return r.json() if r.content else None
 async def db(self,method,path,params=None,body=None,prefer=None):
  h={"apikey":self.key,"Authorization":f"Bearer {self.key}","Content-Type":"application/json"}
  if prefer:h["Prefer"]=prefer
  r=await self.client.request(method,f"{self.base}/rest/v1/{path}",params=params,json=body,headers=h);r.raise_for_status();return r.json() if r.content else None
 async def scan(self,data,filename,media_type):
  return await scan_media_bytes_async(data,filename=filename,media_type=media_type)
 async def run_job(self,job):
  jid=str(job["id"]);token=str(job["lease_token"]);mid=str(job["media_id"]);p=job.get("payload") or {}
  try:
   bucket=str(p["bucket_id"]);path=str(p["storage_path"])
   media_type=str(p["media_type"])
   url=f"{self.base}/storage/v1/object/{quote(bucket,safe='')}/{quote(path,safe='/')}"
   src=await self.client.get(url);src.raise_for_status();data=src.content
   if len(data)!=int(p.get("size_bytes") or 0) or hashlib.sha256(data).hexdigest()!=p["sha256"]:
    raise ValueError("MEDIA_SOURCE_HASH_MISMATCH")
   await self.scan(data,str(p.get("filename") or mid),media_type)
   intent=build_signed_upload_intent(config=self.cloudinary,media_id=mid,media_type=media_type,callback_url=self.callback)
   resource=str(intent["resource_type"])
   public_id=str(intent["public_id"])
   params=dict(intent["params"])
   form={**params,"file":("original.bin",data,media_type)}
   # Never send Supabase service-role headers to the third-party media provider.
   async with httpx.AsyncClient(trust_env=False, follow_redirects=False, timeout=httpx.Timeout(180,connect=10)) as provider_client:
    upload=await provider_client.post(str(intent["upload_url"]),data={k:v for k,v in form.items() if k!="file"},files={"file":form["file"]})
   upload.raise_for_status();asset=upload.json()
   if (
    asset.get("public_id")!=public_id or asset.get("resource_type")!=resource
    or asset.get("type")!="authenticated" or int(asset.get("bytes") or 0)!=len(data)
    or not asset.get("asset_id") or not asset.get("batch_id")
   ):
    raise ValueError("CLOUDINARY_UPLOAD_RESPONSE_INVALID")
   handoff=await self.rpc("handoff_content_provider_job",{
    "p_job_id":jid,"p_lease_token":token,"p_media_id":mid,
    "p_provider_asset_id":asset["asset_id"],"p_provider_public_id":public_id,
    "p_provider_batch_id":asset.get("batch_id"),
   })
   if not isinstance(handoff,dict) or handoff.get("outcome")!="handed_off":
    raise ValueError("MEDIA_PROVIDER_HANDOFF_LEASE_LOST")
   # Job remains processing until the authenticated eager callback verifies the original and persists Cloudinary derivative identities.
  except Exception as exc:
   log.exception("transcode dispatch failed job=%s media=%s",jid,mid)
   try:await self.rpc("fail_content_lifecycle_job",{"p_job_id":jid,"p_lease_token":token,"p_error_code":(str(exc) if isinstance(exc,ValueError) else type(exc).__name__)[:80]})
   except Exception:log.exception("could not persist transcode failure job=%s",jid)
 async def batch(self):
  jobs=await self.rpc("claim_content_lifecycle_jobs",{"p_worker_id":self.worker_id,"p_limit":1,"p_lease_seconds":300,"p_job_type":"media_transcode"}) or []
  for job in jobs:await self.run_job(job)
  return len(jobs)
 async def assert_schema_ready(self):
  result=await self.rpc("cloudinary_media_schema_readiness",{})
  if not isinstance(result,dict) or result.get("ready") is not True:
   raise RuntimeError("MEDIA_SCHEMA_NOT_READY")
 async def run(self):
  try:
   while not self.stopping:
    try:n=await self.batch()
    except Exception:log.exception("transcode worker poll failed");n=0
    if n==0:await asyncio.sleep(5)
  finally:await self.client.aclose()
def enabled():
 raw=os.getenv("ALLPHA_CONTENT_TRANSCODE_WORKER_ENABLED","false").strip().lower()
 if raw not in {"true","false"}:raise SystemExit("ALLPHA_CONTENT_TRANSCODE_WORKER_ENABLED must be true or false")
 if raw!="true":return False
 try:scanner_mode=require_media_scanner_configuration()
 except RuntimeError as exc:raise SystemExit("Content transcode worker requires a configured remote scanner or explicitly enabled pinned ClamAV") from exc
 required=("SUPABASE_URL","CLOUDINARY_CLOUD_NAME","CLOUDINARY_API_KEY","CLOUDINARY_API_SECRET","ALLPHA_CLOUDINARY_CALLBACK_URL") + (("CLAMAV_HOST",) if scanner_mode=="clamd" else ())
 missing=[name for name in required if not os.getenv(name)]
 if not (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SECRET_KEY")):
  missing.append("SUPABASE_SERVICE_ROLE_KEY or SUPABASE_SECRET_KEY")
 if missing:raise SystemExit("Content transcode worker configuration missing: "+", ".join(missing))
 callback=os.environ["ALLPHA_CLOUDINARY_CALLBACK_URL"]
 if not callback.startswith("https://"):raise SystemExit("ALLPHA_CLOUDINARY_CALLBACK_URL must use HTTPS")
 return True

def main():
 logging.basicConfig(level=os.getenv("LOG_LEVEL","INFO"))
 if not enabled():
  log.info("Content transcode worker is disabled")
  return
 worker=TranscodeWorker();loop=asyncio.new_event_loop();asyncio.set_event_loop(loop)
 for sig in (signal.SIGINT,signal.SIGTERM):loop.add_signal_handler(sig,lambda:setattr(worker,"stopping",True))
 try:
  loop.run_until_complete(worker.assert_schema_ready())
  loop.run_until_complete(worker.run())
 finally:loop.close()
if __name__=="__main__":main()

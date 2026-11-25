"""Cloudinary video/audio transcode dispatcher. Provider callback owns readiness promotion."""
from __future__ import annotations
import asyncio, hashlib, logging, os, signal, time, uuid, socket, struct
from urllib.parse import quote
import httpx

from allpha_api.media_scanner import local_scanner_identity_pins, scan_media_bytes

log=logging.getLogger("allpha.content_transcode_worker")

class TranscodeWorker:
 def __init__(self):
  self.base=os.environ["SUPABASE_URL"].rstrip("/")
  self.key=os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ["SUPABASE_SECRET_KEY"]
  self.cloud=os.environ["CLOUDINARY_CLOUD_NAME"]
  self.api_key=os.environ["CLOUDINARY_API_KEY"]
  self.secret=os.environ["CLOUDINARY_API_SECRET"]
  self.callback=os.environ["ALLPHA_CLOUDINARY_CALLBACK_URL"]
  self.clamav_host=os.environ["CLAMAV_HOST"]; self.clamav_port=int(os.getenv("CLAMAV_PORT","3310"))
  self.worker_id=f"content-transcode-{uuid.uuid4()}"
  self.client=httpx.AsyncClient(trust_env=False, follow_redirects=False, timeout=httpx.Timeout(180,connect=10),headers={"apikey":self.key,"Authorization":f"Bearer {self.key}"})
  self.stopping=False
 async def rpc(self,name,payload):
  r=await self.client.post(f"{self.base}/rest/v1/rpc/{name}",json=payload);r.raise_for_status();return r.json() if r.content else None
 async def db(self,method,path,params=None,body=None,prefer=None):
  h={"apikey":self.key,"Authorization":f"Bearer {self.key}","Content-Type":"application/json"}
  if prefer:h["Prefer"]=prefer
  r=await self.client.request(method,f"{self.base}/rest/v1/{path}",params=params,json=body,headers=h);r.raise_for_status();return r.json() if r.content else None
 def scan(self,data):
  return scan_media_bytes(data,self.clamav_host,self.clamav_port)
 async def run_job(self,job):
  jid=str(job["id"]);token=str(job["lease_token"]);mid=str(job["media_id"]);p=job.get("payload") or {}
  try:
   bucket=str(p["bucket_id"]);path=str(p["storage_path"])
   url=f"{self.base}/storage/v1/object/{quote(bucket,safe='')}/{quote(path,safe='/')}"
   src=await self.client.get(url);src.raise_for_status();data=src.content
   if hashlib.sha256(data).hexdigest()!=p["sha256"]:raise ValueError("MEDIA_SOURCE_HASH_MISMATCH")
   await asyncio.to_thread(self.scan,data)
   media_type=str(p["media_type"])
   resource="video" # Cloudinary uses video resource_type for audio assets too.
   public_id=f"allpha/{mid}"
   timestamp=int(time.time())
   if media_type.startswith("video/"):
    eager="c_limit,w_1280,vc_h264,f_mp4|c_limit,w_640,vc_h264,f_mp4|so_0,w_640,h_360,c_fill,f_jpg"
   else:
    eager="ac_mp3,br_128k,f_mp3|ac_aac,br_128k,f_m4a"
   params={"timestamp":str(timestamp),"public_id":public_id,"eager":eager,"eager_async":"true","eager_notification_url":self.callback,"type":"authenticated","overwrite":"true"}
   serialized="&".join(f"{k}={params[k]}" for k in sorted(params))
   signature=hashlib.sha1((serialized+self.secret).encode()).hexdigest()
   form={**params,"api_key":self.api_key,"signature":signature,"file":("original.bin",data,media_type)}
   # Never send Supabase service-role headers to the third-party media provider.
   async with httpx.AsyncClient(trust_env=False, follow_redirects=False, timeout=httpx.Timeout(180,connect=10)) as provider_client:
    upload=await provider_client.post(f"https://api.cloudinary.com/v1_1/{self.cloud}/{resource}/upload",data={k:v for k,v in form.items() if k!="file"},files={"file":form["file"]})
   upload.raise_for_status();asset=upload.json()
   if asset.get("public_id")!=public_id or not asset.get("asset_id") or not asset.get("batch_id"):
    raise ValueError("CLOUDINARY_UPLOAD_RESPONSE_INVALID")
   handoff=await self.rpc("handoff_content_provider_job",{
    "p_job_id":jid,"p_lease_token":token,"p_media_id":mid,
    "p_provider_asset_id":asset["asset_id"],"p_provider_public_id":public_id,
    "p_provider_batch_id":asset.get("batch_id"),
   })
   if not isinstance(handoff,dict) or handoff.get("outcome")!="handed_off":
    raise ValueError("MEDIA_PROVIDER_HANDOFF_LEASE_LOST")
   # Job remains processing until authenticated eager callback copies derivatives to Supabase.
  except Exception as exc:
   log.exception("transcode dispatch failed job=%s media=%s",jid,mid)
   try:await self.rpc("fail_content_lifecycle_job",{"p_job_id":jid,"p_lease_token":token,"p_error_code":(str(exc) if isinstance(exc,ValueError) else type(exc).__name__)[:80]})
   except Exception:log.exception("could not persist transcode failure job=%s",jid)
 async def batch(self):
  jobs=await self.rpc("claim_content_lifecycle_jobs",{"p_worker_id":self.worker_id,"p_limit":1,"p_lease_seconds":300,"p_job_type":"media_transcode"}) or []
  for job in jobs:await self.run_job(job)
  return len(jobs)
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
 if os.getenv("ALLPHA_CLAMAV_ENABLED","false").strip().lower()!="true":
  raise SystemExit("Content transcode worker requires ALLPHA_CLAMAV_ENABLED=true")
 try:local_scanner_identity_pins()
 except RuntimeError as exc:raise SystemExit("Content transcode worker requires pinned ClamAV engine/signature identity") from exc
 required=("SUPABASE_URL","CLAMAV_HOST","CLOUDINARY_CLOUD_NAME","CLOUDINARY_API_KEY","CLOUDINARY_API_SECRET","ALLPHA_CLOUDINARY_CALLBACK_URL")
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
 try:loop.run_until_complete(worker.run())
 finally:loop.close()
if __name__=="__main__":main()

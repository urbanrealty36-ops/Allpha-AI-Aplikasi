"""Processes authenticated Cloudinary eager callbacks outside the webhook request path."""
from __future__ import annotations
import asyncio,hashlib,logging,os,signal,socket,struct,uuid
from urllib.parse import urlparse,quote
import httpx
log=logging.getLogger("allpha.provider_callback_worker")

class CallbackWorker:
 def __init__(self):
  self.base=os.environ["SUPABASE_URL"].rstrip("/")
  self.key=os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ["SUPABASE_SECRET_KEY"]
  self.cloud=os.environ["CLOUDINARY_CLOUD_NAME"]
  self.clamav_host=os.environ["CLAMAV_HOST"];self.clamav_port=int(os.getenv("CLAMAV_PORT","3310"))
  self.worker_id=f"provider-callback-{uuid.uuid4()}"
  self.client=httpx.AsyncClient(timeout=httpx.Timeout(90,connect=5),headers={"apikey":self.key,"Authorization":f"Bearer {self.key}","Content-Type":"application/json"})
  self.stopping=False
 async def rpc(self,name,payload):
  r=await self.client.post(f"{self.base}/rest/v1/rpc/{name}",json=payload);r.raise_for_status();return r.json() if r.content else None
 async def db(self,method,path,params=None,body=None,prefer=None):
  h={"apikey":self.key,"Authorization":f"Bearer {self.key}","Content-Type":"application/json"}
  if prefer:h["Prefer"]=prefer
  r=await self.client.request(method,f"{self.base}/rest/v1/{path}",params=params,json=body,headers=h);r.raise_for_status();return r.json() if r.content else None
 def scan(self,data):
  with socket.create_connection((self.clamav_host,self.clamav_port),timeout=10) as sock:
   sock.settimeout(60);sock.sendall(b"zINSTREAM\\0")
   for offset in range(0,len(data),64*1024):
    chunk=data[offset:offset+64*1024];sock.sendall(struct.pack("!I",len(chunk))+chunk)
   sock.sendall(struct.pack("!I",0));result=sock.recv(4096).decode("utf-8","replace")
  if not result.strip().endswith("OK") or "FOUND" in result or "ERROR" in result:raise ValueError("DERIVATIVE_SCAN_NOT_CLEAN")
 async def process(self,job):
  jid=str(job["id"]);token=str(job["lease_token"]);payload=job.get("payload") or {};event_id=str(payload["provider_event_id"])
  try:
   callbacks=await self.db("GET","content_provider_callbacks",{"select":"provider,provider_event_id,media_id,job_id,payload_sha256,payload,outcome","provider":"eq.cloudinary","provider_event_id":f"eq.{event_id}","limit":"1"})
   if not callbacks:raise ValueError("PROVIDER_CALLBACK_RECORD_MISSING")
   callback=callbacks[0]
   if callback["outcome"]=="processed":
    done=await self.rpc("complete_content_lifecycle_job",{"p_job_id":jid,"p_lease_token":token})
    if done!="succeeded":raise ValueError("CALLBACK_JOB_LEASE_LOST")
    return
   event=callback.get("payload") or {};public_id=str(event.get("public_id",""))
   media_id=str(callback["media_id"]);transcode_job_id=str(callback["job_id"])
   media_rows=await self.db("GET","content_media",{"select":"id,content_id,owner_id,bucket_id,storage_path,media_type,status,provider_asset_id,provider_public_id,provider_batch_id","id":f"eq.{media_id}","status":"eq.processing","limit":"1"})
   if not media_rows:raise ValueError("CALLBACK_MEDIA_NOT_PROCESSING")
   media=media_rows[0]
   transcode=await self.db("GET","content_lifecycle_jobs",{"select":"id,status,payload","id":f"eq.{transcode_job_id}","status":"eq.awaiting_provider","limit":"1"})
   if not transcode:raise ValueError("TRANSCODE_JOB_NOT_WAITING")
   provider_payload=transcode[0].get("payload") or {}
   if public_id!=media["provider_public_id"] or event.get("asset_id")!=media["provider_asset_id"] or event.get("batch_id")!=media["provider_batch_id"] or provider_payload.get("provider_batch_id")!=event.get("batch_id"):
    raise ValueError("PROVIDER_CALLBACK_ASSET_OR_BATCH_MISMATCH")
   eager=event.get("eager") or []
   expected=3 if media["media_type"].startswith("video/") else 2
   if len(eager)<expected or any(not isinstance(item,dict) or item.get("status")=="failed" for item in eager):
    raise ValueError("PROVIDER_EAGER_DERIVATIVES_INCOMPLETE")
   derivatives=[]
   async with httpx.AsyncClient(timeout=httpx.Timeout(90,connect=5),follow_redirects=False) as provider:
    for index,item in enumerate(eager):
     url=item.get("secure_url");parsed=urlparse(url or "")
     if parsed.scheme!="https" or parsed.hostname!="res.cloudinary.com" or not parsed.path.startswith(f"/{self.cloud}/video/authenticated/"):
      raise ValueError("PROVIDER_DERIVATIVE_URL_REJECTED")
     response=await provider.get(url)
     response.raise_for_status()
     if len(response.content)>100*1024*1024:raise ValueError("PROVIDER_DERIVATIVE_TOO_LARGE")
     binary=response.content;mime=response.headers.get("content-type","").split(";")[0].lower()
     if not (mime.startswith("video/") or mime.startswith("audio/") or mime=="image/jpeg"):raise ValueError("PROVIDER_DERIVATIVE_MIME_INVALID")
     await asyncio.to_thread(self.scan,binary)
     suffix="mp4" if mime=="video/mp4" else "mp3" if mime=="audio/mpeg" else "m4a" if mime=="audio/mp4" else "jpg" if mime=="image/jpeg" else "bin"
     kind="moderation_poster" if mime=="image/jpeg" else f"rendition_{index+1}"
     path=f"{media['storage_path']}.derived/{kind}.{suffix}"
     storage=f"{self.base}/storage/v1/object/{quote(media['bucket_id'],safe='')}/{quote(path,safe='/')}"
     uploaded=await self.client.post(storage,content=binary,headers={"Content-Type":mime,"x-upsert":"true"})
     uploaded.raise_for_status()
     derivatives.append({"kind":kind,"storage_path":path,"mime_type":mime,"size_bytes":len(binary),
      "sha256":hashlib.sha256(binary).hexdigest(),"width":item.get("width"),"height":item.get("height"),"duration":item.get("duration")})
   completed=await self.rpc("complete_content_provider_job",{
    "p_job_id":transcode_job_id,"p_media_id":media_id,"p_provider":"cloudinary",
    "p_provider_asset_id":media["provider_asset_id"],"p_provider_public_id":public_id,
    "p_provider_event_id":event_id,"p_payload_sha256":callback["payload_sha256"],
    "p_derivatives":derivatives,"p_scan_status":"clean",
   })
   if not isinstance(completed,dict) or completed.get("outcome")!="completed":raise ValueError("PROVIDER_MEDIA_COMPLETION_CONFLICT")
   done=await self.rpc("complete_content_lifecycle_job",{"p_job_id":jid,"p_lease_token":token})
   if done!="succeeded":raise ValueError("CALLBACK_JOB_LEASE_LOST")
  except Exception as exc:
   log.exception("provider callback processing failed job=%s event=%s",jid,event_id)
   try:await self.rpc("fail_content_lifecycle_job",{"p_job_id":jid,"p_lease_token":token,"p_error_code":type(exc).__name__[:80]})
   except Exception:log.exception("callback failure could not be persisted")
 async def batch(self):
  jobs=await self.rpc("claim_content_lifecycle_jobs",{"p_worker_id":self.worker_id,"p_limit":1,"p_lease_seconds":300,"p_job_type":"provider_callback"}) or []
  for job in jobs:await self.process(job)
  return len(jobs)
 async def run(self):
  try:
   while not self.stopping:
    try:n=await self.batch()
    except Exception:log.exception("provider callback poll failed");n=0
    if n==0:await asyncio.sleep(3)
  finally:await self.client.aclose()
def main():
 logging.basicConfig(level=os.getenv("LOG_LEVEL","INFO"))
 worker=CallbackWorker();loop=asyncio.new_event_loop();asyncio.set_event_loop(loop)
 for sig in (signal.SIGINT,signal.SIGTERM):loop.add_signal_handler(sig,lambda:setattr(worker,"stopping",True))
 try:loop.run_until_complete(worker.run())
 finally:loop.close()
if __name__=="__main__":main()

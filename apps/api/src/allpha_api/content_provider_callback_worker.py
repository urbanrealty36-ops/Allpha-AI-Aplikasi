"""Processes authenticated Cloudinary eager callbacks outside the webhook request path."""
from __future__ import annotations
from typing import Any
import asyncio,hashlib,logging,os,signal,uuid
from urllib.parse import urlparse
import httpx
from allpha_api.cloudinary_provider import CloudinaryConfig, build_signed_private_download_url, eager_transformations
from allpha_api.media_scanner import require_media_scanner_configuration, scan_media_bytes_async
log=logging.getLogger("allpha.provider_callback_worker")
MAX_PROVIDER_DERIVATIVE_BYTES = 100 * 1024 * 1024
MAX_PROVIDER_MEDIA_BYTES = 50 * 1024 * 1024


def validate_eager_derivative_contract(media_type: str, eager: Any) -> None:
 if not isinstance(eager, list) or any(not isinstance(item, dict) for item in eager):
  raise ValueError("PROVIDER_EAGER_DERIVATIVES_INVALID")
 if any(item.get("status") != "success" for item in eager):
  raise ValueError("PROVIDER_EAGER_DERIVATIVES_INCOMPLETE")
 expected_transformations=set((eager_transformations(media_type) or "").split("|")) - {""}
 actual_transformations=[str(item.get("transformation") or "") for item in eager]
 if not expected_transformations or len(actual_transformations)!=len(expected_transformations) or set(actual_transformations)!=expected_transformations:
  raise ValueError("PROVIDER_EAGER_TRANSFORMATIONS_INVALID")
 formats=[str(item.get("format") or item.get("mime_type") or "").lower() for item in eager]
 video_count=sum(value in {"mp4","video/mp4"} for value in formats)
 poster_count=sum(value in {"jpg","jpeg","image/jpeg"} for value in formats)
 audio_count=sum(value in {"mp3","m4a","aac","audio/mpeg","audio/mp4"} for value in formats)
 if media_type.startswith("video/"):
  if len(eager)!=3 or video_count<2 or poster_count<1:
   raise ValueError("PROVIDER_VIDEO_RENDITION_CONTRACT_INVALID")
 elif media_type.startswith("audio/"):
  if len(eager)!=2 or audio_count!=2:
   raise ValueError("PROVIDER_AUDIO_RENDITION_CONTRACT_INVALID")
 elif media_type.startswith("image/"):
  if len(eager)!=2 or poster_count!=2:
   raise ValueError("PROVIDER_IMAGE_RENDITION_CONTRACT_INVALID")
 else:
  raise ValueError("PROVIDER_MEDIA_TYPE_UNSUPPORTED")


def provider_derivative_identity(index: int, mime: str, media_type: str = "video/mp4") -> tuple[str, str]:
 """Return a deterministic private-storage name for an allowlisted derivative MIME."""
 if index < 0:
  raise ValueError("PROVIDER_DERIVATIVE_INDEX_INVALID")
 suffix_by_mime = {
  "video/mp4": "mp4",
  "audio/mpeg": "mp3",
  "audio/mp4": "m4a",
  "image/jpeg": "jpg",
 }
 suffix = suffix_by_mime.get(mime)
 if suffix is None:
  raise ValueError("PROVIDER_DERIVATIVE_MIME_INVALID")
 if mime == "image/jpeg" and media_type.startswith("image/"):
  kind = "display" if index == 0 else "thumbnail"
 else:
  kind = "moderation_poster" if mime == "image/jpeg" else f"rendition_{index + 1}"
 return kind, suffix


async def download_provider_derivative(client: httpx.AsyncClient, url: str) -> tuple[bytes, str]:
 async with client.stream("GET",url) as response:
  response.raise_for_status()
  mime=response.headers.get("content-type","").split(";")[0].lower()
  if not (mime.startswith("video/") or mime.startswith("audio/") or mime=="image/jpeg"):
   raise ValueError("PROVIDER_DERIVATIVE_MIME_INVALID")
  raw_length=response.headers.get("content-length")
  if raw_length:
   try:
    if int(raw_length)>MAX_PROVIDER_DERIVATIVE_BYTES:
     raise ValueError("PROVIDER_DERIVATIVE_TOO_LARGE")
   except ValueError as exc:
    if str(exc)=="PROVIDER_DERIVATIVE_TOO_LARGE": raise
    raise ValueError("PROVIDER_DERIVATIVE_LENGTH_INVALID") from exc
  body=bytearray()
  async for chunk in response.aiter_bytes():
   if len(body)+len(chunk)>MAX_PROVIDER_DERIVATIVE_BYTES:
    raise ValueError("PROVIDER_DERIVATIVE_TOO_LARGE")
   body.extend(chunk)
  if not body:
   raise ValueError("PROVIDER_DERIVATIVE_EMPTY")
  return bytes(body),mime


async def download_cloudinary_original(
 client: httpx.AsyncClient, url: str, *, expected_media_type: str, max_bytes: int,
) -> bytes:
 """Download the exact authenticated original from Cloudinary for malware scanning."""
 parsed = urlparse(url)
 if parsed.scheme != "https" or parsed.hostname != "api.cloudinary.com" or "/download" not in parsed.path:
  raise ValueError("PROVIDER_ORIGINAL_URL_REJECTED")
 if max_bytes <= 0 or max_bytes > MAX_PROVIDER_MEDIA_BYTES:
  raise ValueError("PROVIDER_ORIGINAL_SIZE_INVALID")
 async with client.stream("GET", url) as response:
  response.raise_for_status()
  final_host = (urlparse(str(response.url)).hostname or "").lower()
  if not (final_host == "api.cloudinary.com" or final_host.endswith(".cloudinary.com") or final_host.endswith(".akamaihd.net")):
   raise ValueError("PROVIDER_ORIGINAL_REDIRECT_REJECTED")
  mime = response.headers.get("content-type", "").split(";", 1)[0].lower()
  if mime not in {expected_media_type, "application/octet-stream"}:
   raise ValueError("PROVIDER_ORIGINAL_MIME_MISMATCH")
  raw_length = response.headers.get("content-length")
  if raw_length:
   try:
    if int(raw_length) > max_bytes:
     raise ValueError("PROVIDER_ORIGINAL_TOO_LARGE")
   except ValueError as exc:
    if str(exc) == "PROVIDER_ORIGINAL_TOO_LARGE": raise
    raise ValueError("PROVIDER_ORIGINAL_LENGTH_INVALID") from exc
  body = bytearray()
  async for chunk in response.aiter_bytes():
   if len(body) + len(chunk) > max_bytes:
    raise ValueError("PROVIDER_ORIGINAL_TOO_LARGE")
   body.extend(chunk)
  if not body:
   raise ValueError("PROVIDER_ORIGINAL_EMPTY")
  return bytes(body)


def build_cloudinary_derivative_metadata(
 media_type: str, eager: list[dict[str, Any]], *, cloud_name: str, resource_type: str, public_id: str, version: int,
) -> list[dict[str, Any]]:
 """Persist verified Cloudinary transformation identities without copying derivative bytes."""
 if resource_type not in {"image", "video"} or not cloud_name or version <= 0:
  raise ValueError("PROVIDER_DERIVATIVE_IDENTITY_INVALID")
 validate_eager_derivative_contract(media_type, eager)
 expected = set((eager_transformations(media_type) or "").split("|")) - {""}
 records: list[dict[str, Any]] = []
 mime_by_format = {"jpg":"image/jpeg","jpeg":"image/jpeg","mp4":"video/mp4","mp3":"audio/mpeg","m4a":"audio/mp4","aac":"audio/aac"}
 for index, item in enumerate(eager):
  transformation = str(item.get("transformation") or "")
  output_format = str(item.get("format") or "").lower()
  suffix = {"jpeg":"jpg"}.get(output_format, output_format)
  mime = mime_by_format.get(suffix)
  url = item.get("secure_url")
  parsed = urlparse(url or "")
  if (
   transformation not in expected or mime is None or parsed.scheme != "https"
   or parsed.hostname != "res.cloudinary.com"
   or not parsed.path.startswith(f"/{cloud_name}/{resource_type}/authenticated/")
   or f"/{transformation}/v{version}/{public_id}.{suffix}" not in parsed.path
  ):
   raise ValueError("PROVIDER_DERIVATIVE_URL_REJECTED")
  kind, expected_suffix = provider_derivative_identity(index, mime, media_type)
  if suffix != expected_suffix:
   raise ValueError("PROVIDER_DERIVATIVE_FORMAT_MISMATCH")
  try:
   size_bytes = int(item.get("bytes") or 0)
   width = int(item.get("width") or 0)
   height = int(item.get("height") or 0)
   duration = float(item["duration"]) if item.get("duration") is not None else None
  except (TypeError, ValueError) as exc:
   raise ValueError("PROVIDER_DERIVATIVE_METADATA_INVALID") from exc
  if size_bytes <= 0 or (mime.startswith("image/") and (width <= 0 or height <= 0)):
   raise ValueError("PROVIDER_DERIVATIVE_METADATA_INVALID")
  records.append({
   "kind":kind,"provider":"cloudinary","resource_type":resource_type,
   "delivery_type":"authenticated","format":suffix,"transformation":transformation,
   "version":version,"mime_type":mime,"size_bytes":size_bytes,
   "width":width or None,"height":height or None,"duration":duration,
  })
 return records


class CallbackWorker:
 def __init__(self):
  self.base=os.environ["SUPABASE_URL"].rstrip("/")
  self.key=os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ["SUPABASE_SECRET_KEY"]
  self.cloudinary=CloudinaryConfig.from_environment()
  self.cloud=self.cloudinary.cloud_name
  self.scanner_mode=require_media_scanner_configuration()
  self.worker_id=f"provider-callback-{uuid.uuid4()}"
  self.client=httpx.AsyncClient(trust_env=False, follow_redirects=False, timeout=httpx.Timeout(90,connect=5),headers={"apikey":self.key,"Authorization":f"Bearer {self.key}","Content-Type":"application/json"})
  self.stopping=False
 async def rpc(self,name,payload):
  r=await self.client.post(f"{self.base}/rest/v1/rpc/{name}",json=payload);r.raise_for_status();return r.json() if r.content else None
 async def db(self,method,path,params=None,body=None,prefer=None):
  h={"apikey":self.key,"Authorization":f"Bearer {self.key}","Content-Type":"application/json"}
  if prefer:h["Prefer"]=prefer
  r=await self.client.request(method,f"{self.base}/rest/v1/{path}",params=params,json=body,headers=h);r.raise_for_status();return r.json() if r.content else None
 async def scan(self,data,filename,media_type):
  # The canonical remote scanner pins hostname, scanner/engine/signature identity and content digest.
  return await scan_media_bytes_async(data,filename=filename,media_type=media_type)
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
   media_fields="id,content_id,owner_id,filename,media_type,size_bytes,sha256,status,storage_provider,storage_path,provider_asset_id,provider_public_id,provider_batch_id,provider_resource_type,provider_delivery_type,provider_format,provider_version"
   media_rows=await self.db("GET","content_media",{"select":media_fields,"id":f"eq.{media_id}","status":"eq.processing","limit":"1"})
   if not media_rows:raise ValueError("CALLBACK_MEDIA_NOT_PROCESSING")
   media=media_rows[0]
   transcode=await self.db("GET","content_lifecycle_jobs",{"select":"id,status,payload","id":f"eq.{transcode_job_id}","status":"eq.awaiting_provider","limit":"1"})
   if not transcode:raise ValueError("TRANSCODE_JOB_NOT_WAITING")
   provider_payload=transcode[0].get("payload") or {}
   if public_id!=media["provider_public_id"] or event.get("asset_id")!=media["provider_asset_id"] or event.get("batch_id")!=media["provider_batch_id"] or provider_payload.get("provider_batch_id")!=event.get("batch_id"):
    raise ValueError("PROVIDER_CALLBACK_ASSET_OR_BATCH_MISMATCH")
   eager=event.get("eager") or []
   validate_eager_derivative_contract(str(media["media_type"]),eager)
   if media.get("storage_provider")!="cloudinary" or media.get("provider_delivery_type")!="authenticated":
    raise ValueError("PROVIDER_MEDIA_STORAGE_CONTRACT_INVALID")
   resource_type=str(media.get("provider_resource_type") or "")
   if resource_type not in {"image","video"}:
    raise ValueError("PROVIDER_MEDIA_RESOURCE_TYPE_INVALID")
   original_url=build_signed_private_download_url(
    config=self.cloudinary,public_id=public_id,resource_type=resource_type,
    format=str(media["provider_format"]),expires_in=300,
   )
   async with httpx.AsyncClient(trust_env=False, follow_redirects=True, timeout=httpx.Timeout(180,connect=5)) as provider:
    original=await download_cloudinary_original(
     provider,original_url,expected_media_type=str(media["media_type"]),
     max_bytes=min(int(media["size_bytes"]),MAX_PROVIDER_MEDIA_BYTES),
    )
    if len(original)!=int(media["size_bytes"]) or hashlib.sha256(original).hexdigest()!=str(media["sha256"]):
     raise ValueError("PROVIDER_ORIGINAL_DIGEST_MISMATCH")
    scan_receipt=await self.scan(original,str(media["filename"]),str(media["media_type"]))
    if not isinstance(scan_receipt,dict) or scan_receipt.get("sha256")!=str(media["sha256"]):
     raise ValueError("PROVIDER_ORIGINAL_SCAN_RECEIPT_MISMATCH")
   derivatives=build_cloudinary_derivative_metadata(
    str(media["media_type"]),eager,cloud_name=self.cloud,resource_type=resource_type,
    public_id=public_id,version=int(media["provider_version"]),
   )
   completed=await self.rpc("complete_cloudinary_content_provider_job",{
    "p_job_id":transcode_job_id,"p_media_id":media_id,"p_provider":"cloudinary",
    "p_provider_asset_id":media["provider_asset_id"],"p_provider_public_id":public_id,
    "p_provider_event_id":event_id,"p_payload_sha256":callback["payload_sha256"],
    "p_derivatives":derivatives,"p_scan_status":"clean","p_scan_receipt":scan_receipt,
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
def enabled():
 raw=os.getenv("ALLPHA_CONTENT_PROVIDER_CALLBACK_WORKER_ENABLED","false").strip().lower()
 if raw not in {"true","false"}:raise SystemExit("ALLPHA_CONTENT_PROVIDER_CALLBACK_WORKER_ENABLED must be true or false")
 if raw!="true":return False
 try:scanner_mode=require_media_scanner_configuration()
 except RuntimeError as exc:raise SystemExit("Provider callback worker requires a configured remote scanner or explicitly enabled pinned ClamAV") from exc
 required=("SUPABASE_URL","CLOUDINARY_CLOUD_NAME") + (("CLAMAV_HOST",) if scanner_mode=="clamd" else ())
 missing=[name for name in required if not os.getenv(name)]
 if not (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SECRET_KEY")):missing.append("SUPABASE_SERVICE_ROLE_KEY or SUPABASE_SECRET_KEY")
 if missing:raise SystemExit("Provider callback worker configuration missing: "+", ".join(missing))
 return True
def main():
 logging.basicConfig(level=os.getenv("LOG_LEVEL","INFO"))
 if not enabled():
  log.info("Provider callback worker is disabled")
  return
 worker=CallbackWorker();loop=asyncio.new_event_loop();asyncio.set_event_loop(loop)
 for sig in (signal.SIGINT,signal.SIGTERM):loop.add_signal_handler(sig,lambda:setattr(worker,"stopping",True))
 try:loop.run_until_complete(worker.run())
 finally:loop.close()
if __name__=="__main__":main()

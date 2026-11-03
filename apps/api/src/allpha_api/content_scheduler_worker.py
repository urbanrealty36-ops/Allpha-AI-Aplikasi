"""Durable WP-04 scheduled content publisher; moderation and media are rechecked atomically in Postgres."""
from __future__ import annotations
import asyncio, logging, os, signal, uuid
from typing import Any
import httpx
log=logging.getLogger("allpha.content_scheduler")

class ContentScheduler:
 def __init__(self):
  self.base=os.environ["SUPABASE_URL"].rstrip("/")
  self.key=os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ["SUPABASE_SECRET_KEY"]
  self.worker_id=f"content-scheduler-{uuid.uuid4()}"
  self.client=httpx.AsyncClient(timeout=httpx.Timeout(30,connect=5),headers={"apikey":self.key,"Authorization":f"Bearer {self.key}","Content-Type":"application/json"})
  self.stopping=False
 async def rpc(self,name,payload):
  r=await self.client.post(f"{self.base}/rest/v1/rpc/{name}",json=payload);r.raise_for_status();return r.json() if r.content else None
 async def batch(self):
  jobs=await self.rpc("claim_due_content_schedules",{"p_worker_id":self.worker_id,"p_limit":1,"p_lease_seconds":300}) or []
  for job in jobs:
   try:
    result=await self.rpc("publish_scheduled_content",{"p_schedule_id":job["id"],"p_lease_token":job["lease_token"]})
    if not isinstance(result,dict) or result.get("outcome")!="published":
     code=result.get("outcome","PUBLISH_RESULT_INVALID") if isinstance(result,dict) else "PUBLISH_RESULT_INVALID"
     state=await self.rpc("fail_content_schedule",{"p_schedule_id":job["id"],"p_lease_token":job["lease_token"],"p_error_code":code})
     log.warning("scheduled content deferred schedule=%s outcome=%s state=%s",job["id"],code,state)
    else:
     log.info("scheduled content published schedule=%s content=%s",job["id"],result["content"]["id"])
   except Exception as exc:
    log.exception("scheduled content execution failed schedule=%s",job["id"])
    try:await self.rpc("fail_content_schedule",{"p_schedule_id":job["id"],"p_lease_token":job["lease_token"],"p_error_code":type(exc).__name__[:80]})
    except Exception:log.exception("schedule failure could not be recorded schedule=%s",job["id"])
  return len(jobs)
 async def run(self):
  try:
   while not self.stopping:
    try:n=await self.batch()
    except Exception:log.exception("content scheduler poll failed");n=0
    if n==0:await asyncio.sleep(max(1,int(os.getenv("CONTENT_SCHEDULER_POLL_SECONDS","5"))))
  finally:await self.client.aclose()
def main():
 logging.basicConfig(level=os.getenv("LOG_LEVEL","INFO"))
 worker=ContentScheduler();loop=asyncio.new_event_loop();asyncio.set_event_loop(loop)
 for sig in (signal.SIGINT,signal.SIGTERM):loop.add_signal_handler(sig,lambda:setattr(worker,"stopping",True))
 try:loop.run_until_complete(worker.run())
 finally:loop.close()
if __name__=="__main__":main()

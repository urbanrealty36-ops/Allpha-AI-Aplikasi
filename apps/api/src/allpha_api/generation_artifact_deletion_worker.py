"""Durable cleanup worker for requester-deleted private Generation artifacts.

The worker is disabled by default and does not define an automatic retention TTL.
"""
from __future__ import annotations

import asyncio
import logging
import os
import signal
import uuid
from urllib.parse import quote

import httpx

log = logging.getLogger("allpha.generation_artifact_deletion_worker")
_TRUE = {"1", "true", "yes"}


class GenerationArtifactDeletionWorker:
    def __init__(self) -> None:
        self.base = os.environ["SUPABASE_URL"].rstrip("/")
        self.key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.environ["SUPABASE_SECRET_KEY"]
        self.worker_id = str(uuid.uuid4())
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0, connect=5.0),
            headers={
                "apikey": self.key,
                "Authorization": f"Bearer {self.key}",
                "Content-Type": "application/json",
            },
        )
        self.stopping = False

    async def rpc(self, name: str, command: dict) -> object:
        response = await self.client.post(
            f"{self.base}/rest/v1/rpc/{name}",
            json={"p_command": command},
        )
        response.raise_for_status()
        return response.json() if response.content else None

    async def remove_object(self, bucket: str, object_path: str) -> None:
        url = (
            f"{self.base}/storage/v1/object/"
            f"{quote(bucket, safe='')}/{quote(object_path, safe='/')}"
        )
        response = await self.client.delete(url)
        if response.status_code not in (200, 204, 404):
            response.raise_for_status()

    async def process(self, job: dict) -> None:
        deletion_job_id = str(job["id"])
        lease_token = str(job["lease_token"])
        try:
            await self.remove_object(str(job["bucket_id"]), str(job["object_path"]))
            result = await self.rpc(
                "complete_generation_artifact_deletion",
                {"deletion_job_id": deletion_job_id, "lease_token": lease_token},
            )
            if not isinstance(result, dict) or result.get("status") != "succeeded":
                raise RuntimeError("GENERATION_ARTIFACT_DELETE_COMPLETION_UNCONFIRMED")
            log.info("generation_artifact_deleted deletion_job_id=%s", deletion_job_id)
        except Exception as exc:
            log.exception("generation_artifact_delete_failed deletion_job_id=%s", deletion_job_id)
            attempts = max(1, int(job.get("attempts") or 1))
            retry_seconds = min(3600, 15 * (2 ** min(attempts - 1, 8)))
            try:
                await self.rpc(
                    "fail_generation_artifact_deletion",
                    {
                        "deletion_job_id": deletion_job_id,
                        "lease_token": lease_token,
                        "error_code": type(exc).__name__[:80],
                        "retry_seconds": retry_seconds,
                    },
                )
            except Exception:
                log.exception("generation_artifact_delete_failure_persist_failed deletion_job_id=%s", deletion_job_id)

    async def batch(self) -> int:
        jobs = await self.rpc(
            "claim_generation_artifact_deletions",
            {"worker_id": self.worker_id, "limit": int(os.getenv("GENERATION_ARTIFACT_DELETE_BATCH_SIZE", "5")), "lease_seconds": 300},
        )
        if not isinstance(jobs, list) or not jobs:
            return 0
        for job in jobs:
            if isinstance(job, dict):
                await self.process(job)
        return len(jobs)

    async def run(self) -> None:
        poll_seconds = max(2, min(60, int(os.getenv("GENERATION_ARTIFACT_DELETE_POLL_SECONDS", "10"))))
        try:
            while not self.stopping:
                try:
                    count = await self.batch()
                except Exception:
                    log.exception("generation_artifact_deletion_batch_failed")
                    count = 0
                if count == 0:
                    await asyncio.sleep(poll_seconds)
        finally:
            await self.client.aclose()


def main() -> None:
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO").upper())
    if os.getenv("ALLPHA_GENERATION_ARTIFACT_DELETION_WORKER_ENABLED", "false").strip().lower() not in _TRUE:
        log.info("generation_artifact_deletion_worker_disabled")
        return
    worker = GenerationArtifactDeletionWorker()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: setattr(worker, "stopping", True))
    try:
        loop.run_until_complete(worker.run())
    finally:
        loop.close()


if __name__ == "__main__":
    main()

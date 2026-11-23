"""Durable account export worker. Deletion remains policy-gated until ENG-P03 policy approval."""
from __future__ import annotations

import asyncio
import gzip
import hashlib
import json
import logging
import os
import signal
import uuid
from typing import Any
from urllib.parse import quote

import httpx

log = logging.getLogger("allpha.account_lifecycle_worker")
_TRUE = {"1", "true", "yes"}
_EXPORT_LEASE_SECONDS = 900
_EXPORT_LEASE_HEARTBEAT_SECONDS = 240


class AccountLifecycleWorker:
    def __init__(self) -> None:
        self.base = os.environ["SUPABASE_URL"].rstrip("/")
        self.key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.environ["SUPABASE_SECRET_KEY"]
        self.worker_id = f"account-export-{uuid.uuid4()}"
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(120.0, connect=10.0),
            headers={
                "apikey": self.key,
                "Authorization": f"Bearer {self.key}",
                "Content-Type": "application/json",
            },
        )
        self.stopping = False
        self.lease_heartbeat_seconds = max(5, min(600, int(os.getenv("ACCOUNT_EXPORT_LEASE_HEARTBEAT_SECONDS", str(_EXPORT_LEASE_HEARTBEAT_SECONDS)))))

    async def rpc(self, name: str, payload: dict[str, Any]) -> Any:
        response = await self.client.post(
            f"{self.base}/rest/v1/rpc/{name}",
            json=payload,
        )
        response.raise_for_status()
        return response.json() if response.content else None

    async def upload(self, object_path: str, payload: bytes) -> None:
        response = await self.client.post(
            f"{self.base}/storage/v1/object/account-exports/{quote(object_path, safe='/')}",
            content=payload,
            headers={
                "Content-Type": "application/gzip",
                "x-upsert": "true",
                "Cache-Control": "no-store",
            },
        )
        if response.status_code not in (200, 201):
            response.raise_for_status()

    async def _maintain_lease(
        self,
        job_id: str,
        lease_token: str,
        stop: asyncio.Event,
        lease_lost: asyncio.Event,
    ) -> None:
        while not stop.is_set():
            try:
                await asyncio.wait_for(stop.wait(), timeout=self.lease_heartbeat_seconds)
                return
            except asyncio.TimeoutError:
                pass
            try:
                renewed = await self.rpc(
                    "renew_account_export_job_lease",
                    {
                        "p_job_id": job_id,
                        "p_lease_token": lease_token,
                        "p_lease_seconds": _EXPORT_LEASE_SECONDS,
                    },
                )
            except Exception:
                log.exception("account_export_lease_heartbeat_failed job_id=%s", job_id)
                lease_lost.set()
                return
            if renewed is not True:
                log.warning("account_export_lease_lost job_id=%s", job_id)
                lease_lost.set()
                return

    async def process(self, job: dict[str, Any]) -> None:
        job_id = str(job["id"])
        user_id = str(job["user_id"])
        lease_token = str(job["lease_token"])
        stop_heartbeat = asyncio.Event()
        lease_lost = asyncio.Event()
        heartbeat_task: asyncio.Task[None] | None = None
        try:
            renewed = await self.rpc(
                "renew_account_export_job_lease",
                {
                    "p_job_id": job_id,
                    "p_lease_token": lease_token,
                    "p_lease_seconds": _EXPORT_LEASE_SECONDS,
                },
            )
            if renewed is not True:
                log.warning("account_export_lease_lost job_id=%s", job_id)
                return
            heartbeat_task = asyncio.create_task(
                self._maintain_lease(job_id, lease_token, stop_heartbeat, lease_lost)
            )

            snapshot = await self.rpc(
                "build_my_account_export_snapshot",
                {"p_job_id": job_id, "p_lease_token": lease_token},
            )
            if lease_lost.is_set():
                raise RuntimeError("ACCOUNT_EXPORT_LEASE_LOST")
            if not isinstance(snapshot, dict) or snapshot.get("schema_version") != "1.0":
                raise RuntimeError("ACCOUNT_EXPORT_SNAPSHOT_INVALID")
            manifest = snapshot.get("manifest")
            data = snapshot.get("data")
            source_count = snapshot.get("source_count")
            source_keys = [
                item.get("source") for item in manifest
                if isinstance(item, dict) and isinstance(item.get("source"), str)
            ] if isinstance(manifest, list) else []
            if (
                not isinstance(data, dict)
                or type(source_count) is not int
                or source_count != len(manifest or [])
                or len(source_keys) != len(manifest or [])
                or len(set(source_keys)) != len(source_keys)
                or set(source_keys) != set(data)
            ):
                raise RuntimeError("ACCOUNT_EXPORT_SNAPSHOT_INCOMPLETE")

            encoded = json.dumps(
                snapshot,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
            compressed = gzip.compress(encoded, compresslevel=6, mtime=0)
            digest = hashlib.sha256(compressed).hexdigest()
            object_path = f"{user_id}/{job_id}.json.gz"
            await self.upload(object_path, compressed)
            if lease_lost.is_set():
                raise RuntimeError("ACCOUNT_EXPORT_LEASE_LOST")

            completed = await self.rpc(
                "complete_account_export_job",
                {
                    "p_job_id": job_id,
                    "p_lease_token": lease_token,
                    "p_storage_path": object_path,
                    "p_file_sha256": digest,
                    "p_file_size_bytes": len(compressed),
                    "p_manifest": {
                        "schema_version": snapshot.get("schema_version"),
                        "source_count": snapshot.get("source_count", 0),
                        "sources": snapshot.get("manifest", []),
                        "compression": "gzip",
                    },
                },
            )
            if completed is not True:
                raise RuntimeError("ACCOUNT_EXPORT_COMPLETION_UNCONFIRMED")
            log.info(
                "account_export_completed job_id=%s source_count=%s bytes=%s",
                job_id,
                snapshot.get("source_count", 0),
                len(compressed),
            )
        except Exception as exc:
            log.exception("account_export_failed job_id=%s", job_id)
            attempts = max(1, int(job.get("attempts") or 1))
            retry_seconds = min(3600, 15 * (2 ** min(attempts - 1, 8)))
            try:
                await self.rpc(
                    "fail_account_export_job",
                    {
                        "p_job_id": job_id,
                        "p_lease_token": lease_token,
                        "p_error_code": type(exc).__name__[:80],
                        "p_retry_seconds": retry_seconds,
                    },
                )
            except Exception:
                log.exception("account_export_failure_persist_failed job_id=%s", job_id)
        finally:
            stop_heartbeat.set()
            if heartbeat_task is not None:
                await heartbeat_task

    async def batch(self) -> int:
        jobs = await self.rpc(
            "claim_account_export_jobs",
            {
                "p_worker_id": self.worker_id,
                "p_limit": int(os.getenv("ACCOUNT_EXPORT_BATCH_SIZE", "2")),
                "p_lease_seconds": 900,
            },
        )
        if not isinstance(jobs, list) or not jobs:
            return 0
        for job in jobs:
            if isinstance(job, dict):
                await self.process(job)
        return len(jobs)

    async def run(self) -> None:
        poll_seconds = max(2, min(60, int(os.getenv("ACCOUNT_EXPORT_POLL_SECONDS", "10"))))
        try:
            while not self.stopping:
                try:
                    count = await self.batch()
                except asyncio.CancelledError:
                    raise
                except Exception:
                    log.exception("account_export_batch_failed")
                    count = 0
                if count == 0:
                    await asyncio.sleep(poll_seconds)
        finally:
            await self.client.aclose()


def main() -> None:
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO").upper())
    if os.getenv("ALLPHA_ACCOUNT_LIFECYCLE_WORKER_ENABLED", "false").strip().lower() not in _TRUE:
        log.info("account_lifecycle_worker_disabled")
        return
    worker = AccountLifecycleWorker()
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

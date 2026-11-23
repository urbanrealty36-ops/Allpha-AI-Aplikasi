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
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

import httpx

log = logging.getLogger("allpha.account_lifecycle_worker")
_TRUE = {"1", "true", "yes"}
_EXPORT_LEASE_SECONDS = 900
_EXPORT_LEASE_HEARTBEAT_SECONDS = 240
_DELETION_LEASE_SECONDS = 3600
_DELETION_LEASE_HEARTBEAT_SECONDS = 900


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
        self.started_at = datetime.now(timezone.utc).isoformat()
        self.last_poll_at: str | None = None
        self.last_claimed_count = 0
        self.last_cleanup_count = 0
        self.last_deletion_governance_count = 0
        self.last_deletion_execution_count = 0
        self.poll_count = 0
        self.last_error_code: str | None = None
        self.lease_heartbeat_seconds = max(5, min(600, int(os.getenv("ACCOUNT_EXPORT_LEASE_HEARTBEAT_SECONDS", str(_EXPORT_LEASE_HEARTBEAT_SECONDS)))))
        self.deletion_lease_heartbeat_seconds = max(30, min(1800, int(os.getenv("ACCOUNT_DELETION_LEASE_HEARTBEAT_SECONDS", str(_DELETION_LEASE_HEARTBEAT_SECONDS)))))

    async def rpc(self, name: str, payload: dict[str, Any]) -> Any:
        response = await self.client.post(
            f"{self.base}/rest/v1/rpc/{name}",
            json=payload,
        )
        response.raise_for_status()
        return response.json() if response.content else None

    async def set_progress(self, job_id: str, lease_token: str, percent: int, stage: str) -> None:
        updated = await self.rpc(
            "update_account_export_job_progress",
            {
                "p_job_id": job_id,
                "p_lease_token": lease_token,
                "p_progress_percent": percent,
                "p_progress_stage": stage,
            },
        )
        if updated is not True:
            raise RuntimeError("ACCOUNT_EXPORT_PROGRESS_NOT_RECORDED")

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

    async def delete_upload(self, object_path: str) -> None:
        """Remove only this lease's uncommitted export artifact."""
        response = await self.client.request(
            "DELETE",
            f"{self.base}/storage/v1/object/account-exports",
            json={"prefixes": [object_path]},
        )
        if response.status_code == 404:
            return
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
        uploaded_path: str | None = None
        completion_attempted = False
        completion_response_received = False
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

            await self.set_progress(job_id, lease_token, 10, "snapshot")
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
                not isinstance(manifest, list)
                or not isinstance(data, dict)
                or type(source_count) is not int
                or source_count != len(manifest or [])
                or len(source_keys) != len(manifest or [])
                or len(set(source_keys)) != len(source_keys)
                or set(source_keys) != set(data)
            ):
                raise RuntimeError("ACCOUNT_EXPORT_SNAPSHOT_INCOMPLETE")

            await self.set_progress(job_id, lease_token, 50, "compress")
            encoded = json.dumps(
                snapshot,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
            compressed = gzip.compress(encoded, compresslevel=6, mtime=0)
            digest = hashlib.sha256(compressed).hexdigest()
            # A unique path per lease prevents a stale worker from deleting or
            # overwriting the artifact produced by a worker holding a newer lease.
            object_path = f"{user_id}/{job_id}/{lease_token}.json.gz"
            uploaded_path = object_path
            await self.set_progress(job_id, lease_token, 75, "upload")
            await self.upload(object_path, compressed)
            if lease_lost.is_set():
                raise RuntimeError("ACCOUNT_EXPORT_LEASE_LOST")

            await self.set_progress(job_id, lease_token, 90, "publishing")
            completion_attempted = True
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
            completion_response_received = True
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
            # Cleanup is safe before the completion RPC, or after an explicit
            # negative response. A timeout/connection error during completion
            # is ambiguous: the database may have committed, so retain the
            # object rather than risk deleting a completed export.
            if uploaded_path is not None and (
                not completion_attempted or completion_response_received
            ):
                try:
                    await self.delete_upload(uploaded_path)
                except Exception:
                    log.exception("account_export_orphan_cleanup_failed job_id=%s", job_id)
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

    async def cleanup_batch(self) -> int:
        """Expire only artifacts whose approved retention policy has elapsed."""
        if os.getenv("ACCOUNT_EXPORT_CLEANUP_ENABLED", "false").strip().lower() not in {"1", "true", "yes"}:
            return 0
        await self.rpc("enqueue_expired_account_export_artifacts", {})
        jobs = await self.rpc(
            "claim_account_export_artifact_cleanup_jobs",
            {
                "p_worker_id": self.worker_id,
                "p_limit": int(os.getenv("ACCOUNT_EXPORT_CLEANUP_BATCH_SIZE", "10")),
                "p_lease_seconds": 300,
            },
        )
        if not isinstance(jobs, list) or not jobs:
            return 0
        for job in jobs:
            if not isinstance(job, dict):
                continue
            job_id = str(job["id"])
            lease_token = str(job["lease_token"])
            try:
                if job.get("storage_bucket") != "account-exports":
                    raise RuntimeError("ACCOUNT_EXPORT_CLEANUP_BUCKET_INVALID")
                object_path = str(job["storage_path"])
                if not object_path or object_path.startswith("/") or ".." in object_path.split("/"):
                    raise RuntimeError("ACCOUNT_EXPORT_CLEANUP_PATH_INVALID")
                await self.delete_upload(object_path)
                completed = await self.rpc(
                    "complete_account_export_artifact_cleanup_job",
                    {"p_job_id": job_id, "p_lease_token": lease_token},
                )
                if completed is not True:
                    raise RuntimeError("ACCOUNT_EXPORT_CLEANUP_COMPLETION_UNCONFIRMED")
                log.info("account_export_artifact_expired export_job_id=%s", job.get("export_job_id"))
            except Exception as exc:
                log.exception("account_export_artifact_cleanup_failed cleanup_job_id=%s", job_id)
                try:
                    await self.rpc(
                        "fail_account_export_artifact_cleanup_job",
                        {
                            "p_job_id": job_id,
                            "p_lease_token": lease_token,
                            "p_error_code": type(exc).__name__[:80],
                            "p_retry_seconds": min(86400, 30 * (2 ** min(int(job.get("attempts") or 1) - 1, 10))),
                        },
                    )
                except Exception:
                    log.exception("account_export_artifact_cleanup_failure_persist_failed cleanup_job_id=%s", job_id)
        return len(jobs)

    async def delete_storage_object(self, bucket: str, object_path: str) -> None:
        """Delete one explicitly queued object from its canonical Supabase bucket."""
        import re

        if not isinstance(bucket, str) or not re.fullmatch(r"[a-z0-9][a-z0-9._-]{1,62}", bucket):
            raise RuntimeError("ACCOUNT_DELETION_STORAGE_BUCKET_INVALID")
        if (
            not isinstance(object_path, str)
            or not object_path
            or len(object_path) > 1024
            or object_path.startswith("/")
            or "\\" in object_path
            or any(part in {"", ".", ".."} for part in object_path.split("/"))
        ):
            raise RuntimeError("ACCOUNT_DELETION_STORAGE_PATH_INVALID")
        response = await self.client.request(
            "DELETE",
            f"{self.base}/storage/v1/object/{quote(bucket, safe='')}",
            json={"prefixes": [object_path]},
        )
        if response.status_code in (200, 204, 404):
            return
        response.raise_for_status()

    async def _maintain_deletion_lease(
        self,
        job_id: str,
        lease_token: str,
        stop: asyncio.Event,
        lease_lost: asyncio.Event,
    ) -> None:
        while not stop.is_set():
            try:
                await asyncio.wait_for(stop.wait(), timeout=self.deletion_lease_heartbeat_seconds)
                return
            except asyncio.TimeoutError:
                pass
            try:
                renewed = await self.rpc(
                    "renew_account_deletion_execution_job_lease",
                    {
                        "p_job_id": job_id,
                        "p_lease_token": lease_token,
                        "p_lease_seconds": _DELETION_LEASE_SECONDS,
                    },
                )
            except Exception:
                log.exception("account_deletion_lease_heartbeat_failed execution_job_id=%s", job_id)
                lease_lost.set()
                return
            if renewed is not True:
                log.warning("account_deletion_lease_lost execution_job_id=%s", job_id)
                lease_lost.set()
                return

    async def deletion_execution_batch(self) -> int:
        """Prepare and execute only policy-complete, lease-fenced account deletions."""
        if os.getenv("ACCOUNT_DELETION_EXECUTION_ENABLED", "false").strip().lower() not in _TRUE:
            return 0

        prepared = await self.rpc(
            "prepare_account_deletion_execution_batch",
            {"p_limit": int(os.getenv("ACCOUNT_DELETION_PREPARE_BATCH_SIZE", "20"))},
        )
        if not isinstance(prepared, list):
            raise RuntimeError("ACCOUNT_DELETION_PREPARE_RESPONSE_INVALID")

        jobs = await self.rpc(
            "claim_account_deletion_execution_jobs",
            {
                "p_worker_id": self.worker_id,
                "p_limit": int(os.getenv("ACCOUNT_DELETION_EXECUTION_BATCH_SIZE", "2")),
                "p_lease_seconds": _DELETION_LEASE_SECONDS,
            },
        )
        if not isinstance(jobs, list) or not jobs:
            return 0

        processed = 0
        for job in jobs:
            if not isinstance(job, dict):
                continue
            job_id = str(job.get("id") or "")
            lease_token = str(job.get("lease_token") or "")
            if not job_id or not lease_token:
                raise RuntimeError("ACCOUNT_DELETION_EXECUTION_LEASE_INVALID")
            processed += 1
            stop_heartbeat = asyncio.Event()
            lease_lost = asyncio.Event()
            heartbeat_task: asyncio.Task[None] | None = None
            try:
                renewed = await self.rpc(
                    "renew_account_deletion_execution_job_lease",
                    {"p_job_id": job_id, "p_lease_token": lease_token,
                     "p_lease_seconds": _DELETION_LEASE_SECONDS},
                )
                if renewed is not True:
                    log.warning("account_deletion_lease_lost execution_job_id=%s", job_id)
                    continue
                heartbeat_task = asyncio.create_task(
                    self._maintain_deletion_lease(job_id, lease_token, stop_heartbeat, lease_lost)
                )
                # Drain storage jobs in bounded batches. The DB claim RPC rechecks
                # the execution lease and legal holds before issuing each batch.
                while True:
                    storage_jobs = await self.rpc(
                        "claim_account_deletion_storage_jobs",
                        {
                            "p_execution_job_id": job_id,
                            "p_job_lease_token": lease_token,
                            "p_limit": int(os.getenv("ACCOUNT_DELETION_STORAGE_BATCH_SIZE", "50")),
                            "p_lease_seconds": 3600,
                        },
                    )
                    if lease_lost.is_set():
                        raise RuntimeError("ACCOUNT_DELETION_EXECUTION_LEASE_LOST")
                    if not isinstance(storage_jobs, list):
                        raise RuntimeError("ACCOUNT_DELETION_STORAGE_CLAIM_INVALID")
                    if not storage_jobs:
                        break
                    for storage_job in storage_jobs:
                        if not isinstance(storage_job, dict):
                            raise RuntimeError("ACCOUNT_DELETION_STORAGE_JOB_INVALID")
                        storage_job_id = str(storage_job.get("id") or "")
                        storage_lease = str(storage_job.get("lease_token") or "")
                        bucket = storage_job.get("storage_bucket")
                        object_path = storage_job.get("storage_path")
                        if not storage_job_id or not storage_lease:
                            raise RuntimeError("ACCOUNT_DELETION_STORAGE_LEASE_INVALID")
                        try:
                            if lease_lost.is_set():
                                raise RuntimeError("ACCOUNT_DELETION_EXECUTION_LEASE_LOST")
                            await self.delete_storage_object(str(bucket or ""), object_path)
                            if lease_lost.is_set():
                                raise RuntimeError("ACCOUNT_DELETION_EXECUTION_LEASE_LOST")
                            completed = await self.rpc(
                                "complete_account_deletion_storage_job",
                                {"p_job_id": storage_job_id, "p_lease_token": storage_lease},
                            )
                            if completed is not True:
                                raise RuntimeError("ACCOUNT_DELETION_STORAGE_COMPLETION_UNCONFIRMED")
                        except Exception as storage_error:
                            try:
                                await self.rpc(
                                    "fail_account_deletion_storage_job",
                                    {
                                        "p_job_id": storage_job_id,
                                        "p_lease_token": storage_lease,
                                        "p_error_code": type(storage_error).__name__[:80],
                                        "p_retry_seconds": min(
                                            86400,
                                            30 * (2 ** min(int(storage_job.get("attempts") or 1) - 1, 10)),
                                        ),
                                    },
                                )
                            except Exception:
                                log.exception(
                                    "account_deletion_storage_failure_persist_failed storage_job_id=%s",
                                    storage_job_id,
                                )
                            raise

                if lease_lost.is_set():
                    raise RuntimeError("ACCOUNT_DELETION_EXECUTION_LEASE_LOST")
                completed = await self.rpc(
                    "execute_account_deletion_execution_job",
                    {"p_job_id": job_id, "p_lease_token": lease_token},
                )
                if completed is True:
                    log.info("account_deletion_execution_completed execution_job_id=%s", job_id)
                else:
                    # False is an explicit DB outcome (for example, a legal hold
                    # raced with execution); it is not a successful deletion.
                    log.warning("account_deletion_execution_not_completed execution_job_id=%s", job_id)
            except Exception as exc:
                log.exception("account_deletion_execution_failed execution_job_id=%s", job_id)
                try:
                    await self.rpc(
                        "fail_account_deletion_execution_job",
                        {
                            "p_job_id": job_id,
                            "p_lease_token": lease_token,
                            "p_error_code": type(exc).__name__[:80],
                            "p_retry_seconds": min(
                                86400,
                                60 * (2 ** min(int(job.get("attempts") or 1) - 1, 10)),
                            ),
                        },
                    )
                except Exception:
                    log.exception(
                        "account_deletion_execution_failure_persist_failed execution_job_id=%s",
                        job_id,
                    )
            finally:
                stop_heartbeat.set()
                if heartbeat_task is not None:
                    await heartbeat_task
        return processed

    async def deletion_governance_batch(self) -> int:
        """Reconcile legal holds; never execute deletion without complete policy mapping."""
        if os.getenv("ACCOUNT_DELETION_GOVERNANCE_ENABLED", "false").strip().lower() not in {"1", "true", "yes"}:
            return 0
        rows = await self.rpc("evaluate_account_deletion_governance", {
            "p_limit": int(os.getenv("ACCOUNT_DELETION_GOVERNANCE_BATCH_SIZE", "100")),
        })
        if not isinstance(rows, list) or not rows or not isinstance(rows[0], dict):
            return 0
        return int(rows[0].get("processed_count") or 0)

    async def run(self) -> None:
        poll_seconds = max(2, min(60, int(os.getenv("ACCOUNT_EXPORT_POLL_SECONDS", "10"))))
        log.warning("account_lifecycle_worker_started worker_id=%s poll_seconds=%s", self.worker_id, poll_seconds)
        try:
            while not self.stopping:
                try:
                    count = await self.batch()
                    cleanup_count = await self.cleanup_batch()
                    deletion_governance_count = await self.deletion_governance_batch()
                    deletion_execution_count = await self.deletion_execution_batch()
                    self.last_error_code = None
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    self.last_error_code = type(exc).__name__[:80]
                    log.exception("account_export_batch_failed")
                    count = 0
                    cleanup_count = 0
                    deletion_governance_count = 0
                    deletion_execution_count = 0
                self.last_poll_at = datetime.now(timezone.utc).isoformat()
                self.last_claimed_count = count
                self.last_cleanup_count = cleanup_count
                self.last_deletion_governance_count = deletion_governance_count
                self.last_deletion_execution_count = deletion_execution_count
                self.poll_count += 1
                if count == 0 and cleanup_count == 0 and deletion_governance_count == 0 and deletion_execution_count == 0:
                    await asyncio.sleep(poll_seconds)
        finally:
            log.warning(
                "account_lifecycle_worker_stopped worker_id=%s polls=%s",
                self.worker_id,
                self.poll_count,
            )
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

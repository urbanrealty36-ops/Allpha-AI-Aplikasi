"""Lease-based worker for ENG-P07 knowledge embedding jobs.

The deployment supplies a factory only after an approved Model Router policy and
vector persistence implementation exist. Missing configuration fails before any
job is claimed. This module never marks a source retrieval-ready.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import signal
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Protocol

import httpx

from allpha_api.embedding_contract import EmbeddingRequest, EmbeddingResponse
from allpha_api.lease_heartbeat import run_with_lease_heartbeat
from allpha_api.knowledge_vector_store import (
    VectorPersistenceConflict, VectorPersistenceUnavailable,
)
from allpha_api.model_router import (
    CanonicalModelRouter,
    EmbeddingRouter,
    ModelRouterRejected,
    ModelRouterUnavailable,
    route_embedding,
)

log = logging.getLogger("allpha.knowledge_worker")


class WorkerConfigurationError(RuntimeError):
    pass


class KnowledgeJobStore(Protocol):
    async def claim(self, *, lease_seconds: int, stage: str) -> dict[str, Any] | None: ...
    async def heartbeat(self, job: dict[str, Any], *, lease_seconds: int) -> bool: ...
    async def load_source(self, job: dict[str, Any]) -> dict[str, Any] | None: ...
    async def load_chunks(self, job: dict[str, Any]) -> list[dict[str, Any]]: ...
    async def finalize(
        self, job: dict[str, Any], *, outcome: str, stage: str,
        progress: int, error_code: str | None = None, retry_delay_seconds: int = 30
    ) -> bool: ...


VectorSink = Callable[[dict[str, Any], EmbeddingRequest, EmbeddingResponse], Awaitable[None]]


@dataclass
class KnowledgeEmbeddingWorker:
    store: KnowledgeJobStore
    router: EmbeddingRouter
    vector_sink: VectorSink
    lease_seconds: int = 90
    batch_size: int = 64
    request_timeout_ms: int = 30_000

    def __post_init__(self):
        if not 10 <= self.lease_seconds <= 900:
            raise ValueError("lease_seconds must be between 10 and 900")
        if not 1 <= self.batch_size <= 128:
            raise ValueError("batch_size must be between 1 and 128")
        if not 100 <= self.request_timeout_ms <= 120_000:
            raise ValueError("request_timeout_ms must be between 100 and 120000")

    async def process_once(self) -> bool:
        job = await self.store.claim(lease_seconds=self.lease_seconds, stage="embedding_indexing")
        if not job:
            return False
        job_id = str(job.get("id", ""))
        lease_token = str(job.get("lease_token", ""))
        if not job_id or not lease_token:
            # A claimed row without its fencing token cannot safely be finalized.
            log.error("Claim RPC returned job without id/lease token")
            return True
        try:
            lease_active = await run_with_lease_heartbeat(
                lambda: self._process(job),
                lambda: self.store.heartbeat(job, lease_seconds=self.lease_seconds),
                lease_seconds=self.lease_seconds,
                identity=job_id,
            )
            if not lease_active:
                log.warning("Knowledge embedding job %s abandoned after lease loss", job_id)
        except ModelRouterUnavailable:
            await self.store.finalize(
                job, outcome="retry", stage="awaiting_model_router", progress=75,
                error_code="MODEL_ROUTER_UNAVAILABLE", retry_delay_seconds=60,
            )
        except VectorPersistenceUnavailable:
            await self.store.finalize(
                job, outcome="retry", stage="embedding_indexing_retry", progress=75,
                error_code="KNOWLEDGE_VECTOR_STORE_UNAVAILABLE", retry_delay_seconds=60,
            )
        except VectorPersistenceConflict:
            await self.store.finalize(
                job, outcome="failed", stage="embedding_indexing_failed", progress=75,
                error_code="KNOWLEDGE_VECTOR_PERSISTENCE_CONFLICT",
            )
        except ModelRouterRejected as exc:
            retryable = bool(exc.failure.retryable)
            await self.store.finalize(
                job,
                outcome="retry" if retryable else "failed",
                stage="embedding_indexing_failed" if not retryable else "embedding_indexing_retry",
                progress=75,
                error_code=exc.failure.code,
                retry_delay_seconds=max(1, min(300, (exc.failure.retry_after_ms or 1000) // 1000)),
            )
        except WorkerConfigurationError as exc:
            # Configuration/schema prerequisites are not transient provider errors.
            log.warning("Knowledge job %s blocked by configuration: %s", job_id, exc)
            await self.store.finalize(
                job, outcome="failed", stage="embedding_indexing_blocked", progress=75,
                error_code="KNOWLEDGE_WORKER_PREREQUISITE_MISSING",
            )
        except Exception:
            log.exception("Unexpected knowledge embedding worker error for job %s", job_id)
            await self.store.finalize(
                job, outcome="retry", stage="embedding_indexing_retry", progress=75,
                error_code="KNOWLEDGE_WORKER_UNEXPECTED_ERROR", retry_delay_seconds=30,
            )
        return True

    async def _process(self, job: dict[str, Any]) -> None:
        source = await self.store.load_source(job)
        if not source:
            await self.store.finalize(
                job, outcome="failed", stage="source_missing", progress=75,
                error_code="KNOWLEDGE_SOURCE_NOT_FOUND",
            )
            return
        if str(source.get("id")) != str(job.get("source_id")):
            raise WorkerConfigurationError("source identity does not match claimed job")
        if int(source.get("source_version", 0)) != int(job.get("source_version", -1)):
            await self.store.finalize(
                job, outcome="failed", stage="stale_source_version", progress=75,
                error_code="STALE_SOURCE_VERSION",
            )
            return
        sensitivity = source.get("sensitivity") or (source.get("provenance") or {}).get("sensitivity")
        if sensitivity not in {"public", "internal", "confidential", "restricted"}:
            raise WorkerConfigurationError("source sensitivity classification is absent or invalid")
        chunks = await self.store.load_chunks(job)
        if not chunks:
            await self.store.finalize(
                job, outcome="failed", stage="no_chunks", progress=75,
                error_code="KNOWLEDGE_CHUNKS_NOT_FOUND",
            )
            return
        version = int(job["source_version"])
        for start in range(0, len(chunks), self.batch_size):
            batch = chunks[start:start + self.batch_size]
            inputs = []
            for chunk in batch:
                if int(chunk.get("source_version", -1)) != version:
                    raise WorkerConfigurationError("chunk source_version differs from job")
                chunk_text = str(chunk.get("content") or "")
                actual_digest = hashlib.sha256(chunk_text.encode("utf-8")).hexdigest()
                declared_digest = str(chunk.get("content_sha256") or "").lower()
                if not chunk_text or actual_digest != declared_digest:
                    raise WorkerConfigurationError("chunk content hash is absent or does not match stored content")
                inputs.append({
                    "chunk_id": str(chunk["id"]),
                    "content_sha256": actual_digest,
                    "text": chunk_text,
                })
            request = EmbeddingRequest(
                task_id=f"{job['id']}:{start // self.batch_size}",
                idempotency_key=f"knowledge:{job['id']}:v{version}:batch{start // self.batch_size}",
                trace_id=str(job.get("trace_id") or job["id"]),
                owner_id=str(job["owner_id"]),
                agent_id=str(job["agent_id"]),
                source_id=str(job["source_id"]),
                source_version=version,
                sensitivity=sensitivity,
                attempt=max(1, min(8, int(job.get("attempt", 1)))),
                timeout_ms=self.request_timeout_ms,
                chunks=inputs,
            )
            response = await route_embedding(self.router, request)
            # Sink must atomically verify source_version and be idempotent. The
            # database finalizer independently fences stale job completion.
            await self.vector_sink(job, request, response)
        finalized = await self.store.finalize(
            job, outcome="succeeded", stage="embedding_indexed_pending_retrieval_qa",
            progress=95,
        )
        if not finalized:
            log.warning("Job %s lost lease or source version changed during processing", job["id"])


class SupabaseKnowledgeJobStore:
    """Minimal service-role PostgREST/RPC adapter; never used by client code."""
    def __init__(self, *, supabase_url: str, service_key: str):
        if not supabase_url or not service_key:
            raise WorkerConfigurationError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required")
        self.base = supabase_url.rstrip("/")
        self.key = service_key

    def _headers(self) -> dict[str, str]:
        return {"apikey": self.key, "Authorization": f"Bearer {self.key}", "Content-Type": "application/json"}

    async def _request(self, method: str, path: str, *, params=None, body=None):
        async with httpx.AsyncClient(timeout=httpx.Timeout(15, connect=3)) as client:
            response = await client.request(method, f"{self.base}/rest/v1/{path}", headers=self._headers(), params=params, json=body)
        if response.status_code >= 400:
            raise RuntimeError(f"Supabase worker operation failed: {method} {path} ({response.status_code})")
        return response.json() if response.content else None

    async def claim(self, *, lease_seconds: int, stage: str):
        rows = await self._request("POST", "rpc/claim_agent_knowledge_job", body={"p_lease_seconds": lease_seconds, "p_stage": stage})
        return rows[0] if rows else None

    async def heartbeat(self, job, *, lease_seconds: int) -> bool:
        result = await self._request("POST", "rpc/heartbeat_agent_knowledge_job", body={
            "p_job_id": job["id"],
            "p_lease_token": job["lease_token"],
            "p_lease_seconds": lease_seconds,
        })
        return result is True

    async def load_source(self, job):
        rows = await self._request("GET", "agent_knowledge_sources", params={
            "select": "id,agent_id,owner_id,filename,media_type,size_bytes,sha256,storage_path,source_version,status,processing_stage,error_code,provenance,sensitivity",
            "id": f"eq.{job['source_id']}", "owner_id": f"eq.{job['owner_id']}",
            "agent_id": f"eq.{job['agent_id']}", "limit": "1",
        })
        return rows[0] if rows else None

    async def update_source_state(
        self, job, *, status, stage, error_code=None, scanner_receipt=None,
    ) -> bool:
        if status != "processing" or error_code is not None:
            raise WorkerConfigurationError("document source state updates must remain in the fenced processing lifecycle")
        result = await self._request(
            "POST", "rpc/update_agent_knowledge_source_processing_state",
            body={
                "p_job_id": job["id"],
                "p_lease_token": job["lease_token"],
                "p_source_version": job["source_version"],
                "p_stage": stage,
                "p_scanner_receipt": scanner_receipt,
            },
        )
        return result is True

    async def persist_document_chunk_batch(self, job, *, chunks, reset):
        return await self._request("POST", "rpc/persist_agent_knowledge_chunk_batch", body={
            "p_job_id": job["id"], "p_lease_token": job["lease_token"],
            "p_source_version": job["source_version"], "p_reset": reset, "p_chunks": chunks,
        })

    async def complete_document_parse(self, job, *, expected_chunk_count):
        return await self._request("POST", "rpc/complete_agent_knowledge_document_parse", body={
            "p_job_id": job["id"], "p_lease_token": job["lease_token"],
            "p_source_version": job["source_version"], "p_expected_chunk_count": expected_chunk_count,
        })

    async def fail_document_job(self, job, *, error_code, stage, retryable, retry_delay_seconds=30):
        return await self._request("POST", "rpc/fail_agent_knowledge_document_job", body={
            "p_job_id": job["id"], "p_lease_token": job["lease_token"],
            "p_error_code": error_code, "p_stage": stage,
            "p_retryable": retryable, "p_retry_delay_seconds": retry_delay_seconds,
        })

    async def load_chunks(self, job):
        return await self._request("GET", "agent_knowledge_chunks", params={
            "select": "id,content,content_sha256,source_version",
            "source_id": f"eq.{job['source_id']}", "owner_id": f"eq.{job['owner_id']}",
            "agent_id": f"eq.{job['agent_id']}", "source_version": f"eq.{job['source_version']}",
            "order": "chunk_index.asc",
        }) or []

    async def finalize(self, job, *, outcome, stage, progress, error_code=None, retry_delay_seconds=30):
        result = await self._request("POST", "rpc/finalize_agent_knowledge_job", body={
            "p_job_id": job["id"], "p_lease_token": job["lease_token"],
            "p_outcome": outcome, "p_stage": stage, "p_progress": progress,
            "p_error_code": error_code, "p_retry_delay_seconds": retry_delay_seconds,
        })
        return bool(result)


def enabled() -> bool:
    raw = os.getenv("ALLPHA_KNOWLEDGE_EMBEDDING_WORKER_ENABLED", "false").strip().lower()
    if raw not in {"true", "false"}:
        raise SystemExit("ALLPHA_KNOWLEDGE_EMBEDDING_WORKER_ENABLED must be true or false")
    return raw == "true"


async def build_worker_from_environment() -> KnowledgeEmbeddingWorker:
    """Use the canonical Model Router and pgvector repository composition root."""
    from allpha_api.knowledge_worker_factory import build_worker

    worker = await build_worker()
    if not isinstance(worker, KnowledgeEmbeddingWorker):
        raise WorkerConfigurationError("canonical Knowledge worker factory returned an invalid worker")
    return worker


async def run_forever(
    worker: KnowledgeEmbeddingWorker,
    *,
    poll_seconds: float = 2.0,
    stop_event: asyncio.Event | None = None,
) -> None:
    stop = stop_event or asyncio.Event()
    if stop_event is None:
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, stop.set)
            except NotImplementedError:
                pass
    while not stop.is_set():
        try:
            found = await worker.process_once()
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("Knowledge worker polling failed")
            found = False
        if not found and not stop.is_set():
            try:
                await asyncio.wait_for(stop.wait(), timeout=max(0.25, min(poll_seconds, 30)))
            except asyncio.TimeoutError:
                pass


async def serve_enabled(*, stop_event: asyncio.Event) -> None:
    if not enabled():
        return
    worker = await build_worker_from_environment()
    poll_seconds = float(os.getenv("KNOWLEDGE_EMBEDDING_POLL_SECONDS", "2"))
    log.info(
        "Knowledge embedding consumer enabled; poll_seconds=%s batch_size=%s lease_seconds=%s",
        poll_seconds, worker.batch_size, worker.lease_seconds,
    )
    await run_forever(worker, poll_seconds=poll_seconds, stop_event=stop_event)


async def _main() -> None:
    worker = await build_worker_from_environment()
    await run_forever(
        worker, poll_seconds=float(os.getenv("KNOWLEDGE_EMBEDDING_POLL_SECONDS", "2")),
    )


def main() -> None:
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
    asyncio.run(_main())


if __name__ == "__main__":
    main()

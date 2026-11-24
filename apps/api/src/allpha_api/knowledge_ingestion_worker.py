"""Lease-based quarantine scanner and document parser for ENG-P07."""
from __future__ import annotations

import asyncio
import hashlib
import logging
import os
from dataclasses import dataclass
from urllib.parse import quote

import httpx
from fastapi import HTTPException

from allpha_api.knowledge import _chunk, _extract, _scan
from allpha_api.knowledge_worker import SupabaseKnowledgeJobStore, WorkerConfigurationError

log = logging.getLogger(__name__)


class KnowledgeStorageUnavailable(RuntimeError):
    pass


class KnowledgeStorageObjectMissing(RuntimeError):
    pass


@dataclass
class SupabaseKnowledgeStorage:
    supabase_url: str
    service_key: str
    bucket: str = "agent-knowledge"
    timeout_seconds: float = 30.0

    def __post_init__(self) -> None:
        if not self.supabase_url.strip() or not self.service_key.strip():
            raise WorkerConfigurationError("SUPABASE_URL and server-side Supabase key are required")
        if self.bucket != "agent-knowledge":
            raise WorkerConfigurationError("Knowledge worker may access only the canonical agent-knowledge bucket")

    async def download(self, storage_path: str) -> bytes:
        if not storage_path or storage_path.startswith("/") or ".." in storage_path.split("/"):
            raise KnowledgeStorageObjectMissing("Knowledge storage path is invalid")
        url = f"{self.supabase_url.rstrip('/')}/storage/v1/object/{self.bucket}/{quote(storage_path, safe='/')}"
        headers = {"apikey": self.service_key, "Authorization": f"Bearer {self.service_key}"}
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(self.timeout_seconds, connect=4)) as client:
                response = await client.get(url, headers=headers)
        except httpx.HTTPError as exc:
            raise KnowledgeStorageUnavailable("Knowledge Storage request failed") from exc
        if response.status_code == 404:
            raise KnowledgeStorageObjectMissing("Knowledge source object is missing")
        if response.status_code in (408, 425, 429) or response.status_code >= 500:
            raise KnowledgeStorageUnavailable(f"Knowledge Storage returned {response.status_code}")
        if response.status_code != 200:
            raise WorkerConfigurationError(f"Knowledge Storage rejected service access ({response.status_code})")
        return response.content


@dataclass
class KnowledgeDocumentWorker:
    store: SupabaseKnowledgeJobStore
    storage: SupabaseKnowledgeStorage
    lease_seconds: int = 120
    batch_size: int = 50

    def __post_init__(self) -> None:
        if not 10 <= self.lease_seconds <= 900:
            raise ValueError("lease_seconds must be between 10 and 900")
        if not 1 <= self.batch_size <= 100:
            raise ValueError("batch_size must be between 1 and 100")

    async def process_once(self) -> bool:
        job = await self.store.claim(lease_seconds=self.lease_seconds, stage="awaiting_malware_scan")
        if not job:
            return False
        job_id = str(job.get("id", ""))
        if not job_id or not job.get("lease_token"):
            log.error("Knowledge document claim returned a job without lease fencing identity")
            return True
        try:
            await self._process(job)
        except HTTPException as exc:
            detail = exc.detail if isinstance(exc.detail, dict) else {}
            code = str(detail.get("code") or "DOCUMENT_PROCESSING_FAILED")
            retryable = code in {"SCANNER_UNAVAILABLE", "STORAGE_UNAVAILABLE"}
            stage = (
                "malware_scan_retry" if retryable and code.startswith("SCANNER_")
                else "storage_retry" if retryable
                else "malware_scan_failed" if code.startswith("MALWARE_") or code.startswith("SCANNER_")
                else "document_parse_failed"
            )
            await self._fail(job, code, stage, retryable, 60 if retryable else 0)
        except KnowledgeStorageObjectMissing:
            await self._fail(job, "KNOWLEDGE_STORAGE_OBJECT_MISSING", "document_parse_failed", False, 0)
        except KnowledgeStorageUnavailable:
            await self._fail(job, "STORAGE_UNAVAILABLE", "storage_retry", True, 60)
        except WorkerConfigurationError as exc:
            log.error("Knowledge document job %s blocked by configuration: %s", job_id, exc)
            await self._fail(job, "KNOWLEDGE_WORKER_CONFIGURATION_INVALID", "document_worker_failed", False, 0)
        except Exception:
            log.exception("Unexpected Knowledge document worker error for job %s", job_id)
            await self._fail(job, "KNOWLEDGE_DOCUMENT_WORKER_UNEXPECTED", "document_worker_failed", True, 30)
        return True

    async def _process(self, job: dict) -> None:
        source = await self.store.load_source(job)
        if not source:
            await self._fail(job, "KNOWLEDGE_SOURCE_NOT_FOUND", "document_parse_failed", False, 0)
            return
        if str(source.get("id")) != str(job.get("source_id")):
            raise WorkerConfigurationError("source identity does not match the leased job")
        if int(source.get("source_version", 0)) != int(job.get("source_version", -1)):
            await self._fail(job, "STALE_SOURCE_VERSION", "document_parse_failed", False, 0)
            return
        sensitivity = source.get("sensitivity") or (source.get("provenance") or {}).get("sensitivity")
        if sensitivity not in {"public", "internal", "confidential", "restricted"}:
            await self._fail(job, "SENSITIVITY_CLASSIFICATION_REQUIRED", "document_parse_failed", False, 0)
            return

        await self.store.update_source_state(job, status="processing", stage="malware_scan", error_code=None)
        data = await self.storage.download(str(source.get("storage_path") or ""))
        expected_sha = str(source.get("sha256") or "").lower()
        expected_size = int(source.get("size_bytes") or 0)
        if expected_size <= 0 or expected_size > 15 * 1024 * 1024 or len(data) != expected_size:
            await self._fail(job, "KNOWLEDGE_SOURCE_SIZE_MISMATCH", "document_parse_failed", False, 0)
            return
        if not expected_sha or hashlib.sha256(data).hexdigest() != expected_sha:
            await self._fail(job, "KNOWLEDGE_SOURCE_SHA256_MISMATCH", "document_parse_failed", False, 0)
            return

        await _scan(data, str(source["filename"]), str(source["media_type"]))
        await self.store.update_source_state(job, status="processing", stage="document_parsing", error_code=None)
        pages = _extract(str(source["filename"]), data)
        chunks = _chunk(pages)
        if not chunks:
            await self._fail(job, "NO_TEXT_EXTRACTED", "document_parse_failed", False, 0)
            return

        await self.store.update_source_state(job, status="processing", stage="chunk_persistence", error_code=None)
        total = 0
        for start in range(0, len(chunks), self.batch_size):
            batch = [
                {
                    "chunk_index": start + index,
                    "content": item["content"],
                    "source_location": item["source_location"],
                    "content_sha256": hashlib.sha256(item["content"].encode("utf-8")).hexdigest(),
                }
                for index, item in enumerate(chunks[start:start + self.batch_size])
            ]
            persisted = await self.store.persist_document_chunk_batch(job, chunks=batch, reset=(start == 0))
            total += int(persisted or 0)
        if total != len(chunks):
            raise WorkerConfigurationError("persisted Knowledge chunk count differs from parser output")
        completed = await self.store.complete_document_parse(job, expected_chunk_count=total)
        if not isinstance(completed, dict) or int(completed.get("chunks_created", -1)) != total:
            raise WorkerConfigurationError("atomic Knowledge parse completion did not confirm all chunks")
        log.info(
            "Knowledge document job %s extracted %s chunks; embedding job %s queued",
            job["id"], total, completed.get("embedding_job_id"),
        )

    async def _fail(self, job: dict, code: str, stage: str, retryable: bool, delay: int) -> None:
        try:
            outcome = await self.store.fail_document_job(
                job, error_code=code, stage=stage, retryable=retryable,
                retry_delay_seconds=delay,
            )
            if outcome == "lease_lost":
                log.warning("Knowledge document job %s lost its lease before failure finalization", job.get("id"))
            else:
                log.info("Knowledge document job %s finalized as %s (%s)", job.get("id"), outcome, code)
        except Exception:
            log.exception("Could not persist failure state for Knowledge document job %s", job.get("id"))


async def run_forever(worker: KnowledgeDocumentWorker, *, poll_seconds: float = 2.0) -> None:
    while True:
        try:
            worked = await worker.process_once()
        except Exception:
            log.exception("Knowledge document worker poll failed")
            worked = False
        if not worked:
            await asyncio.sleep(max(0.25, min(poll_seconds, 30.0)))


def main() -> None:
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
    supabase_url = os.getenv("SUPABASE_URL", "").strip()
    service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip() or os.getenv("SUPABASE_SECRET_KEY", "").strip()
    scanner_url = os.getenv("ALLPHA_DOCUMENT_SCANNER_URL", "").strip()
    if not supabase_url or not service_key:
        raise SystemExit("Knowledge document worker disabled: server-side Supabase credentials are required")
    if not scanner_url:
        raise SystemExit("Knowledge document worker disabled: ALLPHA_DOCUMENT_SCANNER_URL is required; quarantined files remain queued")
    store = SupabaseKnowledgeJobStore(supabase_url=supabase_url, service_key=service_key)
    storage = SupabaseKnowledgeStorage(supabase_url=supabase_url, service_key=service_key)
    worker = KnowledgeDocumentWorker(
        store=store,
        storage=storage,
        lease_seconds=int(os.getenv("KNOWLEDGE_DOCUMENT_LEASE_SECONDS", "120")),
        batch_size=int(os.getenv("KNOWLEDGE_DOCUMENT_BATCH_SIZE", "50")),
    )
    asyncio.run(run_forever(worker, poll_seconds=float(os.getenv("KNOWLEDGE_DOCUMENT_POLL_SECONDS", "2"))))


if __name__ == "__main__":
    main()

"""Lease-based quarantine scanner and document parser for ENG-P07."""
from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import shutil
import subprocess
from dataclasses import dataclass
from urllib.parse import quote

import httpx
from fastapi import HTTPException

from allpha_api.document_scanner import DocumentScannerConfigurationError, RemoteDocumentScanner
from allpha_api.knowledge import _chunk, _extract, _scan
from allpha_api.knowledge_policy import KNOWLEDGE_INGESTION_PURPOSE, KnowledgePolicyDenied, KnowledgePolicyUnavailable, VersionedKnowledgePolicyResolver, load_policy_resolver_from_environment
from allpha_api.knowledge_worker import SupabaseKnowledgeJobStore, WorkerConfigurationError
from allpha_api.lease_heartbeat import run_with_lease_heartbeat

log = logging.getLogger(__name__)


class KnowledgeJobLeaseLost(RuntimeError):
    """The current document job no longer owns the source-state lease."""


class KnowledgeStorageUnavailable(RuntimeError):
    pass


class KnowledgeStorageObjectMissing(RuntimeError):
    pass


class KnowledgeStorageObjectTooLarge(RuntimeError):
    pass


class KnowledgeStorageIdentityMismatch(RuntimeError):
    """A persisted object path does not belong to the leased owner/Agent/source."""
    pass


def _validate_source_storage_identity(source: dict, job: dict) -> str:
    """Bind privileged Storage reads to the exact owner/Agent/source tuple.

    Uploads use the canonical object key:
      <owner UUID>/<agent UUID>/<source UUID>/<filename>
    A service-role worker must not trust a database storage_path blindly.
    """
    import uuid

    def canonical_uuid(value: object, label: str) -> str:
        if not isinstance(value, str):
            raise KnowledgeStorageIdentityMismatch(f"{label} identity is missing")
        try:
            canonical = str(uuid.UUID(value))
        except (ValueError, TypeError, AttributeError) as exc:
            raise KnowledgeStorageIdentityMismatch(f"{label} identity is invalid") from exc
        if value.lower() != canonical:
            raise KnowledgeStorageIdentityMismatch(f"{label} identity is not canonical")
        return canonical

    owner_id = canonical_uuid(job.get("owner_id"), "job owner")
    agent_id = canonical_uuid(job.get("agent_id"), "job Agent")
    source_id = canonical_uuid(job.get("source_id"), "job source")
    if canonical_uuid(source.get("owner_id"), "source owner") != owner_id:
        raise KnowledgeStorageIdentityMismatch("source owner does not match the leased job")
    if canonical_uuid(source.get("agent_id"), "source Agent") != agent_id:
        raise KnowledgeStorageIdentityMismatch("source Agent does not match the leased job")
    if canonical_uuid(source.get("id"), "source") != source_id:
        raise KnowledgeStorageIdentityMismatch("source ID does not match the leased job")

    filename = source.get("filename")
    if (
        not isinstance(filename, str)
        or not filename
        or filename in {".", ".."}
        or "/" in filename
        or "\\" in filename
        or any(ord(char) < 32 or ord(char) == 127 for char in filename)
    ):
        raise KnowledgeStorageIdentityMismatch("source filename is not a safe object-key segment")
    expected_path = f"{owner_id}/{agent_id}/{source_id}/{filename}"
    if source.get("storage_path") != expected_path:
        raise KnowledgeStorageIdentityMismatch("Storage object key is not bound to the leased owner/Agent/source")
    return expected_path


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
        headers["Accept-Encoding"] = "identity"
        chunks: list[bytes] = []
        total = 0
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout_seconds, connect=4),
                follow_redirects=False,
                trust_env=False,
            ) as client:
                async with client.stream("GET", url, headers=headers) as response:
                    if response.status_code == 404:
                        raise KnowledgeStorageObjectMissing("Knowledge source object is missing")
                    if response.status_code in (408, 425, 429) or response.status_code >= 500:
                        raise KnowledgeStorageUnavailable(f"Knowledge Storage returned {response.status_code}")
                    if response.status_code != 200:
                        raise WorkerConfigurationError(
                            f"Knowledge Storage rejected service access ({response.status_code})"
                        )
                    declared = response.headers.get("content-length")
                    if declared is not None and (
                        not declared.isdigit() or int(declared) > 15 * 1024 * 1024
                    ):
                        raise KnowledgeStorageObjectTooLarge("Knowledge source object exceeds the 15 MiB limit")
                    async for chunk in response.aiter_bytes():
                        total += len(chunk)
                        if total > 15 * 1024 * 1024:
                            raise KnowledgeStorageObjectTooLarge(
                                "Knowledge source object exceeds the 15 MiB limit"
                            )
                        chunks.append(chunk)
        except (KnowledgeStorageObjectMissing, KnowledgeStorageObjectTooLarge,
                KnowledgeStorageUnavailable, WorkerConfigurationError):
            raise
        except httpx.HTTPError as exc:
            raise KnowledgeStorageUnavailable("Knowledge Storage request failed") from exc
        return b"".join(chunks)


@dataclass
class KnowledgeDocumentWorker:
    store: SupabaseKnowledgeJobStore
    storage: SupabaseKnowledgeStorage
    lease_seconds: int = 120
    batch_size: int = 50
    policy_resolver: VersionedKnowledgePolicyResolver | None = None

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
            lease_active = await run_with_lease_heartbeat(
                lambda: self._process(job),
                lambda: self.store.heartbeat(job, lease_seconds=self.lease_seconds),
                lease_seconds=self.lease_seconds,
                identity=job_id,
            )
            if not lease_active:
                log.warning("Knowledge document job %s abandoned after lease loss", job_id)
        except KnowledgeJobLeaseLost:
            log.warning("Knowledge document job %s abandoned after source-state lease loss", job_id)
        except KnowledgePolicyDenied:
            await self._fail(job, "KNOWLEDGE_CONSENT_OR_GRANT_REVOKED", "knowledge_policy_denied", False, 0)
        except KnowledgePolicyUnavailable:
            await self._fail(job, "KNOWLEDGE_POLICY_UNAVAILABLE", "knowledge_policy_retry", True, 60)
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
        except KnowledgeStorageObjectTooLarge:
            await self._fail(job, "KNOWLEDGE_STORAGE_OBJECT_TOO_LARGE", "document_parse_failed", False, 0)
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
        try:
            storage_path = _validate_source_storage_identity(source, job)
        except KnowledgeStorageIdentityMismatch:
            await self._fail(job, "KNOWLEDGE_STORAGE_PATH_IDENTITY_MISMATCH", "document_parse_failed", False, 0)
            return
        if int(source.get("source_version", 0)) != int(job.get("source_version", -1)):
            await self._fail(job, "STALE_SOURCE_VERSION", "document_parse_failed", False, 0)
            return
        sensitivity = source.get("sensitivity") or (source.get("provenance") or {}).get("sensitivity")
        if sensitivity not in {"public", "internal", "confidential", "restricted"}:
            await self._fail(job, "SENSITIVITY_CLASSIFICATION_REQUIRED", "document_parse_failed", False, 0)
            return
        if self.policy_resolver is None:
            raise WorkerConfigurationError("canonical Knowledge consent/source-grant resolver is not configured")
        await self.policy_resolver.authorize_source(owner_id=str(job["owner_id"]), agent_id=str(job["agent_id"]), source_id=str(source["id"]), sensitivity=str(sensitivity), purpose=KNOWLEDGE_INGESTION_PURPOSE)

        await self._set_processing_state(job, stage="malware_scan")
        data = await self.storage.download(storage_path)
        expected_sha = str(source.get("sha256") or "").lower()
        expected_size = int(source.get("size_bytes") or 0)
        if expected_size <= 0 or expected_size > 15 * 1024 * 1024 or len(data) != expected_size:
            await self._fail(job, "KNOWLEDGE_SOURCE_SIZE_MISMATCH", "document_parse_failed", False, 0)
            return
        if not expected_sha or hashlib.sha256(data).hexdigest() != expected_sha:
            await self._fail(job, "KNOWLEDGE_SOURCE_SHA256_MISMATCH", "document_parse_failed", False, 0)
            return

        scanner_receipt = await _scan(data, str(source["filename"]), str(source["media_type"]))
        await self._set_processing_state(
            job, stage="document_parsing", scanner_receipt=scanner_receipt,
        )
        pages = _extract(str(source["filename"]), data)
        chunks = _chunk(pages)
        if not chunks:
            await self._fail(job, "NO_TEXT_EXTRACTED", "document_parse_failed", False, 0)
            return

        await self._set_processing_state(job, stage="chunk_persistence")
        total = 0
        for start in range(0, len(chunks), self.batch_size):
            await self.policy_resolver.authorize_source(owner_id=str(job["owner_id"]), agent_id=str(job["agent_id"]), source_id=str(source["id"]), sensitivity=str(sensitivity), purpose=KNOWLEDGE_INGESTION_PURPOSE)
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
        await self.policy_resolver.authorize_source(owner_id=str(job["owner_id"]), agent_id=str(job["agent_id"]), source_id=str(source["id"]), sensitivity=str(sensitivity), purpose=KNOWLEDGE_INGESTION_PURPOSE)
        completed = await self.store.complete_document_parse(job, expected_chunk_count=total)
        if not isinstance(completed, dict) or int(completed.get("chunks_created", -1)) != total:
            raise WorkerConfigurationError("atomic Knowledge parse completion did not confirm all chunks")
        log.info(
            "Knowledge document job %s extracted %s chunks; embedding job %s queued",
            job["id"], total, completed.get("embedding_job_id"),
        )

    async def _set_processing_state(
        self, job: dict, *, stage: str, scanner_receipt: dict | None = None,
    ) -> None:
        updated = await self.store.update_source_state(
            job, status="processing", stage=stage, error_code=None,
            scanner_receipt=scanner_receipt,
        )
        if updated is False:
            raise KnowledgeJobLeaseLost("document source-state update rejected the current lease")

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


async def run_forever(
    worker: KnowledgeDocumentWorker,
    *,
    poll_seconds: float = 2.0,
    stop_event: asyncio.Event | None = None,
) -> None:
    stop = stop_event or asyncio.Event()
    interval = max(0.25, min(poll_seconds, 30.0))
    while not stop.is_set():
        try:
            worked = await worker.process_once()
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("Knowledge document worker poll failed")
            worked = False
        if not worked and not stop.is_set():
            try:
                await asyncio.wait_for(stop.wait(), timeout=interval)
            except asyncio.TimeoutError:
                pass


def enabled() -> bool:
    raw = os.getenv("ALLPHA_KNOWLEDGE_DOCUMENT_WORKER_ENABLED", "false").strip().lower()
    if raw not in {"true", "false"}:
        raise SystemExit("ALLPHA_KNOWLEDGE_DOCUMENT_WORKER_ENABLED must be true or false")
    return raw == "true"


def build_worker_from_environment() -> KnowledgeDocumentWorker:
    supabase_url = os.getenv("SUPABASE_URL", "").strip()
    service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip() or os.getenv("SUPABASE_SECRET_KEY", "").strip()
    scanner_url = os.getenv("ALLPHA_DOCUMENT_SCANNER_URL", "").strip()
    scanner_mode = os.getenv("ALLPHA_DOCUMENT_SCANNER_MODE", "").strip().lower()
    if not supabase_url or not service_key:
        raise SystemExit("Knowledge document worker disabled: server-side Supabase credentials are required")
    policy_resolver = load_policy_resolver_from_environment()
    if policy_resolver is None:
        raise SystemExit("Knowledge document worker disabled: canonical Knowledge consent/source-grant provider is required")
    if not scanner_url and scanner_mode != "clamd":
        raise SystemExit("Knowledge document worker disabled: configure ALLPHA_DOCUMENT_SCANNER_URL or local ALLPHA_DOCUMENT_SCANNER_MODE=clamd")
    if scanner_url:
        # Startup is gated on a *valid* remote scanner (HTTPS, allowlisted host,
        # credential present), not merely a non-empty URL. Invalid config keeps the
        # document consumer off so every source stays quarantined.
        try:
            RemoteDocumentScanner.from_environment()
        except DocumentScannerConfigurationError as exc:
            raise SystemExit(f"Knowledge document worker disabled: invalid remote scanner configuration ({exc})") from exc
    if not scanner_url and scanner_mode == "clamd":
        scanner = shutil.which("clamdscan")
        if not scanner:
            raise SystemExit("Knowledge document worker disabled: clamdscan binary is missing")
        try:
            probe = subprocess.run([scanner, "--ping=1"], capture_output=True, timeout=6, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise SystemExit("Knowledge document worker disabled: local ClamAV daemon is unavailable") from exc
        if probe.returncode != 0:
            raise SystemExit("Knowledge document worker disabled: local ClamAV daemon did not answer its health probe")
    store = SupabaseKnowledgeJobStore(supabase_url=supabase_url, service_key=service_key)
    storage = SupabaseKnowledgeStorage(supabase_url=supabase_url, service_key=service_key)
    return KnowledgeDocumentWorker(
        store=store,
        storage=storage,
        lease_seconds=int(os.getenv("KNOWLEDGE_DOCUMENT_LEASE_SECONDS", "120")),
        batch_size=int(os.getenv("KNOWLEDGE_DOCUMENT_BATCH_SIZE", "50")),
        policy_resolver=policy_resolver,
    )


async def serve_enabled(*, stop_event: asyncio.Event) -> None:
    if not enabled():
        return
    worker = build_worker_from_environment()
    poll_seconds = float(os.getenv("KNOWLEDGE_DOCUMENT_POLL_SECONDS", "2"))
    log.info(
        "Knowledge document consumer enabled; poll_seconds=%s batch_size=%s lease_seconds=%s",
        poll_seconds, worker.batch_size, worker.lease_seconds,
    )
    await run_forever(worker, poll_seconds=poll_seconds, stop_event=stop_event)


def main() -> None:
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
    if not enabled():
        log.info("Knowledge document consumer disabled; no jobs will be claimed")
        return
    worker = build_worker_from_environment()
    asyncio.run(run_forever(worker, poll_seconds=float(os.getenv("KNOWLEDGE_DOCUMENT_POLL_SECONDS", "2"))))


if __name__ == "__main__":
    main()

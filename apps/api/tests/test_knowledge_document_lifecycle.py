"""Lease, stale-version, idempotency and error-state tests for the document worker."""
import asyncio
import hashlib

from fastapi import HTTPException

from allpha_api.knowledge_ingestion_worker import KnowledgeDocumentWorker
from tests.test_knowledge_ingestion_worker import DATA, FakeStorage, FakeStore

MOD = "allpha_api.knowledge_ingestion_worker"
RECEIPT = {
    "scanner_id": "s", "engine_version": "1", "signature_version": "1",
    "sha256": hashlib.sha256(DATA).hexdigest(), "contract_version": "allpha.document-scan.v1",
}


def patch_clean(monkeypatch, pages=None):
    async def clean(*a):
        return RECEIPT

    monkeypatch.setattr(f"{MOD}._scan", clean)
    monkeypatch.setattr(
        f"{MOD}._extract",
        lambda f, d: pages if pages is not None else [{"text": "t", "location": {"kind": "page", "index": 1}}],
    )


class SingleClaimStore(FakeStore):
    """Claim is atomic: exactly one concurrent worker receives the job."""

    def __init__(self):
        super().__init__()
        self.claim_calls = 0
        self.chunk_writes = 0

    async def claim(self, *, lease_seconds, stage):
        self.claim_calls += 1
        await asyncio.sleep(0)
        return await super().claim(lease_seconds=lease_seconds, stage=stage)

    async def persist_document_chunk_batch(self, job, *, chunks, reset):
        self.chunk_writes += 1
        return await super().persist_document_chunk_batch(job, chunks=chunks, reset=reset)


def test_concurrent_workers_process_a_claimed_job_exactly_once(monkeypatch):
    patch_clean(monkeypatch)
    store = SingleClaimStore()
    workers = [KnowledgeDocumentWorker(store=store, storage=FakeStorage()) for _ in range(5)]

    async def scenario():
        return await asyncio.gather(*(w.process_once() for w in workers))

    results = asyncio.run(scenario())
    assert sorted(results) == [False, False, False, False, True]
    assert store.claim_calls == 5
    assert store.chunk_writes == 1 and store.completed == [1] and store.failures == []


def test_redelivery_after_completion_finds_nothing_to_do(monkeypatch):
    patch_clean(monkeypatch)
    store = SingleClaimStore()
    worker = KnowledgeDocumentWorker(store=store, storage=FakeStorage())
    assert asyncio.run(worker.process_once()) is True
    assert asyncio.run(worker.process_once()) is False
    assert store.completed == [1]


def test_stale_source_version_is_terminal_and_never_scanned(monkeypatch):
    store = FakeStore()
    original = store.load_source

    async def newer(job):
        return {**await original(job), "source_version": 2}

    store.load_source = newer

    async def never(*a):
        raise AssertionError("stale version must not be scanned")

    monkeypatch.setattr(f"{MOD}._scan", never)
    worker = KnowledgeDocumentWorker(store=store, storage=FakeStorage())
    asyncio.run(worker.process_once())
    assert store.failures == [("STALE_SOURCE_VERSION", "document_parse_failed", False, 0)]
    assert store.states == [] and store.batches == []


def test_missing_source_is_terminal(monkeypatch):
    store = FakeStore()

    async def gone(job):
        return None

    store.load_source = gone
    asyncio.run(KnowledgeDocumentWorker(store=store, storage=FakeStorage()).process_once())
    assert store.failures == [("KNOWLEDGE_SOURCE_NOT_FOUND", "document_parse_failed", False, 0)]


def test_missing_sensitivity_blocks_processing_before_any_scan(monkeypatch):
    store = FakeStore()
    original = store.load_source

    async def unclassified(job):
        return {**await original(job), "sensitivity": None, "provenance": {}}

    store.load_source = unclassified
    asyncio.run(KnowledgeDocumentWorker(store=store, storage=FakeStorage()).process_once())
    assert store.failures == [("SENSITIVITY_CLASSIFICATION_REQUIRED", "document_parse_failed", False, 0)]
    assert store.states == []


def test_malware_verdict_is_terminal_and_not_retried(monkeypatch):
    async def malicious(*a):
        raise HTTPException(422, detail={"code": "MALWARE_SCAN_REJECTED"})

    monkeypatch.setattr(f"{MOD}._scan", malicious)
    store = FakeStore()
    asyncio.run(KnowledgeDocumentWorker(store=store, storage=FakeStorage()).process_once())
    assert store.failures == [("MALWARE_SCAN_REJECTED", "malware_scan_failed", False, 0)]
    assert store.batches == [] and store.completed == []


def test_unconfigured_scanner_never_reaches_parser_or_chunks(monkeypatch):
    async def missing(*a):
        raise HTTPException(503, detail={"code": "SCANNER_NOT_CONFIGURED"})

    monkeypatch.setattr(f"{MOD}._scan", missing)
    monkeypatch.setattr(f"{MOD}._extract", lambda *a: (_ for _ in ()).throw(AssertionError("parsed")))
    store = FakeStore()
    asyncio.run(KnowledgeDocumentWorker(store=store, storage=FakeStorage()).process_once())
    assert len(store.failures) == 1 and store.failures[0][0] == "SCANNER_NOT_CONFIGURED"
    assert all(state[1] != "document_parsing" for state in store.states)
    assert store.batches == [] and store.completed == []


def test_parse_error_and_empty_text_are_terminal_parse_failures(monkeypatch):
    patch_clean(monkeypatch)

    def bad(filename, data):
        raise HTTPException(422, detail={"code": "DOCUMENT_PARSER_TIMEOUT"})

    monkeypatch.setattr(f"{MOD}._extract", bad)
    store = FakeStore()
    asyncio.run(KnowledgeDocumentWorker(store=store, storage=FakeStorage()).process_once())
    assert store.failures == [("DOCUMENT_PARSER_TIMEOUT", "document_parse_failed", False, 0)]

    patch_clean(monkeypatch, pages=[])
    store = FakeStore()
    asyncio.run(KnowledgeDocumentWorker(store=store, storage=FakeStorage()).process_once())
    assert store.failures == [("NO_TEXT_EXTRACTED", "document_parse_failed", False, 0)]
    assert store.completed == []


def test_lease_lost_between_stages_stops_before_chunk_persistence(monkeypatch):
    patch_clean(monkeypatch)
    store = FakeStore()
    seen = []

    async def fenced(job, *, status, stage, error_code=None, scanner_receipt=None):
        seen.append(stage)
        return stage != "chunk_persistence"  # lease expires right before chunk write

    store.update_source_state = fenced
    asyncio.run(KnowledgeDocumentWorker(store=store, storage=FakeStorage()).process_once())
    assert seen == ["malware_scan", "document_parsing", "chunk_persistence"]
    assert store.batches == [] and store.completed == [] and store.failures == []


def test_handoff_count_mismatch_is_not_reported_as_success(monkeypatch):
    patch_clean(monkeypatch)
    store = FakeStore()

    async def short(job, *, expected_chunk_count):
        return {"chunks_created": expected_chunk_count - 1}

    store.complete_document_parse = short
    asyncio.run(KnowledgeDocumentWorker(store=store, storage=FakeStorage()).process_once())
    assert store.failures and store.failures[0][0] == "KNOWLEDGE_WORKER_CONFIGURATION_INVALID"


def test_storage_object_missing_and_unavailable_map_to_terminal_and_retry(monkeypatch):
    from allpha_api.knowledge_ingestion_worker import KnowledgeStorageObjectMissing, KnowledgeStorageUnavailable

    for exc, expected in (
        (KnowledgeStorageObjectMissing(), ("KNOWLEDGE_STORAGE_OBJECT_MISSING", "document_parse_failed", False, 0)),
        (KnowledgeStorageUnavailable(), ("STORAGE_UNAVAILABLE", "storage_retry", True, 60)),
    ):
        class Storage:
            async def download(self, path, exc=exc):
                raise exc

        store = FakeStore()
        asyncio.run(KnowledgeDocumentWorker(store=store, storage=Storage()).process_once())
        assert store.failures == [expected]


def test_failure_finalization_lease_loss_is_logged_not_raised():
    store = FakeStore()

    async def lost(job, **kw):
        return "lease_lost"

    store.fail_document_job = lost

    async def missing(job):
        return None

    store.load_source = missing
    assert asyncio.run(KnowledgeDocumentWorker(store=store, storage=FakeStorage()).process_once()) is True

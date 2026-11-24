import asyncio
import hashlib

from fastapi import HTTPException

from allpha_api.knowledge_ingestion_worker import KnowledgeDocumentWorker, main
from knowledge_worker_fakes import DATA, FakeStorage, FakeStore


def test_document_worker_scans_parses_persists_and_atomically_hands_off_embedding(monkeypatch):
    store=FakeStore()
    receipt = {
        "scanner_id": "scanner-prod-1", "engine_version": "1.4.6",
        "signature_version": "2026-11-24", "sha256": hashlib.sha256(DATA).hexdigest(),
        "contract_version": "allpha.document-scan.v1",
    }
    async def clean_scan(data,filename,media_type):
        assert data==DATA and filename=="notes.txt" and media_type=="text/plain"
        return receipt
    monkeypatch.setattr("allpha_api.knowledge_ingestion_worker._scan",clean_scan)
    monkeypatch.setattr("allpha_api.knowledge_ingestion_worker._extract",
        lambda filename,data:[{"text":"knowledge text","location":{"kind":"page","index":1}}])
    worker=KnowledgeDocumentWorker(store=store,storage=FakeStorage(),batch_size=1)
    assert asyncio.run(worker.process_once()) is True
    assert store.states == [
        ("processing", "malware_scan", None, None),
        ("processing", "document_parsing", None, receipt),
        ("processing", "chunk_persistence", None, None),
    ]
    assert len(store.batches)==1 and store.batches[0][1] is True
    assert store.batches[0][0][0]["content"]=="knowledge text"
    assert store.completed==[1]
    assert store.failures==[]


def test_document_worker_rejects_storage_hash_mismatch_before_parser(monkeypatch):
    store=FakeStore()
    async def clean_scan(*args):raise AssertionError("malware scan must not run after hash mismatch")
    monkeypatch.setattr("allpha_api.knowledge_ingestion_worker._scan",clean_scan)
    worker=KnowledgeDocumentWorker(store=store,storage=FakeStorage(b"tampered"))
    assert asyncio.run(worker.process_once()) is True
    assert store.failures==[("KNOWLEDGE_SOURCE_SIZE_MISMATCH","document_parse_failed",False,0)] or store.failures==[("KNOWLEDGE_SOURCE_SHA256_MISMATCH","document_parse_failed",False,0)]
    assert store.batches==[] and store.completed==[]


def test_document_worker_retries_transient_scanner_unavailability(monkeypatch):
    store=FakeStore()
    async def unavailable(*args):
        raise HTTPException(status_code=503,detail={"code":"SCANNER_UNAVAILABLE","message":"scanner down"})
    monkeypatch.setattr("allpha_api.knowledge_ingestion_worker._scan",unavailable)
    worker=KnowledgeDocumentWorker(store=store,storage=FakeStorage())
    assert asyncio.run(worker.process_once()) is True
    assert store.failures==[("SCANNER_UNAVAILABLE","malware_scan_retry",True,60)]
    assert store.batches==[] and store.completed==[]



def test_document_worker_abandons_source_transition_when_job_lease_is_lost(monkeypatch):
    store = FakeStore()

    async def rejected_state_update(job, *, status, stage, error_code=None, scanner_receipt=None):
        return False

    store.update_source_state = rejected_state_update

    async def clean_scan(*args):
        raise AssertionError("scanner must not run after the lease-fenced stage update fails")

    monkeypatch.setattr("allpha_api.knowledge_ingestion_worker._scan", clean_scan)
    worker = KnowledgeDocumentWorker(store=store, storage=FakeStorage())
    assert asyncio.run(worker.process_once()) is True
    assert store.failures == []
    assert store.batches == []
    assert store.completed == []


def test_document_worker_entrypoint_respects_disabled_consumer_flag(monkeypatch):
    monkeypatch.setenv("ALLPHA_KNOWLEDGE_DOCUMENT_WORKER_ENABLED", "false")

    def fail_if_built():
        raise AssertionError("disabled Knowledge consumer must not build or poll the worker")

    monkeypatch.setattr(
        "allpha_api.knowledge_ingestion_worker.build_worker_from_environment",
        fail_if_built,
    )
    main()

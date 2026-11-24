import asyncio
import hashlib

import pytest
from fastapi import HTTPException

from allpha_api.knowledge_ingestion_worker import KnowledgeDocumentWorker


OWNER="11111111-1111-4111-8111-111111111111"
AGENT="22222222-2222-4222-8222-222222222222"
SOURCE="33333333-3333-4333-8333-333333333333"
JOB="44444444-4444-4444-8444-444444444444"
LEASE="55555555-5555-4555-8555-555555555555"
DATA=b"Private knowledge source"


class FakeStore:
    def __init__(self, data=DATA):
        self.data=data
        self.claimed=False
        self.states=[]
        self.batches=[]
        self.completed=[]
        self.failures=[]
    async def claim(self, *, lease_seconds, stage):
        assert stage=="awaiting_malware_scan"
        if self.claimed:return None
        self.claimed=True
        return {"id":JOB,"source_id":SOURCE,"agent_id":AGENT,"owner_id":OWNER,
                "source_version":1,"lease_token":LEASE,"attempt":1,"stage":stage}
    async def load_source(self, job):
        return {"id":SOURCE,"agent_id":AGENT,"owner_id":OWNER,"filename":"notes.txt",
                "media_type":"text/plain","size_bytes":len(self.data),
                "sha256":hashlib.sha256(self.data).hexdigest(),"storage_path":f"{OWNER}/{AGENT}/{SOURCE}/notes.txt",
                "source_version":1,"status":"quarantined","sensitivity":"internal",
                "provenance":{"sensitivity":"internal"}}
    async def update_source_state(self, job, *, status, stage, error_code=None, scanner_receipt=None):
        self.states.append((status,stage,error_code,scanner_receipt))
        return True
    async def persist_document_chunk_batch(self, job, *, chunks, reset):
        self.batches.append((chunks,reset))
        return len(chunks)
    async def complete_document_parse(self, job, *, expected_chunk_count):
        self.completed.append(expected_chunk_count)
        return {"source_id":SOURCE,"source_version":1,"chunks_created":expected_chunk_count,
                "embedding_job_id":"embedding-job","embedding_job_status":"queued","retrieval_ready":False}
    async def fail_document_job(self, job, *, error_code, stage, retryable, retry_delay_seconds=30):
        self.failures.append((error_code,stage,retryable,retry_delay_seconds))
        return "queued" if retryable else "failed"


class FakeStorage:
    def __init__(self,data=DATA):self.data=data
    async def download(self,path):
        assert path.endswith("/notes.txt")
        return self.data


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

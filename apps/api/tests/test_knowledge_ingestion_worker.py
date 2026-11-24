import asyncio
import hashlib

from fastapi import HTTPException
import httpx
import pytest

from allpha_api.knowledge_ingestion_worker import (
    KnowledgeDocumentWorker, KnowledgeStorageObjectTooLarge,
    SupabaseKnowledgeStorage, main,
)
from knowledge_worker_fakes import DATA, FakeStorage, FakeStore
from allpha_api.knowledge_policy import KnowledgePolicyDenied


class FakePolicyResolver:
    def __init__(self, denied=False): self.denied=denied; self.calls=[]
    async def authorize_source(self, **kwargs):
        self.calls.append(kwargs)
        if self.denied: raise KnowledgePolicyDenied("test revoked grant")



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
    worker=KnowledgeDocumentWorker(store=store,storage=FakeStorage(),batch_size=1,policy_resolver=FakePolicyResolver())
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


def test_document_worker_rejects_cross_owner_storage_path_before_privileged_download():
    store = FakeStore()
    original_load_source = store.load_source

    async def cross_owner_source(job):
        source = await original_load_source(job)
        source["storage_path"] = (
            "99999999-9999-4999-8999-999999999999/"
            f"{source['agent_id']}/{source['id']}/{source['filename']}"
        )
        return source

    store.load_source = cross_owner_source
    worker = KnowledgeDocumentWorker(
        store=store, storage=FakeStorage(), policy_resolver=FakePolicyResolver(),
    )

    async def forbidden_download(path):
        raise AssertionError("service-role Storage download must not run for a mismatched object key")

    worker.storage.download = forbidden_download
    assert asyncio.run(worker.process_once()) is True
    assert store.failures == [
        ("KNOWLEDGE_STORAGE_PATH_IDENTITY_MISMATCH", "document_parse_failed", False, 0)
    ]
    assert store.batches == [] and store.completed == []


def test_document_worker_rejects_source_owner_mismatch_before_policy_or_storage():
    store = FakeStore()
    original_load_source = store.load_source

    async def wrong_owner_source(job):
        source = await original_load_source(job)
        source["owner_id"] = "99999999-9999-4999-8999-999999999999"
        return source

    store.load_source = wrong_owner_source
    policy = FakePolicyResolver()
    worker = KnowledgeDocumentWorker(store=store, storage=FakeStorage(), policy_resolver=policy)

    async def forbidden_download(path):
        raise AssertionError("Storage download must not run for a source-owner mismatch")

    worker.storage.download = forbidden_download
    assert asyncio.run(worker.process_once()) is True
    assert store.failures == [
        ("KNOWLEDGE_STORAGE_PATH_IDENTITY_MISMATCH", "document_parse_failed", False, 0)
    ]
    assert policy.calls == []
    assert store.batches == [] and store.completed == []


def test_document_worker_rejects_storage_hash_mismatch_before_parser(monkeypatch):
    store=FakeStore()
    async def clean_scan(*args):raise AssertionError("malware scan must not run after hash mismatch")
    monkeypatch.setattr("allpha_api.knowledge_ingestion_worker._scan",clean_scan)
    worker=KnowledgeDocumentWorker(store=store,storage=FakeStorage(b"tampered"),policy_resolver=FakePolicyResolver())
    assert asyncio.run(worker.process_once()) is True
    assert store.failures==[("KNOWLEDGE_SOURCE_SIZE_MISMATCH","document_parse_failed",False,0)] or store.failures==[("KNOWLEDGE_SOURCE_SHA256_MISMATCH","document_parse_failed",False,0)]
    assert store.batches==[] and store.completed==[]


def test_document_worker_retries_transient_scanner_unavailability(monkeypatch):
    store=FakeStore()
    async def unavailable(*args):
        raise HTTPException(status_code=503,detail={"code":"SCANNER_UNAVAILABLE","message":"scanner down"})
    monkeypatch.setattr("allpha_api.knowledge_ingestion_worker._scan",unavailable)
    worker=KnowledgeDocumentWorker(store=store,storage=FakeStorage(),policy_resolver=FakePolicyResolver())
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
    worker = KnowledgeDocumentWorker(store=store, storage=FakeStorage(), policy_resolver=FakePolicyResolver())
    assert asyncio.run(worker.process_once()) is True
    assert store.failures == []
    assert store.batches == []
    assert store.completed == []



def test_document_worker_stops_before_scanning_when_source_grant_is_revoked(monkeypatch):
    store=FakeStore()
    async def forbidden_scan(*args,**kwargs): raise AssertionError("revoked source must never reach scanner")
    monkeypatch.setattr("allpha_api.knowledge_ingestion_worker._scan",forbidden_scan)
    worker=KnowledgeDocumentWorker(store=store,storage=FakeStorage(),policy_resolver=FakePolicyResolver(denied=True))
    assert asyncio.run(worker.process_once()) is True
    assert store.failures==[("KNOWLEDGE_CONSENT_OR_GRANT_REVOKED","knowledge_policy_denied",False,0)]
    assert store.states==[] and store.batches==[] and store.completed==[]

def test_document_worker_entrypoint_respects_disabled_consumer_flag(monkeypatch):
    monkeypatch.setenv("ALLPHA_KNOWLEDGE_DOCUMENT_WORKER_ENABLED", "false")

    def fail_if_built():
        raise AssertionError("disabled Knowledge consumer must not build or poll the worker")

    monkeypatch.setattr(
        "allpha_api.knowledge_ingestion_worker.build_worker_from_environment",
        fail_if_built,
    )
    main()


class OversizedBody(httpx.AsyncByteStream):
    async def __aiter__(self):
        yield b"123"
        yield b"45"

    async def aclose(self):
        return None


def test_storage_download_stream_is_bounded_without_content_length(monkeypatch):
    monkeypatch.setattr(
        "allpha_api.knowledge_ingestion_worker.MAX_KNOWLEDGE_SOURCE_BYTES", 4,
    )
    seen = {}

    def handler(request):
        seen["authorization"] = request.headers.get("authorization")
        seen["accept_encoding"] = request.headers.get("accept-encoding")
        return httpx.Response(200, stream=OversizedBody())

    storage = SupabaseKnowledgeStorage(
        supabase_url="https://supabase.example",
        service_key="server-secret",
    )
    storage._transport = httpx.MockTransport(handler)

    async def run():
        with pytest.raises(KnowledgeStorageObjectTooLarge):
            await storage.download(
                "11111111-1111-4111-8111-111111111111/"
                "22222222-2222-4222-8222-222222222222/"
                "33333333-3333-4333-8333-333333333333/notes.txt"
            )

    asyncio.run(run())
    assert seen == {
        "authorization": "Bearer server-secret",
        "accept_encoding": "identity",
    }


def test_storage_download_rejects_declared_oversize_before_reading(monkeypatch):
    monkeypatch.setattr(
        "allpha_api.knowledge_ingestion_worker.MAX_KNOWLEDGE_SOURCE_BYTES", 4,
    )
    body_read = False

    class UnreadableBody(httpx.AsyncByteStream):
        async def __aiter__(self):
            nonlocal body_read
            body_read = True
            yield b"x"

        async def aclose(self):
            return None

    storage = SupabaseKnowledgeStorage(
        supabase_url="https://supabase.example",
        service_key="server-secret",
        timeout_seconds=1,
    )
    storage._transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            headers={"content-length": "5"},
            stream=UnreadableBody(),
        )
    )

    async def run():
        with pytest.raises(KnowledgeStorageObjectTooLarge):
            await storage.download(
                "11111111-1111-4111-8111-111111111111/"
                "22222222-2222-4222-8222-222222222222/"
                "33333333-3333-4333-8333-333333333333/notes.txt"
            )

    asyncio.run(run())
    assert body_read is False



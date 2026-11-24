import asyncio
import hashlib
from datetime import datetime, timezone

from allpha_api.embedding_contract import EmbeddingResponse
from allpha_api.knowledge_worker import KnowledgeEmbeddingWorker
from allpha_api.model_router import ModelRouterUnavailable
from allpha_api.knowledge_policy import KnowledgePolicyDenied


class FakePolicyResolver:
    def __init__(self, denied=False): self.denied=denied; self.calls=[]
    async def authorize_source(self, **kwargs):
        self.calls.append(kwargs)
        if self.denied: raise KnowledgePolicyDenied("test revoked grant")



class FakeStore:
    def __init__(self, source_version=2, job_version=2, sensitivity="internal", chunks=None):
        self.job = {"id":"job-1","lease_token":"lease-1","source_id":"source-1","owner_id":"owner-1","agent_id":"agent-1","source_version":job_version,"attempt":1}
        self.source = {"id":"source-1","source_version":source_version,"sensitivity":sensitivity}
        self.chunks = chunks if chunks is not None else [{"id":"chunk-1","content":"hello","content_sha256":hashlib.sha256(b"hello").hexdigest(),"source_version":job_version}]
        self.claims = []
        self.finalizations = []
        self.heartbeats = []
    async def heartbeat(self, job, *, lease_seconds):
        self.heartbeats.append((job["id"], job["lease_token"], lease_seconds))
        return True
    async def claim(self, *, lease_seconds, stage):
        self.claims.append((lease_seconds, stage))
        return self.job
    async def load_source(self, job):
        return self.source
    async def load_chunks(self, job):
        return self.chunks
    async def finalize(self, job, **kwargs):
        self.finalizations.append(kwargs)
        return True


class FakeRouter:
    def __init__(self, result=None, error=None):
        self.result, self.error = result, error
        self.requests = []
    async def embed(self, request):
        self.requests.append(request)
        if self.error:
            raise self.error
        return self.result


def embedding_response():
    digest = hashlib.sha256(b"hello").hexdigest()
    return EmbeddingResponse(
        task_id="job-1:0", provider_id="provider", model_id="model",
        model_version="v1", dimensions=2,
        vectors=[{"chunk_id":"chunk-1","content_sha256":digest,"values":[0.1,0.2]}],
        trace_id="job-1", completed_at=datetime.now(timezone.utc),
    )


def test_worker_claims_only_embedding_stage_and_finalizes_pending_qa():
    async def scenario():
        store = FakeStore()
        router = FakeRouter(result=embedding_response())
        persisted = []
        async def sink(job, request, response):
            persisted.append((job["id"], request.source_version, response.dimensions))
        worker = KnowledgeEmbeddingWorker(store, router, sink, policy_resolver=FakePolicyResolver())
        assert await worker.process_once() is True
        assert store.claims == [(90, "embedding_indexing")]
        assert len(persisted) == 1
        assert store.finalizations[-1]["outcome"] == "succeeded"
        assert store.finalizations[-1]["stage"] == "embedding_indexed_pending_retrieval_qa"
        assert store.finalizations[-1]["progress"] == 95
    asyncio.run(scenario())


def test_worker_cancels_stale_source_version_before_router_call():
    async def scenario():
        store = FakeStore(source_version=3, job_version=2)
        router = FakeRouter(result=embedding_response())
        async def sink(*args):
            raise AssertionError("sink must not be called for stale source")
        await KnowledgeEmbeddingWorker(store, router, sink, policy_resolver=FakePolicyResolver()).process_once()
        assert router.requests == []
        assert store.finalizations[-1]["error_code"] == "STALE_SOURCE_VERSION"
        assert store.finalizations[-1]["stage"] == "stale_source_version"
    asyncio.run(scenario())


def test_worker_retries_when_router_is_not_configured():
    async def scenario():
        store = FakeStore()
        router = FakeRouter(error=ModelRouterUnavailable("no route"))
        async def sink(*args):
            raise AssertionError("sink must not be called")
        await KnowledgeEmbeddingWorker(store, router, sink, policy_resolver=FakePolicyResolver()).process_once()
        final = store.finalizations[-1]
        assert final["outcome"] == "retry"
        assert final["error_code"] == "MODEL_ROUTER_UNAVAILABLE"
        assert final["retry_delay_seconds"] == 60
    asyncio.run(scenario())


def test_worker_fails_closed_without_sensitivity_classification():
    async def scenario():
        store = FakeStore(sensitivity=None)
        router = FakeRouter(result=embedding_response())
        async def sink(*args):
            raise AssertionError("sink must not be called")
        await KnowledgeEmbeddingWorker(store, router, sink, policy_resolver=FakePolicyResolver()).process_once()
        assert store.finalizations[-1]["error_code"] == "KNOWLEDGE_WORKER_PREREQUISITE_MISSING"
        assert not router.requests
    asyncio.run(scenario())


def test_worker_fails_closed_when_chunk_hash_does_not_match_content():
    async def scenario():
        store = FakeStore(chunks=[{
            "id": "chunk-1",
            "content": "tampered",
            "content_sha256": hashlib.sha256(b"hello").hexdigest(),
            "source_version": 2,
        }])
        router = FakeRouter(result=embedding_response())
        async def sink(*args):
            raise AssertionError("sink must not be called for tampered content")
        await KnowledgeEmbeddingWorker(store, router, sink, policy_resolver=FakePolicyResolver()).process_once()
        assert router.requests == []
        assert store.finalizations[-1]["outcome"] == "failed"
        assert store.finalizations[-1]["error_code"] == "KNOWLEDGE_WORKER_PREREQUISITE_MISSING"
    asyncio.run(scenario())




def test_embedding_worker_does_not_call_provider_after_source_grant_revocation():
    async def scenario():
        store=FakeStore(); router=FakeRouter(result=embedding_response())
        async def forbidden_sink(*args): raise AssertionError("revoked source must not persist")
        worker=KnowledgeEmbeddingWorker(store,router,forbidden_sink,policy_resolver=FakePolicyResolver(denied=True))
        await worker.process_once()
        assert router.requests==[]
        assert store.finalizations[-1]["error_code"]=="KNOWLEDGE_CONSENT_OR_GRANT_REVOKED"
        assert store.finalizations[-1]["outcome"]=="failed"
    asyncio.run(scenario())

def test_worker_wraps_embedding_and_vector_persistence_in_lease_heartbeat(monkeypatch):
    async def scenario():
        store = FakeStore()
        router = FakeRouter(result=embedding_response())
        persisted = []

        async def sink(job, request, response):
            persisted.append(job["id"])

        async def heartbeat_runner(operation, heartbeat, *, lease_seconds, identity, heartbeat_interval_seconds=None):
            assert identity == "job-1"
            assert lease_seconds == 90
            assert await heartbeat() is True
            await operation()
            return True

        monkeypatch.setattr("allpha_api.knowledge_worker.run_with_lease_heartbeat", heartbeat_runner)
        worker = KnowledgeEmbeddingWorker(store, router, sink, policy_resolver=FakePolicyResolver())
        assert await worker.process_once() is True
        assert store.heartbeats == [("job-1", "lease-1", 90)]
        assert persisted == ["job-1"]

    asyncio.run(scenario())



def test_worker_retries_when_vector_persistence_is_temporarily_unavailable():
    from allpha_api.knowledge_vector_store import VectorPersistenceUnavailable

    async def scenario():
        store = FakeStore()
        router = FakeRouter(result=embedding_response())

        async def sink(*args):
            raise VectorPersistenceUnavailable("index RPC unavailable")

        await KnowledgeEmbeddingWorker(store, router, sink, policy_resolver=FakePolicyResolver()).process_once()
        final = store.finalizations[-1]
        assert final["outcome"] == "retry"
        assert final["stage"] == "embedding_indexing_retry"
        assert final["error_code"] == "KNOWLEDGE_VECTOR_STORE_UNAVAILABLE"
        assert final["retry_delay_seconds"] == 60

    asyncio.run(scenario())


def test_worker_terminalizes_vector_idempotency_conflict_without_replay():
    from allpha_api.knowledge_vector_store import VectorPersistenceConflict

    async def scenario():
        store = FakeStore()
        router = FakeRouter(result=embedding_response())

        async def sink(*args):
            raise VectorPersistenceConflict("idempotency key payload conflict")

        await KnowledgeEmbeddingWorker(store, router, sink, policy_resolver=FakePolicyResolver()).process_once()
        final = store.finalizations[-1]
        assert final["outcome"] == "failed"
        assert final["stage"] == "embedding_indexing_failed"
        assert final["error_code"] == "KNOWLEDGE_VECTOR_PERSISTENCE_CONFLICT"

    asyncio.run(scenario())

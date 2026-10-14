import asyncio
from datetime import datetime, timezone

from allpha_api.embedding_contract import EmbeddingResponse
from allpha_api.knowledge_worker import KnowledgeEmbeddingWorker
from allpha_api.model_router import ModelRouterUnavailable


class FakeStore:
    def __init__(self, source_version=2, job_version=2, sensitivity="internal", chunks=None):
        self.job = {"id":"job-1","lease_token":"lease-1","source_id":"source-1","owner_id":"owner-1","agent_id":"agent-1","source_version":job_version,"attempt":1}
        self.source = {"id":"source-1","source_version":source_version,"sensitivity":sensitivity}
        self.chunks = chunks if chunks is not None else [{"id":"chunk-1","content":"hello","content_sha256":"a"*64,"source_version":job_version}]
        self.claims = []
        self.finalizations = []
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
    return EmbeddingResponse(
        task_id="job-1:0", provider_id="provider", model_id="model",
        model_version="v1", dimensions=2,
        vectors=[{"chunk_id":"chunk-1","content_sha256":"a"*64,"values":[0.1,0.2]}],
        trace_id="job-1", completed_at=datetime.now(timezone.utc),
    )


def test_worker_claims_only_embedding_stage_and_finalizes_pending_qa():
    async def scenario():
        store = FakeStore()
        router = FakeRouter(result=embedding_response())
        persisted = []
        async def sink(job, request, response):
            persisted.append((job["id"], request.source_version, response.dimensions))
        worker = KnowledgeEmbeddingWorker(store, router, sink)
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
        await KnowledgeEmbeddingWorker(store, router, sink).process_once()
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
        await KnowledgeEmbeddingWorker(store, router, sink).process_once()
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
        await KnowledgeEmbeddingWorker(store, router, sink).process_once()
        assert store.finalizations[-1]["error_code"] == "KNOWLEDGE_WORKER_PREREQUISITE_MISSING"
        assert not router.requests
    asyncio.run(scenario())

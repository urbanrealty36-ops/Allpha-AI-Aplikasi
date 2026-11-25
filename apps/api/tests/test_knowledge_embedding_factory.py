import asyncio

import pytest

from allpha_api.knowledge_worker import KnowledgeEmbeddingWorker, WorkerConfigurationError
from allpha_api.knowledge_worker_factory import build_worker


class ReadyRouter:
    def require_runtime_ready(self):
        return None


class ReadyPolicyResolver:
    async def authorize_source(self, **kwargs): return None


class ReadyRepository:
    def __init__(self):
        self.verified = False

    async def verify_generation(self):
        self.verified = True

    async def upsert_batch(
        self, records, *, expected_source_version, job_id, lease_token, idempotency_key,
    ):
        return None


def test_knowledge_embedding_factory_requires_canonical_supabase_credentials(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)

    async def scenario():
        with pytest.raises(WorkerConfigurationError, match="Supabase credentials"):
            await build_worker()

    asyncio.run(scenario())


def test_knowledge_embedding_factory_requires_approved_model_router_profile(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-role-test-key")
    monkeypatch.setattr(
        "allpha_api.knowledge_worker_factory.build_embedding_router_from_environment",
        lambda: _none_router(),
    )

    async def scenario():
        with pytest.raises(WorkerConfigurationError, match="provider profile"):
            await build_worker()

    async def _none_router():
        return None

    asyncio.run(scenario())


def test_knowledge_embedding_factory_verifies_generation_and_builds_canonical_sink(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-role-test-key")
    repository = ReadyRepository()
    monkeypatch.setattr("allpha_api.knowledge_worker_factory.load_policy_resolver_from_environment",lambda:ReadyPolicyResolver())
    monkeypatch.setattr(
        "allpha_api.knowledge_worker_factory.build_embedding_router_from_environment",
        lambda: _ready_router(),
    )
    monkeypatch.setattr(
        "allpha_api.knowledge_worker_factory.SupabaseKnowledgeVectorRepository.from_environment",
        lambda: repository,
    )

    async def scenario():
        worker = await build_worker()
        assert isinstance(worker, KnowledgeEmbeddingWorker)
        assert repository.verified is True
        assert worker.vector_sink.repository is repository
        assert worker.router is router

    router = ReadyRouter()

    async def _ready_router():
        return router

    asyncio.run(scenario())


def test_knowledge_embedding_factory_fails_closed_without_vector_generation(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-role-test-key")
    monkeypatch.delenv("ALLPHA_KNOWLEDGE_VECTOR_GENERATION_ID", raising=False)
    monkeypatch.setattr("allpha_api.knowledge_worker_factory.load_policy_resolver_from_environment",lambda:ReadyPolicyResolver())
    monkeypatch.setattr(
        "allpha_api.knowledge_worker_factory.build_embedding_router_from_environment",
        lambda: _ready_router(),
    )

    router = ReadyRouter()

    async def _ready_router():
        return router

    async def scenario():
        with pytest.raises(WorkerConfigurationError, match="pgvector generation"):
            await build_worker()

    asyncio.run(scenario())

def test_knowledge_embedding_factory_accepts_supabase_secret_key(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "canonical-secret-key")
    repository = ReadyRepository()
    router = ReadyRouter()

    async def _ready_router():
        return router

    monkeypatch.setattr(
        "allpha_api.knowledge_worker_factory.load_policy_resolver_from_environment",
        lambda: ReadyPolicyResolver(),
    )
    monkeypatch.setattr(
        "allpha_api.knowledge_worker_factory.build_embedding_router_from_environment",
        lambda: _ready_router(),
    )
    monkeypatch.setattr(
        "allpha_api.knowledge_worker_factory.SupabaseKnowledgeVectorRepository.from_environment",
        lambda: repository,
    )

    async def scenario():
        worker = await build_worker()
        assert worker.store.key == "canonical-secret-key"
        assert repository.verified is True

    asyncio.run(scenario())

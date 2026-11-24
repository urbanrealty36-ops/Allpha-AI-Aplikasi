"""Canonical composition root for the Knowledge embedding worker.

The worker uses the single Model Router, service-only Postgres vector repository,
and an explicitly readiness-checked index generation. No deployment-supplied
Python factory can replace the canonical persistence/security boundary.
"""
from __future__ import annotations

import os

from allpha_api.embedding_router_factory import build_embedding_router_from_environment
from allpha_api.knowledge_worker import (
    KnowledgeEmbeddingWorker,
    SupabaseKnowledgeJobStore,
    WorkerConfigurationError,
)
from allpha_api.knowledge_vector_repository import SupabaseKnowledgeVectorRepository
from allpha_api.knowledge_vector_store import IdempotentKnowledgeVectorSink
from allpha_api.model_router import ModelRouterUnavailable


async def build_worker() -> KnowledgeEmbeddingWorker:
    supabase_url = os.getenv("SUPABASE_URL", "").strip()
    service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    if not supabase_url or not service_role_key:
        raise WorkerConfigurationError("server-side Supabase credentials are required for Knowledge embedding")

    router = await build_embedding_router_from_environment()
    if router is None:
        raise WorkerConfigurationError("approved embedding provider profile is not configured")
    try:
        router.require_runtime_ready()
    except ModelRouterUnavailable as exc:
        raise WorkerConfigurationError(f"canonical Model Router is not runtime-ready: {exc}") from exc

    try:
        repository = SupabaseKnowledgeVectorRepository.from_environment()
        await repository.verify_generation()
    except Exception as exc:
        raise WorkerConfigurationError(f"canonical pgvector generation is not runtime-ready: {exc}") from exc

    return KnowledgeEmbeddingWorker(
        store=SupabaseKnowledgeJobStore(
            supabase_url=supabase_url,
            service_key=service_role_key,
        ),
        router=router,
        vector_sink=IdempotentKnowledgeVectorSink(repository),
        lease_seconds=int(os.getenv("KNOWLEDGE_EMBEDDING_LEASE_SECONDS", "90")),
        batch_size=int(os.getenv("KNOWLEDGE_EMBEDDING_BATCH_SIZE", "32")),
        request_timeout_ms=int(os.getenv("KNOWLEDGE_EMBEDDING_REQUEST_TIMEOUT_MS", "30000")),
    )

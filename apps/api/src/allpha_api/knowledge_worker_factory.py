"""Canonical composition root for the Knowledge embedding worker.

The vector sink factory is intentionally mandatory: no unindexed JSON/array
fallback is allowed while the physical pgvector generation/index is pending.
"""
from __future__ import annotations

import importlib
import inspect
import os

from allpha_api.embedding_router_factory import build_embedding_router_from_environment
from allpha_api.knowledge_worker import (
    KnowledgeEmbeddingWorker,
    SupabaseKnowledgeJobStore,
    WorkerConfigurationError,
)
from allpha_api.knowledge_vector_store import IdempotentKnowledgeVectorSink


def _load_factory(path: str):
    module_name, separator, attribute = path.partition(":")
    if not separator or not module_name or not attribute:
        raise WorkerConfigurationError("Knowledge vector sink factory must use module:function syntax")
    try:
        factory = getattr(importlib.import_module(module_name), attribute)
    except (ImportError, AttributeError) as exc:
        raise WorkerConfigurationError("Knowledge vector sink factory could not be loaded") from exc
    if not callable(factory):
        raise WorkerConfigurationError("Knowledge vector sink factory is not callable")
    return factory


def _require_canonical_vector_sink(value) -> IdempotentKnowledgeVectorSink:
    if not isinstance(value, IdempotentKnowledgeVectorSink):
        raise WorkerConfigurationError(
            "vector sink factory must return the canonical IdempotentKnowledgeVectorSink"
        )
    if not callable(getattr(value.repository, "upsert_batch", None)):
        raise WorkerConfigurationError("vector repository must implement atomic upsert_batch")
    return value


async def build_worker() -> KnowledgeEmbeddingWorker:
    vector_factory_path = os.getenv("ALLPHA_KNOWLEDGE_VECTOR_SINK_FACTORY", "").strip()
    if not vector_factory_path:
        raise WorkerConfigurationError(
            "durable pgvector repository/sink factory is not configured; embedding consumer remains disabled"
        )
    supabase_url = os.getenv("SUPABASE_URL", "").strip()
    service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    if not supabase_url or not service_role_key:
        raise WorkerConfigurationError("server-side Supabase credentials are required for Knowledge embedding")
    factory = _load_factory(vector_factory_path)
    vector_sink = factory()
    if inspect.isawaitable(vector_sink):
        vector_sink = await vector_sink
    vector_sink = _require_canonical_vector_sink(vector_sink)
    router = await build_embedding_router_from_environment()
    if router is None:
        raise WorkerConfigurationError("approved embedding provider profile is not configured")
    return KnowledgeEmbeddingWorker(
        store=SupabaseKnowledgeJobStore(
            supabase_url=supabase_url,
            service_key=service_role_key,
        ),
        router=router,
        vector_sink=vector_sink,
        lease_seconds=int(os.getenv("KNOWLEDGE_EMBEDDING_LEASE_SECONDS", "90")),
        batch_size=int(os.getenv("KNOWLEDGE_EMBEDDING_BATCH_SIZE", "32")),
        request_timeout_ms=int(os.getenv("KNOWLEDGE_EMBEDDING_REQUEST_TIMEOUT_MS", "30000")),
    )

import asyncio
import json

import httpx
import pytest

from allpha_api.knowledge_vector_repository import SupabaseKnowledgeVectorRepository
from allpha_api.knowledge_vector_store import VectorPersistenceConflict, VectorPersistenceUnavailable, VectorRecord


GENERATION = "11111111-1111-4111-8111-111111111111"


def repository(handler):
    return SupabaseKnowledgeVectorRepository(
        supabase_url="https://example.supabase.co",
        service_role_key="server-only-test-key",
        generation_id=GENERATION,
        transport=httpx.MockTransport(handler),
    )


def record():
    return VectorRecord(
        owner_id="owner-1",
        agent_id="agent-1",
        source_id="source-1",
        source_version=4,
        chunk_id="chunk-1",
        content_sha256="a" * 64,
        provider_id="provider-1",
        model_id="model-1",
        model_version="immutable-v1",
        contract_version="allpha.embedding.v1",
        dimensions=2,
        values=(0.1, 0.2),
        idempotency_key="batch-1:chunk-1",
    )


def test_vector_repository_requires_a_valid_generation_uuid():
    with pytest.raises(VectorPersistenceUnavailable, match="generation UUID"):
        SupabaseKnowledgeVectorRepository(
            supabase_url="https://example.supabase.co",
            service_role_key="server-only-test-key",
            generation_id="not-a-uuid",
        )


def test_vector_repository_verifies_writable_generation_before_worker_start():
    seen = []

    async def handler(request):
        seen.append(request)
        assert request.url.path.endswith("/rpc/agent_knowledge_vector_generation_readiness")
        assert request.headers["Authorization"] == "Bearer server-only-test-key"
        assert json.loads(request.content) == {"p_generation_id": GENERATION}
        return httpx.Response(200, json={
            "ready": True, "generation_id": GENERATION, "status": "building",
        })

    repo = repository(handler)
    asyncio.run(repo.verify_generation())
    assert len(seen) == 1


def test_vector_repository_fails_closed_when_generation_readiness_rpc_is_missing():
    async def handler(request):
        return httpx.Response(404, json={"code": "PGRST202"})

    async def scenario():
        with pytest.raises(VectorPersistenceUnavailable, match="404"):
            await repository(handler).verify_generation()

    asyncio.run(scenario())


def test_vector_repository_upsert_passes_job_lease_and_content_free_vectors():
    seen = []

    async def handler(request):
        seen.append(request)
        payload = json.loads(request.content)
        assert request.url.path.endswith("/rpc/upsert_agent_knowledge_vectors")
        assert payload["p_generation_id"] == GENERATION
        assert payload["p_job_id"] == "job-1"
        assert payload["p_lease_token"] == "lease-current"
        assert payload["p_owner_id"] == "owner-1"
        assert payload["p_agent_id"] == "agent-1"
        assert payload["p_source_id"] == "source-1"
        assert payload["p_source_version"] == 4
        assert payload["p_records"] == [{
            "chunk_id": "chunk-1",
            "content_sha256": "a" * 64,
            "values": [0.1, 0.2],
            "idempotency_key": "batch-1:chunk-1",
        }]
        assert all("content" not in item for item in payload["p_records"])
        return httpx.Response(200, json={
            "generation_id": GENERATION,
            "source_version": 4,
            "persisted_count": 1,
            "idempotency_key": "batch-1",
        })

    async def scenario():
        await repository(handler).upsert_batch(
            [record()],
            expected_source_version=4,
            job_id="job-1",
            lease_token="lease-current",
            idempotency_key="batch-1",
        )
        assert len(seen) == 1

    asyncio.run(scenario())


def test_vector_repository_maps_lease_conflict_to_typed_conflict():
    async def handler(request):
        return httpx.Response(409, json={"code": "STALE_LEASE"})

    async def scenario():
        with pytest.raises(VectorPersistenceConflict):
            await repository(handler).upsert_batch(
                [record()], expected_source_version=4, job_id="job-1",
                lease_token="expired-lease", idempotency_key="batch-1",
            )

    asyncio.run(scenario())


def test_vector_repository_rejects_mismatched_upsert_receipt():
    async def handler(request):
        return httpx.Response(200, json={
            "generation_id": GENERATION,
            "source_version": 3,
            "persisted_count": 1,
            "idempotency_key": "batch-1",
        })

    async def scenario():
        with pytest.raises(VectorPersistenceConflict, match="receipt"):
            await repository(handler).upsert_batch(
                [record()], expected_source_version=4, job_id="job-1",
                lease_token="lease-current", idempotency_key="batch-1",
            )

    asyncio.run(scenario())

"""Service-role PostgREST adapter for the canonical pgvector generation RPCs.

No client can write vectors. The database RPC owns lease/source fencing,
generation checks, atomic persistence and idempotency. This adapter intentionally
fails closed until the versioned generation/readiness and upsert RPCs are migrated.
"""
from __future__ import annotations

import os
import uuid
from dataclasses import asdict
from typing import Any

import httpx

from allpha_api.knowledge_vector_store import (
    VectorPersistenceConflict,
    VectorPersistenceUnavailable,
    VectorRecord,
)


class SupabaseKnowledgeVectorRepository:
    def __init__(
        self,
        *,
        supabase_url: str,
        service_role_key: str,
        generation_id: str,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        try:
            self.generation_id = str(uuid.UUID(generation_id))
        except (ValueError, TypeError, AttributeError) as exc:
            raise VectorPersistenceUnavailable("a canonical vector generation UUID is required") from exc
        if not supabase_url.strip() or not service_role_key.strip():
            raise VectorPersistenceUnavailable("server-side Supabase credentials are required")
        self._base = supabase_url.rstrip("/") + "/rest/v1"
        self._key = service_role_key
        self._transport = transport

    @classmethod
    def from_environment(
        cls, *, transport: httpx.AsyncBaseTransport | None = None,
    ) -> "SupabaseKnowledgeVectorRepository":
        return cls(
            supabase_url=os.getenv("SUPABASE_URL", "").strip(),
            service_role_key=(os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip() or os.getenv("SUPABASE_SECRET_KEY", "").strip()),
            generation_id=os.getenv("ALLPHA_KNOWLEDGE_VECTOR_GENERATION_ID", "").strip(),
            transport=transport,
        )

    def _headers(self) -> dict[str, str]:
        return {
            "apikey": self._key,
            "Authorization": "Bearer " + self._key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def _rpc(self, name: str, payload: dict[str, Any]) -> Any:
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(12.0, connect=3.0),
                follow_redirects=False,
                trust_env=False,
                transport=self._transport,
            ) as client:
                response = await client.post(
                    f"{self._base}/rpc/{name}",
                    headers=self._headers(),
                    json=payload,
                )
        except httpx.HTTPError as exc:
            raise VectorPersistenceUnavailable("canonical Supabase vector RPC is unreachable") from exc
        if response.status_code == 409:
            raise VectorPersistenceConflict("canonical vector RPC rejected a stale lease or idempotency conflict")
        if response.status_code != 200:
            raise VectorPersistenceUnavailable(
                f"canonical vector RPC {name} is unavailable ({response.status_code})"
            )
        try:
            return response.json()
        except ValueError as exc:
            raise VectorPersistenceUnavailable("canonical vector RPC returned invalid JSON") from exc

    async def verify_generation(self) -> None:
        result = await self._rpc(
            "agent_knowledge_vector_generation_readiness",
            {"p_generation_id": self.generation_id},
        )
        if isinstance(result, list):
            result = result[0] if len(result) == 1 else None
        if (
            not isinstance(result, dict)
            or result.get("ready") is not True
            or str(result.get("generation_id")) != self.generation_id
            or result.get("status") not in {"building", "active"}
        ):
            raise VectorPersistenceUnavailable(
                "configured pgvector generation is absent, unapproved, or not writable"
            )

    async def upsert_batch(
        self,
        records: list[VectorRecord],
        *,
        expected_source_version: int,
        job_id: str,
        lease_token: str,
        idempotency_key: str,
    ) -> None:
        if not records or not job_id.strip() or not lease_token.strip() or not idempotency_key.strip():
            raise VectorPersistenceConflict("vector batch is missing records or lease/idempotency identity")
        first = records[0]
        for record in records:
            if (
                record.owner_id != first.owner_id
                or record.agent_id != first.agent_id
                or record.source_id != first.source_id
                or record.source_version != expected_source_version
                or record.provider_id != first.provider_id
                or record.model_id != first.model_id
                or record.model_version != first.model_version
                or record.contract_version != first.contract_version
                or record.dimensions != first.dimensions
            ):
                raise VectorPersistenceConflict("vector batch mixes owner, source, model or dimension identities")
        payload = {
            "p_generation_id": self.generation_id,
            "p_job_id": job_id,
            "p_lease_token": lease_token,
            "p_owner_id": first.owner_id,
            "p_agent_id": first.agent_id,
            "p_source_id": first.source_id,
            "p_source_version": expected_source_version,
            "p_provider_id": first.provider_id,
            "p_model_id": first.model_id,
            "p_model_version": first.model_version,
            "p_contract_version": first.contract_version,
            "p_dimensions": first.dimensions,
            "p_idempotency_key": idempotency_key,
            "p_records": [
                {
                    "chunk_id": record.chunk_id,
                    "content_sha256": record.content_sha256,
                    "values": list(record.values),
                    "idempotency_key": record.idempotency_key,
                }
                for record in records
            ],
        }
        result = await self._rpc("upsert_agent_knowledge_vectors", payload)
        if isinstance(result, list):
            result = result[0] if len(result) == 1 else None
        if not isinstance(result, dict):
            raise VectorPersistenceUnavailable("vector upsert RPC returned an invalid receipt")
        if (
            str(result.get("generation_id")) != self.generation_id
            or result.get("source_version") != expected_source_version
            or result.get("persisted_count") != len(records)
            or result.get("idempotency_key") != idempotency_key
        ):
            raise VectorPersistenceConflict("vector upsert receipt does not match the requested batch")


async def build_vector_sink_from_environment(
    *, transport: httpx.AsyncBaseTransport | None = None,
):
    from allpha_api.knowledge_vector_store import IdempotentKnowledgeVectorSink

    repository = SupabaseKnowledgeVectorRepository.from_environment(transport=transport)
    await repository.verify_generation()
    return IdempotentKnowledgeVectorSink(repository)

"""Provider-neutral, fail-closed vector persistence boundary for knowledge indexing.

This module intentionally contains no provider SDK, physical vector column, guessed
dimension, or default index. A deployment adapter must implement atomic upsert and
owner/source-version fencing in the canonical database.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from allpha_api.embedding_contract import (
    EmbeddingRequest,
    EmbeddingResponse,
    validate_response_matches_request,
)


class VectorPersistenceUnavailable(RuntimeError):
    """No approved vector persistence adapter is configured."""


class VectorPersistenceConflict(RuntimeError):
    """Stored identity/version conflicts with the requested idempotent write."""


@dataclass(frozen=True)
class VectorRecord:
    owner_id: str
    agent_id: str
    source_id: str
    source_version: int
    chunk_id: str
    content_sha256: str
    provider_id: str
    model_id: str
    model_version: str
    contract_version: str
    dimensions: int
    values: tuple[float, ...]
    idempotency_key: str


class VectorRepository(Protocol):
    async def upsert_batch(
        self,
        records: list[VectorRecord],
        *,
        expected_source_version: int,
        idempotency_key: str,
    ) -> None:
        """Atomically persist all records, fenced by current source version.

        Implementations must scope records to owner/agent/source, reject a source
        version mismatch, and make retries of the same key+payload idempotent.
        Reuse of a key with different payload must raise VectorPersistenceConflict.
        """
        ...


def build_vector_records(
    job: dict[str, Any],
    request: EmbeddingRequest,
    response: EmbeddingResponse,
) -> list[VectorRecord]:
    """Validate the full response and produce immutable provenance-rich records."""
    validate_response_matches_request(request, response)
    if (
        str(job.get("owner_id")) != request.owner_id
        or str(job.get("agent_id")) != request.agent_id
        or str(job.get("source_id")) != request.source_id
        or int(job.get("source_version", -1)) != request.source_version
    ):
        raise VectorPersistenceConflict("job and embedding request identity/version differ")
    if not job.get("lease_token"):
        raise VectorPersistenceConflict("job lease fencing token is missing")

    by_id = {item.chunk_id: item for item in response.vectors}
    records: list[VectorRecord] = []
    for chunk in request.chunks:
        vector = by_id[chunk.chunk_id]
        if vector.content_sha256 != chunk.content_sha256:
            raise VectorPersistenceConflict("chunk content hash differs from embedding response")
        if len(vector.values) != response.dimensions:
            raise VectorPersistenceConflict("vector dimension differs from response metadata")
        records.append(VectorRecord(
            owner_id=request.owner_id,
            agent_id=request.agent_id,
            source_id=request.source_id,
            source_version=request.source_version,
            chunk_id=chunk.chunk_id,
            content_sha256=chunk.content_sha256,
            provider_id=response.provider_id,
            model_id=response.model_id,
            model_version=response.model_version,
            contract_version=response.contract_version,
            dimensions=response.dimensions,
            values=tuple(vector.values),
            idempotency_key=f"{request.idempotency_key}:{chunk.chunk_id}",
        ))
    if len(records) != len(request.chunks):
        raise VectorPersistenceConflict("response did not produce one record per requested chunk")
    return records


@dataclass
class IdempotentKnowledgeVectorSink:
    """Worker callback that persists only validated vectors via an injected adapter."""
    repository: VectorRepository

    async def __call__(
        self,
        job: dict[str, Any],
        request: EmbeddingRequest,
        response: EmbeddingResponse,
    ) -> None:
        records = build_vector_records(job, request, response)
        # The idempotency key must be stable across retries. Do not salt it with
        # the payload digest: doing so would turn a conflicting replay into a new write.
        # The repository compares a canonical payload fingerprint for this stable key
        # and raises VectorPersistenceConflict when the same key is reused differently.
        await self.repository.upsert_batch(
            records,
            expected_source_version=request.source_version,
            idempotency_key=request.idempotency_key,
        )


def require_vector_repository(repository: VectorRepository | None) -> VectorRepository:
    if repository is None:
        raise VectorPersistenceUnavailable("approved vector repository is not configured")
    return repository

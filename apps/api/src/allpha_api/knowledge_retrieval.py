"""Authorization-first retrieval orchestration for private agent knowledge.

Physical vector search is an injected adapter because the approved embedding model,
dimension, index generation and evaluation gates have not been selected. This layer
never queries a provider directly and never treats an embedding index as ready merely
because vectors exist.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field


Sensitivity = Literal["public", "internal", "confidential", "restricted"]


class KnowledgeRetrievalUnavailable(RuntimeError):
    """Retrieval dependencies or a verified index generation are unavailable."""


class KnowledgeAccessDenied(RuntimeError):
    """The requesting user does not own the agent/source context."""


class RetrievalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    owner_id: str = Field(min_length=1, max_length=128)
    agent_id: str = Field(min_length=1, max_length=128)
    query: str = Field(min_length=1, max_length=4000)
    allowed_sensitivities: list[Sensitivity] = Field(min_length=1, max_length=4)
    limit: int = Field(default=8, ge=1, le=50)
    trace_id: str = Field(min_length=1, max_length=128)


@dataclass(frozen=True)
class RetrievalHit:
    owner_id: str
    agent_id: str
    source_id: str
    source_version: int
    chunk_id: str
    content: str
    content_sha256: str
    source_location: dict[str, Any]
    sensitivity: str
    retrieval_method: Literal["vector", "keyword", "hybrid"]
    score: float
    provider_id: str | None = None
    model_id: str | None = None
    model_version: str | None = None
    index_generation: str | None = None


class KnowledgeRetrievalRepository(Protocol):
    async def authorize_agent(self, *, owner_id: str, agent_id: str) -> bool: ...
    async def search_hybrid(
        self,
        *,
        owner_id: str,
        agent_id: str,
        query: str,
        allowed_sensitivities: list[str],
        limit: int,
        trace_id: str,
    ) -> list[RetrievalHit]:
        """Search only ready sources, applying owner/agent/sensitivity filters in DB.

        Vector query must use the active approved index generation; keyword retrieval
        must use the canonical full-text index. Adapters must enforce the same filters
        within SQL/RPC, not post-filter an unrestricted result set.
        """
        ...


@dataclass
class KnowledgeRetrievalService:
    repository: KnowledgeRetrievalRepository | None

    async def retrieve(self, request: RetrievalRequest) -> list[RetrievalHit]:
        if self.repository is None:
            raise KnowledgeRetrievalUnavailable("knowledge retrieval repository is not configured")
        authorized = await self.repository.authorize_agent(
            owner_id=request.owner_id, agent_id=request.agent_id
        )
        if not authorized:
            raise KnowledgeAccessDenied("owner does not have active access to this agent")
        hits = await self.repository.search_hybrid(
            owner_id=request.owner_id,
            agent_id=request.agent_id,
            query=request.query,
            allowed_sensitivities=list(request.allowed_sensitivities),
            limit=request.limit,
            trace_id=request.trace_id,
        )
        # Defense-in-depth contract check. Repository must already enforce these
        # constraints in its query/RPC; any violation is a hard failure, not a filter.
        for hit in hits:
            if hit.owner_id != request.owner_id or hit.agent_id != request.agent_id:
                raise KnowledgeAccessDenied("retrieval adapter returned cross-owner/agent data")
            if hit.sensitivity not in request.allowed_sensitivities:
                raise KnowledgeAccessDenied("retrieval adapter returned disallowed sensitivity")
            if not hit.source_id or not hit.chunk_id or not hit.content_sha256:
                raise KnowledgeRetrievalUnavailable("retrieval result lacks source/chunk provenance")
        return hits

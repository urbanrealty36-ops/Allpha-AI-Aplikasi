"""Authorization-first retrieval orchestration and fail-closed FastAPI boundary.

Physical vector search and sensitivity policy are injected because approved model/index
and data-access policy decisions are not present yet. The public API never accepts an
owner ID or allowed-sensitivity list from the caller.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, Literal, Protocol

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from allpha_api.auth import current_user

router = APIRouter(prefix="/v1/agents/{agent_id}/knowledge", tags=["agent-knowledge-retrieval"])
Sensitivity = Literal["public", "internal", "confidential", "restricted"]


class KnowledgeRetrievalUnavailable(RuntimeError):
    """Retrieval dependencies or a verified index generation are unavailable."""


class KnowledgeAccessDenied(RuntimeError):
    """The requesting user does not own the agent/source context."""


class RetrievalQuery(BaseModel):
    """Only caller-controlled query parameters; identity and sensitivity are server-derived."""
    model_config = ConfigDict(extra="forbid", frozen=True)
    query: str = Field(min_length=1, max_length=4000)
    limit: int = Field(default=8, ge=1, le=50)


class RetrievalRequest(BaseModel):
    """Trusted internal context created by server code after authentication and policy."""
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
        self, *, owner_id: str, agent_id: str, query: str,
        allowed_sensitivities: list[str], limit: int, trace_id: str,
    ) -> list[RetrievalHit]:
        """Enforce ready-source, owner/agent/sensitivity filters inside SQL/RPC.

        Vector retrieval must use the active approved index generation; keyword
        retrieval must use the canonical full-text index. Never post-filter an
        unrestricted result set as a substitute for query-time authorization.
        """
        ...


class KnowledgeRetrievalPolicy(Protocol):
    async def allowed_sensitivities(self, *, owner_id: str, agent_id: str) -> list[str]:
        """Return policy-approved classes for this authenticated owner/agent."""
        ...


@dataclass
class KnowledgeRetrievalService:
    repository: KnowledgeRetrievalRepository | None
    policy: KnowledgeRetrievalPolicy | None = None

    async def retrieve(self, request: RetrievalRequest) -> list[RetrievalHit]:
        if self.repository is None or self.policy is None:
            raise KnowledgeRetrievalUnavailable("knowledge retrieval repository/policy is not configured")
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
        for hit in hits:
            if hit.owner_id != request.owner_id or hit.agent_id != request.agent_id:
                raise KnowledgeAccessDenied("retrieval adapter returned cross-owner/agent data")
            if hit.sensitivity not in request.allowed_sensitivities:
                raise KnowledgeAccessDenied("retrieval adapter returned disallowed sensitivity")
            if not hit.source_id or not hit.chunk_id or not hit.content_sha256:
                raise KnowledgeRetrievalUnavailable("retrieval result lacks source/chunk provenance")
        return hits


@router.post("/retrieve")
async def retrieve_knowledge(
    agent_id: uuid.UUID,
    payload: RetrievalQuery,
    request: Request,
    user: dict[str, Any] = Depends(current_user),
):
    """Authenticated retrieval endpoint; identity and sensitivity never come from JSON."""
    service = getattr(request.app.state, "knowledge_retrieval_service", None)
    if not isinstance(service, KnowledgeRetrievalService):
        raise HTTPException(
            status_code=503,
            detail={"code": "KNOWLEDGE_RETRIEVAL_UNAVAILABLE", "message": "Retrieval belum dikonfigurasi."},
        )
    owner_id = str(user["id"])
    agent = str(agent_id)
    try:
        if service.repository is None or not await service.repository.authorize_agent(owner_id=owner_id, agent_id=agent):
            raise KnowledgeAccessDenied("owner does not have active access to this agent")
        allowed = await service.policy.allowed_sensitivities(owner_id=owner_id, agent_id=agent) if service.policy else None
        if not allowed or any(value not in {"public", "internal", "confidential", "restricted"} for value in allowed):
            raise KnowledgeRetrievalUnavailable("approved sensitivity policy is missing or invalid")
        trace_id = str(getattr(request.state, "request_id", "") or uuid.uuid4())
        internal = RetrievalRequest(
            owner_id=owner_id,
            agent_id=agent,
            query=payload.query,
            allowed_sensitivities=allowed,
            limit=payload.limit,
            trace_id=trace_id,
        )
        hits = await service.retrieve(internal)
    except KnowledgeAccessDenied as exc:
        raise HTTPException(status_code=403, detail={"code": "KNOWLEDGE_ACCESS_DENIED", "message": "Akses knowledge ditolak."}) from exc
    except KnowledgeRetrievalUnavailable as exc:
        raise HTTPException(status_code=503, detail={"code": "KNOWLEDGE_RETRIEVAL_UNAVAILABLE", "message": "Retrieval belum siap atau dependensi tidak tersedia."}) from exc
    return {
        "trace_id": trace_id,
        "results": [
            {
                "source_id": hit.source_id,
                "source_version": hit.source_version,
                "chunk_id": hit.chunk_id,
                "content": hit.content,
                "content_sha256": hit.content_sha256,
                "source_location": hit.source_location,
                "sensitivity": hit.sensitivity,
                "retrieval_method": hit.retrieval_method,
                "score": hit.score,
                "provider_id": hit.provider_id,
                "model_id": hit.model_id,
                "model_version": hit.model_version,
                "index_generation": hit.index_generation,
            }
            for hit in hits
        ],
    }

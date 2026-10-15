"""Authorization-first retrieval orchestration and fail-closed FastAPI boundary.

Physical vector search and sensitivity policy are injected because approved model/index
and data-access policy decisions are not present yet. The public API never accepts an
owner ID or allowed-sensitivity list from the caller.
"""
from __future__ import annotations

import os
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


class ConfiguredKnowledgeRetrievalPolicy:
    """Explicit server-configured sensitivity allowlist; unset config fails closed.

    This platform-level switch does not replace future owner/tenant-specific policy.
    Enable it only after intentionally selecting allowed sensitivity classes.
    """
    _VALID = {"public", "internal", "confidential", "restricted"}

    def __init__(self, allowed: list[str]):
        self._allowed = allowed if allowed and all(value in self._VALID for value in allowed) else []

    @classmethod
    def from_environment(cls) -> "ConfiguredKnowledgeRetrievalPolicy":
        raw = os.getenv("ALLPHA_KNOWLEDGE_ALLOWED_SENSITIVITIES", "")
        values = list(dict.fromkeys(item.strip().lower() for item in raw.split(",") if item.strip()))
        return cls(values)

    async def allowed_sensitivities(self, *, owner_id: str, agent_id: str) -> list[str]:
        return list(self._allowed)


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
    service = request_scoped_retrieval_service(request)
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


class SupabaseKeywordKnowledgeRepository:
    """User-scoped PostgREST keyword candidate search over the canonical chunk tables.

    Uses the authenticated user's access token so PostgreSQL RLS remains authoritative.
    This adapter is deliberately keyword-only: it does not pretend to provide hybrid
    retrieval until an approved physical vector-index generation is configured.
    """
    def __init__(self, *, access_token: str):
        if not access_token or not access_token.strip():
            raise ValueError("authenticated Supabase access token is required")
        self._access_token = access_token

    async def authorize_agent(self, *, owner_id: str, agent_id: str) -> bool:
        from allpha_api.auth import user_db_request

        rows = await user_db_request(
            "GET", "agent_ownerships", self._access_token,
            params={
                "select": "agent_id",
                "agent_id": f"eq.{agent_id}",
                "owner_user_id": f"eq.{owner_id}",
                "status": "eq.active",
                "limit": "1",
            },
        )
        return bool(rows)

    async def search_keyword(
        self,
        *,
        owner_id: str,
        agent_id: str,
        query: str,
        allowed_sensitivities: list[str],
        limit: int,
        trace_id: str,
    ) -> list[RetrievalHit]:
        from allpha_api.auth import user_db_request

        # PostgREST applies all filters in the database query. Source status and
        # sensitivity are joined as an inner relation; no unrestricted search followed
        # by in-memory filtering is permitted.
        params = {
            "select": (
                "id,source_id,agent_id,owner_id,chunk_index,content,source_location,"
                "source_version,content_sha256,"
                "agent_knowledge_sources!inner(id,source_version,status,sensitivity)"
            ),
            "owner_id": f"eq.{owner_id}",
            "agent_id": f"eq.{agent_id}",
            "agent_knowledge_sources.status": "eq.ready",
            "agent_knowledge_sources.sensitivity": "in.(" + ",".join(allowed_sensitivities) + ")",
            "search_vector": "fts(simple)." + query,
            "order": "chunk_index.asc",
            "limit": str(limit),
        }
        rows = await user_db_request(
            "GET", "agent_knowledge_chunks", self._access_token, params=params
        )
        hits: list[RetrievalHit] = []
        for row in rows or []:
            source = row.get("agent_knowledge_sources") or {}
            # Fail closed if the embedded relationship or any invariant is absent.
            if (
                row.get("owner_id") != owner_id
                or row.get("agent_id") != agent_id
                or source.get("status") != "ready"
                or source.get("sensitivity") not in allowed_sensitivities
                or int(source.get("source_version", -1)) != int(row.get("source_version", -2))
                or not row.get("content_sha256")
                or not row.get("id")
                or not row.get("source_id")
            ):
                raise KnowledgeRetrievalUnavailable(
                    "database keyword result violated owner/source/version/sensitivity invariants"
                )
            hits.append(RetrievalHit(
                owner_id=owner_id,
                agent_id=agent_id,
                source_id=str(row["source_id"]),
                source_version=int(row["source_version"]),
                chunk_id=str(row["id"]),
                content=str(row.get("content") or ""),
                content_sha256=str(row["content_sha256"]),
                source_location=row.get("source_location") or {},
                sensitivity=str(source["sensitivity"]),
                retrieval_method="keyword",
                score=0.0,
            ))
        return hits


class KeywordOnlyKnowledgeRepository:
    """Opt-in keyword-only mode over the existing full-text contract; not hybrid search."""
    def __init__(self, *, keyword_repository: SupabaseKeywordKnowledgeRepository):
        self._keyword = keyword_repository

    async def authorize_agent(self, *, owner_id: str, agent_id: str) -> bool:
        return await self._keyword.authorize_agent(owner_id=owner_id, agent_id=agent_id)

    async def search_hybrid(self, *, owner_id: str, agent_id: str, query: str,
                            allowed_sensitivities: list[str], limit: int, trace_id: str) -> list[RetrievalHit]:
        return await self._keyword.search_keyword(
            owner_id=owner_id, agent_id=agent_id, query=query,
            allowed_sensitivities=allowed_sensitivities, limit=limit, trace_id=trace_id,
        )


def request_scoped_retrieval_service(request: Request) -> KnowledgeRetrievalService | None:
    """Resolve injected wiring or explicitly configured canonical policy provider.

    An environment sensitivity allowlist alone is not authorization and cannot activate
    retrieval. The provider must resolve current knowledge consent, revocation and grants.
    """
    configured = getattr(request.app.state, "knowledge_retrieval_service", None)
    if isinstance(configured, KnowledgeRetrievalService):
        return configured
    mode = os.getenv("ALLPHA_KNOWLEDGE_RETRIEVAL_MODE", "disabled").strip().lower()
    if mode != "keyword":
        return None
    token = getattr(request.state, "supabase_access_token", None)
    if not isinstance(token, str) or not token.strip():
        return None
    from allpha_api.knowledge_policy import (
        VersionedKnowledgeRetrievalPolicy,
        load_policy_resolver_from_environment,
    )
    resolver = load_policy_resolver_from_environment()
    if resolver is None:
        return None
    keyword = SupabaseKeywordKnowledgeRepository(access_token=token)
    return KnowledgeRetrievalService(
        repository=KeywordOnlyKnowledgeRepository(keyword_repository=keyword),
        policy=VersionedKnowledgeRetrievalPolicy(resolver),
    )


class HybridKnowledgeRepository:
    """Compose keyword and approved vector adapters without inventing a vector schema."""
    def __init__(self, *, keyword_repository: SupabaseKeywordKnowledgeRepository, vector_search: Any | None):
        self._keyword = keyword_repository
        self._vector_search = vector_search

    async def authorize_agent(self, *, owner_id: str, agent_id: str) -> bool:
        return await self._keyword.authorize_agent(owner_id=owner_id, agent_id=agent_id)

    async def search_hybrid(
        self, *, owner_id: str, agent_id: str, query: str,
        allowed_sensitivities: list[str], limit: int, trace_id: str,
    ) -> list[RetrievalHit]:
        if self._vector_search is None:
            raise KnowledgeRetrievalUnavailable(
                "approved vector index/search adapter is not configured; hybrid retrieval is unavailable"
            )
        keyword_hits = await self._keyword.search_keyword(
            owner_id=owner_id, agent_id=agent_id, query=query,
            allowed_sensitivities=allowed_sensitivities, limit=limit, trace_id=trace_id,
        )
        vector_hits = await self._vector_search.search(
            owner_id=owner_id, agent_id=agent_id, query=query,
            allowed_sensitivities=allowed_sensitivities, limit=limit, trace_id=trace_id,
        )
        merged: dict[tuple[str, int, str], RetrievalHit] = {}
        for hit in [*keyword_hits, *vector_hits]:
            key = (hit.source_id, hit.source_version, hit.chunk_id)
            previous = merged.get(key)
            method = "hybrid" if previous is not None else hit.retrieval_method
            merged[key] = RetrievalHit(
                owner_id=hit.owner_id, agent_id=hit.agent_id, source_id=hit.source_id,
                source_version=hit.source_version, chunk_id=hit.chunk_id,
                content=hit.content, content_sha256=hit.content_sha256,
                source_location=hit.source_location, sensitivity=hit.sensitivity,
                retrieval_method=method, score=max(hit.score, previous.score if previous else hit.score),
                provider_id=hit.provider_id, model_id=hit.model_id,
                model_version=hit.model_version, index_generation=hit.index_generation,
            )
        # Do not invent an evaluation-derived rank score; preserve the adapter score
        # and return bounded candidates. Reranking remains a separately approved step.
        return list(merged.values())[:limit]

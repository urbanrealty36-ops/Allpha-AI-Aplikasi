import asyncio

import pytest

from allpha_api.knowledge_retrieval import (
    KnowledgeAccessDenied,
    KnowledgeRetrievalService,
    KnowledgeRetrievalUnavailable,
    RetrievalHit,
    RetrievalRequest,
)


def request():
    return RetrievalRequest(
        owner_id="owner-a", agent_id="agent-a", query="contract details",
        allowed_sensitivities=["internal"], limit=5, trace_id="trace-a",
    )


class Repo:
    def __init__(self, authorized=True, hits=None):
        self.authorized = authorized
        self.hits = hits or []
        self.search_args = None
    async def authorize_agent(self, *, owner_id, agent_id):
        return self.authorized and owner_id == "owner-a" and agent_id == "agent-a"
    async def search_hybrid(self, **kwargs):
        self.search_args = kwargs
        return self.hits


def hit(**overrides):
    value = dict(
        owner_id="owner-a", agent_id="agent-a", source_id="source-a", source_version=1,
        chunk_id="chunk-a", content="matching source excerpt", content_sha256="a" * 64,
        source_location={"kind":"page","index":1}, sensitivity="internal",
        retrieval_method="hybrid", score=0.5, index_generation=None,
    )
    value.update(overrides)
    return RetrievalHit(**value)


def test_retrieval_fails_closed_when_repository_is_missing():
    async def scenario():
        with pytest.raises(KnowledgeRetrievalUnavailable):
            await KnowledgeRetrievalService(None).retrieve(request())
    asyncio.run(scenario())


def test_retrieval_requires_owner_authorization_before_search():
    async def scenario():
        repo = Repo(authorized=False)
        with pytest.raises(KnowledgeAccessDenied):
            await KnowledgeRetrievalService(repo).retrieve(request())
        assert repo.search_args is None
    asyncio.run(scenario())


def test_retrieval_scopes_search_and_returns_source_provenance():
    async def scenario():
        repo = Repo(hits=[hit()])
        results = await KnowledgeRetrievalService(repo).retrieve(request())
        assert results[0].source_id == "source-a"
        assert repo.search_args["owner_id"] == "owner-a"
        assert repo.search_args["agent_id"] == "agent-a"
        assert repo.search_args["allowed_sensitivities"] == ["internal"]
        assert repo.search_args["limit"] == 5
    asyncio.run(scenario())


def test_retrieval_rejects_cross_owner_result_even_if_adapter_is_buggy():
    async def scenario():
        repo = Repo(hits=[hit(owner_id="owner-b")])
        with pytest.raises(KnowledgeAccessDenied):
            await KnowledgeRetrievalService(repo).retrieve(request())
    asyncio.run(scenario())


def test_retrieval_rejects_disallowed_sensitivity():
    async def scenario():
        repo = Repo(hits=[hit(sensitivity="restricted")])
        with pytest.raises(KnowledgeAccessDenied):
            await KnowledgeRetrievalService(repo).retrieve(request())
    asyncio.run(scenario())

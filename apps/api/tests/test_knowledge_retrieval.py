import asyncio
import hashlib
import uuid

import pytest
from fastapi import Request
from fastapi.testclient import TestClient
from types import SimpleNamespace

from allpha_api.auth import current_user
from allpha_api.knowledge_retrieval import (
    KnowledgeAccessDenied,
    KnowledgeRetrievalService,
    KnowledgeRetrievalUnavailable,
    RetrievalHit,
    RetrievalRequest,
)
from allpha_api.main import app


def internal_request():
    return RetrievalRequest(
        owner_id="owner-a", agent_id="agent-a", query="contract details",
        allowed_sensitivities=["internal"], allowed_source_ids=["00000000-0000-0000-0000-0000000000c9"],
        limit=5, trace_id="trace-a",
    )


class Policy:
    def __init__(self, values=None):
        self.values = values if values is not None else ["internal"]
        self.calls = []
    async def allowed_sensitivities(self, *, owner_id, agent_id):
        self.calls.append((owner_id, agent_id))
        return self.values
    async def resolve_context(self, *, owner_id, agent_id):
        self.calls.append((owner_id, agent_id))
        return SimpleNamespace(policy_version="test-policy.v1", consent_version="test-consent.v1",
            allowed_sensitivities=tuple(self.values), allowed_source_ids=("00000000-0000-0000-0000-0000000000c9",),
            grant_version="test-grant.v1", audience="owner_private", decision_reference="test-decision")


class Repo:
    def __init__(self, authorized=True, hits=None):
        self.authorized = authorized
        self.hits = hits or []
        self.search_args = None
        self.authorize_calls = []
    async def authorize_agent(self, *, owner_id, agent_id):
        self.authorize_calls.append((owner_id, agent_id))
        return self.authorized and owner_id == "owner-a" and agent_id in {"agent-a", str(uuid.UUID(int=101))}
    async def search_hybrid(self, **kwargs):
        self.search_args = kwargs
        return self.hits


def hit(**overrides):
    value = dict(
        owner_id="owner-a", agent_id="agent-a", source_id="00000000-0000-0000-0000-0000000000c9", source_version=1,
        chunk_id="chunk-a", content="matching source excerpt", content_sha256=hashlib.sha256(b"matching source excerpt").hexdigest(),
        source_location={"kind":"page","index":1}, sensitivity="internal",
        retrieval_method="keyword", score=0.5, index_generation=None,
    )
    value.update(overrides)
    return RetrievalHit(**value)


def test_retrieval_fails_closed_when_repository_or_policy_is_missing():
    async def scenario():
        with pytest.raises(KnowledgeRetrievalUnavailable):
            await KnowledgeRetrievalService(None).retrieve(internal_request())
        with pytest.raises(KnowledgeRetrievalUnavailable):
            await KnowledgeRetrievalService(Repo()).retrieve(internal_request())
    asyncio.run(scenario())


def test_retrieval_requires_owner_authorization_before_search():
    async def scenario():
        repo = Repo(authorized=False)
        with pytest.raises(KnowledgeAccessDenied):
            await KnowledgeRetrievalService(repo, Policy()).retrieve(internal_request())
        assert repo.search_args is None
    asyncio.run(scenario())


def test_retrieval_scopes_search_and_returns_source_provenance():
    async def scenario():
        repo = Repo(hits=[hit()])
        results = await KnowledgeRetrievalService(repo, Policy()).retrieve(internal_request())
        assert results[0].source_id == "00000000-0000-0000-0000-0000000000c9"
        assert repo.search_args["owner_id"] == "owner-a"
        assert repo.search_args["agent_id"] == "agent-a"
        assert repo.search_args["allowed_sensitivities"] == ["internal"]
        assert repo.search_args["allowed_source_ids"] == ["00000000-0000-0000-0000-0000000000c9"]
        assert repo.search_args["limit"] == 5
    asyncio.run(scenario())


def test_retrieval_returns_empty_list_without_fabricating_results():
    async def scenario():
        repo = Repo(hits=[])
        results = await KnowledgeRetrievalService(repo, Policy()).retrieve(internal_request())
        assert results == []
        assert repo.search_args["owner_id"] == "owner-a"
        assert repo.search_args["agent_id"] == "agent-a"
    asyncio.run(scenario())


def test_configured_sensitivity_policy_fails_closed_when_unset_or_invalid(monkeypatch):
    from allpha_api.knowledge_retrieval import ConfiguredKnowledgeRetrievalPolicy

    monkeypatch.delenv("ALLPHA_KNOWLEDGE_ALLOWED_SENSITIVITIES", raising=False)
    assert asyncio.run(ConfiguredKnowledgeRetrievalPolicy.from_environment().allowed_sensitivities(
        owner_id="owner-a", agent_id="agent-a"
    )) == []

    monkeypatch.setenv("ALLPHA_KNOWLEDGE_ALLOWED_SENSITIVITIES", "internal,unknown")
    assert asyncio.run(ConfiguredKnowledgeRetrievalPolicy.from_environment().allowed_sensitivities(
        owner_id="owner-a", agent_id="agent-a"
    )) == []

    monkeypatch.setenv("ALLPHA_KNOWLEDGE_ALLOWED_SENSITIVITIES", " internal, public,internal ")
    assert asyncio.run(ConfiguredKnowledgeRetrievalPolicy.from_environment().allowed_sensitivities(
        owner_id="owner-a", agent_id="agent-a"
    )) == ["internal", "public"]


def test_retrieval_rejects_cross_owner_result_even_if_adapter_is_buggy():
    async def scenario():
        repo = Repo(hits=[hit(owner_id="owner-b")])
        with pytest.raises(KnowledgeAccessDenied):
            await KnowledgeRetrievalService(repo, Policy()).retrieve(internal_request())
    asyncio.run(scenario())


def test_retrieval_rejects_disallowed_sensitivity():
    async def scenario():
        repo = Repo(hits=[hit(sensitivity="restricted")])
        with pytest.raises(KnowledgeAccessDenied):
            await KnowledgeRetrievalService(repo, Policy()).retrieve(internal_request())
    asyncio.run(scenario())


def test_retrieval_rejects_missing_source_provenance():
    async def scenario():
        repo = Repo(hits=[hit(source_id="", content_sha256="")])
        with pytest.raises(KnowledgeRetrievalUnavailable):
            await KnowledgeRetrievalService(repo, Policy()).retrieve(internal_request())
    asyncio.run(scenario())


def test_public_route_rejects_forged_owner_and_sensitivity_fields(monkeypatch):
    async def fake_current_user(request: Request):
        request.state.user_id = "owner-a"
        return {"id": "owner-a"}
    app.dependency_overrides[current_user] = fake_current_user
    try:
        response = TestClient(app).post(
            f"/v1/agents/{uuid.UUID(int=101)}/knowledge/retrieve",
            json={"query":"private info","owner_id":"owner-b","allowed_sensitivities":["restricted"]},
            headers={"Authorization":"Bearer test"},
        )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 422


def test_public_route_fails_closed_when_retrieval_not_configured(monkeypatch):
    async def fake_current_user(request: Request):
        return {"id": "owner-a"}
    app.dependency_overrides[current_user] = fake_current_user
    prior = getattr(app.state, "knowledge_retrieval_service", None)
    if hasattr(app.state, "knowledge_retrieval_service"):
        delattr(app.state, "knowledge_retrieval_service")
    try:
        response = TestClient(app).post(
            f"/v1/agents/{uuid.UUID(int=101)}/knowledge/retrieve",
            json={"query":"private info"},
            headers={"Authorization":"Bearer test"},
        )
    finally:
        app.dependency_overrides.clear()
        if prior is not None:
            app.state.knowledge_retrieval_service = prior
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "KNOWLEDGE_RETRIEVAL_UNAVAILABLE"


def test_public_route_denies_unowned_agent_before_search():
    async def fake_current_user(request: Request):
        return {"id": "owner-a"}

    async def scenario():
        repo = Repo(authorized=False)
        prior = getattr(app.state, "knowledge_retrieval_service", None)
        app.state.knowledge_retrieval_service = KnowledgeRetrievalService(repo, Policy())
        app.dependency_overrides[current_user] = fake_current_user
        try:
            response = TestClient(app).post(
                f"/v1/agents/{uuid.UUID(int=101)}/knowledge/retrieve",
                json={"query": "private info"},
                headers={"Authorization": "Bearer test"},
            )
        finally:
            app.dependency_overrides.clear()
            if prior is None:
                delattr(app.state, "knowledge_retrieval_service")
            else:
                app.state.knowledge_retrieval_service = prior
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "KNOWLEDGE_ACCESS_DENIED"
        assert repo.search_args is None

    asyncio.run(scenario())


def test_public_route_returns_empty_results_with_trace_when_no_matches():
    async def fake_current_user(request: Request):
        return {"id": "owner-a"}

    async def scenario():
        repo = Repo(hits=[])
        prior = getattr(app.state, "knowledge_retrieval_service", None)
        app.state.knowledge_retrieval_service = KnowledgeRetrievalService(repo, Policy())
        app.dependency_overrides[current_user] = fake_current_user
        try:
            response = TestClient(app).post(
                f"/v1/agents/{uuid.UUID(int=101)}/knowledge/retrieve",
                json={"query": "no matching source"},
                headers={"Authorization": "Bearer test", "X-Request-ID": "trace-empty"},
            )
        finally:
            app.dependency_overrides.clear()
            if prior is None:
                delattr(app.state, "knowledge_retrieval_service")
            else:
                app.state.knowledge_retrieval_service = prior
        assert response.status_code == 200
        assert response.json() == {
            "trace_id": "trace-empty", "results": [],
            "policy_version": "test-policy.v1", "consent_version": "test-consent.v1",
        }

    asyncio.run(scenario())


def test_public_route_derives_owner_from_authenticated_identity_and_policy():
    async def fake_current_user(request: Request):
        return {"id": "owner-a"}
    async def scenario():
        repo = Repo(hits=[hit(agent_id=str(uuid.UUID(int=101)))])
        policy = Policy(["internal"])
        app.state.knowledge_retrieval_service = KnowledgeRetrievalService(repo, policy)
        app.dependency_overrides[current_user] = fake_current_user
        try:
            response = TestClient(app).post(
                f"/v1/agents/{uuid.UUID(int=101)}/knowledge/retrieve",
                json={"query":"contract details","limit":5},
                headers={"Authorization":"Bearer test","X-Request-ID":"trace-http"},
            )
        finally:
            app.dependency_overrides.clear()
            delattr(app.state, "knowledge_retrieval_service")
        assert response.status_code == 200
        assert repo.authorize_calls[0] == ("owner-a", str(uuid.UUID(int=101)))
        assert policy.calls == [("owner-a", str(uuid.UUID(int=101)))]
        assert repo.search_args["owner_id"] == "owner-a"
        assert response.json()["results"][0]["source_id"] == "00000000-0000-0000-0000-0000000000c9"
    asyncio.run(scenario())


def test_supabase_keyword_repository_pushes_security_filters_into_database_query(monkeypatch):
    from allpha_api import auth
    from allpha_api.knowledge_retrieval import SupabaseKeywordKnowledgeRepository

    calls = []
    async def fake_request(method, path, access_token, *, params=None, body=None, prefer=None):
        calls.append((method, path, access_token, params))
        return [{
            "id": "chunk-a", "source_id": "source-a", "agent_id": "agent-a",
            "owner_id": "owner-a", "chunk_index": 0, "content": "private text",
            "source_location": {"kind": "page", "index": 1}, "source_version": 2,
            "content_sha256": hashlib.sha256(b"private text").hexdigest(),
            "agent_knowledge_sources": {
                "id": "source-a", "owner_id": "owner-a", "agent_id": "agent-a",
                "source_version": 2, "status": "ready", "sensitivity": "internal",
            },
        }]
    monkeypatch.setattr(auth, "user_db_request", fake_request)
    async def scenario():
        repo = SupabaseKeywordKnowledgeRepository(access_token="user-token")
        hits = await repo.search_keyword(
            owner_id="owner-a", agent_id="agent-a", query="private phrase",
            allowed_sensitivities=["internal"], allowed_source_ids=["source-a"], limit=7, trace_id="trace-1",
        )
        assert len(hits) == 1 and hits[0].retrieval_method == "keyword"
        method, path, token, params = calls[0]
        assert (method, path, token) == ("GET", "agent_knowledge_chunks", "user-token")
        assert params["owner_id"] == "eq.owner-a"
        assert params["agent_id"] == "eq.agent-a"
        assert params["agent_knowledge_sources.owner_id"] == "eq.owner-a"
        assert params["agent_knowledge_sources.agent_id"] == "eq.agent-a"
        assert params["agent_knowledge_sources.status"] == "eq.ready"
        assert params["source_id"] == "in.(source-a)"
        assert params["agent_knowledge_sources.sensitivity"] == "in.(internal)"
        assert params["search_vector"] == "fts(simple).private phrase"
        assert params["limit"] == "7"
    asyncio.run(scenario())


def test_supabase_keyword_repository_rejects_source_version_conflict(monkeypatch):
    from allpha_api import auth
    from allpha_api.knowledge_retrieval import (
        KnowledgeRetrievalUnavailable, SupabaseKeywordKnowledgeRepository,
    )
    async def fake_request(method, path, access_token, *, params=None, body=None, prefer=None):
        return [{
            "id": "chunk-a", "source_id": "source-a", "agent_id": "agent-a",
            "owner_id": "owner-a", "chunk_index": 0, "content": "private text",
            "source_location": {}, "source_version": 1, "content_sha256": hashlib.sha256(b"private text").hexdigest(),
            "agent_knowledge_sources": {
                "id": "source-a", "owner_id": "owner-a", "agent_id": "agent-a",
                "source_version": 2, "status": "ready", "sensitivity": "internal",
            },
        }]
    monkeypatch.setattr(auth, "user_db_request", fake_request)
    async def scenario():
        repo = SupabaseKeywordKnowledgeRepository(access_token="user-token")
        with pytest.raises(KnowledgeRetrievalUnavailable):
            await repo.search_keyword(
                owner_id="owner-a", agent_id="agent-a", query="private phrase",
                allowed_sensitivities=["internal"], allowed_source_ids=["source-a"], limit=5, trace_id="trace-1",
            )
    asyncio.run(scenario())


def test_hybrid_repository_fails_closed_without_approved_vector_adapter():
    from allpha_api.knowledge_retrieval import (
        HybridKnowledgeRepository, KnowledgeRetrievalUnavailable,
        SupabaseKeywordKnowledgeRepository,
    )
    async def scenario():
        repo = HybridKnowledgeRepository(
            keyword_repository=SupabaseKeywordKnowledgeRepository(access_token="user-token"),
            vector_search=None,
        )
        with pytest.raises(KnowledgeRetrievalUnavailable):
            await repo.search_hybrid(
                owner_id="owner-a", agent_id="agent-a", query="text",
                allowed_sensitivities=["internal"], allowed_source_ids=["source-a"], limit=5, trace_id="trace-1",
            )
    asyncio.run(scenario())


def test_keyword_only_repository_is_explicitly_keyword_not_hybrid(monkeypatch):
    from allpha_api import auth
    from allpha_api.knowledge_retrieval import KeywordOnlyKnowledgeRepository, SupabaseKeywordKnowledgeRepository

    async def fake_request(method, path, access_token, *, params=None, body=None, prefer=None):
        if path == "agent_knowledge_chunks":
            return [{
                "id": "chunk-keyword", "source_id": "source-a", "agent_id": "agent-a",
                "owner_id": "owner-a", "chunk_index": 0, "content": "verified keyword result",
                "source_location": {}, "source_version": 1, "content_sha256": hashlib.sha256(b"verified keyword result").hexdigest(),
                "agent_knowledge_sources": {"id": "source-a", "owner_id": "owner-a", "agent_id": "agent-a",
                    "source_version": 1, "status": "ready", "sensitivity": "internal"},
            }]
        return [{"agent_id": "agent-a"}]

    monkeypatch.setattr(auth, "user_db_request", fake_request)
    async def scenario():
        repo = KeywordOnlyKnowledgeRepository(
            keyword_repository=SupabaseKeywordKnowledgeRepository(access_token="user-token")
        )
        hits = await repo.search_hybrid(owner_id="owner-a", agent_id="agent-a", query="verified",
            allowed_sensitivities=["internal"], allowed_source_ids=["source-a"], limit=5, trace_id="trace-keyword")
        assert len(hits) == 1
        assert hits[0].retrieval_method == "keyword"
        assert hits[0].index_generation is None
        assert hits[0].provider_id is None and hits[0].model_id is None
    asyncio.run(scenario())


def test_keyword_runtime_stays_disabled_when_only_sensitivity_allowlist_is_configured(monkeypatch):
    from starlette.requests import Request as StarletteRequest
    from allpha_api.knowledge_retrieval import request_scoped_retrieval_service

    scope = {
        "type": "http", "app": app,
        "state": {"supabase_access_token": "user-token"},
        "method": "POST", "path": "/", "headers": [], "query_string": b"",
        "server": ("test", 80), "client": ("test", 1), "scheme": "http",
    }
    monkeypatch.setattr(
        "allpha_api.knowledge_retrieval.os.getenv",
        lambda key, default="": {
            "ALLPHA_KNOWLEDGE_RETRIEVAL_MODE": "keyword",
            "ALLPHA_KNOWLEDGE_ALLOWED_SENSITIVITIES": "internal",
        }.get(key, default),
    )
    assert request_scoped_retrieval_service(StarletteRequest(scope)) is None

def test_keyword_runtime_stays_disabled_without_explicit_mode_or_policy(monkeypatch):
    from starlette.requests import Request as StarletteRequest
    from allpha_api.knowledge_retrieval import request_scoped_retrieval_service
    scope = {"type": "http", "app": app, "state": {"supabase_access_token": "user-token"},
        "method": "POST", "path": "/", "headers": [], "query_string": b"", "server": ("test", 80),
        "client": ("test", 1), "scheme": "http"}
    monkeypatch.setattr("allpha_api.knowledge_retrieval.os.getenv", lambda key, default="": default)
    assert request_scoped_retrieval_service(StarletteRequest(scope)) is None

def test_retrieval_rejects_source_outside_active_grant_scope_even_if_adapter_is_buggy():
    async def scenario():
        repo = Repo(hits=[hit(source_id="00000000-0000-0000-0000-0000000000ca")])
        with pytest.raises(KnowledgeAccessDenied, match="outside the active grant scope"):
            await KnowledgeRetrievalService(repo, Policy()).retrieve(internal_request())
    asyncio.run(scenario())


def test_retrieval_rejects_cross_agent_result_even_if_adapter_is_buggy():
    async def scenario():
        repo = Repo(hits=[hit(agent_id="agent-b")])
        with pytest.raises(KnowledgeAccessDenied):
            await KnowledgeRetrievalService(repo, Policy()).retrieve(internal_request())
    asyncio.run(scenario())


def test_supabase_keyword_repository_rejects_unready_source_even_if_query_adapter_returns_it(monkeypatch):
    from allpha_api import auth
    from allpha_api.knowledge_retrieval import KnowledgeRetrievalUnavailable, SupabaseKeywordKnowledgeRepository

    calls = []
    async def fake_request(method, path, access_token, *, params=None, body=None, prefer=None):
        calls.append((method, path, params))
        return [{
            "id": "chunk-unready", "source_id": "source-unready", "agent_id": "agent-a",
            "owner_id": "owner-a", "chunk_index": 0, "content": "must not leak",
            "source_location": {}, "source_version": 1, "content_sha256": hashlib.sha256(b"must not leak").hexdigest(),
            "agent_knowledge_sources": {
                "id": "source-unready", "owner_id": "owner-a", "agent_id": "agent-a",
                "source_version": 1, "status": "processing", "sensitivity": "internal",
            },
        }]
    monkeypatch.setattr(auth, "user_db_request", fake_request)

    async def scenario():
        repo = SupabaseKeywordKnowledgeRepository(access_token="user-token")
        with pytest.raises(KnowledgeRetrievalUnavailable):
            await repo.search_keyword(
                owner_id="owner-a", agent_id="agent-a", query="must not leak",
                allowed_sensitivities=["internal"], allowed_source_ids=["source-unready"], limit=5, trace_id="trace-unready",
            )
        assert calls[0][2]["agent_knowledge_sources.owner_id"] == "eq.owner-a"
        assert calls[0][2]["agent_knowledge_sources.agent_id"] == "eq.agent-a"
        assert calls[0][2]["agent_knowledge_sources.status"] == "eq.ready"
    asyncio.run(scenario())


def test_public_route_traces_resolved_policy_and_consent_versions():
    from allpha_api.knowledge_policy import (
        KnowledgePolicySnapshot, VersionedKnowledgePolicyResolver,
        VersionedKnowledgeRetrievalPolicy,
    )

    async def fake_current_user(request: Request):
        return {"id": "owner-a"}

    class Provider:
        async def resolve(self, *, owner_id, agent_id, audience):
            return KnowledgePolicySnapshot(
                policy_version="knowledge-policy.v3",
                owner_id=owner_id,
                agent_id=agent_id,
                allowed_sensitivities=("internal",),
                allowed_source_ids=("00000000-0000-0000-0000-0000000000c9",),
                audience="owner_private", grant_version="knowledge-grant.v1", decision_reference="decision-42",
                knowledge_consent_granted=True,
                consent_version="knowledge-consent.v2",
                consent_revoked=False,
                allowed_purposes=("agent_context_retrieval",),
                grants_active=True,
                resolved_at_version="snapshot-42",
            )

    async def scenario():
        repo = Repo(hits=[hit(agent_id=str(uuid.UUID(int=101)))])
        policy = VersionedKnowledgeRetrievalPolicy(VersionedKnowledgePolicyResolver(Provider()))
        prior = getattr(app.state, "knowledge_retrieval_service", None)
        app.state.knowledge_retrieval_service = KnowledgeRetrievalService(repo, policy)
        app.dependency_overrides[current_user] = fake_current_user
        try:
            response = TestClient(app).post(
                f"/v1/agents/{uuid.UUID(int=101)}/knowledge/retrieve",
                json={"query": "contract details"},
                headers={"Authorization": "Bearer test", "X-Request-ID": "trace-policy"},
            )
        finally:
            app.dependency_overrides.clear()
            if prior is None:
                delattr(app.state, "knowledge_retrieval_service")
            else:
                app.state.knowledge_retrieval_service = prior
        assert response.status_code == 200
        assert response.json()["policy_version"] == "knowledge-policy.v3"
        assert response.json()["consent_version"] == "knowledge-consent.v2"

    asyncio.run(scenario())


def test_public_route_fails_closed_on_revoked_knowledge_consent_before_search():
    from allpha_api.knowledge_policy import (
        KnowledgePolicySnapshot, VersionedKnowledgePolicyResolver,
        VersionedKnowledgeRetrievalPolicy,
    )

    async def fake_current_user(request: Request):
        return {"id": "owner-a"}

    class Provider:
        async def resolve(self, *, owner_id, agent_id, audience):
            return KnowledgePolicySnapshot(
                policy_version="knowledge-policy.v3",
                owner_id=owner_id,
                agent_id=agent_id,
                allowed_sensitivities=("internal",),
                allowed_source_ids=("00000000-0000-0000-0000-0000000000c9",),
                audience="owner_private", grant_version="knowledge-grant.v1", decision_reference="decision-42",
                knowledge_consent_granted=True,
                consent_version="knowledge-consent.v2",
                consent_revoked=True,
                allowed_purposes=("agent_context_retrieval",),
                grants_active=True,
                resolved_at_version="snapshot-43",
            )

    async def scenario():
        repo = Repo(hits=[hit(agent_id=str(uuid.UUID(int=101)))])
        policy = VersionedKnowledgeRetrievalPolicy(VersionedKnowledgePolicyResolver(Provider()))
        prior = getattr(app.state, "knowledge_retrieval_service", None)
        app.state.knowledge_retrieval_service = KnowledgeRetrievalService(repo, policy)
        app.dependency_overrides[current_user] = fake_current_user
        try:
            response = TestClient(app).post(
                f"/v1/agents/{uuid.UUID(int=101)}/knowledge/retrieve",
                json={"query": "private details"},
                headers={"Authorization": "Bearer test"},
            )
        finally:
            app.dependency_overrides.clear()
            if prior is None:
                delattr(app.state, "knowledge_retrieval_service")
            else:
                app.state.knowledge_retrieval_service = prior
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "KNOWLEDGE_ACCESS_DENIED"
        assert repo.search_args is None

    asyncio.run(scenario())



def test_supabase_keyword_repository_rejects_content_digest_mismatch(monkeypatch):
    from allpha_api import auth
    from allpha_api.knowledge_retrieval import KnowledgeRetrievalUnavailable, SupabaseKeywordKnowledgeRepository

    async def fake_request(method, path, access_token, *, params=None, body=None, prefer=None):
        return [{
            "id": "chunk-a", "source_id": "source-a", "agent_id": "agent-a",
            "owner_id": "owner-a", "chunk_index": 0, "content": "tampered private text",
            "source_location": {}, "source_version": 2,
            "content_sha256": hashlib.sha256(b"original private text").hexdigest(),
            "agent_knowledge_sources": {
                "id": "source-a", "owner_id": "owner-a", "agent_id": "agent-a",
                "source_version": 2, "status": "ready", "sensitivity": "internal",
            },
        }]

    monkeypatch.setattr(auth, "user_db_request", fake_request)

    async def scenario():
        repo = SupabaseKeywordKnowledgeRepository(access_token="user-token")
        with pytest.raises(KnowledgeRetrievalUnavailable, match="content digest"):
            await repo.search_keyword(
                owner_id="owner-a", agent_id="agent-a", query="private phrase",
                allowed_sensitivities=["internal"], allowed_source_ids=["source-a"], limit=5, trace_id="trace-digest",
            )

    asyncio.run(scenario())



def test_retrieval_service_rejects_content_digest_mismatch():
    async def scenario():
        repo = Repo(hits=[hit(content="tampered excerpt", content_sha256=hashlib.sha256(b"original excerpt").hexdigest())])
        with pytest.raises(KnowledgeRetrievalUnavailable, match="content digest"):
            await KnowledgeRetrievalService(repo, Policy()).retrieve(internal_request())

    asyncio.run(scenario())



def test_supabase_keyword_repository_rejects_cross_owner_source_relation(monkeypatch):
    from allpha_api import auth
    from allpha_api.knowledge_retrieval import KnowledgeRetrievalUnavailable, SupabaseKeywordKnowledgeRepository

    async def fake_request(method, path, access_token, *, params=None, body=None, prefer=None):
        return [{
            "id": "chunk-a", "source_id": "source-a", "agent_id": "agent-a",
            "owner_id": "owner-a", "chunk_index": 0, "content": "private text",
            "source_location": {}, "source_version": 2,
            "content_sha256": hashlib.sha256(b"private text").hexdigest(),
            "agent_knowledge_sources": {
                "id": "source-a", "owner_id": "owner-b", "agent_id": "agent-a",
                "source_version": 2, "status": "ready", "sensitivity": "internal",
            },
        }]

    monkeypatch.setattr(auth, "user_db_request", fake_request)

    async def scenario():
        repo = SupabaseKeywordKnowledgeRepository(access_token="user-token")
        with pytest.raises(KnowledgeRetrievalUnavailable, match="owner/source/version"):
            await repo.search_keyword(
                owner_id="owner-a", agent_id="agent-a", query="private phrase",
                allowed_sensitivities=["internal"], allowed_source_ids=["source-a"], limit=5, trace_id="trace-cross-owner",
            )

    asyncio.run(scenario())


@pytest.mark.parametrize("overrides", [
    {"source_version": 0}, {"source_version": True}, {"source_location": None},
    {"score": float("nan")}, {"score": float("inf")},
    {"retrieval_method": "vector"},
    {"retrieval_method": "hybrid", "provider_id": "p", "model_id": "m", "model_version": "v1", "index_generation": " "},
])
def test_retrieval_rejects_hits_with_invalid_citation_or_vector_provenance(overrides):
    async def scenario():
        repo = Repo(hits=[hit(**overrides)])
        with pytest.raises(KnowledgeRetrievalUnavailable):
            await KnowledgeRetrievalService(repo, Policy()).retrieve(internal_request())
    asyncio.run(scenario())


def test_retrieval_accepts_vector_hit_with_full_model_and_index_identity():
    async def scenario():
        repo = Repo(hits=[hit(retrieval_method="vector", provider_id="p", model_id="m", model_version="v1", index_generation="gen-1")])
        assert len(await KnowledgeRetrievalService(repo, Policy()).retrieve(internal_request())) == 1
    asyncio.run(scenario())


def test_retrieval_rejects_duplicate_chunks_and_over_limit_results():
    async def scenario():
        with pytest.raises(KnowledgeRetrievalUnavailable):
            await KnowledgeRetrievalService(Repo(hits=[hit(), hit()]), Policy()).retrieve(internal_request())
        many = [hit(chunk_id=f"c{i}") for i in range(6)]
        with pytest.raises(KnowledgeRetrievalUnavailable):
            await KnowledgeRetrievalService(Repo(hits=many), Policy()).retrieve(internal_request())
    asyncio.run(scenario())

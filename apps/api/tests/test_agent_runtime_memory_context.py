import asyncio
import hashlib
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from allpha_api.agent_runtime_api import (
    _knowledge_context_snapshot, _memory_context_snapshot,
    _validate_knowledge_context_provenance, _revalidate_knowledge_context_sources,
    _retrieve_agent_knowledge_context,
)
from allpha_api.knowledge_retrieval import KnowledgeRetrievalService, RetrievalHit
from allpha_api.memory_coordinator import MemoryUnavailable


def memory_item(content="Owner prefers concise, direct explanations."):
    return {
        "id": "memory-item-1",
        "content": content,
        "content_sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
        "retrieved_content_sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
        "memory_type": "long_term",
        "classification": "internal",
        "version": 3,
        "policy_version": 5,
        "source_ref": {"private_message_id": "must-not-enter-planner-payload"},
        "provenance": {"private_origin": "must-not-enter-planner-payload"},
    }


def test_memory_snapshot_contains_only_consent_scoped_prompt_data_and_provenance():
    context, references, digest = _memory_context_snapshot([memory_item()])

    assert context == [{
        "memory_type": "long_term",
        "classification": "internal",
        "content": "Owner prefers concise, direct explanations.",
    }]
    assert references == [{
        "id": "memory-item-1",
        "content_sha256": memory_item()["content_sha256"],
        "retrieved_content_sha256": memory_item()["retrieved_content_sha256"],
        "version": 3,
        "policy_version": 5,
    }]
    assert len(digest) == 64
    assert "private_message_id" not in str(context)
    assert "private_origin" not in str(references)


def test_memory_snapshot_fails_closed_when_content_digest_or_version_is_invalid():
    invalid_digest = {**memory_item(), "retrieved_content_sha256": "0" * 64}
    with pytest.raises(MemoryUnavailable):
        _memory_context_snapshot([invalid_digest])

    invalid_version = {**memory_item(), "version": True}
    with pytest.raises(MemoryUnavailable):
        _memory_context_snapshot([invalid_version])



def test_memory_snapshot_accepts_verified_bounded_excerpt_with_full_source_digest():
    full_content = "A" * 7000
    excerpt = full_content[:3000]
    item = {
        **memory_item(full_content),
        "content": excerpt,
        "retrieved_content_sha256": hashlib.sha256(excerpt.encode("utf-8")).hexdigest(),
    }

    context, references, digest = _memory_context_snapshot([item])

    assert context[0]["content"] == excerpt
    assert references[0]["content_sha256"] == hashlib.sha256(full_content.encode("utf-8")).hexdigest()
    assert references[0]["retrieved_content_sha256"] == hashlib.sha256(excerpt.encode("utf-8")).hexdigest()
    assert references[0]["content_sha256"] != references[0]["retrieved_content_sha256"]
    assert len(digest) == 64



def knowledge_hit(content="Owner-approved document excerpt."):
    return RetrievalHit(
        owner_id="owner-a",
        agent_id="agent-a",
        source_id="11111111-1111-4111-8111-111111111111",
        source_version=4,
        chunk_id="22222222-2222-4222-8222-222222222222",
        content=content,
        content_sha256=hashlib.sha256(content.encode("utf-8")).hexdigest(),
        source_location={"kind": "page", "index": 3},
        sensitivity="internal",
        retrieval_method="keyword",
        score=0.0,
    )


def test_knowledge_context_snapshot_keeps_prompt_content_separate_from_citation_refs():
    hit = knowledge_hit()
    context, references, digest = _knowledge_context_snapshot([hit])

    assert context == [{
        "source_id": "11111111-1111-4111-8111-111111111111",
        "source_version": 4,
        "chunk_id": "22222222-2222-4222-8222-222222222222",
        "source_location": {"kind": "page", "index": 3},
        "sensitivity": "internal",
        "content_sha256": hit.content_sha256,
        "retrieved_content_sha256": hit.content_sha256,
        "content": hit.content,
    }]
    assert references[0]["source_id"] == "11111111-1111-4111-8111-111111111111"
    assert references[0]["source_version"] == 4
    assert references[0]["chunk_id"] == "22222222-2222-4222-8222-222222222222"
    assert "content" not in references[0]
    assert len(digest) == 64


def test_knowledge_context_snapshot_bounds_excerpt_and_preserves_both_digests():
    full = "K" * 7000
    context, references, digest = _knowledge_context_snapshot([knowledge_hit(full)], max_chars=6000)

    assert len(context[0]["content"]) == 6000
    assert references[0]["content_sha256"] == hashlib.sha256(full.encode("utf-8")).hexdigest()
    assert references[0]["retrieved_content_sha256"] == hashlib.sha256(context[0]["content"].encode("utf-8")).hexdigest()
    assert references[0]["content_sha256"] != references[0]["retrieved_content_sha256"]
    assert len(digest) == 64


def test_agent_runtime_marks_knowledge_not_configured_without_policy_service(monkeypatch):
    monkeypatch.setenv("ALLPHA_KNOWLEDGE_RETRIEVAL_MODE", "disabled")

    async def scenario():
        request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace()))
        result = await _retrieve_agent_knowledge_context(
            request, owner_id="owner-a", agent_id="agent-a",
            query="find relevant source", trace_id="trace-knowledge",
        )
        context, refs, digest, state = result
        assert context == [] and refs == []
        assert digest == hashlib.sha256(b"[]").hexdigest()
        assert state == "not_configured"

    asyncio.run(scenario())


def test_agent_runtime_retrieves_owner_authorized_knowledge_and_keeps_provenance():
    class Policy:
        async def resolve_context(self, *, owner_id, agent_id):
            assert (owner_id, agent_id) == ("owner-a", "agent-a")
            return SimpleNamespace(allowed_sensitivities=("internal",),
                allowed_source_ids=("11111111-1111-4111-8111-111111111111",),
                policy_version="knowledge-policy.v1", consent_version="consent.v1", grant_version="grant.v1",
                audience="owner_private", decision_reference="decision-1")

    class Repository:
        async def authorize_agent(self, *, owner_id, agent_id):
            return (owner_id, agent_id) == ("owner-a", "agent-a")

        async def search_hybrid(self, **kwargs):
            assert kwargs["owner_id"] == "owner-a"
            assert kwargs["agent_id"] == "agent-a"
            assert kwargs["allowed_sensitivities"] == ["internal"]
            assert kwargs["allowed_source_ids"] == ["11111111-1111-4111-8111-111111111111"]
            return [knowledge_hit()]

    async def scenario():
        service = KnowledgeRetrievalService(repository=Repository(), policy=Policy())
        request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(knowledge_retrieval_service=service)))
        context, refs, digest, state = await _retrieve_agent_knowledge_context(
            request, owner_id="owner-a", agent_id="agent-a",
            query="find relevant source", trace_id="trace-knowledge",
        )
        assert state == "available"
        assert context[0]["content"] == "Owner-approved document excerpt."
        assert refs[0]["source_id"] == "11111111-1111-4111-8111-111111111111"
        assert "content" not in refs[0]
        assert len(digest) == 64

    asyncio.run(scenario())


def test_agent_runtime_rejects_knowledge_context_without_valid_policy():
    class Policy:
        async def resolve_context(self, *, owner_id, agent_id):
            return SimpleNamespace(allowed_sensitivities=(), allowed_source_ids=(), policy_version="",
                consent_version="", grant_version="", audience="", decision_reference="")

    class Repository:
        async def authorize_agent(self, *, owner_id, agent_id):
            return True

        async def search_hybrid(self, **kwargs):
            raise AssertionError("retrieval must not run without a valid policy")

    async def scenario():
        service = KnowledgeRetrievalService(repository=Repository(), policy=Policy())
        request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(knowledge_retrieval_service=service)))
        from allpha_api.knowledge_retrieval import KnowledgeRetrievalUnavailable
        with pytest.raises(KnowledgeRetrievalUnavailable, match="source-grant scope"):
            await _retrieve_agent_knowledge_context(
                request, owner_id="owner-a", agent_id="agent-a",
                query="find relevant source", trace_id="trace-knowledge",
            )

    asyncio.run(scenario())



def test_agent_runtime_bounds_long_intent_before_knowledge_retrieval():
    class Policy:
        async def resolve_context(self, *, owner_id, agent_id):
            return SimpleNamespace(allowed_sensitivities=("internal",),
                allowed_source_ids=("11111111-1111-4111-8111-111111111111",),
                policy_version="knowledge-policy.v1", consent_version="consent.v1", grant_version="grant.v1",
                audience="owner_private", decision_reference="decision-1")

    class Repository:
        async def authorize_agent(self, *, owner_id, agent_id):
            return True

        async def search_hybrid(self, **kwargs):
            assert len(kwargs["query"]) == 4000
            return []

    async def scenario():
        service = KnowledgeRetrievalService(repository=Repository(), policy=Policy())
        request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(knowledge_retrieval_service=service)))
        context, refs, digest, state = await _retrieve_agent_knowledge_context(
            request, owner_id="owner-a", agent_id="agent-a",
            query="x" * 9000, trace_id="trace-long-intent",
        )
        assert context == [] and refs == []
        assert state == "empty"
        assert digest == hashlib.sha256(b"[]").hexdigest()

    asyncio.run(scenario())



def test_knowledge_context_snapshot_drops_untrusted_source_location_metadata():
    hit = knowledge_hit()
    hit = RetrievalHit(
        **{**hit.__dict__, "source_location": {"kind": "page", "index": 3, "raw_text": "must not persist"}}
    )
    context, references, _ = _knowledge_context_snapshot([hit])
    assert context[0]["source_location"] == {"kind": "page", "index": 3}
    assert "raw_text" not in str(context)
    assert "raw_text" not in str(references)



def test_task_knowledge_provenance_validator_accepts_content_free_references():
    hit = knowledge_hit()
    _, refs, _ = _knowledge_context_snapshot([hit])
    digest = hashlib.sha256(b"planner knowledge context").hexdigest()
    normalized, actual_digest, state = _validate_knowledge_context_provenance(refs, digest, "available")
    assert normalized == refs
    assert actual_digest == digest
    assert state == "available"
    assert "content" not in normalized[0]


def test_task_knowledge_provenance_validator_rejects_raw_document_content():
    hit = knowledge_hit()
    _, refs, _ = _knowledge_context_snapshot([hit])
    unsafe = [{**refs[0], "content": hit.content}]
    with pytest.raises(HTTPException) as exc:
        _validate_knowledge_context_provenance(
            unsafe, hashlib.sha256(b"planner knowledge context").hexdigest(), "available",
        )
    assert exc.value.status_code == 409
    assert exc.value.detail["code"] == "TOOL_PLAN_KNOWLEDGE_PROVENANCE_INVALID"


def test_task_knowledge_provenance_validator_accepts_not_configured_empty_state():
    empty_digest = hashlib.sha256(b"[]").hexdigest()
    refs, digest, state = _validate_knowledge_context_provenance([], empty_digest, "not_configured")
    assert refs == []
    assert digest == empty_digest
    assert state == "not_configured"



def test_task_creation_rejects_stale_knowledge_source_version(monkeypatch):
    hit = knowledge_hit()
    _, refs, _ = _knowledge_context_snapshot([hit])

    async def fake_user_db_request(method, path, access_token, *, params=None, body=None, prefer=None):
        assert access_token == "user-token"
        if path == "agent_knowledge_sources":
            return [{
                "id": refs[0]["source_id"], "owner_id": "owner-a", "agent_id": "agent-a",
                "source_version": 5, "status": "ready", "sensitivity": "internal",
            }]
        if path == "agent_knowledge_chunks":
            return [{
                "id": refs[0]["chunk_id"], "source_id": refs[0]["source_id"],
                "owner_id": "owner-a", "agent_id": "agent-a",
                "source_version": 4, "content_sha256": refs[0]["content_sha256"],
            }]
        raise AssertionError(f"unexpected path {path}")

    monkeypatch.setattr("allpha_api.agent_runtime_api.user_db_request", fake_user_db_request)

    async def scenario():
        request = SimpleNamespace(state=SimpleNamespace(supabase_access_token="user-token"))
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc:
            await _revalidate_knowledge_context_sources(
                request, owner_id="owner-a", agent_id="agent-a", refs=refs,
            )
        assert exc.value.status_code == 409
        assert exc.value.detail["code"] == "TOOL_PLAN_KNOWLEDGE_SNAPSHOT_STALE"

    asyncio.run(scenario())

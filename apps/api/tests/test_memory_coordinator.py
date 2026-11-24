import asyncio
import hashlib
import pytest

from allpha_api.memory_coordinator import (
    CONSENT_VERSION, MemoryCoordinator, MemoryDenied, MemoryUnavailable,
)

OWNER = "owner-1"
AGENT = "agent-1"


class FakeMemoryCoordinator(MemoryCoordinator):
    def __init__(self, *, owned=True, rows=None, policies=None):
        self.owned = owned
        self.rows = rows or []
        self.policy_rows = policies or [{
            "id": "policy-1", "memory_type": "long_term", "enabled": True,
            "consent_version": CONSENT_VERSION, "consent_revoked_at": None,
            "allowed_purposes": ["agent_generation_context"],
            "allowed_sensitivities": ["public", "internal"],
            "policy_version": 4,
        }]
        self.calls = []

    async def db(self, method, path, *, params=None, body=None, prefer=None):
        self.calls.append({"method": method, "path": path, "params": params, "body": body})
        if path == "agent_ownerships":
            return [{"agent_id": AGENT}] if self.owned else []
        if path == "agent_memory_policies":
            return self.policy_rows
        if path == "rpc/agent_memory_transition":
            return {"expired_count": 0}
        if path == "rpc/agent_memory_search":
            return self.rows
        raise AssertionError(f"unexpected Memory DB request: {method} {path}")


def memory_row(*, content="The owner prefers concise summaries.", classification="internal",
               score=0.75, policy_version=4):
    return {
        "id": "memory-1", "policy_id": "policy-1", "policy_version": policy_version,
        "memory_type": "long_term", "content": content, "classification": classification,
        "content_sha256": hashlib.sha256(content.encode()).hexdigest(),
        "retrieval_score": score, "retrieval_method": "keyword",
        "source_ref": {"message_id": "message-1"}, "provenance": {"origin": "owner"},
        "confidence": 0.92, "version": 2, "created_at": "2026-11-16T10:00:00Z",
    }


def test_retrieve_context_uses_ranked_policy_scoped_search_and_content_digest(monkeypatch):
    monkeypatch.setenv("ALLPHA_MEMORY_COORDINATOR_ENABLED", "true")
    store = FakeMemoryCoordinator(rows=[memory_row()])
    items = asyncio.run(store.retrieve_context(
        OWNER, AGENT, purpose="agent_generation_context",
        query="How should summaries be written?", limit=8, max_chars=2000,
        max_sensitivity="internal",
    ))
    assert len(items) == 1
    assert items[0]["retrieval_method"] == "keyword"
    assert items[0]["retrieval_score"] == 0.75
    search = next(call for call in store.calls if call["path"] == "rpc/agent_memory_search")
    assert search["method"] == "POST"
    assert search["body"]["p_owner_user_id"] == OWNER
    assert search["body"]["p_agent_id"] == AGENT
    assert search["body"]["p_query"] == "How should summaries be written?"
    assert search["body"]["p_max_sensitivity"] == "internal"
    assert search["body"]["p_policy_ids"] == ["policy-1"]
    ownership = next(call for call in store.calls if call["path"] == "agent_ownerships")
    assert ownership["params"]["ownership_role"] == "eq.owner"


def test_retrieve_context_uses_metadata_recency_when_query_is_absent(monkeypatch):
    monkeypatch.setenv("ALLPHA_MEMORY_COORDINATOR_ENABLED", "true")
    store = FakeMemoryCoordinator(rows=[memory_row()])
    items = asyncio.run(store.retrieve_context(OWNER, AGENT, purpose="agent_generation_context"))
    assert items[0]["retrieval_method"] == "metadata"
    search = next(call for call in store.calls if call["path"] == "rpc/agent_memory_search")
    assert search["body"]["p_query"] is None


def test_retrieve_context_fails_closed_on_policy_or_digest_mismatch(monkeypatch):
    monkeypatch.setenv("ALLPHA_MEMORY_COORDINATOR_ENABLED", "true")
    policy_mismatch = FakeMemoryCoordinator(rows=[memory_row(policy_version=99)])
    with pytest.raises(MemoryDenied):
        asyncio.run(policy_mismatch.retrieve_context(OWNER, AGENT, query="preference"))

    digest_mismatch = FakeMemoryCoordinator(rows=[{**memory_row(), "content_sha256": "0" * 64}])
    with pytest.raises(MemoryUnavailable):
        asyncio.run(digest_mismatch.retrieve_context(OWNER, AGENT, query="preference"))


def test_retrieve_context_does_not_search_without_active_agent_ownership(monkeypatch):
    monkeypatch.setenv("ALLPHA_MEMORY_COORDINATOR_ENABLED", "true")
    store = FakeMemoryCoordinator(owned=False, rows=[memory_row()])
    assert asyncio.run(store.retrieve_context(OWNER, AGENT, query="preference")) == []
    assert not any(call["path"] == "rpc/agent_memory_search" for call in store.calls)


def test_retrieve_context_rejects_rows_above_sensitivity_ceiling(monkeypatch):
    monkeypatch.setenv("ALLPHA_MEMORY_COORDINATOR_ENABLED", "true")
    store = FakeMemoryCoordinator(rows=[memory_row(classification="confidential")])
    with pytest.raises(MemoryDenied):
        asyncio.run(store.retrieve_context(
            OWNER, AGENT, query="preference", max_sensitivity="internal",
        ))


def test_explicit_memory_intent_checks_current_owner_before_existing_source_lookup(monkeypatch):
    monkeypatch.setenv("ALLPHA_MEMORY_COORDINATOR_ENABLED","true")
    store=FakeMemoryCoordinator(owned=False)
    with pytest.raises(MemoryDenied):
        asyncio.run(store.propose_explicit_intent(
            OWNER,AGENT,"remember that the owner prefers concise summaries",
            source_ref={"generation_job_id":"generation-1"},
        ))
    assert store.calls[0]["path"]=="agent_ownerships"
    assert store.calls[0]["params"]["ownership_role"]=="eq.owner"
    assert not any(call["path"]=="agent_memory_items" for call in store.calls)


def test_memory_api_agent_scope_requires_active_owner_role(monkeypatch):
    from types import SimpleNamespace
    from allpha_api import memory_api
    calls=[]
    async def fake_user_db_request(method,path,token,**kwargs):
        calls.append((method,path,token,kwargs))
        return [{"agent_id":AGENT}]
    monkeypatch.setattr(memory_api,"user_db_request",fake_user_db_request)
    request=SimpleNamespace(state=SimpleNamespace(supabase_access_token="owner-token"))
    asyncio.run(memory_api._owner(AGENT,request,{"id":OWNER}))
    assert calls[0][0:3]==("GET","agent_ownerships","owner-token")
    assert calls[0][3]["params"]["ownership_role"]=="eq.owner"
    assert calls[0][3]["params"]["status"]=="eq.active"


def test_memory_api_agent_scope_rejects_non_owner(monkeypatch):
    from types import SimpleNamespace
    from fastapi import HTTPException
    from allpha_api import memory_api
    async def fake_user_db_request(method,path,token,**kwargs):
        return []
    monkeypatch.setattr(memory_api,"user_db_request",fake_user_db_request)
    request=SimpleNamespace(state=SimpleNamespace(supabase_access_token="non-owner-token"))
    with pytest.raises(HTTPException) as error:
        asyncio.run(memory_api._owner(AGENT,request,{"id":"other-owner"}))
    assert error.value.status_code==404

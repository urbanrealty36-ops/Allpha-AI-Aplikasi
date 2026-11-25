import asyncio
import hashlib
import pytest

from allpha_api.memory_coordinator import (
    CONSENT_VERSION, MemoryCoordinator, MemoryDenied, MemoryUnavailable,
)

OWNER = "owner-1"
AGENT = "agent-1"


class FakeMemoryCoordinator(MemoryCoordinator):
    def __init__(self, *, owned=True, rows=None, policies=None, conversation_participants=None, message_rows=None):
        self.owned = owned
        self.rows = rows or []
        self.conversation_participants = conversation_participants or []
        self.message_rows = message_rows or []
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
        if path == "agent_memory_items":
            return self.rows
        if path == "conversation_participants":
            return self.conversation_participants
        if path == "messages":
            return self.message_rows
        if path == "rpc/expire_agent_memory_items_batch":
            return {"expired_count": 7}
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


def test_owner_pin_and_unpin_use_canonical_memory_transition(monkeypatch):
    store=FakeMemoryCoordinator()
    pinned=asyncio.run(store.pin(OWNER,"memory-1",True))
    unpinned=asyncio.run(store.pin(OWNER,"memory-1",False))
    assert pinned=={"expired_count":0}
    assert unpinned=={"expired_count":0}
    calls=[call for call in store.calls if call["path"]=="rpc/agent_memory_transition"]
    assert calls[0]["body"]["p_action"]=="pin"
    assert calls[0]["body"]["p_owner_user_id"]==OWNER
    assert calls[0]["body"]["p_item_id"]=="memory-1"
    assert calls[0]["body"]["p_payload"]=={"pinned":True}
    assert calls[1]["body"]["p_payload"]=={"pinned":False}


def test_owner_immediate_expiry_uses_canonical_memory_transition():
    store=FakeMemoryCoordinator()
    result=asyncio.run(store.expire_item(OWNER,"memory-1"))
    assert result=={"expired_count":0}
    call=store.calls[0]
    assert call["path"]=="rpc/agent_memory_transition"
    assert call["body"]["p_action"]=="expire_item"
    assert call["body"]["p_owner_user_id"]==OWNER
    assert call["body"]["p_item_id"]=="memory-1"


def test_memory_api_owner_pin_and_expire_routes_use_coordinator(monkeypatch):
    import uuid
    from allpha_api import memory_api
    item_id=uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
    calls=[]
    class Store:
        async def pin(self,owner_id,requested_item_id,pinned):
            calls.append(("pin",owner_id,requested_item_id,pinned))
            return {"id":str(requested_item_id),"status":"active","pinned_at":"2026-11-24T00:00:00Z" if pinned else None}
        async def expire_item(self,owner_id,requested_item_id):
            calls.append(("expire",owner_id,requested_item_id))
            return {"id":str(requested_item_id),"status":"expired"}
    monkeypatch.setattr(memory_api,"_store",lambda:Store())
    pinned=asyncio.run(memory_api.pin(item_id,memory_api.PinInput(pinned=True),{"id":OWNER}))
    expired=asyncio.run(memory_api.expire_item(item_id,{"id":OWNER}))
    assert pinned["pinned_at"]=="2026-11-24T00:00:00Z"
    assert expired["content_cleared"] is True
    assert calls==[("pin",OWNER,str(item_id),True),("expire",OWNER,str(item_id))]


def test_memory_items_projection_includes_owner_pin_state():
    store=FakeMemoryCoordinator()
    asyncio.run(store.items(OWNER,AGENT))
    call=store.calls[0]
    assert call["path"]=="agent_memory_items"
    assert "pinned_at" in call["params"]["select"].split(",")


def test_conversation_context_is_centralized_and_participant_scoped():
    import uuid
    conversation = str(uuid.uuid4())
    requester = str(uuid.uuid4())
    agent = str(uuid.uuid4())
    store = FakeMemoryCoordinator(
        policies=[{
            "id": "conversation-policy", "memory_type": "conversation", "enabled": True,
            "consent_version": CONSENT_VERSION, "consent_revoked_at": None,
            "allowed_purposes": ["agent_runtime_context"],
            "allowed_sensitivities": ["public", "internal", "confidential", "restricted"],
            "retention_days": 30, "policy_version": 2,
        }],
        conversation_participants=[{"user_id": requester}, {"agent_id": agent}],
        message_rows=[
            {"sender_type": "agent", "sender_agent_id": agent, "body": "  Hello back  "},
            {"sender_type": "human", "sender_user_id": requester, "body": "Hello"},
            {"sender_type": "human", "sender_user_id": str(uuid.uuid4()), "body": "private other participant"},
        ],
    )
    context = asyncio.run(store.conversation_context(conversation, requester, agent))
    assert context == "Human: Hello\nAgent: Hello back"
    membership = next(call for call in store.calls if call["path"] == "conversation_participants")
    assert membership["params"]["conversation_id"] == f"eq.{conversation}"
    message_read = next(call for call in store.calls if call["path"] == "messages")
    assert message_read["params"]["limit"] == "12"
    assert message_read["params"]["delivery_status"] == "in.(sent,delivered,read)"


def test_conversation_context_denies_when_requester_or_agent_is_not_a_participant():
    import uuid
    store = FakeMemoryCoordinator(conversation_participants=[{"user_id": str(uuid.uuid4())}])
    with pytest.raises(MemoryDenied):
        asyncio.run(store.conversation_context(str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())))
    assert not any(call["path"] == "messages" for call in store.calls)


def test_conversation_context_requires_explicit_consent_and_restricted_scope():
    import uuid
    conversation, requester, agent = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
    no_consent = FakeMemoryCoordinator(
        policies=[{"memory_type":"long_term","enabled":True,"consent_version":CONSENT_VERSION}],
        conversation_participants=[{"user_id":requester},{"agent_id":agent}],
        message_rows=[{"sender_type":"human","sender_user_id":requester,"body":"private"}],
    )
    with pytest.raises(MemoryDenied):
        asyncio.run(no_consent.conversation_context(conversation,requester,agent))
    assert not any(call["path"]=="messages" for call in no_consent.calls)

    insufficient_scope = FakeMemoryCoordinator(
        policies=[{
            "memory_type":"conversation","enabled":True,"consent_version":CONSENT_VERSION,
            "consent_revoked_at":None,"allowed_purposes":["agent_runtime_context"],
            "allowed_sensitivities":["public","internal"],"retention_days":30,"policy_version":1,
        }],
        conversation_participants=[{"user_id":requester},{"agent_id":agent}],
        message_rows=[{"sender_type":"human","sender_user_id":requester,"body":"private"}],
    )
    with pytest.raises(MemoryDenied):
        asyncio.run(insufficient_scope.conversation_context(conversation,requester,agent))
    assert not any(call["path"]=="messages" for call in insufficient_scope.calls)


def test_conversation_context_applies_policy_retention_window():
    import uuid
    conversation, requester, agent = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
    store = FakeMemoryCoordinator(
        policies=[{
            "memory_type":"conversation","enabled":True,"consent_version":CONSENT_VERSION,
            "consent_revoked_at":None,"allowed_purposes":["agent_runtime_context"],
            "allowed_sensitivities":["restricted"],"retention_days":7,"policy_version":3,
        }],
        conversation_participants=[{"user_id":requester},{"agent_id":agent}],
        message_rows=[{"sender_type":"human","sender_user_id":requester,"body":"recent"}],
    )
    assert asyncio.run(store.conversation_context(conversation,requester,agent)) == "Human: recent"
    message_read = next(call for call in store.calls if call["path"]=="messages")
    assert message_read["params"]["created_at"].startswith("gte.")


def test_global_memory_expiry_uses_bounded_batch_rpc(monkeypatch):
    monkeypatch.setenv("ALLPHA_MEMORY_COORDINATOR_ENABLED", "true")
    store = FakeMemoryCoordinator()
    result = asyncio.run(store.expire_all(batch_limit=25))
    assert result == {"expired_count": 7, "batch_limit": 25}
    call = next(call for call in store.calls if call["path"] == "rpc/expire_agent_memory_items_batch")
    assert call["method"] == "POST"
    assert call["body"] == {"p_limit": 25}
    assert not any(
        call["path"] == "rpc/agent_memory_transition"
        and call["body"]["p_action"] == "expire_all"
        for call in store.calls
    )


@pytest.mark.parametrize("batch_limit", [0, 501, True, 1.5, "10"])
def test_global_memory_expiry_rejects_unbounded_or_invalid_batch_size(monkeypatch, batch_limit):
    monkeypatch.setenv("ALLPHA_MEMORY_COORDINATOR_ENABLED", "true")
    store = FakeMemoryCoordinator()
    with pytest.raises(MemoryDenied):
        asyncio.run(store.expire_all(batch_limit=batch_limit))
    assert not store.calls


def test_global_memory_expiry_fails_closed_when_bounded_rpc_response_is_invalid(monkeypatch):
    monkeypatch.setenv("ALLPHA_MEMORY_COORDINATOR_ENABLED", "true")

    class InvalidRetentionRPC(FakeMemoryCoordinator):
        async def db(self, method, path, *, params=None, body=None, prefer=None):
            self.calls.append({"method": method, "path": path, "params": params, "body": body})
            return {"expired_count": 501}

    store = InvalidRetentionRPC()
    with pytest.raises(MemoryUnavailable):
        asyncio.run(store.expire_all(batch_limit=500))

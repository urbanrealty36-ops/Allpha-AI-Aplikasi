from __future__ import annotations
from fastapi import Request
from fastapi.testclient import TestClient
from allpha_api.auth import current_user
from allpha_api.main import app
from allpha_api import messaging_api

def _user(request: Request):
    request.state.user_id="messaging-test-user"
    return {"id":"messaging-test-user","email":"messaging@example.invalid"}

def test_message_contract_requires_auth():
    response=TestClient(app).get("/v1/messages/conversations")
    assert response.status_code==401

def test_message_create_requires_exactly_one_recipient(monkeypatch):
    app.dependency_overrides[current_user]=_user
    try:
        response=TestClient(app).post("/v1/messages/conversations",json={})
        assert response.status_code==422
    finally:
        app.dependency_overrides.clear()

def test_send_message_rejects_non_member(monkeypatch):
    async def no_membership(conversation_id,user_id):
        from fastapi import HTTPException
        raise HTTPException(404,detail={"code":"CONVERSATION_NOT_FOUND","message":"Percakapan tidak ditemukan."})
    monkeypatch.setattr(messaging_api,"_membership",no_membership)
    app.dependency_overrides[current_user]=_user
    try:
        import uuid
        response=TestClient(app).post(f"/v1/messages/conversations/{uuid.uuid4()}/messages",json={"body":"hello","client_message_id":str(uuid.uuid4())})
        assert response.status_code==404
    finally:
        app.dependency_overrides.clear()

def test_send_message_checks_block_after_membership(monkeypatch):
    import uuid
    async def member(conversation_id,user_id): return {"conversation_id":str(conversation_id),"user_id":user_id}
    async def blocked(conversation_id,user_id):
        from fastapi import HTTPException
        raise HTTPException(403,detail={"code":"MESSAGING_BLOCKED","message":"blocked"})
    monkeypatch.setattr(messaging_api,"_membership",member)
    monkeypatch.setattr(messaging_api,"_assert_not_blocked",blocked)
    app.dependency_overrides[current_user]=_user
    try:
        response=TestClient(app).post(f"/v1/messages/conversations/{uuid.uuid4()}/messages",json={"body":"hello","client_message_id":str(uuid.uuid4())})
        assert response.status_code==403
    finally:
        app.dependency_overrides.clear()

def test_send_message_returns_existing_idempotent_message(monkeypatch):
    import uuid
    conversation_id = uuid.uuid4()
    client_message_id = uuid.uuid4()
    calls = []
    async def member(conversation_id, user_id): return {"conversation_id":str(conversation_id),"user_id":user_id}
    async def unblocked(conversation_id, user_id): return None
    async def db(method, table, *, params=None, body=None, prefer=None):
        calls.append((method,table,params))
        if method == "GET" and table == "messages":
            return [{"id":"existing-message","conversation_id":str(conversation_id),"body":"hello","client_message_id":str(client_message_id),"delivery_status":"sent","sender_user_id":"messaging-test-user"}]
        if method == "GET" and table == "conversations":
            return [{"id":str(conversation_id),"kind":"human"}]
        raise AssertionError("idempotent replay must not write a second user message")
    monkeypatch.setattr(messaging_api,"_membership",member)
    monkeypatch.setattr(messaging_api,"_assert_not_blocked",unblocked)
    monkeypatch.setattr(messaging_api,"_db",db)
    app.dependency_overrides[current_user]=_user
    try:
        response=TestClient(app).post(f"/v1/messages/conversations/{conversation_id}/messages",json={"body":"hello","client_message_id":str(client_message_id)})
        assert response.status_code==200 or response.status_code==201
        assert response.json()["replayed"] is True
        assert response.json()["message"]["id"] == "existing-message"
        assert not any(call[0] == "POST" and call[1] == "messages" for call in calls)
    finally:
        app.dependency_overrides.clear()


def test_agent_reply_retry_reuses_persisted_user_message(monkeypatch):
    import uuid
    from types import SimpleNamespace

    conversation_id = uuid.uuid4()
    client_message_id = uuid.uuid4()
    user_message = {
        "id": "persisted-user-message", "conversation_id": str(conversation_id),
        "sender_type": "human", "sender_user_id": "messaging-test-user",
        "body": "please retry", "client_message_id": str(client_message_id),
        "delivery_status": "sent", "created_at": "2026-10-19T12:00:00+00:00",
    }
    calls = []
    async def member(conversation_id, user_id):
        return {"conversation_id": str(conversation_id), "user_id": user_id}
    async def unblocked(conversation_id, user_id):
        return None
    async def db(method, table, *, params=None, body=None, prefer=None):
        calls.append((method, table, body))
        if method == "GET" and table == "messages":
            return [user_message]
        if method == "GET" and table == "conversations":
            return [{"id": str(conversation_id), "kind": "agent"}]
        if method == "GET" and table == "conversation_participants":
            return [{"agent_id": "agent-1"}]
        if method == "GET" and table == "ai_agents":
            return [{"id": "agent-1", "version": 1, "status": "active", "persona": {}, "boundaries": {}}]
        if method == "GET" and table == "agent_skills":
            return [{"id": "skill-1", "version": 1, "status": "published", "name": "Answer", "instructions": "Answer safely"}]
        if method == "POST" and table == "messages":
            return [{
                "id": "agent-reply-1", "conversation_id": str(conversation_id),
                "sender_type": "agent", "sender_agent_id": "agent-1", "body": "Recovered reply",
                "client_message_id": body["client_message_id"], "created_at": "2026-10-19T12:00:01+00:00",
                "delivery_status": "sent",
            }]
        if method == "PATCH":
            return None
        raise AssertionError(f"Unexpected database call: {method} {table}")

    class FakeStore:
        async def owner_has_agent(self, owner_id, agent_id):
            return True

    class FakeRouter:
        def require_runtime_ready(self, sensitivity):
            assert sensitivity == "private"
        def policy_version_for(self, sensitivity):
            assert sensitivity == "private"
            return "private-v1"

    async def generate(self, **kwargs):
        calls.append(("GENERATE", "runtime", kwargs))
        return SimpleNamespace(output_text="Recovered reply"), SimpleNamespace(trace_id="trace-retry")

    monkeypatch.setattr(messaging_api, "_membership", member)
    monkeypatch.setattr(messaging_api, "_assert_not_blocked", unblocked)
    monkeypatch.setattr(messaging_api, "_db", db)
    monkeypatch.setattr(messaging_api.AgentRuntimeStore, "from_environment", classmethod(lambda cls: FakeStore()))
    monkeypatch.setattr(messaging_api.AgentRuntime, "execute_skill_generation", generate)
    app.state.text_generation_router = FakeRouter()
    app.dependency_overrides[current_user] = _user
    try:
        response = TestClient(app).post(
            f"/v1/messages/conversations/{conversation_id}/messages",
            json={"body": "please retry", "client_message_id": str(client_message_id)},
        )
        assert response.status_code == 200
        result = response.json()
        assert result["replayed"] is True
        assert result["message"]["id"] == "persisted-user-message"
        assert result["agent_reply"]["status"] == "sent"
        assert any(call[0] == "GENERATE" for call in calls)
        assert not any(call[0] == "POST" and call[1] == "messages" and call[2].get("sender_type") == "human" for call in calls)
    finally:
        app.dependency_overrides.clear()
        if hasattr(app.state, "text_generation_router"):
            delattr(app.state, "text_generation_router")

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
            return [{"id":"existing-message","conversation_id":str(conversation_id),"body":"hello","client_message_id":str(client_message_id),"delivery_status":"sent"}]
        raise AssertionError("idempotent replay must not write a second message")
    monkeypatch.setattr(messaging_api,"_membership",member)
    monkeypatch.setattr(messaging_api,"_assert_not_blocked",unblocked)
    monkeypatch.setattr(messaging_api,"_db",db)
    app.dependency_overrides[current_user]=_user
    try:
        response=TestClient(app).post(f"/v1/messages/conversations/{conversation_id}/messages",json={"body":"hello","client_message_id":str(client_message_id)})
        assert response.status_code==200 or response.status_code==201
        assert response.json()["replayed"] is True
        assert response.json()["message"]["id"] == "existing-message"
        assert not any(call[0] == "POST" for call in calls)
    finally:
        app.dependency_overrides.clear()

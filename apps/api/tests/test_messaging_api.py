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

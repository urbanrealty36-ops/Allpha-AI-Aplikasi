"""ENG-P02 account-state enforcement at the authenticated API boundary."""
import asyncio
import json
import time
import uuid

import jwt
import pytest
from fastapi import HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials

from allpha_api import auth


class _AuthResponse:
    status_code = 200

    def json(self):
        return {"id": "11111111-1111-4111-8111-111111111111", "email": "human@example.invalid"}


class _AuthClient:
    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def get(self, *args, **kwargs):
        return _AuthResponse()


def _request():
    return Request({"type": "http", "method": "GET", "path": "/v1/me", "headers": [], "query_string": b"", "server": ("test", 80), "client": ("test", 1), "scheme": "http", "http_version": "1.1"})


def _token():
    return jwt.encode({
        "sub": "11111111-1111-4111-8111-111111111111",
        "session_id": str(uuid.uuid4()),
        "exp": int(time.time()) + 300,
        "aud": "authenticated",
    }, "test-only-unverified-signature", algorithm="HS256")


def test_deactivated_account_is_denied_even_with_active_supabase_session(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://unit-test.supabase.co")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "sb_publishable_test")
    monkeypatch.setattr(auth.httpx, "AsyncClient", _AuthClient)
    calls = []

    async def fake_user_db_request(method, path, access_token, **kwargs):
        calls.append((method, path, kwargs))
        if path == "rpc/is_auth_session_active":
            return True
        if path == "profiles":
            return [{"id": "11111111-1111-4111-8111-111111111111", "account_status": "deactivation_requested"}]
        raise AssertionError(path)

    monkeypatch.setattr(auth, "user_db_request", fake_user_db_request)
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=_token())

    with pytest.raises(HTTPException) as exc:
        asyncio.run(auth.current_user(_request(), asyncio.run(auth.current_session_user(_request(), credentials))))

    assert exc.value.status_code == 403
    assert exc.value.detail["code"] == "ACCOUNT_NOT_ACTIVE"
    assert [call[1] for call in calls] == ["rpc/is_auth_session_active", "profiles"]


def test_missing_identity_profile_fails_closed(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://unit-test.supabase.co")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "sb_publishable_test")
    monkeypatch.setattr(auth.httpx, "AsyncClient", _AuthClient)

    async def fake_user_db_request(method, path, access_token, **kwargs):
        if path == "rpc/is_auth_session_active":
            return True
        if path == "profiles":
            return []
        raise AssertionError(path)

    monkeypatch.setattr(auth, "user_db_request", fake_user_db_request)
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=_token())

    with pytest.raises(HTTPException) as exc:
        asyncio.run(auth.current_user(_request(), credentials))

    assert exc.value.status_code == 403
    assert exc.value.detail["code"] == "ACCOUNT_PROFILE_UNAVAILABLE"


def test_active_account_keeps_authenticated_api_access(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://unit-test.supabase.co")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "sb_publishable_test")
    monkeypatch.setattr(auth.httpx, "AsyncClient", _AuthClient)

    async def fake_user_db_request(method, path, access_token, **kwargs):
        if path == "rpc/is_auth_session_active":
            return True
        if path == "profiles":
            return [{"id": "11111111-1111-4111-8111-111111111111", "account_status": "active"}]
        raise AssertionError(path)

    monkeypatch.setattr(auth, "user_db_request", fake_user_db_request)
    request = _request()
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=_token())

    user = asyncio.run(auth.current_user(request, credentials))

    assert user["id"] == "11111111-1111-4111-8111-111111111111"
    assert request.state.user_id == user["id"]
    assert request.state.auth_session_id

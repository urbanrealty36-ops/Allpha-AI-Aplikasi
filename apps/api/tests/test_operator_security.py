from __future__ import annotations

from fastapi import HTTPException, Request
from fastapi.testclient import TestClient

from allpha_api.auth import current_user
from allpha_api.main import app
import allpha_api.operator_security as security

client = TestClient(app)


def auth_as(user_id="ordinary-user"):
    async def fake_current_user(request: Request):
        request.state.supabase_access_token = f"token-{user_id}"
        return {"id": user_id, "email": f"{user_id}@example.invalid"}
    return fake_current_user


def install_auth(user_id="ordinary-user"):
    app.dependency_overrides[current_user] = auth_as(user_id)


def test_operator_routes_require_authentication():
    response = client.get("/v1/admin/operator/access")
    assert response.status_code == 401


def test_authenticated_user_without_grant_is_denied_and_audited(monkeypatch):
    calls = []

    async def fake_db(method, path, token, **kwargs):
        calls.append((method, path, token, kwargs))
        return []

    async def fake_audit(request, **kwargs):
        calls.append(("AUDIT", kwargs["action"], kwargs["outcome"], kwargs["metadata"]))

    monkeypatch.setattr(security, "user_db_request", fake_db)
    monkeypatch.setattr(security, "write_operator_audit", fake_audit)
    install_auth()
    try:
        response = client.get("/v1/admin/operator/access")
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "OPERATOR_SCOPE_REQUIRED"
        assert calls[0][1] == "platform_operator_grants"
        assert calls[-1][0:3] == ("AUDIT", "operator.scope.check", "denied")
    finally:
        app.dependency_overrides.clear()


def test_scope_grant_is_checked_exactly_and_audited_before_route(monkeypatch):
    events = []

    async def fake_db(method, path, token, **kwargs):
        assert token == "token-operator"
        return [{
            "id": "grant-1",
            "user_id": "operator",
            "scopes": ["platform:operations.read"],
            "status": "active",
            "expires_at": None,
        }]

    async def fake_audit(request, **kwargs):
        events.append(kwargs["outcome"])

    monkeypatch.setattr(security, "user_db_request", fake_db)
    monkeypatch.setattr(security, "write_operator_audit", fake_audit)
    install_auth("operator")
    try:
        allowed = client.get("/v1/admin/operator/access")
        assert allowed.status_code == 200
        assert allowed.json()["operator"]["scopes"] == ["platform:operations.read"]
        assert events == ["allowed"]

        # A different scope is not implied by operations.read.
        denied = client.get("/v1/admin/operator/audit")
        assert denied.status_code == 403
        assert events == ["allowed", "denied"]
    finally:
        app.dependency_overrides.clear()


def test_expired_grant_is_denied(monkeypatch):
    async def fake_db(method, path, token, **kwargs):
        return [{
            "id": "grant-expired",
            "user_id": "operator",
            "scopes": ["platform:operations.read"],
            "status": "active",
            "expires_at": "2000-01-01T00:00:00Z",
        }]

    outcomes = []

    async def fake_audit(request, **kwargs):
        outcomes.append(kwargs["outcome"])

    monkeypatch.setattr(security, "user_db_request", fake_db)
    monkeypatch.setattr(security, "write_operator_audit", fake_audit)
    install_auth("operator")
    try:
        response = client.get("/v1/admin/operator/access")
        assert response.status_code == 403
        assert outcomes == ["denied"]
    finally:
        app.dependency_overrides.clear()


def test_audit_failure_fails_closed(monkeypatch):
    async def fake_db(method, path, token, **kwargs):
        return [{
            "id": "grant-1",
            "user_id": "operator",
            "scopes": ["platform:operations.read"],
            "status": "active",
            "expires_at": None,
        }]

    async def failing_audit(request, **kwargs):
        raise HTTPException(status_code=503, detail={"code": "OPERATOR_AUDIT_UNAVAILABLE", "message": "audit unavailable"})

    monkeypatch.setattr(security, "user_db_request", fake_db)
    monkeypatch.setattr(security, "write_operator_audit", failing_audit)
    install_auth("operator")
    try:
        response = client.get("/v1/admin/operator/access")
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "OPERATOR_AUDIT_UNAVAILABLE"
    finally:
        app.dependency_overrides.clear()


def test_grant_lookup_error_fails_closed_and_is_audited(monkeypatch):
    async def broken_db(method, path, token, **kwargs):
        raise HTTPException(status_code=503, detail={"code": "DATABASE_UNAVAILABLE", "message": "db unavailable"})

    outcomes = []

    async def fake_audit(request, **kwargs):
        outcomes.append(kwargs["outcome"])

    monkeypatch.setattr(security, "user_db_request", broken_db)
    monkeypatch.setattr(security, "write_operator_audit", fake_audit)
    install_auth("operator")
    try:
        response = client.get("/v1/admin/operator/access")
        assert response.status_code == 503
        assert outcomes == ["error"]
    finally:
        app.dependency_overrides.clear()


def test_operator_grant_create_uses_verified_actor_and_audited_scope(monkeypatch):
    calls = []
    async def fake_db(method, path, token, **kwargs):
        return [{
            "id": "grant-operator",
            "user_id": "operator",
            "scopes": ["platform:operators.manage"],
            "status": "active",
            "expires_at": None,
        }]

    async def fake_audit(request, **kwargs):
        calls.append(("audit", kwargs["outcome"]))

    async def fake_privileged(method, table, **kwargs):
        calls.append((method, table, kwargs))
        return [{
            "id": "new-grant",
            "user_id": "00000000-0000-0000-0000-000000000099",
            "scopes": ["platform:operations.read"],
            "status": "active",
            "granted_by": "operator",
        }]

    monkeypatch.setattr(security, "user_db_request", fake_db)
    monkeypatch.setattr(security, "write_operator_audit", fake_audit)
    monkeypatch.setattr(security, "privileged_rest_request", fake_privileged)
    install_auth("operator")
    try:
        response = client.post("/v1/admin/operator/grants", json={
            "user_id": "00000000-0000-0000-0000-000000000099",
            "scopes": ["platform:operations.read"],
            "reason": "Operator on-call access",
        })
        assert response.status_code == 201
        assert calls[0] == ("audit", "allowed")
        method, table, kwargs = calls[1]
        assert (method, table) == ("POST", "platform_operator_grants")
        assert kwargs["body"]["granted_by"] == "operator"
        assert kwargs["body"]["user_id"] == "00000000-0000-0000-0000-000000000099"
    finally:
        app.dependency_overrides.clear()


def test_operator_grant_rejects_client_supplied_privilege_fields(monkeypatch):
    async def fake_db(method, path, token, **kwargs):
        return [{
            "id": "grant-operator",
            "user_id": "operator",
            "scopes": ["platform:operators.manage"],
            "status": "active",
            "expires_at": None,
        }]

    async def fake_audit(request, **kwargs):
        return None

    monkeypatch.setattr(security, "user_db_request", fake_db)
    monkeypatch.setattr(security, "write_operator_audit", fake_audit)
    install_auth("operator")
    try:
        response = client.post("/v1/admin/operator/grants", json={
            "user_id": "00000000-0000-0000-0000-000000000099",
            "scopes": ["platform:operations.read"],
            "reason": "Operator on-call access",
            "granted_by": "attacker",
            "status": "active",
        })
        assert response.status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_operator_grant_revoke_is_scoped_and_audited(monkeypatch):
    calls = []
    async def fake_db(method, path, token, **kwargs):
        return [{
            "id": "grant-operator",
            "user_id": "operator",
            "scopes": ["platform:operators.manage"],
            "status": "active",
            "expires_at": None,
        }]

    async def fake_audit(request, **kwargs):
        calls.append(("audit", kwargs["outcome"]))

    async def fake_privileged(method, table, **kwargs):
        calls.append((method, table, kwargs))
        return [{"id": "grant-1", "status": "revoked", "revoked_by": "operator"}]

    monkeypatch.setattr(security, "user_db_request", fake_db)
    monkeypatch.setattr(security, "write_operator_audit", fake_audit)
    monkeypatch.setattr(security, "privileged_rest_request", fake_privileged)
    install_auth("operator")
    try:
        response = client.post(
            "/v1/admin/operator/grants/00000000-0000-0000-0000-000000000123/revoke",
            json={"reason": "Contractor access ended"},
        )
        assert response.status_code == 200
        assert response.json()["revoked"] is True
        assert calls[0] == ("audit", "allowed")
        method, table, kwargs = calls[1]
        assert (method, table) == ("PATCH", "platform_operator_grants")
        assert kwargs["params"]["status"] == "eq.active"
        assert kwargs["body"]["revoked_by"] == "operator"
        assert kwargs["body"]["status"] == "revoked"
    finally:
        app.dependency_overrides.clear()

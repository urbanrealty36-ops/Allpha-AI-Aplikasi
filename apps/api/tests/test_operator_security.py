from __future__ import annotations

from fastapi import HTTPException, Request
from fastapi.testclient import TestClient
from pathlib import Path

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
            "scopes": ["platform:operators.manage", "platform:operations.read"],
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


def test_operator_cannot_self_grant_or_escalate_scopes(monkeypatch):
    async def fake_db(method, path, token, **kwargs):
        return [{
            "id": "grant-operator",
            "user_id": "operator",
            "scopes": ["platform:operators.manage", "platform:operations.read"],
            "status": "active",
            "expires_at": None,
        }]

    async def fake_audit(request, **kwargs):
        return None

    async def unexpected_privileged(*args, **kwargs):
        raise AssertionError("privileged store must not be called for a self-escalation attempt")

    monkeypatch.setattr(security, "user_db_request", fake_db)
    monkeypatch.setattr(security, "write_operator_audit", fake_audit)
    monkeypatch.setattr(security, "privileged_rest_request", unexpected_privileged)
    install_auth("operator")
    try:
        response = client.post("/v1/admin/operator/grants", json={
            "user_id": "00000000-0000-0000-0000-000000000099",
            "scopes": ["platform:operators.manage", "platform:capabilities.review"],
            "reason": "Escalate review scope",
        })
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "OPERATOR_SCOPE_ESCALATION_DENIED"
    finally:
        app.dependency_overrides.clear()


def test_operator_audit_configuration_fails_closed_without_server_key(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    monkeypatch.delenv("SUPABASE_SECRET_KEY", raising=False)
    try:
        security._audit_config()
        assert False, "missing audit key must fail closed"
    except HTTPException as exc:
        assert exc.status_code == 503
        assert exc.detail["code"] == "OPERATOR_AUDIT_UNAVAILABLE"


def test_operator_migration_has_rls_private_append_only_audit_and_trigger_contract():
    migration_path = Path(__file__).parents[1] / "supabase" / "migrations" / "20261014140000_eng_p06_platform_operator_grants_and_audit.sql"
    sql = migration_path.read_text(encoding="utf-8")
    assert "public.platform_operator_grants" in sql
    assert "user_id = (select auth.uid())" in sql
    assert "status = 'active'" in sql
    assert "expires_at > now()" in sql
    assert "public.platform_operator_audit_events" in sql
    assert "alter table public.platform_operator_audit_events enable row level security" in sql
    assert "grant select, insert on public.platform_operator_audit_events to service_role" in sql
    assert "platform_operator_grants_audit_insert" in sql
    assert "platform_operator_grants_audit_revoke" in sql
    assert "revoke all on public.platform_operator_audit_events from public, anon, authenticated, service_role" in sql


def test_capability_review_requires_scope_and_updates_only_pending_request(monkeypatch):
    calls = []
    async def fake_db(method, path, token, **kwargs):
        return [{
            "id": "operator-grant",
            "user_id": "operator",
            "scopes": ["platform:capabilities.review"],
            "status": "active",
            "expires_at": None,
        }]

    async def fake_audit(request, **kwargs):
        calls.append(("audit", kwargs["outcome"], kwargs["metadata"]))

    async def fake_privileged(method, table, **kwargs):
        calls.append((method, table, kwargs))
        if method == "GET":
            return [{
                "id": "00000000-0000-0000-0000-000000000777",
                "agent_id": "00000000-0000-0000-0000-000000000010",
                "capability_key": "content.publish",
                "description": "Publish content",
                "risk_level": "low",
                "status": "requested",
            }]
        return [{
            "id": "00000000-0000-0000-0000-000000000777",
            "status": "approved",
            "reviewed_by": "operator",
            "review_reason": "Policy review completed",
            "policy_version": "runtime-policy-v1",
        }]

    monkeypatch.setattr(security, "user_db_request", fake_db)
    monkeypatch.setattr(security, "write_operator_audit", fake_audit)
    monkeypatch.setattr(security, "privileged_rest_request", fake_privileged)
    install_auth("operator")
    try:
        response = client.post(
            "/v1/admin/operator/capabilities/00000000-0000-0000-0000-000000000777/review",
            json={"decision": "approved", "reason": "Policy review completed", "policy_version": "runtime-policy-v1"},
        )
        assert response.status_code == 200
        assert response.json()["runtime_authorized"] is False
        patch_call = next(call for call in calls if call[0] == "PATCH")
        assert patch_call[2]["params"]["status"] == "eq.requested"
        assert patch_call[2]["body"]["reviewed_by"] == "operator"
        assert patch_call[2]["body"]["status"] == "approved"
        assert patch_call[2]["body"]["policy_version"] == "runtime-policy-v1"
    finally:
        app.dependency_overrides.clear()


def test_capability_approval_requires_explicit_policy_version(monkeypatch):
    calls = []

    async def fake_db(method, path, token, **kwargs):
        return [{"id": "operator-grant", "user_id": "operator",
                 "scopes": ["platform:capabilities.review"], "status": "active", "expires_at": None}]

    async def fake_audit(request, **kwargs):
        calls.append(("audit", kwargs.get("outcome")))

    async def fake_privileged(method, table, **kwargs):
        calls.append((method, table, kwargs))
        if method == "GET":
            return [{"id": "00000000-0000-0000-0000-000000000777",
                     "agent_id": "00000000-0000-0000-0000-000000000010",
                     "capability_key": "content.publish", "description": "Publish content",
                     "risk_level": "low", "status": "requested"}]
        return [{"id": "capability", "status": "approved"}]

    monkeypatch.setattr(security, "user_db_request", fake_db)
    monkeypatch.setattr(security, "write_operator_audit", fake_audit)
    monkeypatch.setattr(security, "privileged_rest_request", fake_privileged)
    install_auth("operator")
    try:
        response = client.post(
            "/v1/admin/operator/capabilities/00000000-0000-0000-0000-000000000777/review",
            json={"decision": "approved", "reason": "Policy review completed"},
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "POLICY_VERSION_REQUIRED"
        assert not any(call[0] == "PATCH" for call in calls)
    finally:
        app.dependency_overrides.clear()


def test_denial_cannot_set_runtime_policy_version(monkeypatch):
    async def fake_db(method, path, token, **kwargs):
        return [{"id": "operator-grant", "user_id": "operator",
                 "scopes": ["platform:capabilities.review"], "status": "active", "expires_at": None}]

    async def unexpected_privileged(*args, **kwargs):
        raise AssertionError("Denied review must be rejected before database mutation")

    async def fake_audit(request, **kwargs):
        return None

    monkeypatch.setattr(security, "user_db_request", fake_db)
    monkeypatch.setattr(security, "write_operator_audit", fake_audit)
    monkeypatch.setattr(security, "privileged_rest_request", unexpected_privileged)
    install_auth("operator")
    try:
        response = client.post(
            "/v1/admin/operator/capabilities/00000000-0000-0000-0000-000000000777/review",
            json={"decision": "denied", "reason": "Capability not permitted", "policy_version": "runtime-policy-v1"},
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "POLICY_VERSION_NOT_ALLOWED"
    finally:
        app.dependency_overrides.clear()


def test_high_risk_capability_review_requires_separate_scope(monkeypatch):
    events = []
    async def fake_db(method, path, token, **kwargs):
        return [{
            "id": "operator-grant",
            "user_id": "operator",
            "scopes": ["platform:capabilities.review"],
            "status": "active",
            "expires_at": None,
        }]

    async def fake_audit(request, **kwargs):
        events.append((kwargs["action"], kwargs["outcome"]))

    async def fake_privileged(method, table, **kwargs):
        assert method == "GET"
        return [{
            "id": "00000000-0000-0000-0000-000000000777",
            "agent_id": "00000000-0000-0000-0000-000000000010",
            "capability_key": "billing.refund",
            "description": "Refund payment",
            "risk_level": "critical",
            "status": "requested",
        }]

    monkeypatch.setattr(security, "user_db_request", fake_db)
    monkeypatch.setattr(security, "write_operator_audit", fake_audit)
    monkeypatch.setattr(security, "privileged_rest_request", fake_privileged)
    install_auth("operator")
    try:
        response = client.post(
            "/v1/admin/operator/capabilities/00000000-0000-0000-0000-000000000777/review",
            json={"decision": "approved", "reason": "Reviewed carefully", "policy_version": "runtime-policy-v1"},
        )
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "HIGH_RISK_REVIEW_SCOPE_REQUIRED"
        assert events == [("operator.scope.check", "allowed"), ("agent.capability.review", "denied")]
    finally:
        app.dependency_overrides.clear()


def test_capability_review_migration_protects_fields_and_audits_transactionally():
    migration_path = Path(__file__).parents[1] / "supabase" / "migrations" / "20261014150000_eng_p06_capability_review_audit.sql"
    sql = migration_path.read_text(encoding="utf-8")
    assert "reviewed_by" in sql and "reviewed_at" in sql and "review_reason" in sql
    assert "private.guard_agent_capability_review_fields" in sql
    assert "auth.role()" in sql
    assert "private.audit_agent_capability_review" in sql
    assert "public.platform_operator_audit_events" in sql
    assert "old.status = 'requested' and new.status in ('approved','denied')" in sql
    assert "'platform:capabilities.review.high_risk'" in sql
    assert "grant select, update on public.agent_capabilities to service_role" in sql
    assert "private.guard_platform_operator_grant_update" in sql
    assert "grant update (status, revoked_at, revoked_by, revocation_reason)" in sql
    assert "Operator grant identity and scopes are immutable" in sql
    assert "as $$\nbegin" in sql
    assert "\nend;\n$$;" in sql
    assert "returns trigger\nlanguage plpgsql\nset search_path = ''\nas $\nbegin" not in sql

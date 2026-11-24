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
        if method == "GET" and table == "agent_capabilities":
            return [{
                "id": "00000000-0000-0000-0000-000000000777",
                "agent_id": "00000000-0000-0000-0000-000000000010",
                "capability_key": "content.publish",
                "description": "Publish content",
                "risk_level": "low",
                "status": "requested",
                "required_permission_scopes": [],
            }]
        if method == "GET" and table == "agent_runtime_policies":
            return [{
                "id": "00000000-0000-0000-0000-000000000888",
                "agent_id": "00000000-0000-0000-0000-000000000010",
                "policy_version": "runtime-policy-v1",
                "policy_digest": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                "approved_tool_keys": ["content.publish"],
                "required_permission_scopes": [],
                "status": "approved",
            }]
        return [{
            "id": "00000000-0000-0000-0000-000000000777",
            "status": "approved",
            "reviewed_by": "operator",
            "review_reason": "Policy review completed",
            "policy_version": "runtime-policy-v1",
            "runtime_policy_id": "00000000-0000-0000-0000-000000000888",
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
        assert patch_call[2]["body"]["runtime_policy_id"] == "00000000-0000-0000-0000-000000000888"
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



def test_agent_social_governance_snapshot_is_read_only_and_schema_aware(monkeypatch):
    calls = []

    async def fake_db(method, path, token, **kwargs):
        return [{
            "id": "grant-1", "user_id": "operator",
            "scopes": ["platform:security.audit.read"], "status": "active",
            "expires_at": None,
        }]

    async def fake_audit(request, **kwargs):
        return None

    async def fake_privileged(method, table, **kwargs):
        calls.append((method, table, kwargs))
        if table == "agent_social_presence_policies":
            return [{
                "id": "policy-1", "owner_user_id": "owner-1", "agent_id": "agent-1",
                "allowed_actions": ["draft_post"], "approval_mode": "every_post",
                "disclosure_text": "Dibuat bersama AI Agent", "is_enabled": True,
                "version": 2, "updated_at": "2026-11-18T00:00:00Z",
            }]
        if table == "agent_social_action_approvals":
            return [{
                "id": "approval-1", "owner_user_id": "owner-1", "agent_id": "agent-1",
                "action_type": "draft_post", "status": "pending",
                "requested_at": "2026-11-18T00:00:00Z",
            }]
        raise AssertionError(f"automation table must not be queried while schema gate is off: {table}")

    monkeypatch.setattr(security, "user_db_request", fake_db)
    monkeypatch.setattr(security, "write_operator_audit", fake_audit)
    monkeypatch.setattr(security, "privileged_rest_request", fake_privileged)
    monkeypatch.setenv("ALLPHA_AGENT_SOCIAL_AUTOMATION_SCHEMA_ENABLED", "false")
    install_auth("operator")
    try:
        response = client.get("/v1/admin/operator/agent-social/governance?limit=25")
        assert response.status_code == 200
        body = response.json()
        assert len(body["policies"]) == 1
        assert body["approvals"][0]["status"] == "pending"
        assert body["automation_schema_active"] is False
        assert body["control_events"] == []
        assert [call[1] for call in calls] == [
            "agent_social_presence_policies", "agent_social_action_approvals"
        ]
        assert all("body" not in call[2] for call in calls)
    finally:
        app.dependency_overrides.clear()


def test_agent_ownership_audit_requires_operator_scope(monkeypatch):
    calls=[]
    async def fake_db(method,path,token,**kwargs):
        calls.append((method,path,token,kwargs))
        return [{"id":"grant-1","user_id":"operator","scopes":["platform:security.audit.read"],"status":"active","expires_at":None}]
    async def fake_audit(request,**kwargs):
        calls.append(("AUDIT",kwargs["outcome"]))
    async def fake_privileged(method,table,**kwargs):
        calls.append((method,table,kwargs))
        if table=="agent_ownership_transfer_events":
            return [{"id":"event-1","event_type":"accepted","from_owner_subject_ref":"a"*64,"to_owner_subject_ref":"b"*64}]
        return [{"id":"consent-1","event_type":"granted","owner_subject_ref":"a"*64}]
    monkeypatch.setattr(security,"user_db_request",fake_db)
    monkeypatch.setattr(security,"write_operator_audit",fake_audit)
    monkeypatch.setattr(security,"privileged_rest_request",fake_privileged)
    install_auth("operator")
    try:
        response=client.get("/v1/admin/operator/agent-ownership/audit?limit=200")
        assert response.status_code==200
        assert len(response.json()["ownership_transfers"])==1
        assert len(response.json()["passport_consents"])==1
        queries=[call for call in calls if len(call)>1 and call[1] in {"agent_ownership_transfer_events","agent_owner_attribution_consent_events"}]
        assert len(queries)==2
        assert all(call[2]["params"]["limit"]=="100" for call in queries)
        assert "from_owner_user_id" not in queries[0][2]["params"]["select"]
        assert "owner_user_id" not in queries[1][2]["params"]["select"]
    finally:
        app.dependency_overrides.clear()


def test_agent_ownership_audit_denies_operator_without_security_audit_scope(monkeypatch):
    async def fake_db(method,path,token,**kwargs):
        return [{"id":"grant-1","user_id":"operator","scopes":["platform:operations.read"],"status":"active","expires_at":None}]
    async def fake_audit(request,**kwargs):
        return None
    monkeypatch.setattr(security,"user_db_request",fake_db)
    monkeypatch.setattr(security,"write_operator_audit",fake_audit)
    install_auth("operator")
    try:
        response=client.get("/v1/admin/operator/agent-ownership/audit")
        assert response.status_code==403
        assert response.json()["error"]["code"]=="OPERATOR_SCOPE_REQUIRED"
    finally:
        app.dependency_overrides.clear()


def test_agent_skill_installation_audit_requires_security_scope_and_returns_pseudonymous_rows(monkeypatch):
    calls=[]
    async def fake_db(method,path,token,**kwargs):
        return [{"id":"grant-1","user_id":"operator","scopes":["platform:security.audit.read"],"status":"active","expires_at":None}]
    async def fake_audit(request,**kwargs):
        return None
    async def fake_privileged(method,table,**kwargs):
        calls.append((method,table,kwargs))
        if table=="agent_skill_installations":
            return [{"id":"installation-1","installer_subject_ref":"a"*64,"license_terms_digest":"b"*64,"status":"active"}]
        return [{"id":"event-1","actor_subject_ref":"a"*64,"event_type":"installed"}]
    monkeypatch.setattr(security,"user_db_request",fake_db)
    monkeypatch.setattr(security,"write_operator_audit",fake_audit)
    monkeypatch.setattr(security,"privileged_rest_request",fake_privileged)
    install_auth("operator")
    try:
        response=client.get("/v1/admin/operator/agent-skills/installations/audit?limit=500")
        assert response.status_code==200
        assert len(response.json()["installations"])==1
        assert len(response.json()["events"])==1
        assert len(calls)==2
        assert all(call[2]["params"]["limit"]=="100" for call in calls)
        assert "installed_by" not in calls[0][2]["params"]["select"]
        assert "actor_user_id" not in calls[1][2]["params"]["select"]
    finally:
        app.dependency_overrides.clear()


def test_agent_skill_installation_audit_denies_operator_without_security_scope(monkeypatch):
    async def fake_db(method,path,token,**kwargs):
        return [{"id":"grant-1","user_id":"operator","scopes":["platform:operations.read"],"status":"active","expires_at":None}]
    async def fake_audit(request,**kwargs):
        return None
    monkeypatch.setattr(security,"user_db_request",fake_db)
    monkeypatch.setattr(security,"write_operator_audit",fake_audit)
    install_auth("operator")
    try:
        response=client.get("/v1/admin/operator/agent-skills/installations/audit")
        assert response.status_code==403
        assert response.json()["error"]["code"]=="OPERATOR_SCOPE_REQUIRED"
    finally:
        app.dependency_overrides.clear()


def test_list_operator_runtime_policies_requires_capability_review_scope(monkeypatch):
    calls=[]
    async def fake_db(method,path,token,**kwargs):
        return [{"id":"grant-1","user_id":"operator","scopes":["platform:capabilities.review"],"status":"active","expires_at":None}]
    async def fake_audit(request,**kwargs):
        return None
    async def fake_privileged(method,table,**kwargs):
        calls.append((method,table,kwargs))
        return [{"id":"policy-1","agent_id":"agent-1","policy_version":4,"approved_tool_keys":["web_search"],"required_permission_scopes":["network.read"],"status":"approved"}]
    monkeypatch.setattr(security,"user_db_request",fake_db)
    monkeypatch.setattr(security,"write_operator_audit",fake_audit)
    monkeypatch.setattr(security,"privileged_rest_request",fake_privileged)
    install_auth("operator")
    try:
        response=client.get("/v1/admin/operator/runtime-policies?agent_id=11111111-1111-4111-8111-111111111111")
        assert response.status_code==200
        assert response.json()["items"][0]["policy_version"]==4
        assert calls[0][0:2]==("GET","agent_runtime_policies")
        assert calls[0][2]["params"]["agent_id"]=="eq.11111111-1111-4111-8111-111111111111"
        assert calls[0][2]["params"]["status"]=="eq.approved"
    finally:
        app.dependency_overrides.clear()


def test_list_operator_runtime_policies_denies_missing_capability_review_scope(monkeypatch):
    async def fake_db(method,path,token,**kwargs):
        return [{"id":"grant-1","user_id":"operator","scopes":["platform:operations.read"],"status":"active","expires_at":None}]
    async def fake_audit(request,**kwargs):
        return None
    monkeypatch.setattr(security,"user_db_request",fake_db)
    monkeypatch.setattr(security,"write_operator_audit",fake_audit)
    install_auth("operator")
    try:
        response=client.get("/v1/admin/operator/runtime-policies?agent_id=agent-1")
        assert response.status_code==403
        assert response.json()["error"]["code"]=="OPERATOR_SCOPE_REQUIRED"
    finally:
        app.dependency_overrides.clear()


def test_runtime_policy_creation_rejects_unregistered_tool_before_persistence(monkeypatch):
    async def fake_db(method,path,token,**kwargs):
        return [{"id":"grant-1","user_id":"operator","scopes":["platform:capabilities.review"],"status":"active","expires_at":None}]
    async def fake_audit(request,**kwargs):
        return None
    async def unexpected_privileged(*args,**kwargs):
        raise AssertionError("Unknown tools must be rejected before persistence")
    monkeypatch.setattr(security,"user_db_request",fake_db)
    monkeypatch.setattr(security,"write_operator_audit",fake_audit)
    monkeypatch.setattr(security,"privileged_rest_request",unexpected_privileged)
    install_auth("operator")
    try:
        response=client.post("/v1/admin/operator/runtime-policies",json={
            "agent_id":"11111111-1111-4111-8111-111111111111",
            "policy_version":"v1",
            "approved_tool_keys":["not.registered"],
            "required_permission_scopes":[],
            "risk_constraints":{},
        })
        assert response.status_code==422
        assert response.json()["error"]["code"]=="RUNTIME_POLICY_UNKNOWN_TOOL"
    finally:
        app.dependency_overrides.clear()


def test_runtime_policy_creation_persists_canonical_registry_tool_and_text_version(monkeypatch):
    calls=[]
    async def fake_db(method,path,token,**kwargs):
        return [{"id":"grant-1","user_id":"operator","scopes":["platform:capabilities.review"],"status":"active","expires_at":None}]
    async def fake_audit(request,**kwargs):
        return None
    async def fake_privileged(method,table,**kwargs):
        calls.append((method,table,kwargs))
        return [{"id":"policy-1","agent_id":"11111111-1111-4111-8111-111111111111",
                 "policy_version":"release-v1","status":"draft"}]
    monkeypatch.setattr(security,"user_db_request",fake_db)
    monkeypatch.setattr(security,"write_operator_audit",fake_audit)
    monkeypatch.setattr(security,"privileged_rest_request",fake_privileged)
    install_auth("operator")
    try:
        response=client.post("/v1/admin/operator/runtime-policies",json={
            "agent_id":"11111111-1111-4111-8111-111111111111",
            "policy_version":"release-v1",
            "approved_tool_keys":["text.normalize"],
            "required_permission_scopes":[],
            "risk_constraints":{},
        })
        assert response.status_code==201
        assert response.json()["runtime_authorized"] is False
        assert calls[0][0:2]==("POST","agent_runtime_policies")
        assert calls[0][2]["body"]["policy_version"]=="release-v1"
        assert calls[0][2]["body"]["approved_tool_keys"]==["text.normalize"]
    finally:
        app.dependency_overrides.clear()


def test_model_execution_policy_approval_is_separate_from_tariff_activation_and_audited(monkeypatch):
    import allpha_api.model_costs_api as model_costs
    config_id="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    calls=[]
    audits=[]
    item={
        "id":config_id,"capability":"text_generation","provider_id":"nvidia-nim","model_id":"qwen/model",
        "model_version":"v1","pricing_version":"price-v2","policy_version":"p2",
        "status":"active","policy_approved":False,"effective_at":"2026-11-24T00:00:00Z",
    }
    async def fake_user_db(method,path,token,**kwargs):
        return [{"id":"grant-1","user_id":"operator","scopes":["platform:capabilities.review.high_risk"],"status":"active","expires_at":None}]
    async def fake_privileged(method,table,**kwargs):
        calls.append((method,table,kwargs))
        if method=="GET":
            return [dict(item)]
        if method=="PATCH":
            item.update(kwargs["body"])
            return [dict(item)]
        raise AssertionError(method)
    async def fake_audit(request,**kwargs):
        audits.append(kwargs)
    monkeypatch.setattr(security,"user_db_request",fake_user_db)
    monkeypatch.setattr(security,"write_operator_audit",fake_audit)
    monkeypatch.setattr(model_costs,"privileged_rest_request",fake_privileged)
    monkeypatch.setattr(model_costs,"write_operator_audit",fake_audit)
    install_auth("operator")
    try:
        response=client.post(f"/v1/admin/model-costs/{config_id}/approve-policy",json={
            "reason":"Provider and pricing contract reviewed for this route.",
            "approval_reference":"MODEL-ROUTE-APPROVAL-2026-01",
        })
        assert response.status_code==200
        body=response.json()
        assert body["policy_approved"] is True
        assert body["runtime_enabled"] is False
        assert body["item"]["policy_approved_by"]=="operator"
        assert body["item"]["policy_approval_reference"]=="MODEL-ROUTE-APPROVAL-2026-01"
        assert calls[0][0:2]==("GET","ai_model_cost_configs")
        assert calls[1][0:2]==("PATCH","ai_model_cost_configs")
        assert calls[1][2]["params"]["policy_approved"]=="eq.false"
        assert audits[-1]["action"]=="model_cost.policy_approve"
    finally:
        app.dependency_overrides.clear()


def test_model_execution_policy_approval_requires_high_risk_scope(monkeypatch):
    async def fake_user_db(method,path,token,**kwargs):
        return [{"id":"grant-1","user_id":"operator","scopes":["platform:operations.read"],"status":"active","expires_at":None}]
    async def fake_audit(request,**kwargs):
        return None
    monkeypatch.setattr(security,"user_db_request",fake_user_db)
    monkeypatch.setattr(security,"write_operator_audit",fake_audit)
    install_auth("operator")
    try:
        response=client.post("/v1/admin/model-costs/aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa/approve-policy",json={
            "reason":"Reviewed","approval_reference":"MODEL-ROUTE-APPROVAL-2026-01"
        })
        assert response.status_code==403
        assert response.json()["error"]["code"]=="OPERATOR_SCOPE_REQUIRED"
    finally:
        app.dependency_overrides.clear()


def test_model_router_status_is_safe_and_reports_missing_provider_configuration(monkeypatch):
    import allpha_api.model_costs_api as model_costs
    async def fake_user_db(method,path,token,**kwargs):
        return [{"id":"grant-1","user_id":"operator","scopes":["platform:operations.read"],"status":"active","expires_at":None}]
    async def fake_audit(request,**kwargs):
        return None
    monkeypatch.setattr(security,"user_db_request",fake_user_db)
    monkeypatch.setattr(security,"write_operator_audit",fake_audit)
    monkeypatch.setattr(model_costs,"write_operator_audit",fake_audit)
    previous=getattr(app.state,"text_generation_router",None)
    app.state.text_generation_router=None
    install_auth("operator")
    try:
        response=client.get("/v1/admin/model-costs/runtime-status")
        assert response.status_code==200
        body=response.json()
        assert body["configured"] is False
        assert body["ready"] is False
        assert "ALLPHA_TEXTGEN_API_KEY" in body["missing_configuration"]
    finally:
        app.state.text_generation_router=previous
        app.dependency_overrides.clear()


def test_manual_review_moderation_policy_can_be_created_and_approved_with_high_risk_scope(monkeypatch):
    import allpha_api.model_costs_api as model_costs
    calls=[]
    audits=[]
    policy={"policy_version":"manual-review-v1","approval_reference":"MODERATION-REQUEST-2026-01",
            "configuration":{"mode":"manual_review_only","manual_review_only":True},
            "status":"draft","effective_at":"2026-11-24T00:00:00+00:00","expires_at":None,"approved_by":None}
    async def fake_user_db(method,path,token,**kwargs):
        return [{"id":"grant-1","user_id":"operator","scopes":["platform:capabilities.review","platform:capabilities.review.high_risk"],"status":"active","expires_at":None}]
    async def fake_privileged(method,table,**kwargs):
        calls.append((method,table,kwargs))
        if method=="POST":
            return [dict(policy)]
        if method=="GET":
            return [dict(policy)]
        if method=="PATCH":
            policy.update(kwargs["body"])
            return [dict(policy)]
        raise AssertionError(method)
    async def fake_audit(request,**kwargs):
        audits.append(kwargs)
    monkeypatch.setattr(security,"user_db_request",fake_user_db)
    monkeypatch.setattr(security,"write_operator_audit",fake_audit)
    monkeypatch.setattr(model_costs,"privileged_rest_request",fake_privileged)
    monkeypatch.setattr(model_costs,"write_operator_audit",fake_audit)
    install_auth("operator")
    try:
        created=client.post("/v1/admin/model-costs/moderation-policies",json={
            "policy_version":"manual-review-v1","approval_reference":"MODERATION-REQUEST-2026-01"
        })
        assert created.status_code==201
        assert created.json()["item"]["configuration"]=={"mode":"manual_review_only","manual_review_only":True}
        assert created.json()["runtime_enabled"] is False
        approved=client.post("/v1/admin/model-costs/moderation-policies/manual-review-v1/approve",json={
            "reason":"Manual review is the required fail-closed moderation mode.",
            "approval_reference":"MODERATION-APPROVAL-2026-01"
        })
        assert approved.status_code==200
        assert approved.json()["item"]["status"]=="approved"
        assert approved.json()["item"]["approved_by"]=="operator"
        assert approved.json()["runtime_enabled"] is False
        assert [call[0] for call in calls]==["POST","GET","PATCH"]
        assert audits[-1]["action"]=="generation_moderation_policy.approve"
    finally:
        app.dependency_overrides.clear()


def test_model_usage_summary_uses_service_rpc_and_validates_period(monkeypatch):
    import allpha_api.model_costs_api as model_costs
    calls=[]
    async def fake_user_db(method,path,token,**kwargs):
        return [{"id":"grant-1","user_id":"operator","scopes":["platform:operations.read"],"status":"active","expires_at":None}]
    async def fake_privileged(method,path,**kwargs):
        calls.append((method,path,kwargs))
        return {"totals":{"runs":0},"by_provider_model":[]}
    async def fake_audit(request,**kwargs):
        return None
    monkeypatch.setattr(security,"user_db_request",fake_user_db)
    monkeypatch.setattr(security,"write_operator_audit",fake_audit)
    monkeypatch.setattr(model_costs,"privileged_rest_request",fake_privileged)
    monkeypatch.setattr(model_costs,"write_operator_audit",fake_audit)
    install_auth("operator")
    try:
        response=client.get("/v1/admin/model-costs/usage-summary")
        assert response.status_code==200
        assert response.json()["totals"]["runs"]==0
        assert calls[0][0:2]==("POST","rpc/get_agent_model_usage_summary")
        invalid=client.get("/v1/admin/model-costs/usage-summary?since=2026-01-01T00:00:00Z&until=2026-11-24T00:00:00Z")
        assert invalid.status_code==422
    finally:
        app.dependency_overrides.clear()


def test_list_operator_agents_for_runtime_governance_requires_capability_review(monkeypatch):
    calls=[]
    async def fake_db(method,path,token,**kwargs):
        return [{"id":"grant-1","user_id":"operator","scopes":["platform:capabilities.review"],"status":"active","expires_at":None}]
    async def fake_audit(request,**kwargs):
        return None
    async def fake_privileged(method,table,**kwargs):
        calls.append((method,table,kwargs))
        return [{"id":"11111111-1111-4111-8111-111111111111","handle":"research-agent","display_name":"Research Agent","status":"active","visibility":"private","version":3}]
    monkeypatch.setattr(security,"user_db_request",fake_db)
    monkeypatch.setattr(security,"write_operator_audit",fake_audit)
    monkeypatch.setattr(security,"privileged_rest_request",fake_privileged)
    install_auth("operator")
    try:
        response=client.get("/v1/admin/operator/agents?limit=50")
        assert response.status_code==200
        assert response.json()["items"][0]["display_name"]=="Research Agent"
        assert calls[0][0:2]==("GET","ai_agents")
        assert calls[0][2]["params"]["status"]=="in.(active,draft)"
        assert calls[0][2]["params"]["limit"]=="50"
        assert "owner_user_id" not in calls[0][2]["params"]["select"]
    finally:
        app.dependency_overrides.clear()


def test_list_operator_agents_for_runtime_governance_denies_missing_scope(monkeypatch):
    async def fake_db(method,path,token,**kwargs):
        return [{"id":"grant-1","user_id":"operator","scopes":["platform:operations.read"],"status":"active","expires_at":None}]
    async def fake_audit(request,**kwargs):
        return None
    monkeypatch.setattr(security,"user_db_request",fake_db)
    monkeypatch.setattr(security,"write_operator_audit",fake_audit)
    install_auth("operator")
    try:
        response=client.get("/v1/admin/operator/agents")
        assert response.status_code==403
        assert response.json()["error"]["code"]=="OPERATOR_SCOPE_REQUIRED"
    finally:
        app.dependency_overrides.clear()

from __future__ import annotations

from fastapi import Request
from fastapi.testclient import TestClient

from allpha_api.auth import current_user
from allpha_api.main import app
import allpha_api.model_costs_api as model_costs
import allpha_api.operator_security as security

client = TestClient(app)
CONFIG_ID = "fef153ad-879b-4691-af40-ee1b671987b8"
OPERATOR_ID = "11111111-1111-4111-8111-111111111111"


def install_operator(scopes: list[str]) -> None:
    async def fake_current_user(request: Request):
        request.state.supabase_access_token = "operator-token"
        return {"id": OPERATOR_ID, "email": "operator@example.invalid"}
    app.dependency_overrides[current_user] = fake_current_user


def install_grant(monkeypatch, scopes: list[str]) -> None:
    async def fake_user_db(method, path, token, **kwargs):
        assert token == "operator-token"
        return [{
            "id": "grant-1",
            "user_id": OPERATOR_ID,
            "scopes": scopes,
            "status": "active",
            "expires_at": None,
        }]
    async def no_scope_audit(request, **kwargs):
        return None
    monkeypatch.setattr(security, "user_db_request", fake_user_db)
    monkeypatch.setattr(security, "write_operator_audit", no_scope_audit)


def test_model_policy_approval_persists_actor_reference_and_audit(monkeypatch):
    install_operator(["platform:capabilities.review.high_risk"])
    install_grant(monkeypatch, ["platform:capabilities.review.high_risk"])
    current = {
        "id": CONFIG_ID, "capability": "text_generation", "provider_id": "provider-x", "model_id": "model-x",
        "model_version": "v1", "pricing_version": "price-v1", "policy_version": "policy-v2",
        "status": "active", "policy_approved": False, "effective_at": "2026-10-16T00:00:00+00:00",
    }
    calls = []
    audits = []

    async def fake_privileged(method, table, **kwargs):
        calls.append((method, table, kwargs))
        if method == "GET":
            return [current]
        body = kwargs["body"]
        return [{**current, **body, "policy_approved": True}]

    async def fake_audit(request, **kwargs):
        audits.append(kwargs)

    monkeypatch.setattr(model_costs, "privileged_rest_request", fake_privileged)
    monkeypatch.setattr(model_costs, "write_operator_audit", fake_audit)
    try:
        response = client.post(
            f"/v1/admin/model-costs/{CONFIG_ID}/approve-policy",
            json={"reason": "Approved after policy and cost review.", "approval_reference": "MODEL-APPROVAL-REF-02"},
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["policy_approved"] is True
        assert body["runtime_enabled"] is False
        patch = calls[1][2]
        assert patch["params"]["policy_approved"] == "eq.false"
        assert patch["body"]["policy_approved"] is True
        assert patch["body"]["policy_approval_reference"] == "MODEL-APPROVAL-REF-02"
        assert patch["body"]["policy_approved_by"] == OPERATOR_ID
        assert patch["body"]["policy_approved_at"]
        assert audits[0]["action"] == "model_cost.policy_approve"
        assert audits[0]["metadata"]["policy_version"] == "policy-v2"
    finally:
        app.dependency_overrides.clear()


def test_model_policy_approval_denies_operator_without_high_risk_scope(monkeypatch):
    install_operator(["platform:operations.read", "platform:capabilities.review"])
    install_grant(monkeypatch, ["platform:operations.read", "platform:capabilities.review"])
    privileged_calls = []

    async def fake_privileged(method, table, **kwargs):
        privileged_calls.append((method, table))
        return []

    monkeypatch.setattr(model_costs, "privileged_rest_request", fake_privileged)
    try:
        response = client.post(
            f"/v1/admin/model-costs/{CONFIG_ID}/approve-policy",
            json={"reason": "Approved after policy and cost review.", "approval_reference": "MODEL-APPROVAL-REF-03"},
        )
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "OPERATOR_SCOPE_REQUIRED"
        assert privileged_calls == []
    finally:
        app.dependency_overrides.clear()


def test_tariff_activation_does_not_approve_model_execution_policy(monkeypatch):
    install_operator(["platform:capabilities.review.high_risk"])
    install_grant(monkeypatch, ["platform:capabilities.review.high_risk"])
    draft = {
        "id": CONFIG_ID, "capability": "text_generation", "provider_id": "provider-x", "model_id": "model-x",
        "model_version": "v1", "pricing_version": "price-v2", "policy_version": "policy-v2",
        "status": "draft", "policy_approved": False,
    }
    calls = []
    audits = []

    async def fake_privileged(method, table, **kwargs):
        calls.append((method, table, kwargs))
        if method == "GET" and kwargs["params"].get("id") == f"eq.{CONFIG_ID}":
            return [draft]
        if method == "GET":
            return []
        return [{**draft, **kwargs["body"]}]

    async def fake_audit(request, **kwargs):
        audits.append(kwargs)

    monkeypatch.setattr(model_costs, "privileged_rest_request", fake_privileged)
    monkeypatch.setattr(model_costs, "write_operator_audit", fake_audit)
    try:
        response = client.post(
            f"/v1/admin/model-costs/{CONFIG_ID}/activate",
            json={"reason": "Activate tariff after cost validation."},
        )
        assert response.status_code == 200, response.text
        assert response.json()["item"]["status"] == "active"
        assert response.json()["item"]["policy_approved"] is False
        assert "policy_approved" not in calls[-1][2]["body"]
        assert audits[0]["metadata"]["policy_approved"] is False
    finally:
        app.dependency_overrides.clear()

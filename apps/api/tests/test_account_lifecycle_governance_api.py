import asyncio
from uuid import UUID

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from allpha_api import account_lifecycle_governance_api as governance


OPERATOR = {"id": "11111111-1111-4111-8111-111111111111", "scopes": ["platform:account_lifecycle.manage"]}
POLICY_ID = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
HOLD_ID = UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
SUBJECT_REF = "c" * 64


def _request():
    return Request({"type": "http", "method": "POST", "path": "/", "headers": []})


def test_retention_policy_creation_is_inactive_and_bound_to_verified_operator(monkeypatch):
    calls = []
    audits = []

    async def privileged(method, table, *, params=None, body=None, prefer=None):
        calls.append((method, table, params, body, prefer))
        if method == "GET":
            return []
        return [{
            "id": str(POLICY_ID), "data_class": "social_content", "retention_days": 365,
            "policy_version": "legal-policy-2026.1", "active": False, "approved_by": OPERATOR["id"],
        }]

    async def audit(request, **kwargs):
        audits.append(kwargs)

    monkeypatch.setattr(governance, "privileged_rest_request", privileged)
    monkeypatch.setattr(governance, "write_operator_audit", audit)
    payload = governance.RetentionPolicyCreate(
        data_class="social_content", retention_days=365,
        policy_version="legal-policy-2026.1", legal_basis="Policy reference approved by counsel",
    )
    result = asyncio.run(governance.create_retention_policy(payload, _request(), OPERATOR))

    assert result["item"]["active"] is False
    insert = next(call for call in calls if call[0] == "POST")
    assert insert[1] == "account_data_retention_policies"
    assert insert[3]["approved_by"] == OPERATOR["id"]
    assert insert[3]["active"] is False
    assert [item["outcome"] for item in audits] == ["attempted", "allowed"]


def test_retention_policy_activation_uses_atomic_database_rpc(monkeypatch):
    calls = []
    audits = []

    async def privileged(method, table, *, params=None, body=None, prefer=None):
        calls.append((method, table, params, body))
        if method == "GET":
            return [{"id": str(POLICY_ID), "data_class": "social_content", "policy_version": "v1", "active": False}]
        return {"id": str(POLICY_ID), "active": True}

    async def audit(request, **kwargs):
        audits.append(kwargs)

    monkeypatch.setattr(governance, "privileged_rest_request", privileged)
    monkeypatch.setattr(governance, "write_operator_audit", audit)
    result = asyncio.run(governance.activate_retention_policy(POLICY_ID, _request(), OPERATOR))

    rpc = next(call for call in calls if call[1] == "rpc/set_account_retention_policy_active")
    assert rpc[3] == {"p_policy_id": str(POLICY_ID), "p_actor_user_id": OPERATOR["id"], "p_active": True}
    assert result["item"]["active"] is True
    assert [item["outcome"] for item in audits] == ["attempted", "allowed"]


def test_retention_policy_creation_rejects_duplicate_version(monkeypatch):
    async def privileged(method, table, *, params=None, body=None, prefer=None):
        return [{"id": str(POLICY_ID)}]

    monkeypatch.setattr(governance, "privileged_rest_request", privileged)
    async def audit(request, **kwargs):
        return None

    monkeypatch.setattr(governance, "write_operator_audit", audit)
    payload = governance.RetentionPolicyCreate(
        data_class="social_content", retention_days=365,
        policy_version="v1", legal_basis="Approved legal basis reference",
    )
    with pytest.raises(HTTPException) as error:
        asyncio.run(governance.create_retention_policy(payload, _request(), OPERATOR))
    assert error.value.status_code == 409


def test_legal_hold_create_and_release_are_audited(monkeypatch):
    calls = []
    audits = []

    async def privileged(method, table, *, params=None, body=None, prefer=None):
        calls.append((method, table, params, body))
        if method == "GET":
            return [{"id": str(HOLD_ID), "reference_code": "CASE-2026-001", "reason_code": "legal_preservation"}]
        if method == "POST":
            return [{"id": str(HOLD_ID), "subject_ref": SUBJECT_REF, "active": True}]
        return [{"id": str(HOLD_ID), "active": False, "released_by": OPERATOR["id"]}]

    async def audit(request, **kwargs):
        audits.append(kwargs)

    monkeypatch.setattr(governance, "privileged_rest_request", privileged)
    monkeypatch.setattr(governance, "write_operator_audit", audit)
    create_payload = governance.LegalHoldCreate(
        subject_ref=SUBJECT_REF, reference_code="CASE-2026-001", reason_code="legal_preservation"
    )
    created = asyncio.run(governance.create_legal_hold(create_payload, _request(), OPERATOR))
    release_payload = governance.LegalHoldRelease(reason="Court order closed and hold released")
    released = asyncio.run(governance.release_legal_hold(HOLD_ID, release_payload, _request(), OPERATOR))

    assert created["item"]["active"] is True
    assert released["item"]["active"] is False
    assert calls[0][1] == "account_legal_holds"
    assert calls[-1][2]["active"] == "eq.true"
    assert len(audits) == 4
    assert [item["outcome"] for item in audits] == ["attempted", "allowed", "attempted", "allowed"]


def test_deletion_request_listing_validates_filter_and_uses_bounded_query(monkeypatch):
    captured = {}

    async def privileged(method, table, *, params=None, body=None, prefer=None):
        captured.update(params or {})
        return []

    monkeypatch.setattr(governance, "privileged_rest_request", privileged)
    result = asyncio.run(governance.list_deletion_requests("awaiting_policy", 25, OPERATOR))
    assert result == {"items": [], "limit": 25, "status": "awaiting_policy"}
    assert captured["status"] == "eq.awaiting_policy"
    assert captured["limit"] == "25"

    with pytest.raises(HTTPException) as error:
        asyncio.run(governance.list_deletion_requests("not-a-status", 25, OPERATOR))
    assert error.value.status_code == 422



def test_retention_policy_deactivation_rejects_unconfirmed_database_result(monkeypatch):
    calls = []
    audits = []

    async def privileged(method, table, *, params=None, body=None, prefer=None):
        calls.append((method, table, params, body))
        if method == "GET":
            return [{"id": str(POLICY_ID), "data_class": "social_content", "policy_version": "v1", "active": True}]
        return False

    async def audit(request, **kwargs):
        audits.append(kwargs)

    monkeypatch.setattr(governance, "privileged_rest_request", privileged)
    monkeypatch.setattr(governance, "write_operator_audit", audit)

    with pytest.raises(HTTPException) as error:
        asyncio.run(governance.deactivate_retention_policy(POLICY_ID, _request(), OPERATOR))

    assert error.value.status_code == 503
    assert [item["outcome"] for item in audits] == ["attempted"]


def test_retention_policy_deactivation_requires_exact_inactive_row(monkeypatch):
    audits = []

    async def privileged(method, table, *, params=None, body=None, prefer=None):
        if method == "GET":
            return [{"id": str(POLICY_ID), "data_class": "social_content", "policy_version": "v1", "active": True}]
        return {"id": str(POLICY_ID), "active": False}

    async def audit(request, **kwargs):
        audits.append(kwargs)

    monkeypatch.setattr(governance, "privileged_rest_request", privileged)
    monkeypatch.setattr(governance, "write_operator_audit", audit)
    result = asyncio.run(governance.deactivate_retention_policy(POLICY_ID, _request(), OPERATOR))

    assert result["item"]["active"] is False
    assert [item["outcome"] for item in audits] == ["attempted", "allowed"]


def test_retention_policy_activation_rejects_unconfirmed_state(monkeypatch):
    audits = []

    async def privileged(method, table, *, params=None, body=None, prefer=None):
        if method == "GET":
            return [{"id": str(POLICY_ID), "data_class": "social_content", "policy_version": "v1", "active": False}]
        return {"id": str(POLICY_ID), "active": False}

    async def audit(request, **kwargs):
        audits.append(kwargs)

    monkeypatch.setattr(governance, "privileged_rest_request", privileged)
    monkeypatch.setattr(governance, "write_operator_audit", audit)

    with pytest.raises(HTTPException) as error:
        asyncio.run(governance.activate_retention_policy(POLICY_ID, _request(), OPERATOR))

    assert error.value.status_code == 503
    assert [item["outcome"] for item in audits] == ["attempted"]



def test_legal_hold_subject_ref_matches_hashed_deletion_subject():
    payload = governance.LegalHoldCreate(
        subject_ref="a" * 64,
        reference_code="CASE-2026-002",
        reason_code="legal_preservation",
    )
    assert payload.subject_ref == "a" * 64

    with pytest.raises(ValueError):
        governance.LegalHoldCreate(
            subject_ref="cccccccc-cccc-4ccc-8ccc-cccccccccccc",
            reference_code="CASE-2026-003",
            reason_code="legal_preservation",
        )



def test_deletion_request_listing_includes_dependency_blocked_state(monkeypatch):
    captured = {}

    async def privileged(method, table, *, params=None, body=None, prefer=None):
        captured.update(params or {})
        return [{"status": "blocked_dependency"}]

    monkeypatch.setattr(governance, "privileged_rest_request", privileged)
    result = asyncio.run(governance.list_deletion_requests("blocked_dependency", 25, OPERATOR))
    assert result["items"] == [{"status": "blocked_dependency"}]
    assert captured["status"] == "eq.blocked_dependency"


def test_legal_hold_listing_accepts_hashed_subject_reference(monkeypatch):
    captured = {}

    async def privileged(method, table, *, params=None, body=None, prefer=None):
        captured.update(params or {})
        return []

    monkeypatch.setattr(governance, "privileged_rest_request", privileged)
    result = asyncio.run(governance.list_legal_holds("a" * 64, 25, OPERATOR))
    assert result == {"items": [], "limit": 25}
    assert captured["subject_ref"] == f"eq.{'a' * 64}"


def test_legal_hold_listing_rejects_unhashed_subject_reference(monkeypatch):
    async def privileged(method, table, *, params=None, body=None, prefer=None):
        raise AssertionError("invalid subject_ref must be rejected before database access")

    monkeypatch.setattr(governance, "privileged_rest_request", privileged)
    with pytest.raises(HTTPException) as error:
        asyncio.run(governance.list_legal_holds("not-a-hash", 25, OPERATOR))
    assert error.value.status_code == 422
    assert error.value.detail["code"] == "ACCOUNT_LEGAL_HOLD_SUBJECT_INVALID"

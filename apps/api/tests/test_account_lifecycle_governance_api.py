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
        data_class="owner_private", retention_days=365,
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
        data_class="owner_private", retention_days=365,
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



def test_source_policy_update_requires_registered_source_and_safe_handler(monkeypatch):
    calls = []
    audits = []

    async def privileged(method, table, *, params=None, body=None, prefer=None):
        calls.append((method, table, params, body, prefer))
        if table == "rpc/list_account_deletion_source_registry":
            return [{"source_key": "profile", "table_name": "profiles", "filter_kind": "owner_columns",
                     "owner_columns": ["id"], "enabled": True, "deletion_handler_available": True}]
        if table == "account_deletion_source_policies":
            return [{**body, "source_key": "profile"}]
        return []

    async def audit(request, **kwargs):
        audits.append(kwargs)

    monkeypatch.setattr(governance, "privileged_rest_request", privileged)
    monkeypatch.setattr(governance, "write_operator_audit", audit)
    payload = governance.SourcePolicyUpdate(
        data_class="owner_private", deletion_action="delete_rows", dependency_order=10,
        policy_version="v1", reason="Owner profile data deletion mapping", active=False,
    )
    result = asyncio.run(governance.update_deletion_source_policy("profile", payload, _request(), OPERATOR))
    assert result["item"]["source_key"] == "profile"
    write = next(call for call in calls if call[1] == "account_deletion_source_policies")
    assert write[3]["approved_by"] == OPERATOR["id"]
    assert write[3]["active"] is False
    assert "resolution=merge-duplicates" in write[4]
    assert [item["outcome"] for item in audits] == ["attempted", "allowed"]


def test_source_policy_rejects_delete_rows_without_owner_scoped_handler(monkeypatch):
    async def privileged(method, table, *, params=None, body=None, prefer=None):
        return [{"source_key": "unmapped_shared_messages", "table_name": "messages",
                 "filter_kind": "participant_conversations", "owner_columns": [], "enabled": True, "deletion_handler_available": False}]

    async def audit(request, **kwargs):
        return None

    monkeypatch.setattr(governance, "privileged_rest_request", privileged)
    monkeypatch.setattr(governance, "write_operator_audit", audit)
    payload = governance.SourcePolicyUpdate(
        data_class="session_scoped", deletion_action="delete_rows", dependency_order=20,
        policy_version="v1", reason="Delete owner messages", active=True,
    )
    with pytest.raises(HTTPException) as error:
        asyncio.run(governance.update_deletion_source_policy("unmapped_shared_messages", payload, _request(), OPERATOR))
    assert error.value.status_code == 409
    assert error.value.detail["code"] == "ACCOUNT_DELETION_SOURCE_HANDLER_UNAVAILABLE"


def test_dependency_rule_rejects_incompatible_database_cascade(monkeypatch):
    async def privileged(method, table, *, params=None, body=None, prefer=None):
        return [{"id": str(POLICY_ID), "delete_rule": "RESTRICT", "fk_column": "owner_id"}]

    async def audit(request, **kwargs):
        return None

    monkeypatch.setattr(governance, "privileged_rest_request", privileged)
    monkeypatch.setattr(governance, "write_operator_audit", audit)
    payload = governance.DependencyRuleUpdate(
        resolution_action="database_cascade", reason="Attempted incompatible cascade", active=True,
    )
    with pytest.raises(HTTPException) as error:
        asyncio.run(governance.update_deletion_dependency_rule(POLICY_ID, payload, _request(), OPERATOR))
    assert error.value.status_code == 409
    assert error.value.detail["code"] == "ACCOUNT_DELETION_DEPENDENCY_ACTION_INCOMPATIBLE"


def test_dependency_rule_updates_only_compatible_fk_action_and_audits(monkeypatch):
    calls = []
    audits = []

    async def privileged(method, table, *, params=None, body=None, prefer=None):
        calls.append((method, table, params, body, prefer))
        if method == "GET":
            return [{"id": str(POLICY_ID), "delete_rule": "CASCADE", "fk_column": "owner_id"}]
        return [{**body, "id": str(POLICY_ID), "resolution_action": "database_cascade"}]

    async def audit(request, **kwargs):
        audits.append(kwargs)

    monkeypatch.setattr(governance, "privileged_rest_request", privileged)
    monkeypatch.setattr(governance, "write_operator_audit", audit)
    payload = governance.DependencyRuleUpdate(
        resolution_action="database_cascade", reason="Database FK is defined as cascade", active=True,
    )
    result = asyncio.run(governance.update_deletion_dependency_rule(POLICY_ID, payload, _request(), OPERATOR))
    assert result["item"]["resolution_action"] == "database_cascade"
    patch = next(call for call in calls if call[0] == "PATCH")
    assert patch[3]["approved_by"] == OPERATOR["id"]
    assert patch[3]["active"] is True
    assert [item["outcome"] for item in audits] == ["attempted", "allowed"]



def test_source_policy_allows_registered_specialized_owner_safe_handler(monkeypatch):
    calls = []
    async def privileged(method, table, *, params=None, body=None, prefer=None):
        calls.append((method, table, body))
        if table == "rpc/list_account_deletion_source_registry":
            return [{"source_key": "messages_in_conversations", "table_name": "messages",
                     "filter_kind": "conversation_messages", "owner_columns": [], "enabled": True, "deletion_handler_available": True}]
        if table == "account_deletion_source_policies":
            return [{**body, "source_key": "messages_in_conversations"}]
        return []
    async def audit(request, **kwargs):
        return None
    monkeypatch.setattr(governance, "privileged_rest_request", privileged)
    monkeypatch.setattr(governance, "write_operator_audit", audit)
    payload = governance.SourcePolicyUpdate(
        data_class="session_scoped", deletion_action="delete_rows", dependency_order=113,
        policy_version="v1", reason="Delete only messages authored by owner", active=False,
    )
    result = asyncio.run(governance.update_deletion_source_policy(
        "messages_in_conversations", payload, _request(), OPERATOR
    ))
    assert result["item"]["source_key"] == "messages_in_conversations"
    saved = next(body for _, table, body in calls if table == "account_deletion_source_policies")
    assert saved["deletion_action"] == "delete_rows"
    assert saved["active"] is False



def test_retention_policy_rejects_noncanonical_data_class():
    with pytest.raises(ValueError):
        governance.RetentionPolicyCreate(
            data_class="social_content", retention_days=365,
            policy_version="v1", legal_basis="Approved legal basis reference",
        )


def test_dependency_rule_transfer_owner_is_limited_to_canonical_owner_foreign_keys(monkeypatch):
    calls = []
    audits = []

    async def privileged(method, table, *, params=None, body=None, prefer=None):
        calls.append((method, table, params, body))
        if method == "GET":
            return [{
                "id": str(POLICY_ID),
                "child_schema": "public",
                "child_table": "agent_ownerships",
                "constraint_name": "agent_ownerships_owner_user_id_fkey",
                "fk_column": "owner_user_id",
                "delete_rule": "RESTRICT",
                "resolution_action": "transfer_owner",
            }]
        return [{**body, "id": str(POLICY_ID)}]

    async def audit(request, **kwargs):
        audits.append(kwargs)

    monkeypatch.setattr(governance, "privileged_rest_request", privileged)
    monkeypatch.setattr(governance, "write_operator_audit", audit)
    payload = governance.DependencyRuleUpdate(
        resolution_action="transfer_owner",
        reason="Transfer canonical Agent owner to validated active successor",
        active=True,
    )
    result = asyncio.run(governance.update_deletion_dependency_rule(POLICY_ID, payload, _request(), OPERATOR))

    assert result["item"]["resolution_action"] == "transfer_owner"
    assert calls[-1][3]["resolution_action"] == "transfer_owner"
    assert [item["outcome"] for item in audits] == ["attempted", "allowed"]


def test_source_anonymize_action_is_allowlisted_to_spatial_theme_provenance(monkeypatch):
    calls = []
    audits = []

    async def privileged(method, table, *, params=None, body=None, prefer=None):
        calls.append((method, table, params, body))
        if table == "rpc/list_account_deletion_source_registry":
            return [{
                "source_key": "spatial_theme_versions",
                "table_name": "spatial_theme_versions",
                "filter_kind": "owner_columns",
                "owner_columns": ["created_by"],
                "enabled": True,
                "deletion_handler_available": False,
            }]
        return [{**body, "source_key": "spatial_theme_versions"}]

    async def audit(request, **kwargs):
        audits.append(kwargs)

    monkeypatch.setattr(governance, "privileged_rest_request", privileged)
    monkeypatch.setattr(governance, "write_operator_audit", audit)
    payload = governance.SourcePolicyUpdate(
        data_class="public_catalog",
        deletion_action="anonymize",
        dependency_order=201,
        policy_version="v1",
        reason="Preserve immutable public theme manifest and anonymize creator provenance",
        active=True,
    )
    result = asyncio.run(governance.update_deletion_source_policy(
        "spatial_theme_versions", payload, _request(), OPERATOR
    ))

    assert result["item"]["deletion_action"] == "anonymize"
    assert calls[-1][3]["deletion_action"] == "anonymize"
    assert [item["outcome"] for item in audits] == ["attempted", "allowed"]


def test_source_anonymize_action_rejects_unregistered_source(monkeypatch):
    async def privileged(method, table, *, params=None, body=None, prefer=None):
        if table == "rpc/list_account_deletion_source_registry":
            return [{
                "source_key": "agent_skills_created",
                "table_name": "agent_skills",
                "filter_kind": "owner_columns",
                "owner_columns": ["created_by"],
                "enabled": True,
                "deletion_handler_available": True,
            }]
        raise AssertionError("unallowlisted anonymize action must not write a policy")

    async def audit(request, **kwargs):
        return None

    monkeypatch.setattr(governance, "privileged_rest_request", privileged)
    monkeypatch.setattr(governance, "write_operator_audit", audit)
    payload = governance.SourcePolicyUpdate(
        data_class="agent_operational",
        deletion_action="anonymize",
        dependency_order=52,
        policy_version="v1",
        reason="Attempt to use an unregistered anonymization handler",
        active=True,
    )
    with pytest.raises(HTTPException) as error:
        asyncio.run(governance.update_deletion_source_policy(
            "agent_skills_created", payload, _request(), OPERATOR
        ))
    assert error.value.status_code == 409
    assert error.value.detail["code"] == "ACCOUNT_DELETION_SOURCE_ANONYMIZE_HANDLER_UNAVAILABLE"


def test_dependency_rule_preserve_tombstone_is_limited_to_financial_and_retention_foreign_keys(monkeypatch):
    calls = []
    audits = []

    async def privileged(method, table, *, params=None, body=None, prefer=None):
        calls.append((method, table, params, body))
        if method == "GET":
            return [{
                "id": str(POLICY_ID),
                "child_schema": "public",
                "child_table": "billing_orders",
                "constraint_name": "billing_orders_owner_user_id_fkey",
                "fk_column": "owner_user_id",
                "delete_rule": "RESTRICT",
                "resolution_action": "preserve_tombstone",
            }]
        return [{**body, "id": str(POLICY_ID)}]

    async def audit(request, **kwargs):
        audits.append(kwargs)

    monkeypatch.setattr(governance, "privileged_rest_request", privileged)
    monkeypatch.setattr(governance, "write_operator_audit", audit)
    payload = governance.DependencyRuleUpdate(
        resolution_action="preserve_tombstone",
        reason="Preserve billing record under pseudonymous account subject",
        active=True,
    )
    result = asyncio.run(governance.update_deletion_dependency_rule(POLICY_ID, payload, _request(), OPERATOR))

    assert result["item"]["resolution_action"] == "preserve_tombstone"
    assert calls[-1][3]["resolution_action"] == "preserve_tombstone"
    assert [item["outcome"] for item in audits] == ["attempted", "allowed"]


def test_dependency_rule_rejects_tombstone_for_unregistered_foreign_key(monkeypatch):
    async def privileged(method, table, *, params=None, body=None, prefer=None):
        return [{
            "id": str(POLICY_ID),
            "child_schema": "public",
            "child_table": "profiles",
            "constraint_name": "profiles_id_fkey",
            "fk_column": "id",
            "delete_rule": "RESTRICT",
            "resolution_action": "block",
        }]

    async def audit(request, **kwargs):
        return None

    monkeypatch.setattr(governance, "privileged_rest_request", privileged)
    monkeypatch.setattr(governance, "write_operator_audit", audit)
    payload = governance.DependencyRuleUpdate(
        resolution_action="preserve_tombstone",
        reason="Attempt to apply tombstone to a non-retained identity reference",
        active=True,
    )
    with pytest.raises(HTTPException) as error:
        asyncio.run(governance.update_deletion_dependency_rule(POLICY_ID, payload, _request(), OPERATOR))
    assert error.value.status_code == 409
    assert error.value.detail["code"] == "ACCOUNT_DELETION_DEPENDENCY_ACTION_INCOMPATIBLE"

from __future__ import annotations

import asyncio
from uuid import UUID

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

import allpha_api.spatial_governance_api as governance
from allpha_api.spatial_governance_api import AgentAssetMappingCreate, AssetBatchActivation, AssetDecision, NodeCreate, NodeDecision


def test_universe_must_be_root():
    payload = NodeCreate(node_key="universe-main", level="universe", slug="universe-main", display_name="Universe")
    assert payload.parent_key is None


def test_non_root_requires_parent():
    with pytest.raises(ValidationError):
        NodeCreate(node_key="world-main", level="world", slug="world-main", display_name="World")


def test_coordinate_contract_rejects_non_finite_values():
    with pytest.raises(ValidationError):
        NodeCreate(node_key="universe-main", level="universe", slug="universe-main",
                   display_name="Universe", coordinates={"x": float("inf"), "y": 0, "z": 0})


def test_unknown_fields_are_rejected():
    with pytest.raises(ValidationError):
        NodeCreate(node_key="universe-main", level="universe", slug="universe-main",
                   display_name="Universe", publish=True)


def test_approval_requires_explicit_license_review_attestation():
    payload = AssetDecision(decision="approved", reason="Evidence reviewed", license_evidence_uri="https://example.org/license")
    assert payload.license_evidence_reviewed is False


def test_license_evidence_must_be_https():
    with pytest.raises(ValidationError):
        AssetDecision(decision="approved", reason="Evidence checked", license_evidence_uri="http://example.org/license")


def test_agent_mapping_requires_https_and_rationale():
    with pytest.raises(ValidationError):
        AgentAssetMappingCreate(agent_id="d3f40f6a-83de-4c0b-9f26-6d7e0f2a3b41",
            asset_key="character-test", asset_version=1, evidence_type="source_manifest",
            evidence_uri="http://example.org/manifest", rationale="Enough rationale for this test")


def test_mapping_checksum_must_be_sha256():
    with pytest.raises(ValidationError):
        AgentAssetMappingCreate(agent_id="d3f40f6a-83de-4c0b-9f26-6d7e0f2a3b41",
            asset_key="character-test", asset_version=1, evidence_type="source_manifest",
            evidence_uri="https://example.org/manifest", evidence_sha256="not-a-hash",
            rationale="Enough rationale for this test")



def test_audit_failure_prevents_privileged_node_write(monkeypatch):
    async def fail_audit(*args, **kwargs):
        raise HTTPException(status_code=503, detail={"code": "OPERATOR_AUDIT_UNAVAILABLE"})

    async def forbidden_write(*args, **kwargs):
        pytest.fail("database mutation must not run when audit preflight fails")

    monkeypatch.setattr(governance, "write_operator_audit", fail_audit)
    monkeypatch.setattr(governance, "privileged_rest_request", forbidden_write)
    payload = NodeCreate(node_key="universe-audit", level="universe", slug="universe-audit", display_name="Universe")
    with pytest.raises(HTTPException) as exc:
        asyncio.run(governance.create_spatial_node(payload, object(), {"id": "d3f40f6a-83de-4c0b-9f26-6d7e0f2a3b41"}))
    assert exc.value.status_code == 503


def test_mapping_checksum_mismatch_blocks_approval_before_write(monkeypatch):
    calls = []

    async def fake_store(method, table, *, params=None, body=None, prefer=None):
        calls.append((method, table, params, body))
        if table == "spatial_agent_asset_mappings":
            return [{"id": "e3f40f6a-83de-4c0b-9f26-6d7e0f2a3b41", "agent_id": "d3f40f6a-83de-4c0b-9f26-6d7e0f2a3b41", "asset_key": "character-test", "asset_version": 1, "status": "pending", "evidence_type": "source_manifest", "evidence_uri": "https://example.org/manifest", "evidence_sha256": "a" * 64}]
        if table == "spatial_asset_versions":
            return [{"sha256": "b" * 64, "status": "published", "moderation_status": "approved"}]
        pytest.fail("unexpected store operation: " + table)

    async def unexpected_audit(*args, **kwargs):
        pytest.fail("audit/write must not happen for checksum mismatch")

    monkeypatch.setattr(governance, "privileged_rest_request", fake_store)
    monkeypatch.setattr(governance, "write_operator_audit", unexpected_audit)
    payload = NodeDecision(decision="approved", reason="Checksum mismatch verified")
    with pytest.raises(HTTPException) as exc:
        asyncio.run(governance.review_agent_asset_mapping(UUID("e3f40f6a-83de-4c0b-9f26-6d7e0f2a3b41"), payload, object(), {"id": "d3f40f6a-83de-4c0b-9f26-6d7e0f2a3b41"}))
    assert exc.value.status_code == 409
    assert exc.value.detail["code"] == "SPATIAL_MAPPING_EVIDENCE_MISMATCH"
    assert len(calls) == 2


def test_every_governance_route_requires_operator_scope():
    routes = list(governance.router.routes)
    assert routes
    for route in routes:
        assert route.path.startswith("/v1/admin/spatial"), route.path
        assert route.dependant.dependencies, f"missing operator dependency on {route.path}"
        assert any(dep.call.__name__ == "dependency" for dep in route.dependant.dependencies), route.path



def test_parent_hierarchy_mismatch_blocks_node_creation(monkeypatch):
    async def fake_store(method, table, *, params=None, body=None, prefer=None):
        assert method == "GET"
        assert table == "spatial_navigation_nodes"
        return [{"id": "e3f40f6a-83de-4c0b-9f26-6d7e0f2a3b41", "node_key": "district-parent", "level": "district", "status": "published"}]

    async def unexpected_audit(*args, **kwargs):
        pytest.fail("invalid parent must be rejected before governance write/audit")

    monkeypatch.setattr(governance, "privileged_rest_request", fake_store)
    monkeypatch.setattr(governance, "write_operator_audit", unexpected_audit)
    payload = NodeCreate(node_key="world-invalid-parent", level="world", slug="world-invalid-parent",
                         display_name="World", parent_key="district-parent")
    with pytest.raises(HTTPException) as exc:
        asyncio.run(governance.create_spatial_node(payload, object(), {"id": "d3f40f6a-83de-4c0b-9f26-6d7e0f2a3b41"}))
    assert exc.value.status_code == 422
    assert exc.value.detail["code"] == "SPATIAL_HIERARCHY_INVALID"


def test_missing_operator_scope_is_denied_and_audited(monkeypatch):
    from types import SimpleNamespace
    from allpha_api import operator_security

    async def no_grants(*args, **kwargs):
        return []

    audited = []
    async def audit(*args, **kwargs):
        audited.append(kwargs)

    monkeypatch.setattr(operator_security, "user_db_request", no_grants)
    monkeypatch.setattr(operator_security, "write_operator_audit", audit)
    dependency = operator_security.require_operator_scope("platform:content.moderate")
    request = SimpleNamespace(state=SimpleNamespace(supabase_access_token="test-token"))
    with pytest.raises(HTTPException) as exc:
        asyncio.run(dependency(request, {"id": "d3f40f6a-83de-4c0b-9f26-6d7e0f2a3b41"}))
    assert exc.value.status_code == 403
    assert exc.value.detail["code"] == "OPERATOR_SCOPE_REQUIRED"
    assert audited and audited[-1]["outcome"] == "denied"



def test_batch_publish_includes_assets_already_enabled_for_internal_preview(monkeypatch):
    calls = []
    audit_events = []
    asset_id = "e3f40f6a-83de-4c0b-9f26-6d7e0f2a3b41"

    async def fake_store(method, table, *, params=None, body=None, prefer=None):
        calls.append((method, table, params or {}, body or {}))
        if method == "GET" and table == "spatial_asset_versions":
            if (params or {}).get("internal_preview_enabled") == "eq.false":
                return [{"asset_id": asset_id, "asset_key": "preview-asset", "version": 1,
                         "status": "test_only", "internal_preview_enabled": False}]
            if (params or {}).get("moderation_status") == "eq.approved":
                return [{"asset_id": asset_id, "asset_key": "preview-asset", "version": 1,
                         "status": "test_only", "moderation_status": "approved",
                         "license_evidence_status": "verified", "internal_preview_enabled": True}]
        if method == "PATCH" and table == "spatial_asset_versions":
            return [{"asset_id": asset_id, "asset_key": "preview-asset", "version": 1}]
        pytest.fail(f"unexpected store operation: {method} {table} {params}")

    async def audit(*args, **kwargs):
        audit_events.append(kwargs)

    monkeypatch.setattr(governance, "privileged_rest_request", fake_store)
    monkeypatch.setattr(governance, "write_operator_audit", audit)
    result = asyncio.run(governance.batch_activate_spatial_assets(
        AssetBatchActivation(mode="both", limit=10), object(), {"id": asset_id}
    ))

    assert result["internal_preview"]["succeeded"] == 1
    assert result["catalog_publish"]["succeeded"] == 1
    assert result["internal_preview"]["skipped"] == 0
    assert result["catalog_publish"]["skipped"] == 0
    publish_query = next(params for method, table, params, _ in calls
                         if method == "GET" and table == "spatial_asset_versions"
                         and params.get("moderation_status") == "eq.approved")
    assert "internal_preview_enabled" not in publish_query
    publish_patch = next(body for method, table, _, body in calls
                         if method == "PATCH" and body.get("status") == "published")
    assert publish_patch["status"] == "published"
    assert audit_events

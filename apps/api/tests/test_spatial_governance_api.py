from __future__ import annotations

import pytest
from pydantic import ValidationError

from allpha_api.spatial_governance_api import AgentAssetMappingCreate, AssetDecision, NodeCreate


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

from fastapi.testclient import TestClient
import pytest

from allpha_api.agency_skill_catalog import AGENCY_CATALOG_VERSION, AGENCY_SKILL_CATALOG, AGENCY_SKILL_CATALOG_BY_KEY, search_agency_skill_catalog
from allpha_api.catalog_registry import get_skill_catalog_item, get_skill_catalog_source, get_skill_catalog_version
from allpha_api.main import _validate_catalog_skill_selection, app

client = TestClient(app)


def test_agency_catalog_contains_282_pinned_metadata_only_profiles():
    assert len(AGENCY_SKILL_CATALOG) == 282
    assert len(AGENCY_SKILL_CATALOG_BY_KEY) == 282
    assert len({item["key"] for item in AGENCY_SKILL_CATALOG}) == 282
    assert all(item["executable"] is False for item in AGENCY_SKILL_CATALOG)
    assert all(item["execution_status"] == "catalog_only" for item in AGENCY_SKILL_CATALOG)
    assert all(item["source"]["commit"] == "652b2692f8d8ec2b1f1a38e559073e287dfdc469" for item in AGENCY_SKILL_CATALOG)
    assert all(item["source"]["license"] == "MIT" for item in AGENCY_SKILL_CATALOG)
    assert all(item["character_profile"]["asset_key"] is None for item in AGENCY_SKILL_CATALOG)
    assert all(item["character_profile"]["asset_status"] == "needs_catalog_mapping" for item in AGENCY_SKILL_CATALOG)


def test_agency_catalog_search_and_pagination_are_deterministic():
    first = search_agency_skill_catalog(limit=100, offset=0)
    second = search_agency_skill_catalog(limit=100, offset=100)
    frontend = search_agency_skill_catalog(q="frontend developer", limit=20)
    assert first["total"] == 282
    assert len(first["items"]) == 100
    assert len(second["items"]) == 100
    assert {item["key"] for item in first["items"]}.isdisjoint(item["key"] for item in second["items"])
    assert any("frontend-developer" in item["source"]["path"] for item in frontend["items"])
    assert search_agency_skill_catalog(q="not-a-real-agency-agent")["total"] == 0


def test_agency_persona_selection_requires_matching_source_version_and_character_profile():
    skill = AGENCY_SKILL_CATALOG[0]
    persona = {
        "allpha_skill_key": skill["key"],
        "allpha_skill_source": "agency-agents",
        "allpha_skill_catalog_version": AGENCY_CATALOG_VERSION,
        "character_profile": skill["character_profile"],
    }
    _validate_catalog_skill_selection(persona)
    assert get_skill_catalog_item(skill["key"]) is skill
    assert get_skill_catalog_source(skill["key"]) == "agency-agents"
    assert get_skill_catalog_version(skill["key"]) == AGENCY_CATALOG_VERSION


def test_agency_persona_rejects_forged_source_version_and_character_asset():
    skill = AGENCY_SKILL_CATALOG[0]
    base = {
        "allpha_skill_key": skill["key"],
        "allpha_skill_source": "agency-agents",
        "allpha_skill_catalog_version": AGENCY_CATALOG_VERSION,
        "character_profile": skill["character_profile"],
    }
    with pytest.raises(Exception):
        _validate_catalog_skill_selection({**base, "allpha_skill_source": "allpha-500"})
    with pytest.raises(Exception):
        _validate_catalog_skill_selection({**base, "allpha_skill_catalog_version": "allpha-skill-catalog-v1"})
    with pytest.raises(Exception):
        _validate_catalog_skill_selection({**base, "character_profile": {**skill["character_profile"], "asset_key": "unverified.glb"}})


def test_public_agency_catalog_api_reports_source_and_never_executable_items():
    response = client.get("/v1/skill-catalog/agency-agents?limit=100&offset=0")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 282
    assert body["catalog_version"] == AGENCY_CATALOG_VERSION
    assert body["source_commit"] == "652b2692f8d8ec2b1f1a38e559073e287dfdc469"
    assert body["executable_count"] == 0
    assert all(item["executable"] is False for item in body["items"])

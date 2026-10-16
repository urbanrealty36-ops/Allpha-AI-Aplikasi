import pytest
from fastapi import HTTPException

from allpha_api.main import _validate_catalog_skill_selection
from allpha_api.skill_catalog import (
    SKILL_CATALOG,
    SKILL_CATALOG_BY_KEY,
    SKILL_CATALOG_CATEGORIES,
    search_skill_catalog,
)


def test_catalog_has_exactly_500_unique_blueprints_and_no_fake_executable_handlers():
    assert len(SKILL_CATALOG) == 500
    assert len(SKILL_CATALOG_BY_KEY) == 500
    assert all(item["executable"] is False for item in SKILL_CATALOG)
    assert all(item["execution_status"] == "catalog_only" for item in SKILL_CATALOG)
    assert all(item["character_profile"]["asset_key"] is None for item in SKILL_CATALOG)


def test_upstream_repository_examples_are_explicitly_referenced():
    examples = [item for item in SKILL_CATALOG if item["source"]["kind"] == "repository_agent_example"]
    assert len(examples) == 21
    assert any(item["slug"] == "web-research-agent" for item in examples)
    assert any(item["slug"] == "pii-sanitization-agent" for item in examples)
    assert all(item["source"]["repository"] == "https://github.com/ashishpatel26/500-AI-Agents-Projects" for item in examples)


def test_catalog_search_category_and_pagination_are_deterministic():
    all_results = search_skill_catalog(limit=100, offset=0)
    page_two = search_skill_catalog(limit=100, offset=100)
    research = search_skill_catalog(category="research", limit=100)
    assert all_results["total"] == 500
    assert len(all_results["items"]) == 100
    assert len(page_two["items"]) == 100
    assert set(item["key"] for item in all_results["items"]).isdisjoint(item["key"] for item in page_two["items"])
    assert research["items"]
    assert all(item["category"] == "research" for item in research["items"])
    assert sum(item["count"] for item in SKILL_CATALOG_CATEGORIES) == 500


def test_catalog_search_is_case_insensitive_and_returns_no_fabricated_results():
    result = search_skill_catalog(q="WEB RESEARCH", limit=20)
    assert result["total"] >= 1
    assert any(item["slug"] == "web-research-agent" for item in result["items"])
    assert search_skill_catalog(q="not-a-real-skill-identifier")["total"] == 0

def test_agent_persona_selection_is_validated_against_canonical_catalog():
    skill = SKILL_CATALOG[0]
    _validate_catalog_skill_selection({
        "allpha_skill_key": skill["key"],
        "allpha_skill_catalog_version": "allpha-skill-catalog-v1",
        "character_profile": skill["character_profile"],
    })


def test_agent_persona_rejects_unknown_catalog_key_and_forged_character_profile():
    with pytest.raises(HTTPException) as unknown:
        _validate_catalog_skill_selection({
            "allpha_skill_key": "not.a.real.skill",
            "allpha_skill_catalog_version": "allpha-skill-catalog-v1",
            "character_profile": {},
        })
    assert unknown.value.status_code == 422
    assert unknown.value.detail["code"] == "AGENT_SKILL_CATALOG_KEY_INVALID"

    skill = SKILL_CATALOG[0]
    with pytest.raises(HTTPException) as forged:
        _validate_catalog_skill_selection({
            "allpha_skill_key": skill["key"],
            "allpha_skill_catalog_version": "allpha-skill-catalog-v1",
            "character_profile": {"archetype_key": "forged-role", "asset_key": "unverified.glb"},
        })
    assert forged.value.status_code == 422
    assert forged.value.detail["code"] == "AGENT_CHARACTER_PROFILE_MISMATCH"

import asyncio
from uuid import uuid4

from fastapi import HTTPException
from starlette.requests import Request

from allpha_api import agency_skill_drafts_api as api


def _request() -> Request:
    return Request({
        "type": "http", "method": "GET", "path": "/v1/admin/skill-drafts/agency-agents",
        "headers": [], "query_string": b"", "server": ("test", 80),
        "client": ("test", 80), "scheme": "http",
    })


def _record(skill_id="agency.engineering.frontend"):
    return {
        "skill_id": skill_id, "version": 1, "version_key": f"{skill_id}@v1",
        "name": "Frontend Engineer", "category": "engineering",
        "description": "Build frontend interfaces", "status": "draft",
        "immutable": True, "executable": False,
        "content_sha256": "a" * 64, "adapted_content_sha256": "b" * 64,
        "provenance": {"commit": "652b2692f8d8ec2b1f1a38e559073e287dfdc469"},
        "review": {"review_status": "draft_unreviewed", "manual_security_review": "pending"},
        "character_profile": {"asset_key": None, "asset_status": "needs_catalog_mapping"},
        "source_instructions_markdown": "source body",
        "adapted_instructions": "adapted body",
    }


def test_operator_draft_list_returns_metadata_only_and_never_executable(monkeypatch):
    audits = []
    monkeypatch.setattr(api, "load_agency_skill_drafts", lambda: (_record(),))
    async def audit(*args, **kwargs):
        audits.append(kwargs)
    monkeypatch.setattr(api, "write_operator_audit", audit)
    result = asyncio.run(api.list_agency_skill_drafts(
        _request(), q="frontend", category="engineering", limit=10, offset=0,
        operator={"id": str(uuid4())},
    ))
    assert result["total"] == 1
    assert result["executable_count"] == 0
    assert "source_instructions_markdown" not in result["items"][0]
    assert audits[0]["action"] == "skill_drafts.agency.list"


def test_operator_draft_detail_includes_source_and_is_audited(monkeypatch):
    record = _record()
    audits = []
    monkeypatch.setattr(api, "get_agency_skill_draft", lambda key: record if key == record["skill_id"] else None)
    async def audit(*args, **kwargs):
        audits.append(kwargs)
    monkeypatch.setattr(api, "write_operator_audit", audit)
    result = asyncio.run(api.get_agency_skill_draft_detail(
        record["skill_id"], _request(), {"id": str(uuid4())},
    ))
    assert result["source_instructions_markdown"] == "source body"
    assert result["adapted_instructions"] == "adapted body"
    assert audits[0]["resource_id"] == record["skill_id"]


def test_draft_detail_rejects_unknown_ids_and_missing_drafts(monkeypatch):
    async def audit(*args, **kwargs):
        raise AssertionError("unknown draft must not be audited as allowed")
    monkeypatch.setattr(api, "get_agency_skill_draft", lambda _key: None)
    monkeypatch.setattr(api, "write_operator_audit", audit)
    try:
        asyncio.run(api.get_agency_skill_draft_detail("../not-an-agency-id", _request(), {"id": str(uuid4())}))
    except HTTPException as exc:
        assert exc.status_code == 422
    else:
        raise AssertionError("invalid ID should fail closed")
    try:
        asyncio.run(api.get_agency_skill_draft_detail("agency.unknown.skill", _request(), {"id": str(uuid4())}))
    except HTTPException as exc:
        assert exc.status_code == 404
    else:
        raise AssertionError("missing draft should return 404")


def test_reconciliation_summary_does_not_invent_matches(monkeypatch):
    audits = []
    monkeypatch.setattr(api, "load_agency_reconciliation", lambda: None)
    async def audit(*args, **kwargs):
        audits.append(kwargs)
    monkeypatch.setattr(api, "write_operator_audit", audit)
    result = asyncio.run(api.get_agency_skill_reconciliation(_request(), {"id": str(uuid4())}))
    assert result == {
        "status": "awaiting_import_workflow",
        "agency_count": 282,
        "allpha_blueprint_count": 500,
        "items": [],
    }
    assert audits[0]["action"] == "skill_drafts.agency.reconciliation.read"

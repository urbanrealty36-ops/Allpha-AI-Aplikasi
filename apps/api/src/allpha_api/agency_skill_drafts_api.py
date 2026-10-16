"""Operator-only read surface for imported Agency Skill drafts."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from allpha_api.agency_skill_drafts import (
    get_agency_skill_draft,
    load_agency_reconciliation,
    load_agency_skill_drafts,
)
from allpha_api.operator_security import require_operator_scope, write_operator_audit

router = APIRouter(prefix="/v1/admin/skill-drafts/agency-agents", tags=["skill-draft-governance"])


def _summary(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "skill_id": record["skill_id"],
        "version": record["version"],
        "version_key": record["version_key"],
        "name": record.get("name"),
        "category": record.get("category"),
        "description": record.get("description"),
        "status": record["status"],
        "immutable": record["immutable"],
        "executable": record["executable"],
        "content_sha256": record["content_sha256"],
        "adapted_content_sha256": record["adapted_content_sha256"],
        "provenance": record["provenance"],
        "review": record["review"],
        "character_profile": record["character_profile"],
    }


@router.get("", name="list_agency_skill_drafts")
async def list_agency_skill_drafts(
    q: str = Query(default="", max_length=120),
    category: str = Query(default="", max_length=80),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=100_000),
    request: Request = None,  # type: ignore[assignment]
    operator: dict[str, Any] = Depends(require_operator_scope("platform:capabilities.review")),
) -> dict[str, Any]:
    records = load_agency_skill_drafts()
    query = q.casefold().strip()
    selected = [
        record for record in records
        if (not category or record.get("category") == category)
        and (not query or query in record["skill_id"].casefold()
             or query in str(record.get("name", "")).casefold()
             or query in str(record.get("description", "")).casefold())
    ]
    page = selected[offset:offset + limit]
    if request is not None:
        await write_operator_audit(
            request, actor_user_id=operator["id"], action="skill_drafts.agency.list",
            outcome="allowed", resource_type="agency_skill_draft_catalog",
            metadata={"query_present": bool(query), "category": category or None, "limit": limit, "offset": offset, "result_count": len(page)},
        )
    return {
        "items": [_summary(record) for record in page],
        "total": len(selected),
        "limit": limit,
        "offset": offset,
        "source_commit": "652b2692f8d8ec2b1f1a38e559073e287dfdc469",
        "import_status": "imported" if records else "awaiting_import_workflow",
        "executable_count": 0,
    }


@router.get("/{skill_id:path}", name="get_agency_skill_draft")
async def get_agency_skill_draft_detail(
    skill_id: str,
    request: Request,
    operator: dict[str, Any] = Depends(require_operator_scope("platform:capabilities.review")),
) -> dict[str, Any]:
    if len(skill_id) > 180 or not skill_id.startswith("agency."):
        raise HTTPException(status_code=422, detail={"code": "AGENCY_SKILL_DRAFT_ID_INVALID", "message": "ID draft Skill tidak valid."})
    record = get_agency_skill_draft(skill_id)
    if not record:
        raise HTTPException(status_code=404, detail={"code": "AGENCY_SKILL_DRAFT_NOT_FOUND", "message": "Draft belum diimpor atau ID tidak ditemukan."})
    await write_operator_audit(
        request, actor_user_id=operator["id"], action="skill_drafts.agency.read",
        outcome="allowed", resource_type="agency_skill_draft", resource_id=skill_id,
        metadata={"version_key": record["version_key"], "source_commit": record["provenance"]["commit"]},
    )
    return {
        **_summary(record),
        "source_instructions_markdown": record["source_instructions_markdown"],
        "adapted_instructions": record["adapted_instructions"],
    }


@router.get("/reconciliation/summary", name="get_agency_skill_reconciliation")
async def get_agency_skill_reconciliation(
    request: Request,
    operator: dict[str, Any] = Depends(require_operator_scope("platform:capabilities.review")),
) -> dict[str, Any]:
    document = load_agency_reconciliation()
    await write_operator_audit(
        request, actor_user_id=operator["id"], action="skill_drafts.agency.reconciliation.read",
        outcome="allowed", resource_type="agency_skill_reconciliation",
        metadata={"available": document is not None},
    )
    if document is None:
        return {"status": "awaiting_import_workflow", "agency_count": 282, "allpha_blueprint_count": 500, "items": []}
    return {key: value for key, value in document.items() if key != "items"} | {
        "status": "candidate_map_available",
        "items": document["items"],
    }

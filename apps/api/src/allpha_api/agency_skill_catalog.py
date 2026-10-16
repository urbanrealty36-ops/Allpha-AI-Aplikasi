"""Pinned metadata-only import of Agency Agents definitions.

Upstream files are specialized prompt/persona documents, not executable Allpha Skills
and not 3D GLB character assets. This module exposes catalog metadata only.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

AGENCY_CATALOG_VERSION = "agency-agents-652b2692"
AGENCY_SOURCE_REPOSITORY = "https://github.com/msitarzewski/agency-agents"
AGENCY_SOURCE_COMMIT = "652b2692f8d8ec2b1f1a38e559073e287dfdc469"

with Path(__file__).with_name("agency_agents_catalog.json").open(encoding="utf-8") as _catalog_file:
    _catalog_document = json.load(_catalog_file)

AGENCY_SKILL_CATALOG = tuple(_catalog_document["items"])
AGENCY_SKILL_CATALOG_BY_KEY = {item["key"]: item for item in AGENCY_SKILL_CATALOG}
AGENCY_SKILL_CATALOG_CATEGORIES = tuple(_catalog_document["categories"])

if len(AGENCY_SKILL_CATALOG_BY_KEY) != len(AGENCY_SKILL_CATALOG):
    raise RuntimeError("Agency Agent catalog contains duplicate keys")
if any(item.get("executable") is not False or item.get("execution_status") != "catalog_only" for item in AGENCY_SKILL_CATALOG):
    raise RuntimeError("Agency Agent imports must remain metadata-only until reviewed and registered")


def search_agency_skill_catalog(*, q: str = "", category: str = "", limit: int = 50, offset: int = 0) -> dict[str, Any]:
    """Search the pinned Agency metadata catalog; membership never grants runtime authority."""
    query = q.strip().casefold()
    selected = [
        item for item in AGENCY_SKILL_CATALOG
        if (not category or item["category"] == category)
        and (not query or query in item["name"].casefold()
             or query in item["description"].casefold()
             or query in item["key"].casefold()
             or query in item["source"]["path"].casefold())
    ]
    safe_limit = max(1, min(int(limit), 100))
    safe_offset = max(0, int(offset))
    return {
        "items": list(selected[safe_offset:safe_offset + safe_limit]),
        "total": len(selected),
        "limit": safe_limit,
        "offset": safe_offset,
        "categories": list(AGENCY_SKILL_CATALOG_CATEGORIES),
        "catalog_version": AGENCY_CATALOG_VERSION,
        "executable_count": 0,
        "source_repository": AGENCY_SOURCE_REPOSITORY,
        "source_commit": AGENCY_SOURCE_COMMIT,
        "import_mode": "metadata_only",
    }

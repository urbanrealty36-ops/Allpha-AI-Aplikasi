"""Unified lookup for distinct Allpha and Agency metadata catalogs.

The Allpha 500 blueprint set remains unchanged. Agency is a separately versioned
supplemental source. Neither catalog grants execution authority.
"""
from __future__ import annotations

from typing import Literal

from allpha_api.agency_skill_catalog import (
    AGENCY_CATALOG_VERSION,
    AGENCY_SKILL_CATALOG,
    AGENCY_SKILL_CATALOG_BY_KEY,
)
from allpha_api.skill_catalog import SKILL_CATALOG, SKILL_CATALOG_BY_KEY

ALLPHA_CATALOG_VERSION = "allpha-skill-catalog-v1"
CatalogSource = Literal["allpha-500", "agency-agents"]


def get_skill_catalog_item(key: str) -> dict | None:
    return SKILL_CATALOG_BY_KEY.get(key) or AGENCY_SKILL_CATALOG_BY_KEY.get(key)


def get_skill_catalog_source(key: str) -> str | None:
    if key in SKILL_CATALOG_BY_KEY:
        return "allpha-500"
    if key in AGENCY_SKILL_CATALOG_BY_KEY:
        return "agency-agents"
    return None


def get_skill_catalog_version(key: str) -> str | None:
    source = get_skill_catalog_source(key)
    if source == "allpha-500":
        return ALLPHA_CATALOG_VERSION
    if source == "agency-agents":
        return AGENCY_CATALOG_VERSION
    return None


def get_skill_catalog_items(source: CatalogSource) -> tuple[tuple[dict, ...], str]:
    if source == "agency-agents":
        return AGENCY_SKILL_CATALOG, AGENCY_CATALOG_VERSION
    return SKILL_CATALOG, ALLPHA_CATALOG_VERSION

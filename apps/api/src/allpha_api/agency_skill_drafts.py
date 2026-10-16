"""Read-only loader for pinned, immutable Agency Skill draft manifests.

Drafts are never executable and this module intentionally has no persistence or mutation
API. Source documents remain untrusted until manual review and canonical policy/tool binding.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

EXPECTED_SOURCE_COMMIT = "652b2692f8d8ec2b1f1a38e559073e287dfdc469"
EXPECTED_COUNT = 282
_PACKAGE_DIR = Path(__file__).parent
_DRAFT_DIR = _PACKAGE_DIR / "agency_skill_drafts"
_RECONCILIATION_PATH = _PACKAGE_DIR / "agency_skill_reconciliation_candidates.json"


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def load_agency_skill_drafts(*, verify_digests: bool = True) -> tuple[dict[str, Any], ...]:
    if not _DRAFT_DIR.is_dir():
        return ()
    records: list[dict[str, Any]] = []
    for path in sorted(_DRAFT_DIR.glob("agency_skill_drafts_*.json")):
        document = json.loads(path.read_text(encoding="utf-8"))
        if document.get("source_commit") != EXPECTED_SOURCE_COMMIT:
            raise RuntimeError(f"Unexpected Agency source commit in {path.name}")
        for record in document.get("records", []):
            if record.get("status") != "draft" or record.get("immutable") is not True or record.get("executable") is not False:
                raise RuntimeError(f"Agency Skill draft invariant failed: {record.get('skill_id')}")
            if record.get("provenance", {}).get("commit") != EXPECTED_SOURCE_COMMIT:
                raise RuntimeError(f"Agency Skill provenance mismatch: {record.get('skill_id')}")
            if verify_digests:
                if _digest(record["source_instructions_markdown"]) != record.get("content_sha256"):
                    raise RuntimeError(f"Source checksum mismatch: {record.get('skill_id')}")
                if _digest(record["adapted_instructions"]) != record.get("adapted_content_sha256"):
                    raise RuntimeError(f"Adapted checksum mismatch: {record.get('skill_id')}")
            records.append(record)
    keys = [record["skill_id"] for record in records]
    if len(keys) != len(set(keys)):
        raise RuntimeError("Duplicate Agency Skill draft IDs")
    if records and len(records) != EXPECTED_COUNT:
        raise RuntimeError(f"Expected {EXPECTED_COUNT} Agency Skill drafts, got {len(records)}")
    return tuple(records)


def load_agency_reconciliation() -> dict[str, Any] | None:
    if not _RECONCILIATION_PATH.is_file():
        return None
    document = json.loads(_RECONCILIATION_PATH.read_text(encoding="utf-8"))
    if document.get("agency_source_commit") != EXPECTED_SOURCE_COMMIT:
        raise RuntimeError("Unexpected source commit in Agency reconciliation manifest")
    if any(row.get("canonical_identity_merge") is not False for row in document.get("items", [])):
        raise RuntimeError("Reconciliation manifest attempted an automatic source merge")
    return document


def get_agency_skill_draft(skill_id: str) -> dict[str, Any] | None:
    return next((record for record in load_agency_skill_drafts() if record["skill_id"] == skill_id), None)

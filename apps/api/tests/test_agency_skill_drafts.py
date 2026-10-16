from __future__ import annotations

import hashlib
import importlib
import json


def test_draft_loader_checks_immutable_source_and_adapted_digests(tmp_path, monkeypatch):
    module = importlib.import_module("allpha_api.agency_skill_drafts")
    body = "# Source instructions\nDo the specialist task."
    adapted = "Allpha adapter\n" + body
    record = {
        "skill_id": "agency.test.specialist",
        "version": 1,
        "version_key": "agency.test.specialist@v1",
        "status": "draft",
        "immutable": True,
        "executable": False,
        "source_instructions_markdown": body,
        "adapted_instructions": adapted,
        "content_sha256": hashlib.sha256(body.encode()).hexdigest(),
        "adapted_content_sha256": hashlib.sha256(adapted.encode()).hexdigest(),
        "provenance": {"commit": module.EXPECTED_SOURCE_COMMIT},
    }
    draft_dir = tmp_path / "drafts"
    draft_dir.mkdir()
    (draft_dir / "agency_skill_drafts_01.json").write_text(json.dumps({
        "source_commit": module.EXPECTED_SOURCE_COMMIT,
        "records": [record],
    }))
    monkeypatch.setattr(module, "_DRAFT_DIR", draft_dir)
    monkeypatch.setattr(module, "EXPECTED_COUNT", 1)
    assert module.load_agency_skill_drafts()[0]["skill_id"] == record["skill_id"]


def test_draft_loader_rejects_checksum_tampering(tmp_path, monkeypatch):
    module = importlib.import_module("allpha_api.agency_skill_drafts")
    record = {
        "skill_id": "agency.test.tampered",
        "status": "draft",
        "immutable": True,
        "executable": False,
        "source_instructions_markdown": "changed after import",
        "adapted_instructions": "adapter",
        "content_sha256": "0" * 64,
        "adapted_content_sha256": hashlib.sha256(b"adapter").hexdigest(),
        "provenance": {"commit": module.EXPECTED_SOURCE_COMMIT},
    }
    draft_dir = tmp_path / "drafts"
    draft_dir.mkdir()
    (draft_dir / "agency_skill_drafts_01.json").write_text(json.dumps({
        "source_commit": module.EXPECTED_SOURCE_COMMIT,
        "records": [record],
    }))
    monkeypatch.setattr(module, "_DRAFT_DIR", draft_dir)
    monkeypatch.setattr(module, "EXPECTED_COUNT", 1)
    try:
        module.load_agency_skill_drafts()
    except RuntimeError as exc:
        assert "checksum mismatch" in str(exc).lower()
    else:
        raise AssertionError("checksum tampering must fail closed")


def test_imported_agency_draft_bundle_has_all_282_pinned_versions():
    from allpha_api.agency_skill_drafts import load_agency_reconciliation, load_agency_skill_drafts

    records = load_agency_skill_drafts()
    reconciliation = load_agency_reconciliation()
    assert len(records) == 282
    assert len({record["skill_id"] for record in records}) == 282
    assert all(record["version"] == 1 and record["status"] == "draft" for record in records)
    assert all(record["immutable"] is True and record["executable"] is False for record in records)
    assert all(record["provenance"]["commit"] == "652b2692f8d8ec2b1f1a38e559073e287dfdc469" for record in records)
    assert all(record["content_sha256"] and record["adapted_content_sha256"] for record in records)
    assert all(record["character_profile"]["asset_key"] is None for record in records)
    assert reconciliation is not None
    assert len(reconciliation["items"]) == 282
    assert all(row["canonical_identity_merge"] is False for row in reconciliation["items"])

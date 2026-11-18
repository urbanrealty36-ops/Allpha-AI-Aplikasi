from pathlib import Path

import pytest

from scripts.check_wp07_migration_chain import migration_versions, parse_ledger, reconcile


def test_parse_ledger_ignores_psql_transaction_headers_and_invalid_rows():
    assert parse_ledger("BEGIN\n20261115185633\nnot-a-version\nCOMMIT\n") == {"20261115185633"}


def test_reconcile_distinguishes_canonical_pending_from_source_only_pending():
    report = reconcile(
        {"20261115185633": "base.sql", "20261118195000": "retry.sql"},
        {"20261118195500": "readiness.sql"},
        {"20261115185633"},
    )
    assert report["canonical_pending"] == ["20261118195000"]
    assert report["source_only_pending"] == ["20261118195500"]
    assert report["source_only_applied"] == []
    assert report["applied_without_source"] == []


def test_reconcile_flags_applied_source_only_and_unknown_remote_versions():
    report = reconcile(
        {"20261115185633": "base.sql"},
        {"20261118195500": "readiness.sql"},
        {"20261115185633", "20261118195500", "20261119999999"},
    )
    assert report["source_only_applied"] == ["20261118195500"]
    assert report["applied_without_source"] == ["20261119999999"]


def test_migration_versions_rejects_duplicate_timestamp(tmp_path: Path):
    (tmp_path / "20261119100000_first.sql").write_text("select 1;")
    (tmp_path / "20261119100000_second.sql").write_text("select 2;")
    with pytest.raises(ValueError, match="Duplicate migration version"):
        migration_versions(tmp_path)


def test_reconcile_rejects_version_collision_between_canonical_and_source_only():
    with pytest.raises(ValueError, match="exist in both directories"):
        reconcile(
            {"20261105120000": "wp04_schedule_media_readiness_guard.sql"},
            {"20261105120000": "eng_p30_stripe_billing_subscriptions_entitlements.sql"},
            set(),
        )

#!/usr/bin/env python3
"""Read-only WP-07 Supabase migration-chain reconciliation.

This command never applies, repairs, resets, or rewrites a migration. It compares
local canonical/source-only migration versions with the remote Supabase ledger
inside a read-only PostgreSQL transaction.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Iterable

VERSIONED_SQL = re.compile(r"^(?P<version>\d{14})_(?P<name>[a-z0-9][a-z0-9_-]*)\.sql$")
LEDGER_VERSION = re.compile(r"^\d{14}$")


def migration_versions(directory: Path) -> dict[str, str]:
    versions: dict[str, str] = {}
    if not directory.exists():
        return versions
    for path in sorted(directory.glob("*.sql")):
        match = VERSIONED_SQL.fullmatch(path.name)
        if not match:
            raise ValueError(f"Invalid migration filename: {path}")
        version = match.group("version")
        if version in versions:
            raise ValueError(f"Duplicate migration version {version}: {versions[version]} and {path.name}")
        versions[version] = path.name
    return versions


def parse_ledger(output: str) -> set[str]:
    versions = set()
    for raw in output.splitlines():
        value = raw.strip()
        if LEDGER_VERSION.fullmatch(value):
            versions.add(value)
    return versions


def reconcile(canonical: dict[str, str], source_only: dict[str, str],
              applied: set[str]) -> dict[str, list[str]]:
    overlap = sorted(set(canonical) & set(source_only))
    if overlap:
        raise ValueError("Migration versions exist in both directories: " + ", ".join(overlap))
    known = set(canonical) | set(source_only)
    return {
        "applied_without_source": sorted(applied - known),
        "canonical_pending": sorted(set(canonical) - applied),
        "source_only_applied": sorted(set(source_only) & applied),
        "source_only_pending": sorted(set(source_only) - applied),
        "canonical_applied": sorted(set(canonical) & applied),
    }


def read_remote_ledger(database_url: str) -> set[str]:
    psql = shutil.which("psql")
    if not psql:
        raise RuntimeError("psql is required; no migration or database mutation was attempted")
    query = (
        "BEGIN READ ONLY; "
        "SELECT version FROM supabase_migrations.schema_migrations ORDER BY version; "
        "COMMIT;"
    )
    completed = subprocess.run(
        [psql, "-X", "-A", "-t", "-v", "ON_ERROR_STOP=1", "--dbname", database_url, "-c", query],
        check=False, capture_output=True, text=True, env={**os.environ, "PGOPTIONS": "-c default_transaction_read_only=on"},
    )
    if completed.returncode:
        detail = (completed.stderr or completed.stdout).strip()
        raise RuntimeError(f"Could not read Supabase migration ledger: {detail[:1200]}")
    return parse_ledger(completed.stdout)


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--require-clean", action="store_true",
                        help="exit non-zero when canonical migrations are pending")
    args = parser.parse_args(argv)
    database_url = os.getenv("SUPABASE_DB_URL")
    if not database_url:
        parser.error("SUPABASE_DB_URL is required (read-only connection)")
    try:
        canonical = migration_versions(args.api_root / "supabase" / "migrations")
        source_only = migration_versions(args.api_root / "supabase" / "source-only-migrations")
        applied = read_remote_ledger(database_url)
        report = reconcile(canonical, source_only, applied)
    except (OSError, ValueError, RuntimeError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, indent=2))
        return 2
    report["counts"] = {
        "canonical_total": len(canonical),
        "canonical_applied": len(report["canonical_applied"]),
        "canonical_pending": len(report["canonical_pending"]),
        "source_only_total": len(source_only),
        "source_only_applied": len(report["source_only_applied"]),
        "source_only_pending": len(report["source_only_pending"]),
    }
    has_drift = bool(report["applied_without_source"] or report["source_only_applied"])
    has_pending = bool(report["canonical_pending"])
    report["status"] = "drift" if has_drift else ("pending" if has_pending else "clean")
    print(json.dumps(report, indent=2))
    if has_drift or (args.require_clean and has_pending):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

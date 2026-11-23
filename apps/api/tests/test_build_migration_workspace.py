from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
from build_migration_workspace import build_workspace


def _source_tree(tmp_path: Path) -> tuple[Path, Path]:
    supabase_dir = tmp_path / "supabase"
    source_dir = supabase_dir / "migrations"
    source_dir.mkdir(parents=True)
    (supabase_dir / "config.toml").write_text(
        """project_id = "allpha-test"

[db.migrations]
schema_paths = []
""",
        encoding="utf-8",
    )
    return source_dir, supabase_dir / "config.toml"


def _migration(source_dir: Path, version: str, name: str) -> Path:
    path = source_dir / f"{version}_{name}.sql"
    path.write_text(f"-- {name}\nselect '{version}';\n", encoding="utf-8")
    return path


def test_workspace_contains_remote_history_and_only_the_requested_pending_target(tmp_path: Path) -> None:
    source_dir, _ = _source_tree(tmp_path)
    applied = _migration(source_dir, "20261101000000", "applied")
    target = _migration(source_dir, "20261102000000", "target")
    _migration(source_dir, "20261103000000", "local_pending_a")
    _migration(source_dir, "20261103000000", "local_pending_b")
    remote_versions = tmp_path / "remote-versions.txt"
    remote_versions.write_text("20261101000000\n", encoding="utf-8")

    workspace = tmp_path / "workspace"
    manifest = build_workspace(
        source_dir=source_dir,
        remote_versions_file=remote_versions,
        target_migration=target,
        workspace_dir=workspace,
    )

    copied = sorted(path.name for path in (workspace / "supabase" / "migrations").glob("*.sql"))
    assert copied == sorted([applied.name, target.name])
    config_text = (workspace / "supabase" / "config.toml").read_text(encoding="utf-8")
    assert 'schema_paths = ["./migrations/*.sql"]' in config_text
    assert manifest["remote_applied_version_count"] == 1
    assert manifest["pending_versions"] == ["20261102000000"]
    assert manifest["excluded_local_pending_versions"] == ["20261103000000"]
    stored = json.loads((workspace / "migration-workspace-manifest.json").read_text(encoding="utf-8"))
    assert stored["production_mutated"] is False


def test_workspace_fails_closed_when_a_remote_applied_source_is_missing(tmp_path: Path) -> None:
    source_dir, _ = _source_tree(tmp_path)
    target = _migration(source_dir, "20261102000000", "target")
    remote_versions = tmp_path / "remote-versions.txt"
    remote_versions.write_text("20261101000000\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Expected exactly one canonical source"):
        build_workspace(
            source_dir=source_dir,
            remote_versions_file=remote_versions,
            target_migration=target,
            workspace_dir=tmp_path / "workspace",
        )


def test_workspace_fails_closed_on_duplicate_remote_sources(tmp_path: Path) -> None:
    source_dir, _ = _source_tree(tmp_path)
    _migration(source_dir, "20261101000000", "applied_a")
    _migration(source_dir, "20261101000000", "applied_b")
    target = _migration(source_dir, "20261102000000", "target")
    remote_versions = tmp_path / "remote-versions.txt"
    remote_versions.write_text("20261101000000\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Expected exactly one canonical source"):
        build_workspace(
            source_dir=source_dir,
            remote_versions_file=remote_versions,
            target_migration=target,
            workspace_dir=tmp_path / "workspace",
        )


def test_workspace_does_not_mark_an_already_applied_target_as_pending(tmp_path: Path) -> None:
    source_dir, _ = _source_tree(tmp_path)
    applied = _migration(source_dir, "20261101000000", "applied")
    target = _migration(source_dir, "20261102000000", "target")
    remote_versions = tmp_path / "remote-versions.txt"
    remote_versions.write_text("20261101000000\n20261102000000\n", encoding="utf-8")

    manifest = build_workspace(
        source_dir=source_dir,
        remote_versions_file=remote_versions,
        target_migration=target,
        workspace_dir=tmp_path / "workspace",
    )

    assert manifest["pending_versions"] == []
    assert manifest["copied_file_count"] == 2

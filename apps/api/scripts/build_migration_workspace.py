from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path


VERSION_RE = re.compile(r"^(\d{14})_")


def _read_remote_versions(path: Path) -> list[str]:
    versions = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    invalid = [version for version in versions if not re.fullmatch(r"\d{14}", version)]
    if invalid:
        raise ValueError(f"Remote migration ledger contains invalid versions: {invalid}")
    if len(versions) != len(set(versions)):
        raise ValueError("Remote migration ledger contains duplicate versions")
    return sorted(versions)


def _files_by_version(source_dir: Path) -> dict[str, list[Path]]:
    result: dict[str, list[Path]] = {}
    for path in source_dir.glob("*.sql"):
        match = VERSION_RE.match(path.name)
        if match:
            result.setdefault(match.group(1), []).append(path)
    return result


def build_workspace(
    *,
    source_dir: Path,
    remote_versions_file: Path,
    target_migration: Path,
    workspace_dir: Path,
) -> dict[str, object]:
    source_dir = source_dir.resolve()
    remote_versions_file = remote_versions_file.resolve()
    target_migration = target_migration.resolve()
    workspace_dir = workspace_dir.resolve()

    if not source_dir.is_dir():
        raise ValueError(f"Migration source directory does not exist: {source_dir}")
    if not target_migration.is_file():
        raise ValueError(f"Target migration does not exist: {target_migration}")

    target_match = VERSION_RE.match(target_migration.name)
    if not target_match:
        raise ValueError(f"Target migration filename has no 14-digit version: {target_migration.name}")
    target_version = target_match.group(1)
    remote_versions = _read_remote_versions(remote_versions_file)
    by_version = _files_by_version(source_dir)

    selected: dict[str, Path] = {}
    for version in remote_versions:
        matches = by_version.get(version, [])
        if len(matches) != 1:
            raise ValueError(
                f"Expected exactly one canonical source for remote migration {version}; found "
                f"{[path.name for path in matches]}"
            )
        selected[version] = matches[0]

    target_matches = by_version.get(target_version, [])
    if target_version in remote_versions:
        if len(target_matches) != 1 or target_matches[0] != target_migration:
            raise ValueError(
                f"Applied target {target_version} must resolve to the exact target migration file"
            )
    else:
        if len(target_matches) != 1 or target_matches[0] != target_migration:
            raise ValueError(
                f"Pending target {target_version} must have exactly one canonical source file"
            )
        selected[target_version] = target_migration

    supabase_dir = workspace_dir / "supabase"
    migrations_dir = supabase_dir / "migrations"
    if workspace_dir.exists() and any(workspace_dir.iterdir()):
        raise ValueError(f"Migration workspace must be empty before construction: {workspace_dir}")
    migrations_dir.mkdir(parents=True, exist_ok=True)

    config_source = source_dir.parent / "config.toml"
    if not config_source.is_file():
        raise ValueError(f"Canonical Supabase config is missing: {config_source}")
    config_text = config_source.read_text(encoding="utf-8")
    config_text, replaced = re.subn(
        r"(?m)^schema_paths\\s*=\\s*\\[\\s*\\]\\s*$",
        'schema_paths = ["./migrations/*.sql"]',
        config_text,
    )
    if replaced != 1:
        raise ValueError(
            "Canonical Supabase config must contain exactly one disabled db.migrations.schema_paths setting"
        )
    (supabase_dir / "config.toml").write_text(config_text, encoding="utf-8")

    copied_files: list[str] = []
    for version in sorted(selected):
        source = selected[version]
        destination = migrations_dir / source.name
        shutil.copy2(source, destination)
        copied_files.append(source.name)

    local_versions = set(by_version)
    pending_local_versions = sorted(local_versions - set(remote_versions) - {target_version})
    pending_versions = [] if target_version in remote_versions else [target_version]

    manifest: dict[str, object] = {
        "workspace_kind": "remote-applied-history-plus-one-target",
        "remote_applied_version_count": len(remote_versions),
        "remote_applied_versions": remote_versions,
        "target_version": target_version,
        "pending_versions": pending_versions,
        "copied_file_count": len(copied_files),
        "copied_files": copied_files,
        "excluded_local_pending_versions": pending_local_versions,
        "schema_paths": ["./migrations/*.sql"],\n        "production_mutated": False,
    }
    (workspace_dir / "migration-workspace-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build an isolated Supabase migration workspace matching remote applied history plus one target."
    )
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--remote-versions-file", type=Path, required=True)
    parser.add_argument("--target-migration", type=Path, required=True)
    parser.add_argument("--workspace-dir", type=Path, required=True)
    args = parser.parse_args()
    manifest = build_workspace(
        source_dir=args.source_dir,
        remote_versions_file=args.remote_versions_file,
        target_migration=args.target_migration,
        workspace_dir=args.workspace_dir,
    )
    print(
        "Built isolated migration workspace: "
        f"{manifest['remote_applied_version_count']} applied versions + "
        f"{len(manifest['pending_versions'])} target pending."
    )


if __name__ == "__main__":
    main()

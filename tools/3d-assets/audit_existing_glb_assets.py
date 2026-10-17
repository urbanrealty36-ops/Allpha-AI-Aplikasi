#!/usr/bin/env python3
"""Read-only audit of already-present GLB files and manifests.

This tool performs no network requests and never downloads, moves, deletes, or
publishes assets. It validates GLB v2 structure, computes SHA-256/size, joins
optional existing JSON/CSV manifests, and flags missing license/category/asset
identity evidence for human review.

Examples:
  python tools/3d-assets/audit_existing_glb_assets.py --root .
  python tools/3d-assets/audit_existing_glb_assets.py --root . --output-dir artifacts/glb-audit
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import struct
from collections import defaultdict
from pathlib import Path
from typing import Any

GLB_MAGIC = b"glTF"
GLB_VERSION = 2
JSON_CHUNK = 0x4E4F534A
BIN_CHUNK = 0x004E4942
MANIFEST_SUFFIXES = {".json", ".csv"}
LICENSE_KEYS = ("license", "license_id", "license_url", "spdx_license", "license_name")
CATEGORY_KEYS = ("category", "asset_category", "theme_category")
IDENTITY_KEYS = ("asset_id", "asset_key", "id", "name", "title")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def inspect_glb(path: Path) -> dict[str, Any]:
    result: dict[str, Any] = {
        "glb_valid": False, "glb_error": None, "glb_version": None,
        "gltf_json_valid": False, "gltf_json_error": None,
        "buffer_count": 0, "buffer_views_count": 0, "meshopt_buffer_views": 0,
        "meshopt_source_buffer_indices": [], "buffers_missing_uri_nonzero": [],
        "base_buffer_indices_out_of_range": [], "skin_count": 0, "animation_count": 0,
        "mesh_count": 0, "material_count": 0, "texture_count": 0, "image_count": 0,
        "external_image_uri_count": 0, "extensions_used": [],
        "compatibility_findings": [],
    }
    try:
        size = path.stat().st_size
        with path.open("rb") as stream:
            header = stream.read(12)
            if len(header) != 12:
                raise ValueError("truncated GLB header")
            magic, version, declared_length = struct.unpack("<4sII", header)
            result["glb_version"] = version
            if magic != GLB_MAGIC:
                raise ValueError("invalid GLB magic")
            if version != GLB_VERSION:
                raise ValueError(f"unsupported GLB version {version}")
            if declared_length != size:
                raise ValueError(f"header length {declared_length} != file size {size}")
            offset = 12
            chunk_index = 0
            document: dict[str, Any] | None = None
            bin_chunk_count = 0
            while offset < size:
                chunk_header = stream.read(8)
                if len(chunk_header) != 8:
                    raise ValueError("truncated chunk header")
                chunk_length, chunk_type = struct.unpack("<II", chunk_header)
                offset += 8
                if chunk_length % 4:
                    raise ValueError(f"chunk {chunk_index} length is not 4-byte aligned")
                if offset + chunk_length > size:
                    raise ValueError(f"chunk {chunk_index} exceeds declared file length")
                payload = stream.read(chunk_length)
                if len(payload) != chunk_length:
                    raise ValueError(f"truncated chunk payload {chunk_index}")
                if chunk_index == 0 and chunk_type != JSON_CHUNK:
                    raise ValueError("first chunk is not JSON")
                if chunk_type == JSON_CHUNK:
                    if document is not None:
                        raise ValueError("duplicate JSON chunk")
                    try:
                        parsed = json.loads(payload.decode("utf-8").rstrip(" \\t\\r\\n\\x00"))
                        if not isinstance(parsed, dict):
                            raise ValueError("JSON root must be an object")
                        document = parsed
                    except (UnicodeError, json.JSONDecodeError, ValueError) as exc:
                        result["gltf_json_error"] = str(exc)
                elif chunk_type == BIN_CHUNK:
                    bin_chunk_count += 1
                offset += chunk_length
                chunk_index += 1
            if offset != size:
                raise ValueError("chunk boundaries do not match file length")
            if document is None:
                raise ValueError(result["gltf_json_error"] or "missing or invalid JSON chunk")
            result["glb_valid"] = True
            result["gltf_json_valid"] = True
            result["buffer_count"] = len(document.get("buffers", []))
            views = document.get("bufferViews", [])
            result["buffer_views_count"] = len(views)
            result["mesh_count"] = len(document.get("meshes", []))
            result["material_count"] = len(document.get("materials", []))
            result["texture_count"] = len(document.get("textures", []))
            result["image_count"] = len(document.get("images", []))
            result["skin_count"] = len(document.get("skins", []))
            result["animation_count"] = len(document.get("animations", []))
            result["extensions_used"] = sorted(set(document.get("extensionsUsed", [])) | set(document.get("extensionsRequired", [])))
            buffers = document.get("buffers", [])
            result["buffers_missing_uri_nonzero"] = [
                index for index, buffer in enumerate(buffers)
                if index > 0 and isinstance(buffer, dict) and not buffer.get("uri")
            ]
            meshopt_sources = sorted({
                extension.get("buffer")
                for view in views if isinstance(view, dict)
                for extension in [view.get("extensions", {}).get("EXT_meshopt_compression", {})]
                if isinstance(extension, dict) and isinstance(extension.get("buffer"), int)
            })
            result["meshopt_source_buffer_indices"] = meshopt_sources
            result["meshopt_buffer_views"] = sum(
                1 for view in views if isinstance(view, dict)
                and isinstance(view.get("extensions"), dict)
                and isinstance(view["extensions"].get("EXT_meshopt_compression"), dict)
            )
            result["base_buffer_indices_out_of_range"] = sorted({
                view.get("buffer", 0) for view in views if isinstance(view, dict)
                and isinstance(view.get("buffer", 0), int)
                and not 0 <= view.get("buffer", 0) < len(buffers)
            })
            result["external_image_uri_count"] = sum(
                1 for image in document.get("images", []) if isinstance(image, dict)
                and isinstance(image.get("uri"), str) and not image["uri"].startswith("data:")
            )
            if result["buffers_missing_uri_nonzero"]:
                result["compatibility_findings"].append("nonzero_buffer_missing_uri")
            if result["base_buffer_indices_out_of_range"]:
                result["compatibility_findings"].append("bufferView_base_buffer_index_out_of_range")
            if bin_chunk_count > 1:
                result["compatibility_findings"].append("multiple_BIN_chunks")
            if result["meshopt_buffer_views"] and any(
                index >= len(buffers) for index in result["meshopt_source_buffer_indices"]
            ):
                result["compatibility_findings"].append("meshopt_source_buffer_index_out_of_range")
    except (OSError, ValueError, struct.error) as exc:
        result["glb_error"] = str(exc)
    return result


def read_manifest(path: Path) -> list[dict[str, Any]]:
    try:
        if path.suffix.lower() == ".csv":
            with path.open("r", encoding="utf-8-sig", newline="") as stream:
                return [dict(row) for row in csv.DictReader(stream)]
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return [row for row in data if isinstance(row, dict)]
        if isinstance(data, dict):
            for key in ("assets", "items", "results", "files", "manifest"):
                if isinstance(data.get(key), list):
                    return [row for row in data[key] if isinstance(row, dict)]
            return [data]
    except (OSError, UnicodeError, json.JSONDecodeError, csv.Error):
        return []
    return []


def first_value(row: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = row.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="repository or asset root to scan")
    parser.add_argument("--output-dir", type=Path, default=None, help="optional output directory; default prints JSON")
    parser.add_argument("--manifest", action="append", type=Path, default=[], help="existing JSON/CSV manifest (repeatable)")
    args = parser.parse_args()
    root = args.root.resolve()
    if not root.is_dir():
        parser.error(f"root is not a directory: {root}")

    manifest_paths = [p.resolve() for p in args.manifest if p.exists() and p.suffix.lower() in MANIFEST_SUFFIXES]
    if not manifest_paths:
        for base in (root / "assets", root / "public", root / "tools" / "3d-assets", root / "apps"):
            if base.exists():
                manifest_paths.extend(p for p in base.rglob("*") if p.is_file() and p.suffix.lower() in MANIFEST_SUFFIXES and any(word in p.name.lower() for word in ("manifest", "asset", "catalog", "theme")))
    manifest_rows: list[tuple[Path, dict[str, Any]]] = []
    for manifest in sorted(set(manifest_paths)):
        for row in read_manifest(manifest):
            manifest_rows.append((manifest, row))

    by_filename: dict[str, list[tuple[Path, dict[str, Any]]]] = defaultdict(list)
    by_hash: dict[str, list[tuple[Path, dict[str, Any]]]] = defaultdict(list)
    for manifest, row in manifest_rows:
        file_ref = first_value(row, ("path", "file", "filename", "local_path", "storage_path", "uri", "url"))
        if file_ref:
            by_filename[Path(file_ref.split("?", 1)[0]).name.lower()].append((manifest, row))
        digest = first_value(row, ("sha256", "checksum_sha256", "content_sha256", "hash"))
        if digest:
            by_hash[digest.lower()].append((manifest, row))

    assets = []
    duplicate_hashes: dict[str, list[str]] = defaultdict(list)
    for path in sorted(root.rglob("*.glb")):
        if any(part in {".git", "node_modules", ".venv", "venv"} for part in path.parts):
            continue
        try:
            digest = sha256_file(path)
            size = path.stat().st_size
            details = inspect_glb(path)
        except OSError as exc:
            digest, size, details = None, None, {"glb_valid": False, "glb_error": str(exc), "glb_version": None}
        matched = by_filename.get(path.name.lower(), [])
        if digest and not matched:
            matched = by_hash.get(digest.lower(), [])
        row = matched[0][1] if matched else {}
        license_value = first_value(row, LICENSE_KEYS)
        category_value = first_value(row, CATEGORY_KEYS)
        identity_value = first_value(row, IDENTITY_KEYS)
        record = {
            "path": path.relative_to(root).as_posix(),
            "size_bytes": size,
            "sha256": digest,
            **details,
            "manifest_matches": [{"manifest": str(m.relative_to(root) if m.is_relative_to(root) else m), "identity": first_value(r, IDENTITY_KEYS)} for m, r in matched],
            "asset_identity": identity_value,
            "category": category_value,
            "license_evidence": license_value,
            "license_status": "evidence_present_review_required" if license_value else "missing_quarantine",
            "category_status": "mapped_candidate" if category_value else "unmapped_review_required",
            "duplicate_sha256": False,
        }
        assets.append(record)
        if digest:
            duplicate_hashes[digest].append(record["path"])

    for record in assets:
        if record["sha256"] and len(duplicate_hashes[record["sha256"]]) > 1:
            record["duplicate_sha256"] = True

    report = {
        "audit_mode": "read_only_no_network_no_mutations",
        "root": str(root),
        "manifest_files_examined": [str(p.relative_to(root) if p.is_relative_to(root) else p) for p in sorted(set(manifest_paths))],
        "summary": {
            "glb_count": len(assets),
            "valid_glb_count": sum(bool(a["glb_valid"]) for a in assets),
            "invalid_glb_count": sum(not a["glb_valid"] for a in assets),
            "invalid_gltf_json_count": sum(not a["gltf_json_valid"] for a in assets),
            "meshopt_asset_count": sum(a["meshopt_buffer_views"] > 0 for a in assets),
            "assets_with_skins": sum(a["skin_count"] > 0 for a in assets),
            "assets_with_animation_clips": sum(a["animation_count"] > 0 for a in assets),
            "assets_with_nonzero_buffer_missing_uri": sum(bool(a["buffers_missing_uri_nonzero"]) for a in assets),
            "assets_with_compatibility_findings": sum(bool(a["compatibility_findings"]) for a in assets),
            "missing_license_evidence_count": sum(a["license_status"] == "missing_quarantine" for a in assets),
            "unmapped_category_count": sum(a["category_status"] != "mapped_candidate" for a in assets),
            "duplicate_hash_groups": sum(1 for paths in duplicate_hashes.values() if len(paths) > 1),
            "duplicate_asset_paths": sum(1 for a in assets if a["duplicate_sha256"]),
        },
        "assets": assets,
        "notes": [
            "License metadata presence is not legal approval; review source, license terms, attribution, textures, and likeness rights.",
            "A valid GLB container and parseable JSON are not proof that the renderer can load or display the asset.",
            "Compatibility findings are diagnostic holds, not automatic permission to repair, approve, register, or publish an asset.",
            "No asset is registered, promoted, uploaded, or published by this script.",
            "Manifest matches use filename/path or exact SHA-256 only; ambiguous evidence remains for human review.",
        ],
    }
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output_dir:
        args.output_dir.mkdir(parents=True, exist_ok=True)
        (args.output_dir / "glb-audit-report.json").write_text(rendered, encoding="utf-8")
        with (args.output_dir / "glb-audit-report.csv").open("w", encoding="utf-8", newline="") as stream:
            fields = ["path", "size_bytes", "sha256", "glb_valid", "glb_version", "glb_error", "gltf_json_valid", "gltf_json_error", "buffer_count", "buffer_views_count", "meshopt_buffer_views", "meshopt_source_buffer_indices", "buffers_missing_uri_nonzero", "base_buffer_indices_out_of_range", "mesh_count", "material_count", "texture_count", "image_count", "skin_count", "animation_count", "external_image_uri_count", "compatibility_findings", "asset_identity", "category", "category_status", "license_evidence", "license_status", "duplicate_sha256"]
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            for asset in assets:
                writer.writerow({key: asset.get(key) for key in fields})
    else:
        print(rendered, end="")
    return 0 if all(a["glb_valid"] for a in assets) else 1


if __name__ == "__main__":
    raise SystemExit(main())

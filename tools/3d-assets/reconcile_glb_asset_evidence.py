#!/usr/bin/env python3
"""Evidence-only reconciliation of acquired GLBs. Never approves or publishes assets."""
from __future__ import annotations
import argparse, base64, csv, hashlib, json, struct
from collections import Counter
from pathlib import Path
from typing import Any

def read_manifest(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))

def parse_glb(path: Path) -> tuple[dict[str, Any], bytes, dict[str, Any]]:
    raw = path.read_bytes()
    if len(raw) < 20:
        raise ValueError("glb_too_small")
    magic, version, declared = struct.unpack_from("<4sII", raw, 0)
    if magic != b"glTF" or version != 2 or declared != len(raw):
        raise ValueError("invalid_glb_header_or_length")
    offset, document, bin_chunks, chunk_count = 12, None, [], 0
    while offset < len(raw):
        if offset + 8 > len(raw):
            raise ValueError("truncated_chunk_header")
        length, kind = struct.unpack_from("<I4s", raw, offset)
        start, end = offset + 8, offset + 8 + length
        if length % 4 or end > len(raw):
            raise ValueError("invalid_chunk_bounds")
        payload = raw[start:end]
        chunk_count += 1
        if kind == b"JSON":
            if document is not None:
                raise ValueError("multiple_json_chunks")
            document = json.loads(payload.decode("utf-8").rstrip(" \t\r\n\x00"))
        elif kind == b"BIN\x00":
            bin_chunks.append(payload)
        offset = end
    if offset != len(raw) or not isinstance(document, dict):
        raise ValueError("incomplete_chunk_layout_or_json")
    if len(bin_chunks) > 1:
        raise ValueError("multiple_bin_chunks")
    return document, (bin_chunks[0] if bin_chunks else b""), {
        "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
        "glb_version": version, "chunk_count": chunk_count, "json_valid": True,
    }

def fallback_findings(doc: dict[str, Any]) -> list[str]:
    buffers = doc.get("buffers", [])
    views = doc.get("bufferViews", [])
    required = set(doc.get("extensionsRequired", []))
    findings: list[str] = []
    for index, buffer in enumerate(buffers):
        if index == 0 or not isinstance(buffer, dict) or buffer.get("uri"):
            continue
        refs = [(i, view) for i, view in enumerate(views)
                if isinstance(view, dict) and view.get("buffer", 0) == index]
        compressed_source_refs = [i for i, view in enumerate(views)
            if isinstance(view, dict)
            and isinstance(view.get("extensions", {}).get("EXT_meshopt_compression"), dict)
            and view["extensions"]["EXT_meshopt_compression"].get("buffer") == index]
        reasons = []
        if buffer.get("extensions", {}).get("EXT_meshopt_compression", {}).get("fallback") is not True:
            reasons.append("fallback_flag_missing")
        if "EXT_meshopt_compression" not in required:
            reasons.append("meshopt_extension_not_required")
        if not refs:
            reasons.append("fallback_buffer_unreferenced")
        if any(not isinstance(view.get("extensions", {}).get("EXT_meshopt_compression"), dict) for _, view in refs):
            reasons.append("fallback_view_without_meshopt_extension")
        if compressed_source_refs:
            reasons.append("fallback_used_as_compressed_source")
        ends = []
        for _, view in refs:
            off, length = view.get("byteOffset", 0), view.get("byteLength")
            if not isinstance(off, int) or not isinstance(length, int) or off < 0 or length < 0:
                reasons.append("invalid_fallback_view_range")
            else:
                ends.append(off + length)
        if not isinstance(buffer.get("byteLength"), int) or buffer.get("byteLength", -1) < max(ends, default=0):
            reasons.append("fallback_byte_length_too_short")
        findings.extend(f"buffer_{index}:{reason}" for reason in sorted(set(reasons)))
    return findings

def inspect_json(doc: dict[str, Any], binary: bytes) -> dict[str, Any]:
    images = doc.get("images", [])
    textures = doc.get("textures", [])
    materials = doc.get("materials", [])
    buffer_views = doc.get("bufferViews", [])
    meshopt_views = [v for v in buffer_views if isinstance(v, dict) and isinstance(v.get("extensions", {}).get("EXT_meshopt_compression"), dict)]
    image_kinds = Counter()
    mime_types = Counter()
    external_uris = []
    image_payload_evidence = []
    views = doc.get("bufferViews", [])
    buffers = doc.get("buffers", [])
    for image_index, image in enumerate(images):
        if not isinstance(image, dict):
            image_kinds["invalid"] += 1
            image_payload_evidence.append({"image_index": image_index, "status": "invalid_image_record"})
            continue
        uri = image.get("uri")
        payload = None
        evidence = {"image_index": image_index, "mime_type": image.get("mimeType") or "unspecified"}
        if uri is None and isinstance(image.get("bufferView"), int):
            image_kinds["bufferView_embedded"] += 1
            view_index = image["bufferView"]
            if 0 <= view_index < len(views):
                view = views[view_index]
                buffer_index = view.get("buffer", 0)
                start, length = int(view.get("byteOffset", 0)), int(view.get("byteLength", 0))
                if buffer_index == 0 and start >= 0 and length > 0 and start + length <= len(binary):
                    payload = binary[start:start + length]
                    evidence.update({"source": "glb_bin_bufferView", "buffer_view_index": view_index, "byte_length": length})
                else:
                    evidence.update({"source": "bufferView", "buffer_index": buffer_index, "status": "payload_not_resolved_from_glb_bin"})
            else:
                evidence.update({"source": "bufferView", "status": "bufferView_index_out_of_range"})
        elif uri is None:
            image_kinds["missing_source"] += 1
            evidence.update({"source": "missing", "status": "missing_image_source"})
        elif isinstance(uri, str) and uri.startswith("data:"):
            image_kinds["data_uri_embedded"] += 1
            try:
                header, data = uri.split(",", 1)
                payload = base64.b64decode(data) if ";base64" in header.lower() else __import__("urllib.parse", fromlist=["unquote_to_bytes"]).unquote_to_bytes(data)
                evidence.update({"source": "data_uri", "byte_length": len(payload)})
            except Exception as exc:
                evidence.update({"source": "data_uri", "status": "data_uri_decode_error:" + str(exc)})
        elif isinstance(uri, str):
            image_kinds["external_uri"] += 1
            external_uris.append(uri)
            evidence.update({"source": "external_uri", "uri": uri, "status": "external_payload_not_downloaded"})
        else:
            image_kinds["invalid"] += 1
            evidence.update({"source": "invalid", "status": "invalid_image_uri"})
        if payload is not None:
            evidence["payload_sha256"] = hashlib.sha256(payload).hexdigest()
            evidence["status"] = "embedded_payload_hashed"
        image_payload_evidence.append(evidence)
        mime_types[str(image.get("mimeType") or "unspecified")] += 1
    texture_extension_sources = Counter()
    for texture in textures:
        if not isinstance(texture, dict):
            continue
        if isinstance(texture.get("source"), int):
            texture_extension_sources["core_source"] += 1
        extensions = texture.get("extensions", {})
        if isinstance(extensions, dict):
            for ext_name, value in extensions.items():
                if isinstance(value, dict) and isinstance(value.get("source"), int):
                    texture_extension_sources[ext_name] += 1
    primitive_count = sum(len(m.get("primitives", [])) for m in doc.get("meshes", []) if isinstance(m, dict))
    skinned_mesh_hint = any(isinstance(m, dict) and any("JOINTS_0" in p.get("attributes", {}) and "WEIGHTS_0" in p.get("attributes", {}) for p in m.get("primitives", []) if isinstance(p, dict)) for m in doc.get("meshes", []))
    return {
        "extension_used": ";".join(doc.get("extensionsUsed", [])),
        "extension_required": ";".join(doc.get("extensionsRequired", [])),
        "buffer_count": len(doc.get("buffers", [])),
        "buffer_view_count": len(buffer_views),
        "meshopt_buffer_view_count": len(meshopt_views),
        "mesh_count": len(doc.get("meshes", [])),
        "primitive_count": primitive_count,
        "material_count": len(materials),
        "texture_count": len(textures),
        "image_count": len(images),
        "image_source_kinds": json.dumps(dict(sorted(image_kinds.items())), sort_keys=True),
        "image_mime_types": json.dumps(dict(sorted(mime_types.items())), sort_keys=True),
        "external_image_uri_count": len(external_uris),
        "external_image_uris": json.dumps(external_uris, ensure_ascii=False),
        "image_payload_evidence": json.dumps(image_payload_evidence, ensure_ascii=False),
        "embedded_image_payload_count": sum(1 for item in image_payload_evidence if item.get("payload_sha256")),
        "unresolved_image_payload_count": sum(1 for item in image_payload_evidence if not item.get("payload_sha256")),
        "texture_extension_sources": json.dumps(dict(sorted(texture_extension_sources.items())), sort_keys=True),
        "skin_count": len(doc.get("skins", [])),
        "animation_clip_count": len(doc.get("animations", [])),
        "skinning_attributes_hint": skinned_mesh_hint,
        "meshopt_fallback_findings": ";".join(fallback_findings(doc)),
    }

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".artifacts/acquired", help="Directory containing shard-* and reconciliation/")
    ap.add_argument("--out-dir", default=".artifacts/acquired/evidence-reconciliation")
    args = ap.parse_args()
    root, out = Path(args.root).resolve(), Path(args.out_dir).resolve()
    manifest = root / "reconciliation" / "manifest.csv"
    if not manifest.is_file():
        raise SystemExit(f"missing reconciliation manifest: {manifest}")
    rows = read_manifest(manifest)
    results = []
    seen_paths = set()
    for row in rows:
        # Normalize acquisition manifest provenance into explicit, stable audit fields.
        # The source manifest calls the canonical download URL "url"; preserve it as
        # source_url instead of leaving the downstream evidence field blank.
        result: dict[str, Any] = {
            **row,
            "source_repository": row.get("repo", ""),
            "source_path": row.get("path", ""),
            "source_url": row.get("source_url") or row.get("url", ""),
            "source_license_claim": row.get("license", ""),
            "source_review_status": row.get("review", ""),
            # Record where the repository-level license/texture exception evidence
            # can be inspected. These links are evidence pointers, not per-file legal
            # clearance; unknown derivative/likeness/texture rights stay on hold.
            "source_license_evidence_url": {
                "rostock/3DModels": "https://github.com/rostock/3DModels/blob/main/LICENSE",
                "c-frame/valid-avatars-glb": "https://github.com/c-frame/valid-avatars-glb/blob/main/LICENSE",
                "ramjigeddam/3d": "https://github.com/ramjigeddam/3d",
                "SpectraStudios/SourceCityToolkit_glb": "https://github.com/SpectraStudios/SourceCityToolkit_glb/blob/main/LICENSE",
            }.get(row.get("repo", ""), ""),
            "source_texture_rights_evidence_url": {
                "rostock/3DModels": "https://github.com/rostock/3DModels/blob/main/README.md",
                "c-frame/valid-avatars-glb": "https://github.com/c-frame/valid-avatars-glb/blob/main/README.md",
                "ramjigeddam/3d": "https://github.com/ramjigeddam/3d",
                "SpectraStudios/SourceCityToolkit_glb": "https://github.com/SpectraStudios/SourceCityToolkit_glb/blob/main/README.md",
            }.get(row.get("repo", ""), ""),
            "upstream_source_evidence_url": {
                "c-frame/valid-avatars-glb": "https://github.com/xrtlab/Validated-Avatar-Library-for-Inclusion-and-Diversity---VALID",
            }.get(row.get("repo", ""), ""),
            "upstream_license_evidence_url": {
                "c-frame/valid-avatars-glb": "https://github.com/xrtlab/Validated-Avatar-Library-for-Inclusion-and-Diversity---VALID/blob/main/LICENSE",
            }.get(row.get("repo", ""), ""),
            "upstream_source_scope_assessment": {
                "c-frame/valid-avatars-glb": "UPSTREAM_VALID_AVATAR_LIBRARY_IDENTIFIED; MIT_LICENSE_PRESENT_UPSTREAM_AND_IN_CONVERSION_REPOSITORY; PER_ASSET_DISTRIBUTION_DERIVATIVE_AND_LIKENESS_REVIEW_STILL_REQUIRED",
            }.get(row.get("repo", ""), "NO_UPSTREAM_SOURCE_LINK_RECORDED"),
            "license_scope_assessment": {
                "rostock/3DModels": "REPOSITORY_LEVEL_CC0_CLAIM_ONLY_PER_FILE_CONTENT_AND_THIRD_PARTY_RIGHTS_REVIEW_REQUIRED",
                "c-frame/valid-avatars-glb": "REPOSITORY_MIT_CLAIM_ONLY_LIKENESS_AND_DERIVATIVE_RIGHTS_UNVERIFIED",
                "ramjigeddam/3d": "NO_REPOSITORY_LICENSE_OR_PERMISSION_EVIDENCE_FOUND",
                "SpectraStudios/SourceCityToolkit_glb": "CC0_CLAIM_WITH_README_TEXTURE_EXCEPTIONS_PER_IMAGE_PROVENANCE_REQUIRED",
            }.get(row.get("repo", ""), "LICENSE_SCOPE_UNKNOWN"),
            "distribution_derivative_rights_status": {
                "rostock/3DModels": "UNVERIFIED_PER_FILE_AND_THIRD_PARTY_CONTENT",
                "c-frame/valid-avatars-glb": "UNVERIFIED_LIKENESS_ATTRIBUTION_AND_DERIVATIVE_SCOPE",
                "ramjigeddam/3d": "NO_VERIFIED_DISTRIBUTION_OR_DERIVATIVE_PERMISSION",
                "SpectraStudios/SourceCityToolkit_glb": "UNVERIFIED_TEXTURE_EXCEPTIONS_AND_DERIVATIVE_SCOPE",
            }.get(row.get("repo", ""), "UNVERIFIED"),
            "rights_review_status": (
                "QUARANTINE_REQUIRED" if str(row.get("review", "")).upper().startswith("QUARANTINE")
                else "PER_FILE_RIGHTS_REVIEW_REQUIRED"
            ),
            "category_review_status": (
                "VERIFIED" if row.get("category_mapping_status") == "verified"
                else "UNMAPPED_REQUIRES_REVIEW" if row.get("category_mapping_status") == "unmapped"
                else "HEURISTIC_CANDIDATE_REQUIRES_REVIEW"
            ),
            "texture_rights_review_status": "PENDING_EMBEDDED_TEXTURE_PROVENANCE",
            "visual_review_status": "PENDING_HUMAN_VISUAL_REVIEW",
            "renderer_device_review_status": "PENDING_RENDERER_AND_DEVICE_ACCEPTANCE",
        }
        result.update({"actual_bytes": "", "actual_sha256": "", "container_status": "not_checked",
                       "fallback_status": "not_checked", "rights_disposition": "HOLD",
                       "publication_status": "NOT_APPROVED"})
        local_file = row.get("local_file", "").strip()
        if row.get("status") != "DOWNLOADED" or not local_file:
            result["container_status"] = "not_downloaded_or_deduplicated"
            result["hold_reasons"] = "source_row_not_physical_download"
            results.append(result)
            continue
        matches = sorted(root.glob(f"shard-*/{local_file}"))
        if len(matches) != 1:
            result["container_status"] = "missing_or_ambiguous_file"
            result["hold_reasons"] = f"physical_path_match_count_{len(matches)}"
            results.append(result)
            continue
        path = matches[0]
        try:
            doc, binary, meta = parse_glb(path)
            result["actual_bytes"] = meta["bytes"]
            result["actual_sha256"] = meta["sha256"]
            result["glb_version"] = meta["glb_version"]
            result["chunk_count"] = meta["chunk_count"]
            result["json_valid"] = meta["json_valid"]
            result.update(inspect_json(doc, binary))
            expected_hash = row.get("sha256", "").lower()
            expected_size = row.get("bytes", "")
            integrity = []
            if expected_hash and meta["sha256"].lower() != expected_hash:
                integrity.append("sha256_mismatch")
            if expected_size and expected_size.isdigit() and meta["bytes"] != int(expected_size):
                integrity.append("byte_size_mismatch")
            result["container_status"] = "valid" if not integrity else "integrity_mismatch"
            fallback = result["meshopt_fallback_findings"]
            fallback_candidate = any(i > 0 and isinstance(buffer, dict) and not buffer.get("uri")
                for i, buffer in enumerate(doc.get("buffers", [])))
            result["fallback_status"] = ("invalid" if fallback else "valid") if fallback_candidate else "not_applicable"
            reasons = list(integrity)
            if row.get("review", "").upper().startswith("QUARANTINE"):
                reasons.append("source_manifest_quarantine")
            else:
                reasons.append("per_file_rights_review_pending")
            if row.get("category_mapping_status") != "verified":
                reasons.append("canonical_category_mapping_pending")
            if int(result.get("image_count", 0)) > 0:
                reasons.append("image_texture_provenance_visual_review_pending")
            if int(result.get("unresolved_image_payload_count", 0)) > 0:
                reasons.append("embedded_image_payload_hash_unresolved")
            if int(result.get("external_image_uri_count", 0)) > 0:
                reasons.append("external_image_uri_resolution_and_rights_pending")
            if row.get("category") in {"agent-character", "human-live", "animation"} and int(result.get("animation_clip_count", 0)) == 0:
                reasons.append("animation_capability_not_proven")
            if fallback:
                reasons.append("meshopt_fallback_contract_invalid")
            reasons.append("renderer_and_device_acceptance_pending")
            result["hold_reasons"] = ";".join(dict.fromkeys(reasons))
        except Exception as exc:
            result["container_status"] = "invalid"
            result["hold_reasons"] = "glb_parse_or_integrity_error:" + str(exc)
        results.append(result)
        seen_paths.add(local_file)
    # Assign an explicit, fail-closed per-row disposition. This is a review
    # disposition only: it does not approve, register, upload, or publish assets.
    disposition_counts: Counter[str] = Counter()
    for result in results:
        physical = result.get("status") == "DOWNLOADED" and bool(result.get("local_file"))
        if not physical:
            disposition = "NON_PHYSICAL_OR_DEDUPLICATED_REFERENCE"
            queue = "SOURCE_MANIFEST_RECONCILIATION"
            reason = "manifest row does not represent a unique physical download"
        elif result.get("container_status") in {"invalid", "integrity_mismatch", "missing_or_ambiguous_file"}:
            disposition = "QUARANTINE_TECHNICAL_FAILURE"
            queue = "TECHNICAL_REPAIR_AND_REAUDIT"
            reason = result.get("hold_reasons") or result.get("container_status")
        elif str(result.get("review", "")).upper().startswith("QUARANTINE"):
            disposition = "QUARANTINE_SOURCE_RIGHTS_OR_SAFETY_REVIEW"
            queue = "PROVENANCE_LICENSE_LIKENESS_AND_MODERATION"
            reason = result.get("hold_reasons") or "source manifest marks the asset quarantined"
        elif result.get("category_mapping_status") != "verified":
            disposition = "HOLD_UNMAPPED_RIGHTS_AND_RENDERER_REVIEW"
            queue = "CATEGORY_PROVENANCE_TEXTURE_VISUAL_AND_RENDERER_REVIEW"
            reason = result.get("hold_reasons") or "canonical category mapping is not verified"
        else:
            disposition = "HOLD_RIGHTS_TEXTURE_AND_RENDERER_REVIEW"
            queue = "PER_FILE_RIGHTS_TEXTURE_VISUAL_AND_DEVICE_REVIEW"
            reason = result.get("hold_reasons") or "all required release gates are not evidenced"
        result["asset_disposition"] = disposition
        result["disposition_queue"] = queue
        result["disposition_reason"] = reason
        result["disposition_finality"] = "PROVISIONAL_FAIL_CLOSED_PENDING_REQUIRED_EVIDENCE"
        result["publication_status"] = "NOT_APPROVED"
        disposition_counts[disposition] += 1

    out.mkdir(parents=True, exist_ok=True)
    fields = list(dict.fromkeys(key for row in results for key in row.keys()))
    with (out / "manifest-audit.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(results)
    (out / "manifest-audit.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = {
        "manifest_rows": len(rows),
        "physical_download_rows": sum(1 for r in rows if r.get("status") == "DOWNLOADED" and r.get("local_file")),
        "unique_local_paths_checked": len(seen_paths),
        "valid_containers": sum(1 for r in results if r.get("container_status") == "valid"),
        "integrity_mismatches": sum(1 for r in results if r.get("container_status") == "integrity_mismatch"),
        "invalid_containers": sum(1 for r in results if r.get("container_status") == "invalid"),
        "missing_or_ambiguous_files": sum(1 for r in results if r.get("container_status") == "missing_or_ambiguous_file"),
        "meshopt_fallback_valid": sum(1 for r in results if r.get("fallback_status") == "valid"),
        "meshopt_fallback_invalid": sum(1 for r in results if r.get("fallback_status") == "invalid"),
        "meshopt_fallback_not_applicable": sum(1 for r in results if r.get("fallback_status") == "not_applicable"),
        "assets_with_images": sum(1 for r in results if int(r.get("image_count") or 0) > 0),
        "assets_with_external_image_uris": sum(1 for r in results if int(r.get("external_image_uri_count") or 0) > 0),
        "embedded_image_payloads_hashed": sum(int(r.get("embedded_image_payload_count") or 0) for r in results),
        "unresolved_image_payloads": sum(int(r.get("unresolved_image_payload_count") or 0) for r in results),
        "unique_embedded_image_sha256": len({item.get("payload_sha256") for r in results for item in json.loads(r.get("image_payload_evidence") or "[]") if item.get("payload_sha256")}),
        "assets_with_unresolved_image_payloads": sum(1 for r in results if int(r.get("unresolved_image_payload_count") or 0) > 0),
        "assets_with_skins": sum(1 for r in results if int(r.get("skin_count") or 0) > 0),
        "assets_with_animation_clips": sum(1 for r in results if int(r.get("animation_clip_count") or 0) > 0),
        "all_publication_statuses": sorted(set(r.get("publication_status", "") for r in results)),
        "per_file_disposition_counts": dict(sorted(disposition_counts.items())),
        "rows_with_explicit_disposition": sum(1 for r in results if r.get("asset_disposition")),
        "disposition_is_provisional": True,
        "approved_assets": 0,
        "policy": "Every manifest row receives a fail-closed disposition and review queue. This is not human/legal clearance and never approves, registers, uploads, or publishes assets.",
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    if summary["invalid_containers"] or summary["integrity_mismatches"] or summary["missing_or_ambiguous_files"]:
        return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

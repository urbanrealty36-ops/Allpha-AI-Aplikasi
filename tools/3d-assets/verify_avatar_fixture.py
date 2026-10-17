#!/usr/bin/env python3
"""Acquire one MIT-licensed rigged character from a per-model catalog and validate GLB structure."""
import argparse, hashlib, json, os, struct, sys
from pathlib import Path
from urllib.parse import urljoin
import requests

def walk(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)

def license_text(record):
    values = []
    for key in ("license", "license_name", "license_spdx", "spdx", "license_id"):
        value = record.get(key)
        if isinstance(value, dict):
            value = " ".join(str(value.get(k, "")) for k in ("name", "spdx", "id", "type"))
        if value:
            values.append(str(value))
    return " ".join(values).strip()

def find_glb_url(record, catalog_url):
    for key in ("glb", "glb_url", "model_url", "download_url", "url", "model", "path"):
        value = record.get(key)
        if isinstance(value, str) and value.lower().split("?")[0].endswith(".glb"):
            return urljoin(catalog_url, value)
    return None

def validate_glb(path):
    raw = path.read_bytes()
    if len(raw) < 20:
        raise ValueError("GLB too small")
    magic, version, declared = struct.unpack_from("<4sII", raw, 0)
    if magic != b"glTF" or version != 2 or declared != len(raw):
        raise ValueError(f"invalid GLB header: magic={magic!r} version={version} declared={declared} actual={len(raw)}")
    offset, chunks, document, bin_chunks = 12, [], None, []
    while offset < len(raw):
        if offset + 8 > len(raw):
            raise ValueError("truncated chunk header")
        length, kind = struct.unpack_from("<I4s", raw, offset)
        start, end = offset + 8, offset + 8 + length
        if length % 4 or end > len(raw):
            raise ValueError(f"invalid chunk bounds at {offset}: length={length}")
        payload = raw[start:end]
        chunks.append({"type": kind.decode("ascii", "replace"), "header_offset": offset, "data_offset": start, "byte_length": length, "end_offset": end})
        if kind == b"JSON":
            if document is not None:
                raise ValueError("multiple JSON chunks")
            document = json.loads(payload.decode("utf-8").rstrip(" \t\r\n\x00"))
        elif kind == b"BIN ":
            bin_chunks.append({"start": start, "length": length, "data": payload})
        offset = end
    if offset != len(raw) or document is None:
        raise ValueError("chunk layout incomplete")
    ext_used = document.get("extensionsUsed", [])
    ext_required = document.get("extensionsRequired", [])
    if "EXT_meshopt_compression" not in ext_used and "EXT_meshopt_compression" not in ext_required:
        raise ValueError("fixture does not declare EXT_meshopt_compression")
    buffers = document.get("buffers", [])
    if len(bin_chunks) > 1:
        raise ValueError("multiple BIN chunks are not supported by this fixture checker")
    binary = bin_chunks[0]["data"] if bin_chunks else b""
    for i, buffer in enumerate(buffers):
        if buffer.get("uri") is None:
            if i != 0 or not binary:
                raise ValueError(f"buffer {i} has no URI but no matching GLB BIN payload")
            if buffer.get("byteLength", 0) > len(binary):
                raise ValueError(f"buffer {i} byteLength exceeds BIN chunk")
        elif buffer["uri"].startswith("data:"):
            import base64
            header, data = buffer["uri"].split(",", 1)
            decoded = base64.b64decode(data) if ";base64" in header else data.encode()
            if len(decoded) < buffer.get("byteLength", 0):
                raise ValueError(f"buffer {i} data URI is shorter than byteLength")
        else:
            raise ValueError(f"external buffer URI is unsupported in single-file GLB: {buffer['uri']}")
    meshopt_views = 0
    for i, view in enumerate(document.get("bufferViews", [])):
        ext = view.get("extensions", {}).get("EXT_meshopt_compression")
        if not ext:
            continue
        meshopt_views += 1
        buffer_index = ext.get("buffer")
        if not isinstance(buffer_index, int) or buffer_index < 0 or buffer_index >= len(buffers):
            raise ValueError(f"bufferView {i}: invalid meshopt buffer index")
        source_buffer = buffers[buffer_index]
        if source_buffer.get("uri") is None:
            source_length = len(binary)
        elif source_buffer.get("uri", "").startswith("data:"):
            import base64
            header, data = source_buffer["uri"].split(",", 1)
            source_length = len(base64.b64decode(data)) if ";base64" in header else len(data.encode())
        else:
            raise ValueError(f"bufferView {i}: unsupported external meshopt source buffer")
        start = int(ext.get("byteOffset", 0))
        length = int(ext.get("byteLength", 0))
        count, stride = int(ext.get("count", 0)), int(ext.get("byteStride", 0))
        if start < 0 or length <= 0 or start + length > source_length:
            raise ValueError(f"bufferView {i}: compressed byte range out of bounds")
        if count <= 0 or stride <= 0 or count * stride > 2**31:
            raise ValueError(f"bufferView {i}: invalid count/byteStride")
        if ext.get("mode") not in ("ATTRIBUTES", "TRIANGLES", "INDICES"):
            raise ValueError(f"bufferView {i}: invalid mode {ext.get('mode')}")
    if meshopt_views == 0:
        raise ValueError("EXT_meshopt_compression declared but no compressed bufferViews found")
    return {
        "file_size": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
        "glb_version": version, "declared_length": declared, "chunks": [{k:v for k,v in c.items() if k != "data"} for c in chunks],
        "extensions_used": ext_used, "extensions_required": ext_required, "buffer_count": len(buffers),
        "buffer_views": len(document.get("bufferViews", [])), "meshopt_buffer_views": meshopt_views,
        "mesh_count": len(document.get("meshes", [])), "material_count": len(document.get("materials", [])),
        "texture_count": len(document.get("textures", [])), "image_count": len(document.get("images", [])),
        "skin_count": len(document.get("skins", [])), "animation_count": len(document.get("animations", [])),
        "meshopt_ranges_checked": True,
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--catalog-url", default="https://models.codelove.in/catalog.json")
    ap.add_argument("--out-dir", default=".artifacts/avatar-fixture")
    args = ap.parse_args()
    out = Path(args.out_dir); out.mkdir(parents=True, exist_ok=True)
    response = requests.get(args.catalog_url, timeout=90); response.raise_for_status()
    catalog = response.json()
    (out / "catalog.json").write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")
    candidates = []
    for record in walk(catalog):
        url = find_glb_url(record, args.catalog_url)
        lic = license_text(record)
        text = " ".join(str(record.get(k, "")) for k in ("name", "title", "category", "type", "tags", "description")).lower()
        if url and "mit" in lic.lower() and any(word in text for word in ("character", "avatar", "rigged", "human")):
            candidates.append((record, url, lic))
    if not candidates:
        raise SystemExit("No model with explicit per-model MIT metadata and character/rigged identity found in catalog; refusing to guess a license.")
    selected = None
    candidate_errors = []
    # Try small, explicitly MIT-licensed character entries until one has a valid
    # embedded GLB container and actual meshopt bufferViews. Never silently
    # accept an HTML response or an incomplete candidate as the fixture.
    for record, url, lic in sorted(candidates, key=lambda x: (len(str(x[0])), x[1])):
        try:
            r = requests.get(url, timeout=120); r.raise_for_status()
            candidate_path = out / "avatar-candidate.glb"
            candidate_path.write_bytes(r.content)
            structure = validate_glb(candidate_path)
            if "EXT_texture_webp" not in structure["extensions_used"] and "EXT_texture_webp" not in structure["extensions_required"]:
                raise ValueError("EXT_texture_webp metadata absent")
            selected = (record, url, lic, candidate_path, structure)
            break
        except Exception as exc:
            candidate_errors.append({"url": url, "error": str(exc), "bytes": candidate_path.stat().st_size if candidate_path.exists() else 0})
    if selected is None:
        (out / "candidate-errors.json").write_text(json.dumps(candidate_errors, indent=2), encoding="utf-8")
        raise SystemExit("No candidate passed GLB/container/meshopt checks; see candidate-errors.json.")
    record, url, lic, candidate_path, structure = selected
    glb_path = out / "avatar.glb"
    candidate_path.replace(glb_path)
    license_record = {
        "catalog_url": args.catalog_url, "source_model_url": url,
        "model_name": record.get("name") or record.get("title") or record.get("text") or "unnamed",
        "model_license_metadata": lic, "catalog_entry": record,
        "license_scope_note": "Per-model catalog metadata captured; retain this evidence with the fixture. A repository-wide license is not substituted for per-model metadata.",
        "candidate_failures_before_selection": candidate_errors
    }
    (out / "license-metadata.json").write_text(json.dumps(license_record, ensure_ascii=False, indent=2), encoding="utf-8")
    report = {**structure, **{k:v for k,v in license_record.items() if k != "catalog_entry"},
              "catalog_entry_sha256": hashlib.sha256(json.dumps(record, sort_keys=True, ensure_ascii=False).encode()).hexdigest(),
              "status": "STRUCTURE_PASS_DECODER_PENDING"}
    (out / "fixture-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()

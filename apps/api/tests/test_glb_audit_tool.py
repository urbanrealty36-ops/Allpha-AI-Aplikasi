from __future__ import annotations

import importlib.util
import json
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TOOL_PATH = ROOT / "tools" / "3d-assets" / "audit_existing_glb_assets.py"
SPEC = importlib.util.spec_from_file_location("allpha_glb_audit_tool", TOOL_PATH)
assert SPEC is not None and SPEC.loader is not None
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


def write_glb(path: Path, document: dict) -> None:
    payload = json.dumps(document, separators=(",", ":")).encode("utf-8")
    payload += b" " * ((-len(payload)) % 4)
    binary = b"\x00" * 4
    chunks = struct.pack("<II", len(payload), 0x4E4F534A) + payload
    chunks += struct.pack("<II", len(binary), 0x004E4942) + binary
    total_length = 12 + len(chunks)
    path.write_bytes(struct.pack("<4sII", b"glTF", 2, total_length) + chunks)


def test_audit_parses_json_and_reports_capabilities(tmp_path: Path) -> None:
    path = tmp_path / "valid-capabilities.glb"
    write_glb(
        path,
        {
            "asset": {"version": "2.0"},
            "buffers": [{"byteLength": 4}],
            "bufferViews": [{"buffer": 0, "byteLength": 4}],
            "meshes": [{}],
            "materials": [{}],
            "textures": [{}],
            "images": [{"bufferView": 0, "mimeType": "image/png"}],
            "skins": [{}],
            "animations": [{}],
            "extensionsUsed": [],
        },
    )

    result = AUDIT.inspect_glb(path)

    assert result["glb_valid"] is True
    assert result["gltf_json_valid"] is True
    assert result["buffer_count"] == 1
    assert result["mesh_count"] == 1
    assert result["skin_count"] == 1
    assert result["animation_count"] == 1
    assert result["compatibility_findings"] == []


def test_audit_flags_unresolved_nonzero_base_buffer_without_rejecting_container(tmp_path: Path) -> None:
    path = tmp_path / "unresolved-fallback-buffer.glb"
    write_glb(
        path,
        {
            "asset": {"version": "2.0"},
            "buffers": [
                {"byteLength": 4},
                {"byteLength": 16, "extensions": {"EXT_meshopt_compression": {"fallback": True}}},
            ],
            "bufferViews": [
                {
                    "buffer": 1,
                    "byteLength": 16,
                    "extensions": {
                        "EXT_meshopt_compression": {
                            "buffer": 0,
                            "byteOffset": 0,
                            "byteLength": 4,
                            "byteStride": 4,
                            "count": 1,
                            "mode": "ATTRIBUTES",
                        }
                    },
                }
            ],
            "extensionsUsed": ["EXT_meshopt_compression"],
            "extensionsRequired": ["EXT_meshopt_compression"],
        },
    )

    result = AUDIT.inspect_glb(path)

    assert result["glb_valid"] is True
    assert result["gltf_json_valid"] is True
    assert result["buffers_missing_uri_nonzero"] == [1]
    assert result["meshopt_source_buffer_indices"] == [0]
    assert "nonzero_buffer_missing_uri" in result["compatibility_findings"]

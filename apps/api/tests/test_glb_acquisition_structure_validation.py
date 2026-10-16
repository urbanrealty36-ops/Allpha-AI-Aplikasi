import importlib.util
import json
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "tools" / "3d-assets" / "acquire_glb_assets.py"


def _load_validator():
    spec = importlib.util.spec_from_file_location("allpha_glb_acquisition", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.validate_glb_container


def _write_glb(path: Path, document: dict) -> None:
    raw = json.dumps(document, separators=(",", ":")).encode("utf-8")
    raw += b" " * ((4 - len(raw) % 4) % 4)
    chunk = struct.pack("<I4s", len(raw), b"JSON") + raw
    path.write_bytes(struct.pack("<4sII", b"glTF", 2, 12 + len(chunk)) + chunk)


def test_acquisition_validator_accepts_minimal_glb_v2(tmp_path):
    validate = _load_validator()
    path = tmp_path / "valid.glb"
    _write_glb(path, {"asset": {"version": "2.0"}, "scenes": [{}], "scene": 0})
    assert validate(path) is True


def test_acquisition_validator_rejects_html_or_wrong_magic(tmp_path):
    validate = _load_validator()
    path = tmp_path / "bad.glb"
    path.write_bytes(b"\n\n\n\nnot-a-glb")
    try:
        validate(path)
    except ValueError as exc:
        assert "magic" in str(exc)
    else:
        raise AssertionError("invalid GLB bytes must not be accepted")


def test_acquisition_validator_rejects_malformed_json_chunk(tmp_path):
    validate = _load_validator()
    path = tmp_path / "bad-json.glb"
    raw = b"{not json}"
    raw += b" " * ((4 - len(raw) % 4) % 4)
    chunk = struct.pack("<I4s", len(raw), b"JSON") + raw
    path.write_bytes(struct.pack("<4sII", b"glTF", 2, 12 + len(chunk)) + chunk)
    try:
        validate(path)
    except json.JSONDecodeError:
        pass
    else:
        raise AssertionError("invalid JSON chunk must not be accepted")

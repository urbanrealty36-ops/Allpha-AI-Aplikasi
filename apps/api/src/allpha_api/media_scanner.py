"""Shared pinned-identity ClamAV daemon adapter for media workers."""
from __future__ import annotations

import hashlib
import re
import socket
import struct
from typing import Any

from allpha_api.knowledge import (
    DocumentScannerConfigurationError,
    _local_scanner_identity_pins,
)


def local_scanner_identity_pins() -> tuple[str, str]:
    try:
        return _local_scanner_identity_pins()
    except DocumentScannerConfigurationError as exc:
        raise RuntimeError("MEDIA_SCANNER_IDENTITY_NOT_CONFIGURED") from exc


def _parse_version(data: bytes) -> tuple[str, str]:
    text = data.decode("utf-8", "replace").strip()
    match = re.search(r"ClamAV\s+([^/\s]+)/([^/\s]+)/(.+)", text)
    if not match:
        raise RuntimeError("MEDIA_SCANNER_VERSION_UNAVAILABLE")
    return match.group(1), match.group(2) + "/" + match.group(3)


def scan_media_bytes(data: bytes, host: str, port: int, *, timeout_seconds: int = 180) -> dict[str, Any]:
    expected_engine, expected_signature = local_scanner_identity_pins()
    try:
        with socket.create_connection((host, port), timeout=10) as sock:
            sock.settimeout(10)
            sock.sendall(b"zVERSION\0")
            version_data = sock.recv(4096)
    except OSError as exc:
        raise RuntimeError("MEDIA_SCANNER_UNAVAILABLE") from exc
    actual_engine, actual_signature = _parse_version(version_data)
    if actual_engine != expected_engine or actual_signature != expected_signature:
        raise RuntimeError("MEDIA_SCANNER_IDENTITY_MISMATCH")

    try:
        with socket.create_connection((host, port), timeout=10) as sock:
            sock.settimeout(timeout_seconds)
            sock.sendall(b"zINSTREAM\0")
            for offset in range(0, len(data), 64 * 1024):
                chunk = data[offset:offset + 64 * 1024]
                sock.sendall(struct.pack("!I", len(chunk)) + chunk)
            sock.sendall(struct.pack("!I", 0))
            result = sock.recv(4096).decode("utf-8", "replace")
    except OSError as exc:
        raise RuntimeError("MEDIA_SCANNER_UNAVAILABLE") from exc
    if not result.strip().endswith("OK") or "FOUND" in result or "ERROR" in result:
        raise RuntimeError("MEDIA_SCAN_NOT_CLEAN")
    return {
        "scanner_id": "clamav-local",
        "engine_version": actual_engine,
        "signature_version": actual_signature,
        "sha256": hashlib.sha256(data).hexdigest(),
        "contract_version": "allpha.local-clamav.v1",
    }

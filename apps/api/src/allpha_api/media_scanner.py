"""Shared pinned-identity ClamAV daemon adapter for media workers."""
from __future__ import annotations

import asyncio
import hashlib
import os
import re
import socket
import struct
from typing import Any

from allpha_api.document_scanner import (
    DocumentMalwareDetected,
    DocumentScannerConfigurationError,
    DocumentScannerUnavailable,
    RemoteDocumentScanner,
)
from allpha_api.knowledge import _local_scanner_identity_pins


def local_scanner_identity_pins() -> tuple[str, str]:
    try:
        return _local_scanner_identity_pins()
    except DocumentScannerConfigurationError as exc:
        raise RuntimeError("MEDIA_SCANNER_IDENTITY_NOT_CONFIGURED") from exc


def _parse_version(data: bytes) -> tuple[str, str]:
    text = data.decode("utf-8", "replace").replace("\0", "").strip()
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
    normalized_result = result.replace("\0", "").strip()
    if not normalized_result.endswith("OK") or "FOUND" in normalized_result or "ERROR" in normalized_result:
        raise RuntimeError("MEDIA_SCAN_NOT_CLEAN")
    return {
        "scanner_id": "clamav-local",
        "engine_version": actual_engine,
        "signature_version": actual_signature,
        "sha256": hashlib.sha256(data).hexdigest(),
        "contract_version": "allpha.local-clamav.v1",
    }


def media_scanner_mode() -> str:
    """Resolve the shared malware scanner mode; remote scanning is the default."""
    mode = os.getenv("ALLPHA_DOCUMENT_SCANNER_MODE", "remote").strip().lower()
    if mode not in {"remote", "clamd"}:
        raise RuntimeError("MEDIA_SCANNER_MODE_INVALID")
    return mode


def require_media_scanner_configuration() -> str:
    """Validate scanner configuration without performing a network scan."""
    mode = media_scanner_mode()
    if mode == "clamd":
        if os.getenv("ALLPHA_CLAMAV_ENABLED", "false").strip().lower() != "true":
            raise RuntimeError("MEDIA_LOCAL_CLAMAV_NOT_ENABLED")
        local_scanner_identity_pins()
        return mode
    try:
        RemoteDocumentScanner.from_environment()
    except DocumentScannerConfigurationError as exc:
        raise RuntimeError("MEDIA_REMOTE_SCANNER_NOT_CONFIGURED") from exc
    return mode


async def scan_media_bytes_async(
    data: bytes,
    *,
    filename: str,
    media_type: str,
    clamav_host: str | None = None,
    clamav_port: int = 3310,
) -> dict[str, Any]:
    """Scan media using the canonical remote scanner or explicitly enabled local ClamAV."""
    mode = require_media_scanner_configuration()
    if mode == "clamd":
        host = (clamav_host or os.getenv("CLAMAV_HOST", "")).strip()
        if not host:
            raise ValueError("MEDIA_SCANNER_NOT_CONFIGURED")
        return await asyncio.to_thread(scan_media_bytes, data, host, clamav_port)

    try:
        scanner = RemoteDocumentScanner.from_environment()
        receipt = await scanner.scan(data, filename=filename, media_type=media_type)
        return receipt.as_provenance()
    except DocumentMalwareDetected as exc:
        raise ValueError("MEDIA_SCAN_REJECTED") from exc
    except DocumentScannerConfigurationError as exc:
        raise ValueError("MEDIA_SCANNER_NOT_CONFIGURED") from exc
    except DocumentScannerUnavailable as exc:
        raise ValueError("MEDIA_SCANNER_UNAVAILABLE") from exc

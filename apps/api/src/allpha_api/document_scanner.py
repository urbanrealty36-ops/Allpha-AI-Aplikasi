"""Authenticated, allowlisted remote malware-scanner adapter.

The endpoint contract is Allpha-owned and versioned. A clean verdict is trusted
only when the scanner echoes the exact uploaded SHA-256 and immutable scanner
engine/signature identity. Redirects, ambient proxy configuration and unlisted
hosts are rejected. Missing configuration always fails closed.
"""
from __future__ import annotations

import asyncio
import hashlib
import ipaddress
import json
import os
import re
import socket
from dataclasses import dataclass
from urllib.parse import urlsplit

import httpx


CONTRACT_VERSION = "allpha.document-scan.v1"
MAX_REQUEST_BYTES = 16 * 1024 * 1024  # upload cap is 15 MiB; headroom for multipart framing
MAX_RESPONSE_BYTES = 16 * 1024
OVERALL_TIMEOUT_SECONDS = 30.0
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_IDENTITY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/+\- ]{0,127}$")
_HOST_LABEL = re.compile(r"^(?!-)[a-z0-9-]{1,63}(?<!-)$")
_BLOCKED_SUFFIXES = (
    ".localhost", ".local", ".internal", ".localdomain", ".lan", ".home",
    ".corp", ".intranet", ".private", ".home.arpa", ".railway.internal",
)
_BLOCKED_HOSTS = {"localhost", "metadata", "metadata.google.internal", "instance-data"}


class DocumentScannerConfigurationError(RuntimeError):
    pass


class DocumentScannerUnavailable(RuntimeError):
    pass


class DocumentMalwareDetected(RuntimeError):
    pass


@dataclass(frozen=True)
class DocumentScanReceipt:
    scanner_id: str
    engine_version: str
    signature_version: str
    sha256: str
    contract_version: str

    def as_provenance(self) -> dict[str, str]:
        """Stable, persisted receipt; receipt_id is a digest of the canonical identity fields."""
        fields = {
            "scanner_id": self.scanner_id,
            "engine_version": self.engine_version,
            "signature_version": self.signature_version,
            "sha256": self.sha256,
            "contract_version": self.contract_version,
        }
        canonical = json.dumps(fields, sort_keys=True, separators=(",", ":")).encode()
        return {**fields, "receipt_id": hashlib.sha256(canonical).hexdigest()}


def _is_public_address(value: str) -> bool:
    try:
        address = ipaddress.ip_address(value.split("%", 1)[0])
    except ValueError:
        return False
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped:
        address = address.ipv4_mapped
    return address.is_global and not address.is_multicast


def _hostname_is_publicly_routable_name(host: str) -> bool:
    """Syntactic guard: a public DNS name, never a bare/internal/numeric alias."""
    if host in _BLOCKED_HOSTS or host.endswith(_BLOCKED_SUFFIXES):
        return False
    labels = host.split(".")
    if len(host) > 253 or len(labels) < 2:
        return False
    if not all(_HOST_LABEL.match(label) for label in labels):
        return False
    # Rejects decimal/hex/octal IPv4 spellings such as 2130706433 or 0x7f.1.
    return not re.fullmatch(r"(0x[0-9a-f]+|\d+)", labels[-1])


async def _resolve_public_addresses(host: str) -> None:
    """Fail closed when an allowlisted name resolves to a non-public address."""
    loop = asyncio.get_running_loop()
    try:
        infos = await asyncio.wait_for(
            loop.getaddrinfo(host, 443, type=socket.SOCK_STREAM), timeout=5.0,
        )
    except (OSError, asyncio.TimeoutError) as exc:
        raise DocumentScannerUnavailable("remote scanner hostname could not be resolved") from exc
    addresses = {info[4][0] for info in infos}
    if not addresses or not all(_is_public_address(item) for item in addresses):
        raise DocumentScannerUnavailable("remote scanner hostname resolves to a non-public address")


class RemoteDocumentScanner:
    def __init__(
        self,
        *,
        endpoint: str,
        api_key: str,
        allowed_hosts: set[str],
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        try:
            parsed = urlsplit(endpoint.strip())
            port = parsed.port
        except ValueError as exc:
            raise DocumentScannerConfigurationError("scanner endpoint URL is malformed") from exc
        host = (parsed.hostname or "").lower().rstrip(".")
        try:
            ipaddress.ip_address(host)
            is_ip_literal = True
        except ValueError:
            is_ip_literal = False
        if (
            parsed.scheme != "https"
            or not host
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
            or port not in (None, 443)
            or is_ip_literal
            or not _hostname_is_publicly_routable_name(host)
            or host not in {item.lower().strip().rstrip(".") for item in allowed_hosts if item.strip()}
        ):
            raise DocumentScannerConfigurationError(
                "scanner endpoint must be HTTPS on an explicitly allowlisted hostname"
            )
        if not api_key.strip():
            raise DocumentScannerConfigurationError("scanner API credential is required")
        self._endpoint = endpoint.strip()
        self._host = host
        self._api_key = api_key.strip()
        self._transport = transport

    @classmethod
    def from_environment(
        cls, *, transport: httpx.AsyncBaseTransport | None = None,
    ) -> "RemoteDocumentScanner":
        endpoint = os.getenv("ALLPHA_DOCUMENT_SCANNER_URL", "").strip()
        api_key = os.getenv("ALLPHA_DOCUMENT_SCANNER_API_KEY", "").strip()
        allowed_hosts = {
            host.strip().lower().rstrip(".")
            for host in os.getenv("ALLPHA_DOCUMENT_SCANNER_ALLOWED_HOSTS", "").split(",")
            if host.strip()
        }
        if not endpoint or not api_key or not allowed_hosts:
            raise DocumentScannerConfigurationError(
                "scanner URL, API key and explicit hostname allowlist are required"
            )
        return cls(
            endpoint=endpoint,
            api_key=api_key,
            allowed_hosts=allowed_hosts,
            transport=transport,
        )

    async def scan(
        self, data: bytes, *, filename: str, media_type: str,
    ) -> DocumentScanReceipt:
        if len(data) > MAX_REQUEST_BYTES:
            raise DocumentScannerUnavailable("document exceeds the scanner request size limit")
        digest = hashlib.sha256(data).hexdigest()
        if self._transport is None:
            await _resolve_public_addresses(self._host)
        try:
            status_code, body = await asyncio.wait_for(
                self._post(data, filename=filename, media_type=media_type, digest=digest),
                timeout=OVERALL_TIMEOUT_SECONDS,
            )
        except (httpx.HTTPError, asyncio.TimeoutError) as exc:
            raise DocumentScannerUnavailable("remote document scanner transport failed") from exc

        if status_code in {408, 425, 429} or status_code >= 500:
            raise DocumentScannerUnavailable(
                f"remote document scanner returned retryable HTTP {status_code}"
            )
        if status_code != 200:
            raise DocumentScannerUnavailable(
                f"remote document scanner returned non-verdict HTTP {status_code}"
            )
        receipt, verdict = _parse_response(body, digest)
        if verdict == "malicious":
            raise DocumentMalwareDetected("remote scanner detected malicious content")
        if verdict != "clean":
            raise DocumentScannerUnavailable("remote scanner did not return a definitive verdict")
        return receipt

    async def _post(
        self, data: bytes, *, filename: str, media_type: str, digest: str,
    ) -> tuple[int, bytes]:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(15.0, connect=3.0, pool=3.0),
            follow_redirects=False,
            trust_env=False,
            verify=True,
            transport=self._transport,
        ) as client:
            async with client.stream(
                "POST",
                self._endpoint,
                headers={
                    "Authorization": "Bearer " + self._api_key,
                    "Accept": "application/json",
                    "X-Allpha-Scan-Contract": CONTRACT_VERSION,
                    "X-Content-SHA256": digest,
                },
                files={"file": (filename, data, media_type)},
            ) as response:
                declared = response.headers.get("content-length")
                if declared is not None and (not declared.isdigit() or int(declared) > MAX_RESPONSE_BYTES):
                    raise DocumentScannerUnavailable("remote scanner response exceeds the size limit")
                chunks: list[bytes] = []
                total = 0
                async for chunk in response.aiter_bytes():
                    total += len(chunk)
                    if total > MAX_RESPONSE_BYTES:
                        raise DocumentScannerUnavailable("remote scanner response exceeds the size limit")
                    chunks.append(chunk)
                return response.status_code, b"".join(chunks)


def _identity(value: object) -> str:
    if not isinstance(value, str) or not _IDENTITY.match(value) or value != value.strip():
        raise ValueError("invalid scanner identity")
    return value


def _parse_response(body: bytes, digest: str) -> tuple[DocumentScanReceipt, str]:
    """Strict schema validation; any deviation is untrusted, never clean."""
    invalid = DocumentScannerUnavailable("remote scanner response does not match the Allpha contract")
    try:
        payload = json.loads(body.decode("utf-8"))
        if not isinstance(payload, dict) or set(payload) != {"contract_version", "verdict", "sha256", "scanner"}:
            raise ValueError("unexpected top-level fields")
        scanner = payload["scanner"]
        if not isinstance(scanner, dict) or set(scanner) != {"id", "engine_version", "signature_version"}:
            raise ValueError("unexpected scanner fields")
        verdict = payload["verdict"]
        if verdict not in {"clean", "malicious"}:
            raise ValueError("verdict is not definitive")
        receipt = DocumentScanReceipt(
            scanner_id=_identity(scanner["id"]),
            engine_version=_identity(scanner["engine_version"]),
            signature_version=_identity(scanner["signature_version"]),
            sha256=payload["sha256"],
            contract_version=payload["contract_version"],
        )
    except (ValueError, KeyError, TypeError, UnicodeDecodeError, RecursionError) as exc:
        raise invalid from exc
    if (
        receipt.contract_version != CONTRACT_VERSION
        or not isinstance(receipt.sha256, str)
        or not _SHA256.match(receipt.sha256)
        or receipt.sha256 != digest
    ):
        raise DocumentScannerUnavailable("remote scanner receipt identity or content digest is invalid")
    return receipt, verdict

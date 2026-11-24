"""Authenticated, allowlisted remote malware-scanner adapter.

The endpoint contract is Allpha-owned and versioned. A clean verdict is trusted
only when the scanner echoes the exact uploaded SHA-256 and immutable scanner
engine/signature identity. Redirects, ambient proxy configuration and unlisted
hosts are rejected. Missing configuration always fails closed.
"""
from __future__ import annotations

import hashlib
import ipaddress
import os
from dataclasses import dataclass
from urllib.parse import urlsplit

import httpx


CONTRACT_VERSION = "allpha.document-scan.v1"


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
            or host not in {item.lower().strip().rstrip(".") for item in allowed_hosts if item.strip()}
        ):
            raise DocumentScannerConfigurationError(
                "scanner endpoint must be HTTPS on an explicitly allowlisted hostname"
            )
        if not api_key.strip():
            raise DocumentScannerConfigurationError("scanner API credential is required")
        self._endpoint = endpoint.strip()
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
        digest = hashlib.sha256(data).hexdigest()
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(15.0, connect=3.0),
                follow_redirects=False,
                trust_env=False,
                transport=self._transport,
            ) as client:
                response = await client.post(
                    self._endpoint,
                    headers={
                        "Authorization": "Bearer " + self._api_key,
                        "Accept": "application/json",
                        "X-Allpha-Scan-Contract": CONTRACT_VERSION,
                        "X-Content-SHA256": digest,
                    },
                    files={"file": (filename, data, media_type)},
                )
        except httpx.HTTPError as exc:
            raise DocumentScannerUnavailable("remote document scanner transport failed") from exc

        if response.status_code in {408, 425, 429} or response.status_code >= 500:
            raise DocumentScannerUnavailable(
                f"remote document scanner returned retryable HTTP {response.status_code}"
            )
        if response.status_code != 200:
            raise DocumentScannerUnavailable(
                f"remote document scanner returned non-verdict HTTP {response.status_code}"
            )
        try:
            payload = response.json()
            scanner = payload["scanner"]
            verdict = payload["verdict"]
            receipt = DocumentScanReceipt(
                scanner_id=scanner["id"],
                engine_version=scanner["engine_version"],
                signature_version=scanner["signature_version"],
                sha256=payload["sha256"],
                contract_version=payload["contract_version"],
            )
        except (ValueError, KeyError, TypeError) as exc:
            raise DocumentScannerUnavailable("remote scanner response does not match the Allpha contract") from exc

        if (
            receipt.contract_version != CONTRACT_VERSION
            or receipt.sha256 != digest
            or not all(
                isinstance(value, str) and value.strip()
                for value in (receipt.scanner_id, receipt.engine_version, receipt.signature_version)
            )
        ):
            raise DocumentScannerUnavailable("remote scanner receipt identity or content digest is invalid")
        if verdict == "malicious":
            raise DocumentMalwareDetected("remote scanner detected malicious content")
        if verdict != "clean":
            raise DocumentScannerUnavailable("remote scanner did not return a definitive verdict")
        return receipt

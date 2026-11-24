"""Negative-path hardening tests for the remote document scanner adapter."""
import asyncio
import hashlib
import json

import httpx
import pytest

from allpha_api import document_scanner
from allpha_api.document_scanner import (
    CONTRACT_VERSION, DocumentMalwareDetected, DocumentScannerConfigurationError,
    DocumentScannerUnavailable, RemoteDocumentScanner,
)

DATA = b"sample document"
DIGEST = hashlib.sha256(DATA).hexdigest()


def receipt(**override):
    body = {
        "contract_version": CONTRACT_VERSION, "verdict": "clean", "sha256": DIGEST,
        "scanner": {"id": "scanner-1", "engine_version": "1.4.6", "signature_version": "2026-11-24"},
    }
    body.update(override)
    return body


def scanner(handler, host="scanner.example.com"):
    return RemoteDocumentScanner(
        endpoint=f"https://{host}/v1/scan", api_key="secret-key", allowed_hosts={host},
        transport=httpx.MockTransport(handler),
    )


def run(coro):
    return asyncio.run(coro)


def scan(s, data=DATA):
    return run(s.scan(data, filename="a.txt", media_type="text/plain"))


@pytest.mark.parametrize("endpoint", [
    "http://scanner.example.com/x",
    "https://user:pw@scanner.example.com/x",
    "https://user@scanner.example.com/x",
    "https://127.0.0.1/x", "https://[::1]/x", "https://10.0.0.5/x",
    "https://169.254.169.254/latest/meta-data", "https://192.168.1.1/x",
    "https://2130706433/x", "https://0x7f.1/x",
    "https://localhost/x", "https://scanner/x",
    "https://metadata.google.internal/x", "https://scanner.railway.internal/x",
    "https://scanner.local/x", "https://scanner.example.com:8443/x",
    "https://scanner.example.com/x?token=1", "https://scanner.example.com/x#f",
    "https://scanner.example.com:notaport/x", "",
])
def test_rejects_unsafe_endpoint_even_when_allowlisted(endpoint):
    host = (endpoint.split("//")[-1].split("/")[0].split("@")[-1].rsplit(":", 1)[0]).strip("[]")
    with pytest.raises(DocumentScannerConfigurationError):
        RemoteDocumentScanner(endpoint=endpoint, api_key="k", allowed_hosts={host})


def test_rejects_host_missing_from_strict_allowlist_and_empty_credential():
    with pytest.raises(DocumentScannerConfigurationError):
        RemoteDocumentScanner(endpoint="https://scanner.example.com/x", api_key="k", allowed_hosts={"evil.example.com"})
    with pytest.raises(DocumentScannerConfigurationError):
        RemoteDocumentScanner(endpoint="https://scanner.example.com/x", api_key="  ", allowed_hosts={"scanner.example.com"})
    with pytest.raises(DocumentScannerConfigurationError):  # suffix/subdomain is not an allowlist match
        RemoteDocumentScanner(endpoint="https://a.scanner.example.com/x", api_key="k", allowed_hosts={"scanner.example.com"})


def test_environment_requires_url_key_and_allowlist(monkeypatch):
    for name in ("URL", "API_KEY", "ALLOWED_HOSTS"):
        monkeypatch.delenv(f"ALLPHA_DOCUMENT_SCANNER_{name}", raising=False)
    with pytest.raises(DocumentScannerConfigurationError):
        RemoteDocumentScanner.from_environment()


def test_clean_receipt_is_stable_and_bound_to_digest():
    seen = {}

    def handler(request):
        seen["auth"] = request.headers["authorization"]
        return httpx.Response(200, json=receipt())

    result = scan(scanner(handler))
    assert seen["auth"] == "Bearer secret-key"
    provenance = result.as_provenance()
    assert provenance == result.as_provenance()
    assert provenance["sha256"] == DIGEST and len(provenance["receipt_id"]) == 64
    assert "secret-key" not in json.dumps(provenance)


def test_malicious_verdict_raises_malware():
    with pytest.raises(DocumentMalwareDetected):
        scan(scanner(lambda r: httpx.Response(200, json=receipt(verdict="malicious"))))


@pytest.mark.parametrize("status", [301, 302, 307, 308])
def test_redirects_are_not_followed(status):
    calls = []

    def handler(request):
        calls.append(str(request.url))
        return httpx.Response(status, headers={"location": "https://169.254.169.254/"}, json=receipt())

    with pytest.raises(DocumentScannerUnavailable):
        scan(scanner(handler))
    assert calls == ["https://scanner.example.com/v1/scan"]


@pytest.mark.parametrize("status", [400, 401, 403, 404, 408, 429, 500, 503])
def test_non_200_is_never_clean(status):
    with pytest.raises(DocumentScannerUnavailable):
        scan(scanner(lambda r: httpx.Response(status, json=receipt())))


@pytest.mark.parametrize("payload", [
    receipt(verdict="unknown"), receipt(verdict="CLEAN"), receipt(verdict=True),
    receipt(sha256="0" * 64), receipt(sha256=DIGEST.upper()), receipt(sha256=None),
    receipt(contract_version="allpha.document-scan.v0"),
    receipt(scanner={"id": "", "engine_version": "1", "signature_version": "1"}),
    receipt(scanner={"id": "s", "engine_version": "1"}),
    receipt(scanner={"id": "s", "engine_version": "1", "signature_version": "1", "x": 1}),
    receipt(scanner={"id": 7, "engine_version": "1", "signature_version": "1"}),
    receipt(scanner="scanner-1"),
    receipt(scanner={"id": "a\nb", "engine_version": "1", "signature_version": "1"}),
    {**receipt(), "extra": "field"},
    [], "clean", None,
])
def test_response_schema_violations_are_untrusted(payload):
    with pytest.raises(DocumentScannerUnavailable):
        scan(scanner(lambda r: httpx.Response(200, json=payload)))


def test_non_json_and_invalid_utf8_bodies_are_untrusted():
    for content in (b"<html>clean</html>", b"\xff\xfe", b""):
        with pytest.raises(DocumentScannerUnavailable):
            scan(scanner(lambda r, c=content: httpx.Response(200, content=c)))


def test_oversized_response_is_rejected_streaming_and_by_header():
    big = json.dumps(receipt(pad="x" * (document_scanner.MAX_RESPONSE_BYTES + 1)))
    with pytest.raises(DocumentScannerUnavailable, match="size limit"):
        scan(scanner(lambda r: httpx.Response(200, content=big)))
    with pytest.raises(DocumentScannerUnavailable, match="size limit"):
        scan(scanner(lambda r: httpx.Response(200, headers={"content-length": "999999"}, content=b"{}")))


def test_oversized_request_is_rejected_before_any_network_call():
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(200, json=receipt())

    with pytest.raises(DocumentScannerUnavailable, match="request size"):
        scan(scanner(handler), data=b"0" * (document_scanner.MAX_REQUEST_BYTES + 1))
    assert calls == []


def test_transport_errors_and_overall_timeout_fail_closed(monkeypatch):
    def boom(request):
        raise httpx.ConnectTimeout("timeout")

    with pytest.raises(DocumentScannerUnavailable):
        scan(scanner(boom))

    monkeypatch.setattr(document_scanner, "OVERALL_TIMEOUT_SECONDS", 0.05)

    async def slow(request):
        await asyncio.sleep(1)
        return httpx.Response(200, json=receipt())

    with pytest.raises(DocumentScannerUnavailable):
        scan(scanner(slow))


def test_tls_verification_and_no_redirects_or_env_proxy(monkeypatch):
    captured = {}
    real = httpx.AsyncClient

    def factory(*args, **kwargs):
        captured.update(kwargs)
        return real(*args, **kwargs)

    monkeypatch.setattr(document_scanner.httpx, "AsyncClient", factory)
    scan(scanner(lambda r: httpx.Response(200, json=receipt())))
    assert captured["verify"] is True
    assert captured["follow_redirects"] is False
    assert captured["trust_env"] is False
    timeout = captured["timeout"]
    assert timeout.connect == 3.0 and timeout.read == 15.0


@pytest.mark.parametrize("address", [
    "127.0.0.1", "10.1.2.3", "172.16.0.1", "192.168.0.1", "169.254.169.254",
    "::1", "fe80::1", "fc00::1", "::ffff:127.0.0.1", "100.64.0.1", "0.0.0.0", "224.0.0.1",
])
def test_allowlisted_name_resolving_to_non_public_address_is_refused(monkeypatch, address):
    s = RemoteDocumentScanner(endpoint="https://scanner.example.com/v1/scan", api_key="k", allowed_hosts={"scanner.example.com"})

    async def scenario():
        loop = asyncio.get_running_loop()

        async def gai(host, port, **kw):
            return [(2, 1, 6, "", (address, 443))]

        monkeypatch.setattr(loop, "getaddrinfo", gai)
        with pytest.raises(DocumentScannerUnavailable, match="non-public"):
            await s.scan(DATA, filename="a.txt", media_type="text/plain")

    run(scenario())


def test_public_address_passes_resolution_guard():
    assert document_scanner._is_public_address("93.184.216.34")
    assert not document_scanner._is_public_address("not-an-ip")

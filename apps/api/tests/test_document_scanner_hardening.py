"""Negative-path hardening tests for the remote document scanner adapter."""
import asyncio
import hashlib
import json
import socket
import ssl
import datetime

import httpx
import pytest

from allpha_api import document_scanner
from allpha_api.document_scanner import (
    CONTRACT_VERSION, DocumentMalwareDetected, DocumentScannerConfigurationError,
    DocumentScannerUnavailable, RemoteDocumentScanner,
)

DATA = b"sample document"
DIGEST = hashlib.sha256(DATA).hexdigest()


PUBLIC_IP = "93.184.216.34"
DNS_CALLS: list = []


@pytest.fixture(autouse=True)
def fake_dns(monkeypatch):
    """Deterministic DNS; every lookup (ours or any library's) is recorded."""
    DNS_CALLS.clear()
    answers = {"scanner.example.com": [PUBLIC_IP]}

    def getaddrinfo(host, port, *args, **kwargs):
        DNS_CALLS.append(host)
        if host not in answers:
            raise socket.gaierror("no such host")
        return [(socket.AF_INET6 if ":" in a else socket.AF_INET, socket.SOCK_STREAM, 6, "", (a, port))
                for a in answers[host]]

    monkeypatch.setattr(socket, "getaddrinfo", getaddrinfo)
    return answers


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
        expected_scanner_id="scanner-1", expected_engine_version="1.4.6",
        expected_signature_version="2026-11-24", transport=httpx.MockTransport(handler),
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
        RemoteDocumentScanner(endpoint=endpoint, api_key="k", allowed_hosts={host}, expected_scanner_id="scanner-1", expected_engine_version="1.4.6", expected_signature_version="2026-11-24")


def test_rejects_host_missing_from_strict_allowlist_and_empty_credential():
    with pytest.raises(DocumentScannerConfigurationError):
        RemoteDocumentScanner(endpoint="https://scanner.example.com/x", api_key="k", allowed_hosts={"evil.example.com"}, expected_scanner_id="scanner-1", expected_engine_version="1.4.6", expected_signature_version="2026-11-24")
    with pytest.raises(DocumentScannerConfigurationError):
        RemoteDocumentScanner(endpoint="https://scanner.example.com/x", api_key="  ", allowed_hosts={"scanner.example.com"}, expected_scanner_id="scanner-1", expected_engine_version="1.4.6", expected_signature_version="2026-11-24")
    with pytest.raises(DocumentScannerConfigurationError):  # suffix/subdomain is not an allowlist match
        RemoteDocumentScanner(endpoint="https://a.scanner.example.com/x", api_key="k", allowed_hosts={"scanner.example.com"}, expected_scanner_id="scanner-1", expected_engine_version="1.4.6", expected_signature_version="2026-11-24")


def test_environment_requires_url_key_and_allowlist(monkeypatch):
    for name in ("URL", "API_KEY", "ALLOWED_HOSTS", "ID", "ENGINE_VERSION", "SIGNATURE_VERSION"):
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


@pytest.mark.parametrize(
    "body",
    [
        # Duplicate top-level verdict could otherwise let parser choice determine trust.
        b'{"contract_version":"allpha.document-scan.v1","verdict":"malicious","verdict":"clean","sha256":"' + DIGEST.encode() + b'","scanner":{"id":"scanner-1","engine_version":"1.4.6","signature_version":"2026-11-24"}}',
        # Duplicate nested identity fields are equally ambiguous.
        b'{"contract_version":"allpha.document-scan.v1","verdict":"clean","sha256":"' + DIGEST.encode() + b'","scanner":{"id":"scanner-evil","id":"scanner-1","engine_version":"1.4.6","signature_version":"2026-11-24"}}',
    ],
)
def test_scanner_rejects_duplicate_json_keys_at_any_depth(body):
    with pytest.raises(DocumentScannerUnavailable, match="contract"):
        document_scanner._parse_response(body, DIGEST)


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
    assert calls == [f"https://{PUBLIC_IP}/v1/scan"]  # pinned IP, single request, redirect not followed


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
    s = RemoteDocumentScanner(endpoint="https://scanner.example.com/v1/scan", api_key="k", allowed_hosts={"scanner.example.com"}, expected_scanner_id="scanner-1", expected_engine_version="1.4.6", expected_signature_version="2026-11-24")

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


def test_connect_target_is_validated_ip_with_original_host_and_sni_and_single_lookup(fake_dns):
    fake_dns["scanner.example.com"] = [PUBLIC_IP, "2606:2800:220:1:248:1893:25c8:1946"]
    seen = []

    def handler(request):
        seen.append((request.url.host, request.url.scheme, request.headers["host"], request.extensions))
        return httpx.Response(200, json=receipt())

    scan(scanner(handler))
    host, scheme, host_header, ext = seen[0]
    assert scheme == "https"
    assert host in {PUBLIC_IP, "2606:2800:220:1:248:1893:25c8:1946"}
    assert host_header == "scanner.example.com"
    assert ext["sni_hostname"] == "scanner.example.com"
    assert DNS_CALLS == ["scanner.example.com"]  # one lookup, no second resolution by httpx


def test_any_non_public_answer_refuses_before_any_request(fake_dns):
    fake_dns["scanner.example.com"] = [PUBLIC_IP, "10.0.0.8"]
    called = []
    with pytest.raises(DocumentScannerUnavailable, match="non-public"):
        scan(scanner(lambda r: called.append(r) or httpx.Response(200, json=receipt())))
    assert called == []


def test_resolution_failure_is_fail_closed(fake_dns):
    del fake_dns["scanner.example.com"]
    with pytest.raises(DocumentScannerUnavailable, match="could not be resolved"):
        scan(scanner(lambda r: httpx.Response(200, json=receipt())))


def test_connect_failure_falls_over_only_to_other_validated_ips(fake_dns):
    fake_dns["scanner.example.com"] = [PUBLIC_IP, "93.184.216.35"]
    targets = []

    def handler(request):
        targets.append(request.url.host)
        if len(targets) == 1:
            raise httpx.ConnectError("refused")
        return httpx.Response(200, json=receipt())

    scan(scanner(handler))
    assert targets == [PUBLIC_IP, "93.184.216.35"]
    assert DNS_CALLS == ["scanner.example.com"]


def test_all_connects_failing_is_unavailable_never_clean():
    def handler(request):
        raise httpx.ConnectError("refused")

    with pytest.raises(DocumentScannerUnavailable):
        scan(scanner(handler))


def test_pinned_url_brackets_ipv6_and_drops_hostname():
    assert document_scanner._pinned_url("https://scanner.example.com/v1/scan", "2001:db8::1", 443) == "https://[2001:db8::1]:443/v1/scan"
    assert "scanner.example.com" not in document_scanner._pinned_url("https://scanner.example.com/v1/scan", PUBLIC_IP, 443)


def _tls_material(common_name):
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID

    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1)).not_valid_after(now + datetime.timedelta(days=1))
        .add_extension(x509.SubjectAlternativeName([x509.DNSName(common_name)]), critical=False)
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )
    return (
        cert.public_bytes(serialization.Encoding.PEM),
        key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()),
    )


def _real_tls_scan(tmp_path, monkeypatch, cert_name):
    """Real TLS handshake against a loopback server reached only through the pinned IP."""
    cert_pem, key_pem = _tls_material(cert_name)
    (tmp_path / "c.pem").write_bytes(cert_pem)
    (tmp_path / "k.pem").write_bytes(key_pem)
    server_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    server_ctx.load_cert_chain(tmp_path / "c.pem", tmp_path / "k.pem")
    client_ctx = ssl.create_default_context(cadata=cert_pem.decode())
    hosts = []

    async def serve(reader, writer):
        head = await reader.readuntil(b"\r\n\r\n")
        hosts.append([l for l in head.split(b"\r\n") if l.lower().startswith(b"host:")][0])
        # drain body headers' content-length bytes
        length = int([l.split(b":")[1] for l in head.split(b"\r\n") if l.lower().startswith(b"content-length")][0])
        await reader.readexactly(length)
        body = json.dumps(receipt()).encode()
        writer.write(b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: %d\r\nConnection: close\r\n\r\n" % len(body) + body)
        await writer.drain()
        writer.close()

    monkeypatch.setattr(document_scanner, "_is_public_address", lambda v: v == "127.0.0.1")

    async def scenario():
        server = await asyncio.start_server(serve, "127.0.0.1", 0, ssl=server_ctx)
        port = server.sockets[0].getsockname()[1]
        s = RemoteDocumentScanner(endpoint="https://scanner.example.com/v1/scan", api_key="k", allowed_hosts={"scanner.example.com"}, expected_scanner_id="scanner-1", expected_engine_version="1.4.6", expected_signature_version="2026-11-24")
        s._connect_port = port
        s._ssl_context = client_ctx
        try:
            return await s.scan(DATA, filename="a.txt", media_type="text/plain")
        finally:
            server.close()

    return scenario, hosts


def test_real_tls_connects_to_pinned_ip_and_verifies_certificate_against_hostname(tmp_path, monkeypatch, fake_dns):
    fake_dns["scanner.example.com"] = ["127.0.0.1"]
    scenario, hosts = _real_tls_scan(tmp_path, monkeypatch, "scanner.example.com")
    result = run(scenario())
    assert result.sha256 == DIGEST
    assert hosts == [b"Host: scanner.example.com"] or hosts == [b"host: scanner.example.com"]
    assert DNS_CALLS == ["scanner.example.com"]


def test_real_tls_certificate_for_other_name_is_rejected(tmp_path, monkeypatch, fake_dns):
    fake_dns["scanner.example.com"] = ["127.0.0.1"]
    scenario, _ = _real_tls_scan(tmp_path, monkeypatch, "evil.example.net")
    with pytest.raises(DocumentScannerUnavailable):
        run(scenario())


@pytest.mark.parametrize(
    ("scanner_id", "engine_version", "signature_version"),
    [
        ("scanner-2", "1.4.6", "2026-11-24"),
        ("scanner-1", "1.4.7", "2026-11-24"),
        ("scanner-1", "1.4.6", "2026-11-25"),
    ],
)
def test_clean_verdict_requires_exact_deployment_pinned_scanner_identity(scanner_id, engine_version, signature_version):
    payload = receipt()
    payload["scanner"] = {
        "id": scanner_id,
        "engine_version": engine_version,
        "signature_version": signature_version,
    }
    with pytest.raises(DocumentScannerUnavailable, match="deployment-pinned"):
        scan(scanner(lambda request: httpx.Response(200, json=payload)))


def test_scanner_identity_pins_are_required_and_validated():
    with pytest.raises(DocumentScannerConfigurationError, match="trusted scanner"):
        RemoteDocumentScanner(
            endpoint="https://scanner.example.com/x", api_key="k",
            allowed_hosts={"scanner.example.com"}, expected_scanner_id="",
            expected_engine_version="1.4.6", expected_signature_version="2026-11-24",
        )

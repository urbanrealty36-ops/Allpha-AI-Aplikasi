import asyncio
import hashlib
import json

import httpx
import pytest
from fastapi import HTTPException

from allpha_api import document_scanner, knowledge
from allpha_api.document_scanner import CONTRACT_VERSION


class FakeResponse:
    def __init__(self, status_code=200, payload=None, invalid_json=False):
        self.status_code = status_code
        self.payload = payload
        self.invalid_json = invalid_json

    headers = {}

    async def aiter_bytes(self):
        if self.invalid_json:
            yield b"{not json"
        else:
            yield json.dumps(self.payload).encode()


class FakeAsyncClient:
    response = FakeResponse()
    error = None
    calls = []
    options = []

    def __init__(self, *args, **kwargs):
        type(self).options.append(kwargs)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    def stream(self, method, endpoint, *, files, headers):
        type(self).calls.append((endpoint, files, headers))
        if type(self).error:
            raise type(self).error
        response = type(self).response

        class Context:
            async def __aenter__(self):
                return response

            async def __aexit__(self, *args):
                return False

        return Context()


@pytest.fixture(autouse=True)
def scanner_client_mock(monkeypatch):
    FakeAsyncClient.response = FakeResponse()
    FakeAsyncClient.error = None
    FakeAsyncClient.calls = []
    FakeAsyncClient.options = []
    monkeypatch.setattr(knowledge.httpx, "AsyncClient", FakeAsyncClient)

    async def public_resolver(host):
        return None

    monkeypatch.setattr(document_scanner, "_resolve_public_addresses", public_resolver)
    monkeypatch.delenv("ALLPHA_DOCUMENT_SCANNER_URL", raising=False)
    monkeypatch.delenv("ALLPHA_DOCUMENT_SCANNER_API_KEY", raising=False)
    monkeypatch.delenv("ALLPHA_DOCUMENT_SCANNER_ALLOWED_HOSTS", raising=False)


def clean_receipt(data: bytes):
    return {
        "contract_version": CONTRACT_VERSION,
        "verdict": "clean",
        "sha256": hashlib.sha256(data).hexdigest(),
        "scanner": {
            "id": "scanner-prod-1",
            "engine_version": "engine-1.4.6",
            "signature_version": "2026-11-24T00:00:00Z",
        },
    }


def configure_scanner(monkeypatch):
    monkeypatch.setenv("ALLPHA_DOCUMENT_SCANNER_URL", "https://scanner.example.com/v1/scan")
    monkeypatch.setenv("ALLPHA_DOCUMENT_SCANNER_API_KEY", "test-only-secret")
    monkeypatch.setenv("ALLPHA_DOCUMENT_SCANNER_ALLOWED_HOSTS", "scanner.example.com")


def test_scanner_missing_configuration_fails_closed(monkeypatch):
    async def scenario():
        with pytest.raises(HTTPException) as error:
            await knowledge._scan(b"test", "sample.txt", "text/plain")
        assert error.value.status_code == 503
        assert error.value.detail["code"] == "SCANNER_NOT_CONFIGURED"
        assert FakeAsyncClient.calls == []

    asyncio.run(scenario())


def test_scanner_accepts_only_authenticated_allowlisted_sha_bound_clean_receipt(monkeypatch):
    configure_scanner(monkeypatch)
    data = b"sample document"
    FakeAsyncClient.response = FakeResponse(payload=clean_receipt(data))

    asyncio.run(knowledge._scan(data, "sample.txt", "text/plain"))
    assert len(FakeAsyncClient.calls) == 1
    endpoint, files, headers = FakeAsyncClient.calls[0]
    assert endpoint == "https://scanner.example.com/v1/scan"
    assert files["file"] == ("sample.txt", data, "text/plain")
    assert headers["Authorization"] == "Bearer test-only-secret"
    assert headers["X-Allpha-Scan-Contract"] == CONTRACT_VERSION
    assert headers["X-Content-SHA256"] == hashlib.sha256(data).hexdigest()
    assert FakeAsyncClient.options[0]["follow_redirects"] is False
    assert FakeAsyncClient.options[0]["trust_env"] is False


def test_scanner_rejects_malicious_verdict(monkeypatch):
    configure_scanner(monkeypatch)
    data = b"sample"
    payload = clean_receipt(data)
    payload["verdict"] = "malicious"
    FakeAsyncClient.response = FakeResponse(payload=payload)

    async def scenario():
        with pytest.raises(HTTPException) as error:
            await knowledge._scan(data, "sample.txt", "text/plain")
        assert error.value.status_code == 422
        assert error.value.detail["code"] == "MALWARE_SCAN_REJECTED"

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "response",
    [
        FakeResponse(payload={**clean_receipt(b"sample"), "verdict": "unknown"}),
        FakeResponse(payload={**clean_receipt(b"sample"), "sha256": "0" * 64}),
        FakeResponse(payload=None, invalid_json=True),
        FakeResponse(status_code=302, payload=clean_receipt(b"sample")),
        FakeResponse(status_code=503, payload=clean_receipt(b"sample")),
    ],
)
def test_scanner_rejects_incomplete_untrusted_or_non_success_verdict(monkeypatch, response):
    configure_scanner(monkeypatch)
    FakeAsyncClient.response = response

    async def scenario():
        with pytest.raises(HTTPException) as error:
            await knowledge._scan(b"sample", "sample.txt", "text/plain")
        assert error.value.status_code == 503
        assert error.value.detail["code"] == "SCANNER_UNAVAILABLE"

    asyncio.run(scenario())


def test_scanner_transport_error_fails_closed(monkeypatch):
    configure_scanner(monkeypatch)
    FakeAsyncClient.error = httpx.ConnectError("unreachable")

    async def scenario():
        with pytest.raises(HTTPException) as error:
            await knowledge._scan(b"sample", "sample.txt", "text/plain")
        assert error.value.status_code == 503
        assert error.value.detail["code"] == "SCANNER_UNAVAILABLE"

    asyncio.run(scenario())


@pytest.mark.parametrize(
    ("endpoint", "allowlist", "api_key"),
    [
        ("http://scanner.example.com/scan", "scanner.example.com", "test-key"),
        ("https://scanner.example.com/scan", "other.example.com", "test-key"),
        ("https://127.0.0.1/scan", "127.0.0.1", "test-key"),
        ("https://scanner.example.com/scan", "scanner.example.com", ""),
    ],
)
def test_scanner_rejects_non_https_unallowlisted_or_credentialless_endpoint(
    monkeypatch, endpoint, allowlist, api_key,
):
    monkeypatch.setenv("ALLPHA_DOCUMENT_SCANNER_URL", endpoint)
    monkeypatch.setenv("ALLPHA_DOCUMENT_SCANNER_ALLOWED_HOSTS", allowlist)
    monkeypatch.setenv("ALLPHA_DOCUMENT_SCANNER_API_KEY", api_key)

    async def scenario():
        with pytest.raises(HTTPException) as error:
            await knowledge._scan(b"sample", "sample.txt", "text/plain")
        assert error.value.status_code == 503
        assert error.value.detail["code"] == "SCANNER_NOT_CONFIGURED"
        assert FakeAsyncClient.calls == []

    asyncio.run(scenario())

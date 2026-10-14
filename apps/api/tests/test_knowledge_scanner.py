import asyncio

import httpx
import pytest
from fastapi import HTTPException

from allpha_api import knowledge


class FakeResponse:
    def __init__(self, status_code=200, payload=None, invalid_json=False):
        self.status_code = status_code
        self.payload = payload
        self.invalid_json = invalid_json

    def json(self):
        if self.invalid_json:
            raise ValueError("invalid JSON")
        return self.payload


class FakeAsyncClient:
    response = FakeResponse()
    error = None
    calls = []

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def post(self, endpoint, *, files):
        type(self).calls.append((endpoint, files))
        if type(self).error:
            raise type(self).error
        return type(self).response


def setup_function():
    FakeAsyncClient.response = FakeResponse()
    FakeAsyncClient.error = None
    FakeAsyncClient.calls = []
    knowledge.httpx.AsyncClient = FakeAsyncClient


def test_scanner_missing_endpoint_fails_closed(monkeypatch):
    monkeypatch.delenv("ALLPHA_DOCUMENT_SCANNER_URL", raising=False)

    async def scenario():
        with pytest.raises(HTTPException) as error:
            await knowledge._scan(b"test", "sample.txt", "text/plain")
        assert error.value.status_code == 503
        assert error.value.detail["code"] == "SCANNER_NOT_CONFIGURED"
        assert FakeAsyncClient.calls == []

    asyncio.run(scenario())


def test_scanner_accepts_only_clean_verdict(monkeypatch):
    monkeypatch.setenv("ALLPHA_DOCUMENT_SCANNER_URL", "https://scanner.invalid/scan")
    FakeAsyncClient.response = FakeResponse(payload={"verdict": "clean"})

    asyncio.run(knowledge._scan(b"sample", "sample.txt", "text/plain"))
    assert len(FakeAsyncClient.calls) == 1
    assert FakeAsyncClient.calls[0][0] == "https://scanner.invalid/scan"


@pytest.mark.parametrize(
    "response",
    [
        FakeResponse(payload={"verdict": "malicious"}),
        FakeResponse(payload={"verdict": "unknown"}),
        FakeResponse(status_code=503, payload={"verdict": "clean"}),
        FakeResponse(payload=None, invalid_json=True),
    ],
)
def test_scanner_rejects_non_clean_or_untrusted_verdict(monkeypatch, response):
    monkeypatch.setenv("ALLPHA_DOCUMENT_SCANNER_URL", "https://scanner.invalid/scan")
    FakeAsyncClient.response = response

    async def scenario():
        with pytest.raises(HTTPException) as error:
            await knowledge._scan(b"sample", "sample.txt", "text/plain")
        assert error.value.status_code == 422
        assert error.value.detail["code"] == "MALWARE_SCAN_REJECTED"

    asyncio.run(scenario())


def test_scanner_transport_error_fails_closed(monkeypatch):
    monkeypatch.setenv("ALLPHA_DOCUMENT_SCANNER_URL", "https://scanner.invalid/scan")
    FakeAsyncClient.error = httpx.ConnectError("unreachable")

    async def scenario():
        with pytest.raises(HTTPException) as error:
            await knowledge._scan(b"sample", "sample.txt", "text/plain")
        assert error.value.status_code == 503
        assert error.value.detail["code"] == "SCANNER_UNAVAILABLE"

    asyncio.run(scenario())

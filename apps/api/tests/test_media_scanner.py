from __future__ import annotations

import pytest

from allpha_api import media_scanner


def _pins(monkeypatch):
    monkeypatch.setenv("ALLPHA_DOCUMENT_SCANNER_ID", "clamav-local")
    monkeypatch.setenv("ALLPHA_DOCUMENT_SCANNER_ENGINE_VERSION", "1.2.0")
    monkeypatch.setenv("ALLPHA_DOCUMENT_SCANNER_SIGNATURE_VERSION", "12345/Nov 24 2026")


def test_media_scanner_requires_deployment_pins(monkeypatch):
    for name in (
        "ALLPHA_DOCUMENT_SCANNER_ID",
        "ALLPHA_DOCUMENT_SCANNER_ENGINE_VERSION",
        "ALLPHA_DOCUMENT_SCANNER_SIGNATURE_VERSION",
    ):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(RuntimeError, match="IDENTITY_NOT_CONFIGURED"):
        media_scanner.local_scanner_identity_pins()


def test_media_scanner_rejects_engine_or_signature_drift(monkeypatch):
    _pins(monkeypatch)

    class FakeSocket:
        def __enter__(self): return self
        def __exit__(self, *args): return None
        def settimeout(self, _timeout): pass
        def sendall(self, _data): pass
        def recv(self, _size): return b"ClamAV 1.2.1/12345/Nov 24 2026\n"

    monkeypatch.setattr(media_scanner.socket, "create_connection", lambda *args, **kwargs: FakeSocket())
    with pytest.raises(RuntimeError, match="IDENTITY_MISMATCH"):
        media_scanner.scan_media_bytes(b"test", "clamav.internal", 3310)


def test_media_scanner_checks_pinned_identity_before_instream_and_returns_receipt(monkeypatch):
    _pins(monkeypatch)
    responses = [b"ClamAV 1.2.0/12345/Nov 24 2026\n", b"stream: OK\0"]
    sockets = []

    class FakeSocket:
        def __init__(self, response):
            self.response = response
            self.sent = []
        def __enter__(self): return self
        def __exit__(self, *args): return None
        def settimeout(self, _timeout): pass
        def sendall(self, data): self.sent.append(data)
        def recv(self, _size): return self.response

    def connect(*args, **kwargs):
        sock = FakeSocket(responses.pop(0))
        sockets.append(sock)
        return sock

    monkeypatch.setattr(media_scanner.socket, "create_connection", connect)
    receipt = media_scanner.scan_media_bytes(b"safe media", "clamav.internal", 3310)
    assert receipt["scanner_id"] == "clamav-local"
    assert receipt["engine_version"] == "1.2.0"
    assert receipt["signature_version"] == "12345/Nov 24 2026"
    assert sockets[0].sent == [b"zVERSION\0"]
    assert sockets[1].sent[0] == b"zINSTREAM\0"
    assert sockets[1].sent[-1] == b"\0\0\0\0"


def test_media_scanner_rejects_non_clean_verdict(monkeypatch):
    _pins(monkeypatch)
    responses = [b"ClamAV 1.2.0/12345/Nov 24 2026\n", b"stream: Eicar-Test-Signature FOUND\0"]

    class FakeSocket:
        def __init__(self, response): self.response = response
        def __enter__(self): return self
        def __exit__(self, *args): return None
        def settimeout(self, _timeout): pass
        def sendall(self, _data): pass
        def recv(self, _size): return self.response

    monkeypatch.setattr(media_scanner.socket, "create_connection", lambda *args, **kwargs: FakeSocket(responses.pop(0)))
    with pytest.raises(RuntimeError, match="NOT_CLEAN"):
        media_scanner.scan_media_bytes(b"infected", "clamav.internal", 3310)


def test_remote_media_scanner_uses_canonical_document_scanner_contract(monkeypatch):
    import asyncio
    from types import SimpleNamespace

    monkeypatch.setenv("ALLPHA_DOCUMENT_SCANNER_MODE", "remote")
    expected = {"scanner_id": "scanner-prod", "engine_version": "engine-1", "signature_version": "sig-1"}

    class FakeRemoteScanner:
        @classmethod
        def from_environment(cls):
            return cls()

        async def scan(self, data, *, filename, media_type):
            assert data == b"safe-media"
            assert filename == "photo.jpg"
            assert media_type == "image/jpeg"
            return SimpleNamespace(as_provenance=lambda: {**expected, "sha256": "a" * 64, "contract_version": "allpha.document-scan.v1"})

    monkeypatch.setattr(media_scanner, "RemoteDocumentScanner", FakeRemoteScanner)
    receipt = asyncio.run(media_scanner.scan_media_bytes_async(
        b"safe-media", filename="photo.jpg", media_type="image/jpeg",
    ))
    assert receipt["scanner_id"] == "scanner-prod"
    assert receipt["engine_version"] == "engine-1"
    assert receipt["signature_version"] == "sig-1"
    assert receipt["contract_version"] == "allpha.document-scan.v1"


def test_remote_media_scanner_maps_malware_to_terminal_rejection(monkeypatch):
    import asyncio
    from allpha_api.document_scanner import DocumentMalwareDetected

    monkeypatch.setenv("ALLPHA_DOCUMENT_SCANNER_MODE", "remote")

    class FakeRemoteScanner:
        @classmethod
        def from_environment(cls):
            return cls()

        async def scan(self, data, *, filename, media_type):
            raise DocumentMalwareDetected("malware")

    monkeypatch.setattr(media_scanner, "RemoteDocumentScanner", FakeRemoteScanner)
    with pytest.raises(ValueError, match="MEDIA_SCAN_REJECTED"):
        asyncio.run(media_scanner.scan_media_bytes_async(
            b"bad", filename="bad.mp4", media_type="video/mp4",
        ))


def test_remote_media_scanner_fails_closed_when_not_configured(monkeypatch):
    from allpha_api.document_scanner import DocumentScannerConfigurationError

    monkeypatch.setenv("ALLPHA_DOCUMENT_SCANNER_MODE", "remote")

    class FakeRemoteScanner:
        @classmethod
        def from_environment(cls):
            raise DocumentScannerConfigurationError("missing")

    monkeypatch.setattr(media_scanner, "RemoteDocumentScanner", FakeRemoteScanner)
    with pytest.raises(RuntimeError, match="REMOTE_SCANNER_NOT_CONFIGURED"):
        media_scanner.require_media_scanner_configuration()

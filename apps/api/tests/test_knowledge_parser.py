from __future__ import annotations

import pytest

from allpha_api.knowledge_parser import MAX_INPUT_BYTES, parse_document_isolated


def test_isolated_parser_extracts_utf8_text_with_provenance():
    pages = parse_document_isolated("notes.txt", "Halo Allpha\nBaris dua".encode())
    assert pages == [{"location": {"kind": "document", "index": 1}, "text": "Halo Allpha\nBaris dua"}]


def test_isolated_parser_rejects_unsupported_extension():
    with pytest.raises(ValueError, match="DOCUMENT_PARSE_REJECTED:UNSUPPORTED_FORMAT"):
        parse_document_isolated("payload.bin", b"data")


def test_isolated_parser_rejects_input_over_limit_before_spawning():
    with pytest.raises(ValueError, match="DOCUMENT_INPUT_LIMIT_EXCEEDED"):
        parse_document_isolated("notes.txt", b"x" * (MAX_INPUT_BYTES + 1))


def test_isolated_parser_rejects_unbounded_timeout_configuration():
    with pytest.raises(ValueError, match="PARSER_TIMEOUT_OUT_OF_RANGE"):
        parse_document_isolated("notes.txt", b"ok", timeout_seconds=31)

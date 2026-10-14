"""Bounded, isolated parser for untrusted knowledge documents.

Runs format parsers in a spawned child process with CPU/address-space limits.
This is defense in depth, not a replacement for malware scanning.
"""
from __future__ import annotations

import io
import multiprocessing
import os
import time
import zipfile
import xml.etree.ElementTree as ET
from typing import Any

MAX_INPUT_BYTES = 15 * 1024 * 1024
MAX_OUTPUT_CHARS = 8 * 1024 * 1024
MAX_PDF_PAGES = 500
MAX_DOCX_ENTRIES = 2_000
MAX_DOCX_UNCOMPRESSED = 50 * 1024 * 1024
PARSER_TIMEOUT_SECONDS = 12


def _parse_child(send_conn, filename: str, data: bytes) -> None:
    try:
        try:
            import resource
            resource.setrlimit(resource.RLIMIT_CPU, (6, 6))
            resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024, 512 * 1024 * 1024))
            resource.setrlimit(resource.RLIMIT_FSIZE, (MAX_OUTPUT_CHARS, MAX_OUTPUT_CHARS))
            resource.setrlimit(resource.RLIMIT_NOFILE, (32, 32))
        except (ImportError, AttributeError, OSError, ValueError):
            # Unsupported limits must not silently imply sandbox guarantees;
            # the parent still enforces a hard wall-clock deadline.
            pass
        ext = os.path.splitext(filename.lower())[1]
        if ext in (".txt", ".md"):
            pages = [{"location": {"kind": "document", "index": 1}, "text": data.decode("utf-8-sig")}]
        elif ext == ".pdf":
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(data), strict=True)
            if len(reader.pages) > MAX_PDF_PAGES:
                raise ValueError("PDF_PAGE_LIMIT_EXCEEDED")
            pages = [{"location": {"kind": "page", "index": i}, "text": page.extract_text() or ""} for i, page in enumerate(reader.pages, 1)]
        elif ext == ".docx":
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                infos = archive.infolist()
                if len(infos) > MAX_DOCX_ENTRIES or sum(i.file_size for i in infos) > MAX_DOCX_UNCOMPRESSED:
                    raise ValueError("DOCX_ARCHIVE_LIMIT_EXCEEDED")
                if any(i.file_size > max(1, i.compress_size) * 200 for i in infos):
                    raise ValueError("DOCX_COMPRESSION_RATIO_EXCEEDED")
                if "word/document.xml" not in archive.namelist():
                    raise ValueError("INVALID_DOCX")
                root = ET.fromstring(archive.read("word/document.xml"))
            ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
            pages = []
            for index, paragraph in enumerate(root.findall(".//w:p", ns), 1):
                text = "".join(paragraph.itertext()).strip()
                if text:
                    pages.append({"location": {"kind": "paragraph", "index": index}, "text": text})
        else:
            raise ValueError("UNSUPPORTED_FORMAT")
        if sum(len(str(page["text"])) for page in pages) > MAX_OUTPUT_CHARS:
            raise ValueError("PARSER_OUTPUT_LIMIT_EXCEEDED")
        send_conn.send(("ok", pages))
    except BaseException as exc:
        try:
            send_conn.send(("error", str(exc)[:160]))
        except (BrokenPipeError, EOFError, OSError):
            pass
    finally:
        send_conn.close()


def parse_document_isolated(filename: str, data: bytes, *, timeout_seconds: int = PARSER_TIMEOUT_SECONDS) -> list[dict[str, Any]]:
    if len(data) > MAX_INPUT_BYTES:
        raise ValueError("DOCUMENT_INPUT_LIMIT_EXCEEDED")
    if not 1 <= timeout_seconds <= 30:
        raise ValueError("PARSER_TIMEOUT_OUT_OF_RANGE")
    ctx = multiprocessing.get_context("spawn")
    receive, send = ctx.Pipe(duplex=False)
    process = ctx.Process(target=_parse_child, args=(send, filename, data), daemon=True)
    process.start()
    send.close()
    try:
        if not receive.poll(timeout_seconds):
            process.terminate()
            process.join(1)
            if process.is_alive():
                process.kill()
                process.join(1)
            raise TimeoutError("DOCUMENT_PARSER_TIMEOUT")
        kind, result = receive.recv()
        process.join(1)
        if process.is_alive():
            process.terminate()
            process.join(1)
        if kind != "ok":
            raise ValueError(f"DOCUMENT_PARSE_REJECTED:{result}")
        return result
    finally:
        receive.close()
        if process.is_alive():
            process.terminate()
            process.join(1)

"""Isolated image and subtitle media processor. Requires a reachable ClamAV daemon; fails closed otherwise."""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import re
import signal
import uuid
from io import BytesIO
from typing import Any
from urllib.parse import quote

import httpx
from PIL import Image, ImageOps, UnidentifiedImageError

from allpha_api.media_scanner import require_media_scanner_configuration, scan_media_bytes_async

log = logging.getLogger("allpha.content_media_worker")
Image.MAX_IMAGE_PIXELS = 40_000_000


def validate_subtitle_bytes(data: bytes, media_type: str) -> dict[str, Any]:
    if not data or len(data) > 10 * 1024 * 1024:
        raise ValueError("SUBTITLE_SIZE_INVALID")
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("SUBTITLE_UTF8_INVALID") from exc
    if "\x00" in text or re.search(r"<\s*(script|iframe|object|embed)\b", text, re.IGNORECASE):
        raise ValueError("SUBTITLE_ACTIVE_CONTENT_REJECTED")
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    time_pattern = re.compile(r"(?:(\d{2}):)?(\d{2}):(\d{2})[,.](\d{3})")

    def parse_time(value: str) -> int:
        match = time_pattern.fullmatch(value.strip())
        if not match:
            raise ValueError("SUBTITLE_TIMESTAMP_INVALID")
        hours = int(match.group(1) or 0)
        minutes = int(match.group(2))
        seconds = int(match.group(3))
        millis = int(match.group(4))
        if minutes > 59 or seconds > 59:
            raise ValueError("SUBTITLE_TIMESTAMP_INVALID")
        return ((hours * 60 + minutes) * 60 + seconds) * 1000 + millis

    def validate_timing(line: str) -> None:
        if "-->" not in line:
            raise ValueError("SUBTITLE_TIMING_MISSING")
        left, right = line.split("-->", 1)
        right_time = right.strip().split()[0]
        if parse_time(left) >= parse_time(right_time):
            raise ValueError("SUBTITLE_TIMING_ORDER_INVALID")

    if media_type == "text/vtt":
        lines = normalized.splitlines()
        first = next((line.strip() for line in lines if line.strip()), "")
        if first != "WEBVTT":
            raise ValueError("WEBVTT_HEADER_INVALID")
        timing_lines = [line for line in lines if "-->" in line]
        for line in timing_lines:
            validate_timing(line)
        subtitle_format = "webvtt"
        cue_count = len(timing_lines)
    elif media_type == "application/x-subrip":
        blocks = [block for block in re.split(r"\n\s*\n", normalized.strip()) if block.strip()]
        cue_count = 0
        for block in blocks:
            lines = [line.strip() for line in block.splitlines() if line.strip()]
            if len(lines) < 3 or not lines[0].isdigit():
                raise ValueError("SUBRIP_CUE_INVALID")
            validate_timing(lines[1])
            cue_count += 1
        subtitle_format = "subrip"
    else:
        raise ValueError("SUBTITLE_MEDIA_TYPE_UNSUPPORTED")
    if cue_count < 1:
        raise ValueError("SUBTITLE_CUES_MISSING")
    return {"format": subtitle_format, "cue_count": cue_count, "sha256": hashlib.sha256(data).hexdigest()}


class MediaWorker:
    def __init__(self) -> None:
        self.base = os.environ["SUPABASE_URL"].rstrip("/")
        self.key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ["SUPABASE_SECRET_KEY"]
        self.worker_id = f"content-media-{uuid.uuid4()}"
        self.batch_size = max(1, min(int(os.getenv("CONTENT_IMAGE_BATCH_SIZE", "1")), 10))
        self.lease_seconds = max(30, min(int(os.getenv("CONTENT_IMAGE_LEASE_SECONDS", "300")), 300))
        self.poll_seconds = max(1.0, float(os.getenv("CONTENT_IMAGE_POLL_SECONDS", "3")))
        self.scanner_mode = require_media_scanner_configuration()
        self.client = httpx.AsyncClient(trust_env=False, follow_redirects=False, 
            timeout=httpx.Timeout(60, connect=5),
            headers={"apikey": self.key, "Authorization": f"Bearer {self.key}",
                     "Content-Type": "application/json", "Accept": "application/json"},
        )
        self.stopping = False

    async def rpc(self, name: str, payload: dict[str, Any]) -> Any:
        response = await self.client.post(f"{self.base}/rest/v1/rpc/{name}", json=payload)
        response.raise_for_status()
        return response.json() if response.content else None

    async def scan(self, data: bytes, filename: str, media_type: str) -> dict[str, Any]:
        return await scan_media_bytes_async(data, filename=filename, media_type=media_type)

    def derivatives(self, data: bytes) -> list[tuple[str, bytes, int, int]]:
        try:
            with Image.open(BytesIO(data)) as source:
                source.verify()
            with Image.open(BytesIO(data)) as source:
                image = ImageOps.exif_transpose(source)
                image.load()
                if image.mode not in ("RGB", "RGBA"):
                    image = image.convert("RGBA" if "transparency" in image.info else "RGB")
                outputs: list[tuple[str, bytes, int, int]] = []
                for name, bound in (("display", 1600), ("thumbnail", 320)):
                    variant = image.copy()
                    variant.thumbnail((bound, bound), Image.Resampling.LANCZOS)
                    stream = BytesIO()
                    variant.save(stream, format="WEBP", quality=84, method=5, exact=True)
                    outputs.append((name, stream.getvalue(), variant.width, variant.height))
                return outputs
        except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
            raise ValueError("IMAGE_DECODE_REJECTED") from exc

    async def download_source(self, bucket: str, path: str) -> bytes:
        url = f"{self.base}/storage/v1/object/{quote(bucket, safe='')}/{quote(path, safe='/')}"
        response = await self.client.get(url)
        response.raise_for_status()
        return response.content

    async def upload_derivative(self, bucket: str, path: str, data: bytes) -> None:
        url = f"{self.base}/storage/v1/object/{quote(bucket, safe='')}/{quote(path, safe='/')}"
        response = await self.client.post(url, content=data, headers={
            "Content-Type": "image/webp", "x-upsert": "true",
        })
        response.raise_for_status()

    async def process(self, job: dict[str, Any]) -> None:
        token, job_id = str(job["lease_token"]), str(job["id"])
        payload = job.get("payload") or {}
        media_id = str(job["media_id"])
        try:
            source = await self.download_source(str(payload["bucket_id"]), str(payload["storage_path"]))
            if hashlib.sha256(source).hexdigest() != payload["sha256"]:
                raise ValueError("MEDIA_SOURCE_HASH_MISMATCH")
            await self.scan(source, str(payload.get("filename") or media_id), str(payload.get("media_type") or "application/octet-stream"))
            variants = await asyncio.to_thread(self.derivatives, source)
            derivative_records = []
            root = str(payload["storage_path"])
            for name, binary, width, height in variants:
                path = f"{root}.derived/{name}.webp"
                await self.upload_derivative(str(payload["bucket_id"]), path, binary)
                derivative_records.append({
                    "kind": name, "storage_path": path, "mime_type": "image/webp",
                    "size_bytes": len(binary), "sha256": hashlib.sha256(binary).hexdigest(),
                    "width": width, "height": height,
                })
            result = await self.rpc("complete_content_image_job", {
                "p_job_id": job_id, "p_lease_token": token, "p_media_id": media_id,
                "p_derivatives": derivative_records, "p_processing_version": 1,
            })
            if not isinstance(result, dict) or result.get("outcome") != "completed":
                raise ValueError("MEDIA_COMPLETION_LEASE_LOST")
        except Exception as exc:
            code = str(exc)[:80] if isinstance(exc, ValueError) else type(exc).__name__.upper()[:80]
            try:
                await self.rpc("fail_content_lifecycle_job", {
                    "p_job_id": job_id, "p_lease_token": token, "p_error_code": code,
                })
            except Exception:
                log.exception("could not record image job failure job_id=%s", job_id)
            log.exception("image processing failed job_id=%s media_id=%s", job_id, media_id)

    async def process_subtitle(self, job: dict[str, Any]) -> None:
        token, job_id = str(job["lease_token"]), str(job["id"])
        payload = job.get("payload") or {}
        media_id = str(job["media_id"])
        try:
            source = await self.download_source(str(payload["bucket_id"]), str(payload["storage_path"]))
            digest = hashlib.sha256(source).hexdigest()
            if digest != payload["sha256"]:
                raise ValueError("MEDIA_SOURCE_HASH_MISMATCH")
            scan_receipt = await self.scan(source, str(payload.get("filename") or media_id), str(payload["media_type"]))
            validation = await asyncio.to_thread(validate_subtitle_bytes, source, str(payload["media_type"]))
            receipt = {**scan_receipt, "validation": validation}
            result = await self.rpc("complete_content_subtitle_job", {
                "p_job_id": job_id, "p_lease_token": token, "p_media_id": media_id,
                "p_scan_receipt": receipt, "p_processing_version": 1,
            })
            if not isinstance(result, dict) or result.get("outcome") != "completed":
                raise ValueError("SUBTITLE_COMPLETION_LEASE_LOST")
        except Exception as exc:
            code = str(exc)[:80] if isinstance(exc, ValueError) else type(exc).__name__.upper()[:80]
            try:
                await self.rpc("fail_content_lifecycle_job", {
                    "p_job_id": job_id, "p_lease_token": token, "p_error_code": code,
                })
            except Exception:
                log.exception("could not record subtitle job failure job_id=%s", job_id)
            log.exception("subtitle validation failed job_id=%s media_id=%s", job_id, media_id)

    async def process_batch(self) -> int:
        # Binary image/video/audio jobs are owned by the Cloudinary transcode
        # dispatcher. This worker retains the independent subtitle validation job.
        subtitle_jobs = await self.rpc("claim_content_lifecycle_jobs", {
            "p_worker_id": self.worker_id, "p_limit": self.batch_size,
            "p_lease_seconds": self.lease_seconds, "p_job_type": "subtitle_validate",
        }) or []
        for job in subtitle_jobs:
            await self.process_subtitle(job)
        return len(subtitle_jobs)

    async def assert_schema_ready(self) -> None:
        result = await self.rpc("cloudinary_media_schema_readiness", {})
        if not isinstance(result, dict) or result.get("ready") is not True:
            raise RuntimeError("MEDIA_SCHEMA_NOT_READY")

    async def run(self) -> None:
        try:
            while not self.stopping:
                try:
                    count = await self.process_batch()
                except Exception:
                    log.exception("media worker poll failed")
                    count = 0
                if count == 0:
                    await asyncio.sleep(self.poll_seconds)
        finally:
            await self.client.aclose()


def enabled() -> bool:
    value = os.getenv("ALLPHA_CONTENT_MEDIA_WORKER_ENABLED", "false").strip().lower()
    if value not in {"true", "false"}:
        raise SystemExit("ALLPHA_CONTENT_MEDIA_WORKER_ENABLED must be true or false")
    if value != "true":
        return False
    try:
        scanner_mode = require_media_scanner_configuration()
    except RuntimeError as exc:
        raise SystemExit("Content image worker requires a configured remote scanner or explicitly enabled pinned ClamAV") from exc
    required = ("SUPABASE_URL",) + (("CLAMAV_HOST",) if scanner_mode == "clamd" else ())
    missing = [name for name in required if not os.getenv(name)]
    if not (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SECRET_KEY")):
        missing.append("SUPABASE_SERVICE_ROLE_KEY or SUPABASE_SECRET_KEY")
    if missing:
        raise SystemExit("Content image worker configuration missing: " + ", ".join(missing))
    return True


def main() -> None:
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
    if not enabled():
        log.info("Content image worker is disabled")
        return
    worker = MediaWorker()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: setattr(worker, "stopping", True))
    try:
        loop.run_until_complete(worker.assert_schema_ready())
        loop.run_until_complete(worker.run())
    finally:
        loop.close()


if __name__ == "__main__":
    main()

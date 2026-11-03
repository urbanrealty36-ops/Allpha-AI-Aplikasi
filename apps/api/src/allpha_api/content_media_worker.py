"""Isolated image media processor. Requires a reachable ClamAV daemon; fails closed otherwise."""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import signal
import socket
import struct
import uuid
from io import BytesIO
from typing import Any
from urllib.parse import quote

import httpx
from PIL import Image, ImageOps, UnidentifiedImageError

log = logging.getLogger("allpha.content_media_worker")
Image.MAX_IMAGE_PIXELS = 40_000_000


class MediaWorker:
    def __init__(self) -> None:
        self.base = os.environ["SUPABASE_URL"].rstrip("/")
        self.key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ["SUPABASE_SECRET_KEY"]
        self.worker_id = f"content-image-{uuid.uuid4()}"
        self.batch_size = max(1, min(int(os.getenv("CONTENT_IMAGE_BATCH_SIZE", "1")), 10))
        self.lease_seconds = max(30, min(int(os.getenv("CONTENT_IMAGE_LEASE_SECONDS", "300")), 300))
        self.poll_seconds = max(1.0, float(os.getenv("CONTENT_IMAGE_POLL_SECONDS", "3")))
        self.clamav_host = os.environ["CLAMAV_HOST"]
        self.clamav_port = int(os.getenv("CLAMAV_PORT", "3310"))
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(60, connect=5),
            headers={"apikey": self.key, "Authorization": f"Bearer {self.key}",
                     "Content-Type": "application/json", "Accept": "application/json"},
        )
        self.stopping = False

    async def rpc(self, name: str, payload: dict[str, Any]) -> Any:
        response = await self.client.post(f"{self.base}/rest/v1/rpc/{name}", json=payload)
        response.raise_for_status()
        return response.json() if response.content else None

    def scan(self, data: bytes) -> None:
        # ClamAV INSTREAM. No scanner means no derivative promotion and no ready state.
        with socket.create_connection((self.clamav_host, self.clamav_port), timeout=10) as sock:
            sock.settimeout(30)
            sock.sendall(b"zINSTREAM\0")
            for offset in range(0, len(data), 64 * 1024):
                chunk = data[offset:offset + 64 * 1024]
                sock.sendall(struct.pack("!I", len(chunk)) + chunk)
            sock.sendall(struct.pack("!I", 0))
            result = sock.recv(4096).decode("utf-8", "replace")
        if not result.strip().endswith("OK") or "FOUND" in result or "ERROR" in result:
            raise ValueError("MEDIA_SCAN_NOT_CLEAN")

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
            await asyncio.to_thread(self.scan, source)
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

    async def process_batch(self) -> int:
        jobs = await self.rpc("claim_content_lifecycle_jobs", {
            "p_worker_id": self.worker_id, "p_limit": self.batch_size,
            "p_lease_seconds": self.lease_seconds, "p_job_type": "image_process",
        }) or []
        for job in jobs:
            await self.process(job)
        return len(jobs)

    async def run(self) -> None:
        try:
            while not self.stopping:
                try:
                    count = await self.process_batch()
                except Exception:
                    log.exception("image worker poll failed")
                    count = 0
                if count == 0:
                    await asyncio.sleep(self.poll_seconds)
        finally:
            await self.client.aclose()


def main() -> None:
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
    worker = MediaWorker()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: setattr(worker, "stopping", True))
    try:
        loop.run_until_complete(worker.run())
    finally:
        loop.close()


if __name__ == "__main__":
    main()

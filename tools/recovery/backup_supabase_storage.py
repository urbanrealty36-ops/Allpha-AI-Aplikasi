#!/usr/bin/env python3
"""Create a checksum-verified archive of every object in a Supabase Storage inventory."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tarfile
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


CHUNK_SIZE = 1024 * 1024
MAX_ATTEMPTS = 5


def fail(message: str) -> None:
    raise SystemExit(message)


def load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"Cannot read JSON input {path}: {exc}")


def safe_object_path(bucket_id: str, name: str) -> str:
    if not bucket_id or not name or "\\" in bucket_id or "\\" in name:
        fail("Storage inventory contains an empty or unsafe bucket/object path.")
    if any(ord(ch) < 32 for ch in bucket_id + name):
        fail("Storage inventory contains control characters in an object path.")
    parts = PurePosixPath(name).parts
    if name.startswith("/") or any(part in ("", ".", "..") for part in parts):
        fail("Storage inventory contains a path traversal or absolute object path.")
    return f"objects/{bucket_id}/{name}"


def parse_size(metadata: dict) -> int | None:
    value = metadata.get("size")
    if value is None:
        return None
    try:
        size = int(value)
    except (TypeError, ValueError):
        fail("Storage inventory contains a non-numeric object size.")
    if size < 0:
        fail("Storage inventory contains a negative object size.")
    return size


def request_stream(url: str, api_key: str, destination: Path) -> tuple[int, str]:
    headers = {
        "apikey": api_key,
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/octet-stream",
        "User-Agent": "allpha-storage-recovery/1.0",
    }
    last_error = "unknown download error"
    for attempt in range(1, MAX_ATTEMPTS + 1):
        request = Request(url, headers=headers, method="GET")
        try:
            digest = hashlib.sha256()
            total = 0
            with urlopen(request, timeout=180) as response, destination.open("wb") as output:
                if response.status != 200:
                    fail(f"Storage download returned HTTP {response.status}.")
                while True:
                    chunk = response.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    output.write(chunk)
                    digest.update(chunk)
                    total += len(chunk)
            return total, digest.hexdigest()
        except HTTPError as exc:
            last_error = f"HTTP {exc.code}"
            if exc.code < 500 and exc.code != 429:
                fail(f"Storage object download failed with {last_error}.")
        except (URLError, TimeoutError, OSError) as exc:
            last_error = type(exc).__name__
        if attempt < MAX_ATTEMPTS:
            time.sleep(min(2 ** attempt, 20))
    fail(f"Storage object download failed after {MAX_ATTEMPTS} attempts ({last_error}).")


def parse_timestamp(value: str | None) -> int:
    if not value:
        return int(datetime.now(timezone.utc).timestamp())
    try:
        return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp())
    except ValueError:
        return int(datetime.now(timezone.utc).timestamp())


def verify_archive(archive_path: Path, expected_manifest: dict) -> None:
    expected = {
        f"objects/{item['bucket_id']}/{item['name']}": item
        for item in expected_manifest["objects"]
    }
    with tarfile.open(archive_path, mode="r:") as archive:
        members = {member.name: member for member in archive.getmembers()}
        if "manifest.json" not in members:
            fail("Storage archive is missing its embedded manifest.")
        embedded = json.load(archive.extractfile(members["manifest.json"]))
        if embedded != expected_manifest:
            fail("Embedded Storage manifest does not match the external manifest.")
        for member_name, item in expected.items():
            member = members.get(member_name)
            if member is None or not member.isfile() or member.size != item["size_bytes"]:
                fail("Storage archive member inventory/size does not match its manifest.")
            stream = archive.extractfile(member)
            digest = hashlib.sha256()
            total = 0
            while True:
                chunk = stream.read(CHUNK_SIZE)
                if not chunk:
                    break
                digest.update(chunk)
                total += len(chunk)
            if total != item["size_bytes"] or digest.hexdigest() != item["sha256"]:
                fail("Storage archive member checksum verification failed.")
        if len(members) != len(expected) + 1:
            fail("Storage archive contains unexpected or duplicate members.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inventory", required=True, type=Path)
    parser.add_argument("--buckets", required=True, type=Path)
    parser.add_argument("--archive", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--evidence", required=True, type=Path)
    parser.add_argument("--project-ref", required=True)
    args = parser.parse_args()

    api_key = os.environ.get("SUPABASE_STORAGE_BACKUP_KEY", "").strip()
    if not api_key:
        fail("SUPABASE_STORAGE_BACKUP_KEY is unavailable; Storage backup cannot proceed.")
    project_url = os.environ.get(
        "SUPABASE_URL", f"https://{args.project_ref}.supabase.co"
    ).rstrip("/")
    if not re.fullmatch(r"[a-z0-9]{20}", args.project_ref):
        fail("Invalid canonical Supabase project reference.")

    raw_objects = load_json(args.inventory)
    raw_buckets = load_json(args.buckets)
    if not isinstance(raw_objects, list) or not isinstance(raw_buckets, list):
        fail("Storage inventory and bucket metadata must be JSON arrays.")

    buckets = []
    for bucket in raw_buckets:
        bucket_id = str(bucket.get("id") or "")
        if not bucket_id:
            fail("Storage bucket inventory contains an empty ID.")
        buckets.append({
            "id": bucket_id,
            "name": str(bucket.get("name") or bucket_id),
            "public": bool(bucket.get("public", False)),
            "file_size_limit": bucket.get("file_size_limit"),
            "allowed_mime_types": bucket.get("allowed_mime_types"),
        })

    objects = []
    total_bytes = 0
    args.archive.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.evidence.parent.mkdir(parents=True, exist_ok=True)

    try:
        with tarfile.open(args.archive, mode="w:", format=tarfile.PAX_FORMAT) as archive:
            for index, row in enumerate(raw_objects, start=1):
                bucket_id = str(row.get("bucket_id") or "")
                name = str(row.get("name") or "")
                member_name = safe_object_path(bucket_id, name)
                metadata = row.get("metadata") or {}
                if not isinstance(metadata, dict):
                    fail("Storage object metadata is not a JSON object.")
                expected_size = parse_size(metadata)
                encoded_bucket = quote(bucket_id, safe="")
                encoded_name = quote(name, safe="/")
                url = f"{project_url}/storage/v1/object/authenticated/{encoded_bucket}/{encoded_name}"

                with tempfile.NamedTemporaryFile(prefix="allpha-storage-", delete=False) as temp:
                    temp_path = Path(temp.name)
                try:
                    size, sha256 = request_stream(url, api_key, temp_path)
                    if expected_size is not None and size != expected_size:
                        fail("Downloaded Storage object size does not match database metadata.")
                    content_type = str(metadata.get("mimetype") or "application/octet-stream")
                    item = {
                        "bucket_id": bucket_id,
                        "name": name,
                        "size_bytes": size,
                        "sha256": sha256,
                        "content_type": content_type,
                        "created_at": row.get("created_at"),
                        "updated_at": row.get("updated_at"),
                    }
                    info = tarfile.TarInfo(member_name)
                    info.size = size
                    info.mode = 0o600
                    info.mtime = parse_timestamp(row.get("updated_at"))
                    with temp_path.open("rb") as source:
                        archive.addfile(info, source)
                    objects.append(item)
                    total_bytes += size
                finally:
                    temp_path.unlink(missing_ok=True)

                if index % 50 == 0 or index == len(raw_objects):
                    print(f"Storage backup progress: {index}/{len(raw_objects)} objects")

            manifest = {
                "project_ref": args.project_ref,
                "captured_at_utc": datetime.now(timezone.utc).isoformat(),
                "bucket_count": len(buckets),
                "object_count": len(objects),
                "total_bytes": total_bytes,
                "buckets": buckets,
                "objects": objects,
            }
            payload = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
            manifest_info = tarfile.TarInfo("manifest.json")
            manifest_info.size = len(payload)
            manifest_info.mode = 0o600
            manifest_info.mtime = int(datetime.now(timezone.utc).timestamp())
            import io
            archive.addfile(manifest_info, io.BytesIO(payload))

        external_payload = json.dumps(manifest, indent=2, sort_keys=True)
        args.manifest.write_text(external_payload + "\n", encoding="utf-8")
        verify_archive(args.archive, manifest)

        archive_hash = hashlib.sha256()
        with args.archive.open("rb") as source:
            for chunk in iter(lambda: source.read(CHUNK_SIZE), b""):
                archive_hash.update(chunk)
        evidence = {
            "storage_objects_included": True,
            "storage_archive_file": args.archive.name,
            "storage_archive_sha256": archive_hash.hexdigest(),
            "storage_archive_size_bytes": args.archive.stat().st_size,
            "storage_manifest_file": args.manifest.name,
            "storage_manifest_sha256": hashlib.sha256(args.manifest.read_bytes()).hexdigest(),
            "storage_bucket_count": len(buckets),
            "storage_object_count": len(objects),
            "storage_total_bytes": total_bytes,
            "storage_archive_integrity_verified": True,
        }
        args.evidence.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(evidence, indent=2))
    except Exception:
        args.archive.unlink(missing_ok=True)
        raise


if __name__ == "__main__":
    main()

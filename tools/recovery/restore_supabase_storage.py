#!/usr/bin/env python3
"""Restore a Supabase Storage archive into an isolated local Supabase Storage API."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tarfile
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen

from backup_supabase_storage import verify_archive


CHUNK_SIZE = 1024 * 1024


def fail(message: str) -> None:
    raise SystemExit(message)


def load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"Cannot read JSON input {path}: {exc}")


def api_request(
    api_url: str,
    api_key: str,
    path: str,
    *,
    method: str = "GET",
    payload: bytes | None = None,
    content_type: str = "application/json",
    extra_headers: dict | None = None,
):
    headers = {
        "apikey": api_key,
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
        "User-Agent": "allpha-storage-recovery-restore/1.0",
    }
    if payload is not None:
        headers["Content-Type"] = content_type
        headers["Content-Length"] = str(len(payload))
    if extra_headers:
        headers.update(extra_headers)
    request = Request(f"{api_url.rstrip('/')}{path}", data=payload, headers=headers, method=method)
    return urlopen(request, timeout=180)


def ensure_bucket(api_url: str, api_key: str, bucket: dict) -> None:
    bucket_id = quote(str(bucket["id"]), safe="")
    body = {
        "id": bucket["id"],
        "name": bucket.get("name") or bucket["id"],
        "public": bool(bucket.get("public", False)),
        "file_size_limit": bucket.get("file_size_limit"),
        "allowed_mime_types": bucket.get("allowed_mime_types"),
    }
    payload = json.dumps(body).encode()
    try:
        with api_request(
            api_url, api_key, "/storage/v1/bucket", method="POST", payload=payload
        ) as response:
            if response.status not in (200, 201):
                fail(f"Local Storage bucket create returned HTTP {response.status}.")
            return
    except HTTPError as exc:
        if exc.code != 409:
            fail(f"Local Storage bucket create failed with HTTP {exc.code}.")

    # A local Supabase stack may already contain a bucket from config.toml.
    try:
        with api_request(
            api_url, api_key, f"/storage/v1/bucket/{bucket_id}", method="PUT", payload=payload
        ) as response:
            if response.status not in (200, 201):
                fail(f"Local Storage bucket update returned HTTP {response.status}.")
    except HTTPError as exc:
        fail(f"Local Storage bucket already exists but could not be reconciled (HTTP {exc.code}).")


def upload_and_verify_object(
    api_url: str,
    api_key: str,
    archive: tarfile.TarFile,
    item: dict,
) -> None:
    bucket = quote(item["bucket_id"], safe="")
    name = quote(item["name"], safe="/")
    member_name = f"objects/{item['bucket_id']}/{item['name']}"
    member = archive.getmember(member_name)
    source = archive.extractfile(member)
    if source is None:
        fail("Storage archive member could not be opened.")

    # A single object is buffered at a time; the full archive is never loaded into memory.
    payload = source.read()
    if len(payload) != item["size_bytes"]:
        fail("Storage archive object size changed before restore.")
    if hashlib.sha256(payload).hexdigest() != item["sha256"]:
        fail("Storage archive object checksum changed before restore.")

    object_path = f"/storage/v1/object/{bucket}/{name}"
    try:
        with api_request(
            api_url,
            api_key,
            object_path,
            method="POST",
            payload=payload,
            content_type=item.get("content_type") or "application/octet-stream",
            extra_headers={"x-upsert": "true"},
        ) as response:
            if response.status not in (200, 201):
                fail(f"Local Storage object upload returned HTTP {response.status}.")
    except HTTPError as exc:
        fail(f"Local Storage object upload failed with HTTP {exc.code}.")

    authenticated_path = f"/storage/v1/object/authenticated/{bucket}/{name}"
    request = Request(
        f"{api_url.rstrip('/')}{authenticated_path}",
        headers={
            "apikey": api_key,
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/octet-stream",
            "User-Agent": "allpha-storage-recovery-restore/1.0",
        },
        method="GET",
    )
    digest = hashlib.sha256()
    total = 0
    try:
        with urlopen(request, timeout=180) as response:
            if response.status != 200:
                fail(f"Local Storage object verification returned HTTP {response.status}.")
            while True:
                chunk = response.read(CHUNK_SIZE)
                if not chunk:
                    break
                digest.update(chunk)
                total += len(chunk)
    except (HTTPError, URLError, TimeoutError) as exc:
        fail(f"Local Storage object could not be read after restore ({type(exc).__name__}).")

    if total != item["size_bytes"] or digest.hexdigest() != item["sha256"]:
        fail("Restored local Storage object checksum verification failed.")


def compare_database_inventory(expected_manifest: dict, restored_inventory: list) -> None:
    expected = {
        (item["bucket_id"], item["name"]): (item["size_bytes"], item["content_type"])
        for item in expected_manifest["objects"]
    }
    actual = {}
    for row in restored_inventory:
        bucket_id = str(row.get("bucket_id") or "")
        name = str(row.get("name") or "")
        size = row.get("size_bytes")
        content_type = row.get("content_type") or "application/octet-stream"
        try:
            size = int(size) if size is not None else None
        except (TypeError, ValueError):
            fail("Restored Storage metadata contains a non-numeric object size.")
        actual[(bucket_id, name)] = (size, content_type)
    if actual != expected:
        missing = len(set(expected) - set(actual))
        extra = len(set(actual) - set(expected))
        changed = sum(1 for key in set(expected) & set(actual) if expected[key] != actual[key])
        fail(
            "Restored database Storage metadata does not match the backup manifest "
            f"(missing={missing}, extra={extra}, changed={changed})."
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--buckets", required=True, type=Path)
    parser.add_argument("--restored-inventory", required=True, type=Path)
    parser.add_argument("--evidence", required=True, type=Path)
    parser.add_argument("--api-url", required=True)
    parser.add_argument("--service-role-key", required=True)
    args = parser.parse_args()

    parsed = urlparse(args.api_url)
    if parsed.scheme != "http" or parsed.hostname not in ("127.0.0.1", "localhost"):
        fail("Storage restore API must be a loopback-only local Supabase endpoint.")
    if not args.service_role_key.strip():
        fail("Local Supabase service role key is unavailable.")

    manifest = load_json(args.manifest)
    buckets = load_json(args.buckets)
    restored_inventory = load_json(args.restored_inventory)
    if not isinstance(buckets, list) or not isinstance(restored_inventory, list):
        fail("Bucket metadata and restored Storage inventory must be JSON arrays.")

    verify_archive(args.archive, manifest)
    compare_database_inventory(manifest, restored_inventory)

    for bucket in buckets:
        ensure_bucket(args.api_url, args.service_role_key, bucket)

    with tarfile.open(args.archive, mode="r:") as archive:
        for index, item in enumerate(manifest["objects"], start=1):
            upload_and_verify_object(args.api_url, args.service_role_key, archive, item)
            if index % 50 == 0 or index == len(manifest["objects"]):
                print(f"Storage restore progress: {index}/{len(manifest['objects'])} objects")

    evidence = {
        "storage_restore_tested": True,
        "storage_restore_target": "isolated local Supabase Storage API (loopback only)",
        "storage_metadata_reconciled": True,
        "storage_archive_integrity_verified": True,
        "storage_object_count": len(manifest["objects"]),
        "storage_total_bytes": manifest["total_bytes"],
        "storage_objects_uploaded_and_read_back": len(manifest["objects"]),
        "storage_restore_checksums_verified": True,
    }
    args.evidence.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    main()

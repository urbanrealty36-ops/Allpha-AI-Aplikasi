"""Isolated full-lifecycle ENG-P13 journey; no production records or real user session."""
from __future__ import annotations

import uuid
from copy import deepcopy

from fastapi import Request
from fastapi.testclient import TestClient

from allpha_api import content_api
from allpha_api.auth import current_user
from allpha_api.main import app


def test_content_media_moderation_publish_journey_isolated(monkeypatch):
    """Exercise create -> upload -> preview -> submit -> approve -> public feed."""
    client = TestClient(app)
    owner_id = "eng-p13-test-owner"
    active_owner_id = {"value": owner_id}
    content_rows: dict[str, dict] = {}
    media_rows: dict[str, dict] = {}
    storage_operations: list[tuple[str, str]] = []

    async def fake_user(request: Request):
        request.state.supabase_access_token = "isolated-test-token"
        request.state.user_id = active_owner_id["value"]
        return {"id": active_owner_id["value"], "email": "eng-p13@example.invalid"}

    def matches(row, params):
        for key, value in params.items():
            if key == "select" or key == "order" or key == "limit":
                continue
            if key == "id" and value.startswith("eq.") and row.get("id") != value[3:]:
                return False
            if key == "owner_id" and value.startswith("eq.") and row.get("owner_id") != value[3:]:
                return False
            if key == "content_id" and value.startswith("eq.") and row.get("content_id") != value[3:]:
                return False
            if key == "content_id" and value.startswith("in.("):
                ids = value[4:-1].split(",")
                if row.get("content_id") not in ids:
                    return False
            if key == "status" and value.startswith("eq.") and row.get("status") != value[3:]:
                return False
            if key == "status" and value.startswith("in.(") and row.get("status") not in value[4:-1].split(","):
                return False
            if key == "moderation_status" and value.startswith("eq.") and row.get("moderation_status") != value[3:]:
                return False
            if key == "visibility" and value.startswith("eq.") and row.get("visibility") != value[3:]:
                return False
            if key == "version" and value.startswith("eq.") and str(row.get("version")) != value[3:]:
                return False
        return True

    async def fake_db(method, table, *, params=None, body=None, prefer=None):
        params = params or {}
        store = content_rows if table == "content_items" else media_rows
        if method == "POST":
            row = deepcopy(body or {})
            row.setdefault("id", str(uuid.uuid4()))
            row.setdefault("created_at", "2026-10-18T00:00:00Z")
            row.setdefault("updated_at", "2026-10-18T00:00:00Z")
            store[row["id"]] = row
            return [deepcopy(row)]
        if method == "GET":
            rows = [deepcopy(row) for row in store.values() if matches(row, params)]
            if params.get("limit"):
                rows = rows[: int(params["limit"])]
            return rows
        if method == "PATCH":
            rows = []
            for key, row in list(store.items()):
                if matches(row, params):
                    updated = {**row, **deepcopy(body or {}), "updated_at": "2026-10-18T00:01:00Z"}
                    store[key] = updated
                    rows.append(deepcopy(updated))
            return rows
        if method == "DELETE":
            deleted = []
            for key, row in list(store.items()):
                if matches(row, params):
                    deleted.append(store.pop(key))
            return deleted
        raise AssertionError(f"Unexpected database operation: {method} {table}")

    async def fake_storage(method, path, *, data=None, media_type=None):
        storage_operations.append((method, path))
        class Response:
            status_code = 200
        return Response()

    async def fake_signed(path, *, expires_in=300):
        assert expires_in == 300
        return "https://storage.example.test/private-signed/" + path

    async def fake_audit(*args, **kwargs):
        return None

    monkeypatch.setattr(content_api, "_server_db", fake_db)
    monkeypatch.setattr(content_api, "_storage", fake_storage)
    monkeypatch.setattr(content_api, "_signed_media_preview_url", fake_signed)
    monkeypatch.setattr(content_api, "write_operator_audit", fake_audit)
    app.dependency_overrides[current_user] = fake_user
    try:
        created = client.post("/v1/content", json={
            "body": "ENG-P13 isolated acceptance fixture",
            "visibility": "public",
            "content_type": "image",
        })
        assert created.status_code == 201, created.text
        item = created.json()["item"]
        content_id = item["id"]
        assert item["owner_id"] == owner_id
        assert item["status"] == "draft"

        uploaded = client.post(
            f"/v1/content/{content_id}/media",
            files={"file": ("acceptance.jpg", bytes.fromhex("ffd8ff") + b"test-image-bytes", "image/jpeg")},
        )
        assert uploaded.status_code == 201, uploaded.text
        media_id = uploaded.json()["item"]["id"]
        assert uploaded.json()["content"]["version"] == 2
        assert any(method == "POST" for method, _ in storage_operations)

        preview = client.get(f"/v1/content/{content_id}/preview")
        assert preview.status_code == 200, preview.text
        assert preview.json()["media"][0]["preview_url"].startswith("https://storage.example.test/private-signed/")
        assert preview.json()["preview_expires_in"] == 300

        submitted = client.post(f"/v1/content/{content_id}/publish")
        assert submitted.status_code == 200, submitted.text
        assert submitted.json()["item"]["status"] == "review"
        assert submitted.json()["item"]["moderation_status"] == "pending"

        review_request = Request({
            "type": "http", "method": "POST", "path": f"/v1/content/admin/{content_id}/review",
            "headers": [], "query_string": b"",
        })
        reviewed = __import__("asyncio").run(content_api.review_content(
            uuid.UUID(content_id),
            content_api.ContentReview(decision="approve", expected_version=3, reason="Fixture approved in isolated test"),
            review_request,
            operator={"id": "eng-p13-test-operator"},
        ))
        assert reviewed["item"]["status"] == "published"
        assert reviewed["item"]["moderation_status"] == "approved"
        assert reviewed["item"]["version"] == 4

        feed = client.get("/v1/content/feed/public")
        assert feed.status_code == 200, feed.text
        visible = [row for row in feed.json()["items"] if row["id"] == content_id]
        assert len(visible) == 1
        assert visible[0]["media"][0]["id"] == media_id
        assert visible[0]["media"][0]["preview_url"].startswith("https://storage.example.test/private-signed/")
        assert feed.json()["media_preview_expires_in"] == 300

        # Owner isolation uses an isolated fixture identity, never a real account.
        active_owner_id["value"] = "eng-p13-foreign-owner"
        foreign_preview = client.get(f"/v1/content/{content_id}/preview")
        assert foreign_preview.status_code == 404
        foreign_publish = client.post(f"/v1/content/{content_id}/publish")
        assert foreign_publish.status_code == 404
        active_owner_id["value"] = owner_id

        failed = client.post("/v1/content", json={
            "body": "Isolated retry contract",
            "visibility": "private",
            "content_type": "text",
        })
        assert failed.status_code == 201, failed.text
        failed_id = failed.json()["item"]["id"]
        content_rows[failed_id]["status"] = "failed"
        content_rows[failed_id]["moderation_status"] = "failed"
        retried = client.post(f"/v1/content/{failed_id}/retry")
        assert retried.status_code == 200, retried.text
        assert retried.json()["item"]["status"] == "draft"
        assert retried.json()["item"]["moderation_status"] == "not_submitted"
    finally:
        app.dependency_overrides.clear()

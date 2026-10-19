"""Isolated client→API→data-adapter lifecycle for ENG-P14.

The adapter is an in-process, test-only store. No Supabase credentials, live
network, Production rows, or real user identity are used by this test.
This proves route/data-contract integration only, not configured dependency
or Production integration.
"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import Request
from fastapi.testclient import TestClient

from allpha_api import feed_api
from allpha_api.auth import current_user
from allpha_api.main import app

VIEWER = "isolated-eng-p14-viewer"
CONTENT_ID = "00000000-0000-0000-0000-0000000000a1"
OWNER = "isolated-eng-p14-author"


def _test_identity(request: Request):
    request.state.supabase_access_token = "isolated-test-token-not-valid-outside-tests"
    request.state.user_id = VIEWER
    return {"id": VIEWER, "email": "eng-p14-viewer@example.invalid"}


def test_client_api_data_adapter_feed_interaction_lifecycle(monkeypatch):
    """Exercise feed read and interaction writes through real FastAPI routing."""
    now = datetime.now(timezone.utc).isoformat()
    content = {
        "id": CONTENT_ID, "owner_id": OWNER, "body": "isolated integration fixture",
        "content_type": "text", "visibility": "public", "status": "published",
        "moderation_status": "approved", "version": 1, "created_at": now,
        "updated_at": now, "published_at": now,
    }
    tables = {
        "content_reactions": [],
        "content_saves": [],
        "content_comments": [],
        "content_shares": [],
        "content_reports": [],
        "feed_preferences": [],
    }
    writes = []

    async def isolated_data_adapter(method, table, *, params=None, body=None, prefer=None):
        params = params or {}
        assert table in {
            "content_items", "social_edges", "user_interests", "content_reactions",
            "content_saves", "content_comments", "content_shares", "content_reports",
            "feed_preferences", "content_mentions", "content_media",
        }, f"unexpected data access: {method} {table}"

        if table == "content_items":
            return [content] if params.get("id", "").endswith(CONTENT_ID) or not params.get("id") else []
        if table == "social_edges":
            return []
        if table == "user_interests":
            return []
        if table == "content_media":
            return []
        if table == "content_mentions":
            return []

        rows = tables.setdefault(table, [])
        if method == "GET":
            result = rows
            for key, expected in params.items():
                if key in {"select", "order", "limit"} or expected.startswith("in.("):
                    continue
                if expected.startswith("eq."):
                    value = expected[3:]
                    result = [row for row in result if str(row.get(key)) == value]
            if params.get("status") == "eq.pending":
                result = [row for row in result if row.get("status") == "pending"]
            return [dict(row) for row in result]

        if method == "POST":
            row = dict(body or {})
            row.setdefault("id", f"isolated-{table}-{len(rows) + 1}")
            row.setdefault("created_at", now)
            row.setdefault("updated_at", now)
            if table == "content_reports":
                row.setdefault("status", "pending")
            if table == "content_comments":
                row.setdefault("status", "visible")
            rows.append(row)
            writes.append((table, dict(row)))
            return [dict(row)]

        if method == "DELETE":
            removed = []
            kept = []
            for row in rows:
                matches = all(
                    key in {"select"} or not expected.startswith("eq.")
                    or str(row.get(key)) == expected[3:]
                    for key, expected in params.items()
                )
                (removed if matches else kept).append(row)
            rows[:] = kept
            return removed

        raise AssertionError(f"unexpected method {method} for {table}")

    monkeypatch.setattr(feed_api, "_server_db", isolated_data_adapter)
    monkeypatch.setattr(feed_api, "_signed_media_preview_url", lambda path, *, expires_in=300: None)
    app.dependency_overrides[current_user] = _test_identity
    try:
        client = TestClient(app)
        feed = client.get("/v1/feed?mode=recent&limit=10")
        assert feed.status_code == 200, feed.text
        assert [item["id"] for item in feed.json()["items"]] == [CONTENT_ID]

        reaction = client.put(f"/v1/feed/{CONTENT_ID}/reaction", json={"reaction": "like"})
        assert reaction.status_code == 200, reaction.text
        assert reaction.json()["reaction"]["actor_user_id"] == VIEWER

        saved = client.put(f"/v1/feed/{CONTENT_ID}/save")
        assert saved.status_code == 200 and saved.json()["saved"] is True

        comment = client.post(f"/v1/feed/{CONTENT_ID}/comments", json={"body": "  test-only comment  "})
        assert comment.status_code == 201, comment.text
        assert comment.json()["comment"]["body"] == "test-only comment"

        shared = client.post(f"/v1/feed/{CONTENT_ID}/share", json={"share_target": "copy_link"})
        assert shared.status_code == 201, shared.text
        assert shared.json()["share_url"] == f"https://allpha.web.id/feed?content={CONTENT_ID}"

        report = client.post(f"/v1/feed/{CONTENT_ID}/report", json={"reason": "spam", "details": "isolated test"})
        assert report.status_code == 201, report.text
        assert report.json()["report"]["status"] == "pending"

        comments = client.get(f"/v1/feed/{CONTENT_ID}/comments")
        assert comments.status_code == 200, comments.text
        assert len(comments.json()["items"]) == 1

        item = client.get(f"/v1/feed/item/{CONTENT_ID}")
        assert item.status_code == 200, item.text
        assert item.json()["item"]["engagement"] == {
            "likes": 1, "comments": 1, "saves": 1, "shares": 1,
        }
        assert len(writes) == 5
        assert {table for table, _ in writes} == {
            "content_reactions", "content_saves", "content_comments",
            "content_shares", "content_reports",
        }
        assert all(row.get("actor_user_id", row.get("reporter_user_id")) == VIEWER for _, row in writes)
    finally:
        app.dependency_overrides.pop(current_user, None)

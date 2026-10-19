from datetime import datetime, timedelta, timezone

from fastapi import Request
from fastapi.testclient import TestClient

from allpha_api import stories_api
from allpha_api.auth import current_user
from allpha_api.main import app

client = TestClient(app)
OWNER = "isolated-eng-p16-owner"
OTHER = "isolated-eng-p16-other"
STORY_ID = "00000000-0000-0000-0000-000000000016"


def _auth(user_id=OWNER):
    async def dependency(request: Request):
        request.state.user_id = user_id
        request.state.supabase_access_token = "test-only"
        return {"id": user_id, "email": "eng-p16@example.invalid"}
    return dependency


def test_stories_routes_require_authentication():
    assert client.get("/v1/stories").status_code == 401
    assert client.get("/v1/stories/mine").status_code == 401
    assert client.post("/v1/stories", json={"body": "hello"}).status_code == 401


def test_create_story_uses_canonical_content_registry_and_server_owner(monkeypatch):
    calls = []

    async def fake_db(method, table, *, params=None, body=None, prefer=None):
        calls.append((method, table, params, body, prefer))
        return [{**body, "id": STORY_ID, "created_at": datetime.now(timezone.utc).isoformat()}]

    monkeypatch.setattr(stories_api, "_server_db", fake_db)
    app.dependency_overrides[current_user] = _auth()
    try:
        response = client.post("/v1/stories", json={
            "body": "  Moment  ", "visibility": "followers", "expires_after_hours": 12,
        })
    finally:
        app.dependency_overrides.pop(current_user, None)
    assert response.status_code == 201, response.text
    row = calls[0][3]
    assert calls[0][1] == "content_items"
    assert row["owner_id"] == OWNER
    assert row["content_type"] == "story"
    assert row["body"] == "Moment"
    assert row["status"] == "draft"
    assert row["moderation_status"] == "not_submitted"
    assert row["provenance"]["stories"]["expires_after_hours"] == 12


def test_story_creation_rejects_client_owned_fields(monkeypatch):
    app.dependency_overrides[current_user] = _auth()
    try:
        response = client.post("/v1/stories", json={
            "body": "Moment", "owner_id": OTHER, "status": "published",
            "moderation_status": "approved", "expires_at": "2099-01-01T00:00:00Z",
        })
    finally:
        app.dependency_overrides.pop(current_user, None)
    assert response.status_code == 422


def test_story_ttl_is_bounded():
    app.dependency_overrides[current_user] = _auth()
    try:
        low = client.post("/v1/stories", json={"body": "Moment", "expires_after_hours": 0})
        high = client.post("/v1/stories", json={"body": "Moment", "expires_after_hours": 169})
    finally:
        app.dependency_overrides.pop(current_user, None)
    assert low.status_code == 422
    assert high.status_code == 422


def test_active_story_feed_enforces_expiry_and_audience(monkeypatch):
    now = datetime.now(timezone.utc)
    rows = [
        {"id": STORY_ID, "owner_id": OWNER, "body": "active", "content_type": "story",
         "visibility": "public", "status": "published", "moderation_status": "approved",
         "version": 2, "published_at": now.isoformat(), "expires_at": (now + timedelta(hours=2)).isoformat()},
        {"id": "00000000-0000-0000-0000-000000000017", "owner_id": OTHER, "body": "expired",
         "content_type": "story", "visibility": "public", "status": "published",
         "moderation_status": "approved", "version": 1, "published_at": now.isoformat(),
         "expires_at": (now - timedelta(seconds=1)).isoformat()},
    ]
    calls = []

    async def fake_db(method, table, *, params=None, body=None, prefer=None):
        calls.append((method, table, params, body))
        if table == "content_items" and method == "GET":
            return rows
        if table == "content_media":
            return []
        if table == "content_items" and method == "PATCH":
            return [{"id": STORY_ID}]
        raise AssertionError((method, table))

    async def fake_edges(user_id):
        assert user_id == OWNER
        return set(), set()

    monkeypatch.setattr(stories_api, "_server_db", fake_db)
    monkeypatch.setattr(stories_api, "_edges", fake_edges)
    app.dependency_overrides[current_user] = _auth()
    try:
        response = client.get("/v1/stories")
    finally:
        app.dependency_overrides.pop(current_user, None)
    assert response.status_code == 200, response.text
    assert [item["id"] for item in response.json()["items"]] == [STORY_ID]
    feed_query = next(params for method, table, params, _ in calls if method == "GET" and table == "content_items" and params.get("status") == "eq.published")
    assert feed_query["expires_at"].startswith("gt.")
    assert feed_query["moderation_status"] == "eq.approved"


def test_story_delete_is_owner_scoped_and_compare_and_set(monkeypatch):
    calls = []

    async def fake_db(method, table, *, params=None, body=None, prefer=None):
        calls.append((method, table, params, body))
        if method == "GET":
            return [{"id": STORY_ID, "owner_id": OWNER, "content_type": "story", "status": "published", "version": 2}]
        return [{"id": STORY_ID, "status": "archived", **(body or {})}]

    monkeypatch.setattr(stories_api, "_server_db", fake_db)
    app.dependency_overrides[current_user] = _auth()
    try:
        response = client.delete(f"/v1/stories/{STORY_ID}")
    finally:
        app.dependency_overrides.pop(current_user, None)
    assert response.status_code == 200, response.text
    assert calls[0][2]["owner_id"] == f"eq.{OWNER}"
    assert calls[1][2]["version"] == "eq.2"
    assert calls[1][3]["status"] == "archived"


def test_migration_has_server_expiry_trigger_and_index():
    from pathlib import Path
    migration = (Path(__file__).parents[1] / "supabase/migrations/20261019100000_eng_p16_stories_expiry.sql").read_text()
    assert "content_items_story_expiry" in migration
    assert "expires_at" in migration
    assert "content_stories_active_expiry_idx" in migration
    assert "content_items" in migration

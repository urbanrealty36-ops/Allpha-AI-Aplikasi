from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import Request
from fastapi.testclient import TestClient

from allpha_api import feed_api
from allpha_api.auth import current_user
from allpha_api.main import app


def _fixture_user(request: Request):
    request.state.supabase_access_token = "isolated-eng-p14-token"
    request.state.user_id = "eng-p14-viewer"
    return {"id": "eng-p14-viewer", "email": "eng-p14@example.invalid"}


def test_feed_cursor_round_trip_and_rejects_tampering():
    as_of = datetime(2026, 10, 19, 12, 0, tzinfo=timezone.utc)
    cursor = feed_api._cursor_encode(40, as_of)
    offset, decoded = feed_api._cursor_decode(cursor)
    assert offset == 40
    assert decoded == as_of
    client = TestClient(app)
    app.dependency_overrides[current_user] = _fixture_user
    app.dependency_overrides[feed_api.optional_current_user] = _fixture_user
    try:
        response = client.get("/v1/feed?cursor=not-a-valid-cursor")
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "FEED_CURSOR_INVALID"
    finally:
        app.dependency_overrides.clear()


def test_feed_ranks_followed_creator_and_applies_block_mute_filters(monkeypatch):
    now = datetime.now(timezone.utc)
    followed_owner = "eng-p14-followed"
    fresh_owner = "eng-p14-fresh"
    hidden_owner = "eng-p14-hidden"
    content_rows = [
        {"id": "00000000-0000-0000-0000-000000000001", "owner_id": followed_owner, "body": "followed",
         "content_type": "text", "visibility": "public", "status": "published", "moderation_status": "approved",
         "version": 1, "created_at": now.isoformat(), "updated_at": now.isoformat(), "published_at": (now-timedelta(days=1)).isoformat()},
        {"id": "00000000-0000-0000-0000-000000000002", "owner_id": fresh_owner, "body": "AI fresh",
         "content_type": "text", "visibility": "public", "status": "published", "moderation_status": "approved",
         "version": 1, "created_at": now.isoformat(), "updated_at": now.isoformat(), "published_at": now.isoformat()},
        {"id": "00000000-0000-0000-0000-000000000003", "owner_id": hidden_owner, "body": "hidden",
         "content_type": "text", "visibility": "public", "status": "published", "moderation_status": "approved",
         "version": 1, "created_at": now.isoformat(), "updated_at": now.isoformat(), "published_at": now.isoformat()},
        {"id": "00000000-0000-0000-0000-000000000004", "owner_id": "eng-p14-not-interested", "body": "Crypto news",
         "content_type": "text", "visibility": "public", "status": "published", "moderation_status": "approved",
         "version": 1, "created_at": now.isoformat(), "updated_at": now.isoformat(), "published_at": now.isoformat()},
    ]

    async def fake_db(method, table, *, params=None, body=None, prefer=None):
        params = params or {}
        if table == "feed_preferences":
            return []
        if table == "user_interests":
            return [{"interest_key": "ai", "preference": "interested"}, {"interest_key": "crypto", "preference": "not_interested"}]
        if table == "content_items":
            return content_rows
        if table == "profiles":
            return [{"id": row["owner_id"], "visibility": "public"} for row in content_rows]
        if table == "social_edges":
            if params.get("actor_user_id") == "eq.eng-p14-viewer":
                return [
                    {"target_user_id": followed_owner, "edge_type": "follow", "status": "active"},
                    {"target_user_id": hidden_owner, "edge_type": "mute", "status": "active"},
                ]
            return []
        if table in {"content_reactions", "content_comments", "content_saves", "content_shares", "content_media"}:
            return []
        raise AssertionError(f"unexpected table {table}")

    async def no_signed_url(path: str, *, expires_in: int = 300):
        raise AssertionError("feed fixture has no media")

    monkeypatch.setattr(feed_api, "_server_db", fake_db)
    monkeypatch.setattr(feed_api, "_signed_media_preview_url", no_signed_url)
    app.dependency_overrides[current_user] = _fixture_user
    app.dependency_overrides[feed_api.optional_current_user] = _fixture_user
    try:
        response = TestClient(app).get("/v1/feed?mode=for_you&limit=10")
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["mode"] == "for_you"
        assert len(payload["items"]) == 2
        assert payload["items"][0]["owner_id"] == followed_owner
        assert "followed_creator" in payload["items"][0]["ranking_signals"]
        fresh_item = next(item for item in payload["items"] if item["owner_id"] == fresh_owner)
        assert "explicit_interest_match" in fresh_item["ranking_signals"]
        assert hidden_owner not in {item["owner_id"] for item in payload["items"]}
        assert "eng-p14-not-interested" not in {item["owner_id"] for item in payload["items"]}
    finally:
        app.dependency_overrides.clear()


def test_feed_preferences_default_without_persisting_a_row(monkeypatch):
    async def fake_db(method, table, *, params=None, body=None, prefer=None):
        assert table == "feed_preferences"
        assert method == "GET"
        return []

    monkeypatch.setattr(feed_api, "_server_db", fake_db)
    app.dependency_overrides[current_user] = _fixture_user
    app.dependency_overrides[feed_api.optional_current_user] = _fixture_user
    try:
        response = TestClient(app).get("/v1/feed/preferences")
        assert response.status_code == 200
        assert response.json()["preferences"] == {"personalization_enabled": True, "ranking_mode": "for_you"}
    finally:
        app.dependency_overrides.clear()


def test_reaction_refuses_non_public_content(monkeypatch):
    async def fake_db(method, table, *, params=None, body=None, prefer=None):
        assert table == "content_items"
        return []

    monkeypatch.setattr(feed_api, "_server_db", fake_db)
    app.dependency_overrides[current_user] = _fixture_user
    app.dependency_overrides[feed_api.optional_current_user] = _fixture_user
    try:
        response = TestClient(app).put(
            "/v1/feed/00000000-0000-0000-0000-000000000001/reaction",
            json={"reaction": "like"},
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "FEED_CONTENT_NOT_FOUND"
    finally:
        app.dependency_overrides.clear()


def test_follower_visibility_allows_only_active_followers_to_interact(monkeypatch):
    owner_id = "eng-p14-followed"
    content_id = "00000000-0000-0000-0000-000000000011"
    now = datetime.now(timezone.utc).isoformat()
    content = {"id": content_id, "owner_id": owner_id, "body": "followers-only", "content_type": "text",
               "visibility": "followers", "status": "published", "moderation_status": "approved",
               "version": 1, "created_at": now, "updated_at": now, "published_at": now}

    async def fake_db(method, table, *, params=None, body=None, prefer=None):
        params = params or {}
        if table == "content_items":
            return [content]
        if table == "profiles":
            return [{"id": owner_id, "visibility": "private"}]
        if table == "social_edges" and params.get("actor_user_id") == "eq.eng-p14-viewer":
            return [{"target_user_id": owner_id, "edge_type": "follow", "status": "active"}]
        if table == "social_edges":
            return []
        if method == "POST" and table == "content_reactions":
            return [{"content_id": content_id, "actor_user_id": "eng-p14-viewer", "reaction": "like"}]
        raise AssertionError(f"unexpected {method} {table}")

    monkeypatch.setattr(feed_api, "_server_db", fake_db)
    app.dependency_overrides[current_user] = _fixture_user
    app.dependency_overrides[feed_api.optional_current_user] = _fixture_user
    try:
        response = TestClient(app).put(f"/v1/feed/{content_id}/reaction", json={"reaction": "like"})
        assert response.status_code == 200, response.text
        assert response.json()["reaction"]["reaction"] == "like"
    finally:
        app.dependency_overrides.clear()


def test_blocked_creator_content_cannot_receive_interactions(monkeypatch):
    content_id = "00000000-0000-0000-0000-000000000012"
    now = datetime.now(timezone.utc).isoformat()
    content = {"id": content_id, "owner_id": "eng-p14-blocked", "body": "public-but-blocked", "content_type": "text",
               "visibility": "public", "status": "published", "moderation_status": "approved",
               "version": 1, "created_at": now, "updated_at": now, "published_at": now}

    async def fake_db(method, table, *, params=None, body=None, prefer=None):
        params = params or {}
        if table == "content_items":
            return [content]
        if table == "social_edges" and params.get("actor_user_id") == "eq.eng-p14-viewer":
            return [{"target_user_id": "eng-p14-blocked", "edge_type": "block", "status": "active"}]
        if table == "social_edges":
            return []
        raise AssertionError(f"interaction write should not occur: {method} {table}")

    monkeypatch.setattr(feed_api, "_server_db", fake_db)
    app.dependency_overrides[current_user] = _fixture_user
    app.dependency_overrides[feed_api.optional_current_user] = _fixture_user
    try:
        response = TestClient(app).put(f"/v1/feed/{content_id}/reaction", json={"reaction": "like"})
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "FEED_CONTENT_NOT_FOUND"
    finally:
        app.dependency_overrides.clear()


def test_share_records_event_and_returns_deep_link(monkeypatch):
    content_id = "00000000-0000-0000-0000-000000000021"
    now = datetime.now(timezone.utc).isoformat()
    content = {"id": content_id, "owner_id": "eng-p14-author", "body": "shareable", "content_type": "text",
               "visibility": "public", "status": "published", "moderation_status": "approved",
               "version": 1, "created_at": now, "updated_at": now, "published_at": now}
    writes = []

    async def fake_db(method, table, *, params=None, body=None, prefer=None):
        params = params or {}
        if table == "content_items": return [content]
        if table == "profiles": return [{"id": content["owner_id"], "visibility": "public"}]
        if table == "social_edges": return []
        if method == "POST" and table == "content_shares":
            writes.append(body)
            return [{"id": "share-event", **body, "created_at": now}]
        raise AssertionError(f"unexpected {method} {table}")

    monkeypatch.setattr(feed_api, "_server_db", fake_db)
    app.dependency_overrides[current_user] = _fixture_user
    app.dependency_overrides[feed_api.optional_current_user] = _fixture_user
    try:
        response = TestClient(app).post(f"/v1/feed/{content_id}/share", json={"share_target": "copy_link"})
        assert response.status_code == 201, response.text
        payload = response.json()
        assert payload["share"]["share_target"] == "copy_link"
        assert payload["share_url"] == f"https://allpha.web.id/feed?content={content_id}"
        assert len(writes) == 1
    finally:
        app.dependency_overrides.clear()


def test_shared_item_deep_link_returns_viewer_state(monkeypatch):
    content_id = "00000000-0000-0000-0000-000000000022"
    now = datetime.now(timezone.utc).isoformat()
    content = {"id": content_id, "owner_id": "eng-p14-author", "body": "deep link", "content_type": "text",
               "visibility": "public", "status": "published", "moderation_status": "approved",
               "version": 1, "created_at": now, "updated_at": now, "published_at": now}

    async def fake_db(method, table, *, params=None, body=None, prefer=None):
        if table == "content_items": return [content]
        if table == "profiles": return [{"id": content["owner_id"], "visibility": "public"}]
        if table == "social_edges": return []
        if table in {"content_reactions", "content_comments", "content_saves", "content_shares", "content_media"}: return []
        raise AssertionError(f"unexpected {method} {table}")

    monkeypatch.setattr(feed_api, "_server_db", fake_db)
    monkeypatch.setattr(feed_api, "_signed_media_preview_url", lambda path: None)
    app.dependency_overrides[current_user] = _fixture_user
    app.dependency_overrides[feed_api.optional_current_user] = _fixture_user
    try:
        response = TestClient(app).get(f"/v1/feed/item/{content_id}")
        assert response.status_code == 200, response.text
        assert response.json()["item"]["id"] == content_id
        assert response.json()["item"]["engagement"] == {"likes": 0, "comments": 0, "saves": 0, "shares": 0}
    finally:
        app.dependency_overrides.clear()


def test_feed_allows_anonymous_public_reads(monkeypatch):
    async def fake_db(method, table, *, params=None, body=None, prefer=None):
        return []
    monkeypatch.setattr(feed_api, "_server_db", fake_db)
    response = TestClient(app).get("/v1/feed")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["items"] == []
    assert payload["mode"] == "recent"
    assert payload["personalization_enabled"] is False

def test_inactive_social_edges_do_not_hide_feed_content(monkeypatch):
    now = datetime.now(timezone.utc).isoformat()
    owners = ["eng-p14-inactive-block", "eng-p14-inactive-mute", "eng-p14-inactive-incoming-block", "eng-p14-active-block"]
    content_rows = [
        {"id": f"00000000-0000-0000-0000-{index:012d}", "owner_id": owner, "body": owner,
         "content_type": "text", "visibility": "public", "status": "published", "moderation_status": "approved",
         "version": 1, "created_at": now, "updated_at": now, "published_at": now}
        for index, owner in enumerate(owners, start=100)
    ]

    async def fake_db(method, table, *, params=None, body=None, prefer=None):
        params = params or {}
        if table == "feed_preferences":
            return []
        if table == "content_items":
            return content_rows
        if table == "profiles":
            return [{"id": row["owner_id"], "visibility": "public"} for row in content_rows]
        if table == "social_edges":
            if params.get("actor_user_id") == "eq.eng-p14-viewer":
                return [
                    {"target_user_id": owners[0], "edge_type": "block", "status": "inactive"},
                    {"target_user_id": owners[1], "edge_type": "mute", "status": "inactive"},
                    {"target_user_id": owners[3], "edge_type": "block", "status": "active"},
                ]
            if params.get("target_user_id") == "eq.eng-p14-viewer":
                # Adversarial fixture: even if a backend returned an inactive edge,
                # it must not affect visibility.
                return [{"actor_user_id": owners[2], "status": "inactive"}]
            return []
        if table in {"content_reactions", "content_comments", "content_saves", "content_shares", "content_media"}:
            return []
        raise AssertionError(f"unexpected table {table}")

    monkeypatch.setattr(feed_api, "_server_db", fake_db)
    app.dependency_overrides[current_user] = _fixture_user
    app.dependency_overrides[feed_api.optional_current_user] = _fixture_user
    try:
        response = TestClient(app).get("/v1/feed?mode=recent&limit=10")
        assert response.status_code == 200, response.text
        visible_owners = {item["owner_id"] for item in response.json()["items"]}
        assert set(owners[:3]).issubset(visible_owners)
        assert owners[3] not in visible_owners
    finally:
        app.dependency_overrides.clear()

def test_guest_account_recommendations_use_real_public_profiles_and_follower_counts(monkeypatch):
    owner_a = "00000000-0000-0000-0000-000000000031"
    owner_b = "00000000-0000-0000-0000-000000000032"
    now = datetime.now(timezone.utc).isoformat()

    async def fake_db(method, table, *, params=None, body=None, prefer=None):
        params = params or {}
        if table == "content_items":
            return [
                {"owner_id": owner_a, "published_at": now},
                {"owner_id": owner_b, "published_at": now},
            ]
        if table == "profiles":
            return [
                {"id": owner_a, "username": "public_a", "display_name": "Public A", "avatar_url": None, "bio": "Creator", "visibility": "public"},
                {"id": owner_b, "username": "public_b", "display_name": "Public B", "avatar_url": None, "bio": "Creator", "visibility": "public"},
            ]
        if table == "social_edges" and params.get("target_user_id"):
            return [
                {"target_user_id": owner_a},
                {"target_user_id": owner_a},
                {"target_user_id": owner_b},
            ]
        return []

    monkeypatch.setattr(feed_api, "_server_db", fake_db)
    response = TestClient(app).get("/v1/recommendations/accounts")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert [item["id"] for item in payload["items"]] == [owner_a, owner_b]
    assert all("followers" not in item for item in payload["items"])
    assert all("verified" not in item for item in payload["items"])


def test_follow_endpoint_creates_canonical_social_edge(monkeypatch):
    target = "00000000-0000-0000-0000-000000000041"
    writes = []

    async def fake_db(method, table, *, params=None, body=None, prefer=None):
        params = params or {}
        if table == "profiles" and method == "GET":
            return [{"id": target, "visibility": "public"}]
        if table == "social_edges" and method == "GET":
            return []
        if table == "social_edges" and method == "POST":
            writes.append(body)
            return [{**body, "id": "follow-edge", "created_at": datetime.now(timezone.utc).isoformat()}]
        raise AssertionError(f"unexpected {method} {table}")

    monkeypatch.setattr(feed_api, "_server_db", fake_db)
    app.dependency_overrides[current_user] = _fixture_user
    try:
        response = TestClient(app).post(f"/v1/social/follow/{target}")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 201, response.text
    assert response.json()["status"] == "active"
    assert writes[0]["actor_user_id"] == "eng-p14-viewer"
    assert writes[0]["target_user_id"] == target
    assert writes[0]["edge_type"] == "follow"

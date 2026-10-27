from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import Request
from fastapi.testclient import TestClient

from allpha_api import feed_api
from allpha_api.auth import current_user, optional_current_user
from allpha_api.main import app
import allpha_api.main as main_api


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
    app.dependency_overrides[optional_current_user] = _fixture_user
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
            return [{"id": str(row.get("owner_id")), "username": "public_user", "display_name": "Public User",
                     "avatar_url": None, "bio": "", "visibility": "public"}
                    for row in content_rows]
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
    app.dependency_overrides[optional_current_user] = _fixture_user
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
    app.dependency_overrides[optional_current_user] = _fixture_user
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
    app.dependency_overrides[optional_current_user] = _fixture_user
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
            return [{"id": owner_id, "username": "followed", "display_name": "Followed", "avatar_url": None,
                     "bio": "", "visibility": "public", "account_status": "active"}]
        if table == "social_edges" and params.get("actor_user_id") == "eq.eng-p14-viewer":
            return [{"target_user_id": owner_id, "edge_type": "follow", "status": "active"}]
        if table == "social_edges":
            return []
        if method == "POST" and table == "content_reactions":
            return [{"content_id": content_id, "actor_user_id": "eng-p14-viewer", "reaction": "like"}]
        raise AssertionError(f"unexpected {method} {table}")

    monkeypatch.setattr(feed_api, "_server_db", fake_db)
    app.dependency_overrides[current_user] = _fixture_user
    app.dependency_overrides[optional_current_user] = _fixture_user
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
    app.dependency_overrides[optional_current_user] = _fixture_user
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
        if table == "profiles":
            return [{"id": "eng-p14-author", "username": "author", "display_name": "Author", "avatar_url": None,
                     "bio": "", "visibility": "public", "account_status": "active"}]
        if table == "social_edges": return []
        if method == "POST" and table == "content_shares":
            writes.append(body)
            return [{"id": "share-event", **body, "created_at": now}]
        raise AssertionError(f"unexpected {method} {table}")

    monkeypatch.setattr(feed_api, "_server_db", fake_db)
    app.dependency_overrides[current_user] = _fixture_user
    app.dependency_overrides[optional_current_user] = _fixture_user
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
        if table == "profiles":
            return [{"id": "eng-p14-author", "username": "author", "display_name": "Author", "avatar_url": None,
                     "bio": "", "visibility": "public", "account_status": "active"}]
        if table == "social_edges": return []
        if table in {"content_reactions", "content_comments", "content_saves", "content_shares", "content_media"}: return []
        raise AssertionError(f"unexpected {method} {table}")

    monkeypatch.setattr(feed_api, "_server_db", fake_db)
    monkeypatch.setattr(feed_api, "_signed_media_preview_url", lambda path: None)
    app.dependency_overrides[current_user] = _fixture_user
    app.dependency_overrides[optional_current_user] = _fixture_user
    try:
        response = TestClient(app).get(f"/v1/feed/item/{content_id}")
        assert response.status_code == 200, response.text
        assert response.json()["item"]["id"] == content_id
        assert response.json()["item"]["engagement"] == {"likes": 0, "comments": 0, "saves": 0, "shares": 0}
    finally:
        app.dependency_overrides.clear()


def test_feed_allows_anonymous_public_read_with_empty_state(monkeypatch):
    async def fake_db(method, table, *, params=None, body=None, prefer=None):
        if table == "content_items":
            assert (params or {}).get("visibility") == "eq.public"
            return []
        if table == "profiles":
            return [
                {"id": "public-author", "username": "public_author", "display_name": "Public Author",
                 "avatar_url": None, "bio": "", "visibility": "public", "account_status": "active"},
                {"id": "private-author", "username": "private_author", "display_name": "Private Author",
                 "avatar_url": "/private.png", "bio": "private profile", "visibility": "private", "account_status": "active"},
            ]
        if table in {"content_reactions", "content_comments", "content_saves", "content_shares", "content_media"}:
            return []
        raise AssertionError(f"guest feed must not query {table}")

    monkeypatch.setattr(feed_api, "_server_db", fake_db)
    response = TestClient(app).get("/v1/feed")
    assert response.status_code == 200, response.text
    assert response.json()["items"] == []
    assert response.json()["mode"] == "recent"
    assert response.json()["personalization_enabled"] is False

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
            return [{"id": owner, "username": "public_user", "display_name": "Public User",
                     "avatar_url": None, "bio": "", "visibility": "public"} for owner in owners]
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
    app.dependency_overrides[optional_current_user] = _fixture_user
    try:
        response = TestClient(app).get("/v1/feed?mode=recent&limit=10")
        assert response.status_code == 200, response.text
        visible_owners = {item["owner_id"] for item in response.json()["items"]}
        assert set(owners[:3]).issubset(visible_owners)
        assert owners[3] not in visible_owners
    finally:
        app.dependency_overrides.clear()

def test_guest_feed_returns_only_public_published_content(monkeypatch):
    now = datetime.now(timezone.utc)
    rows = [
        {"id": "00000000-0000-0000-0000-000000000101", "owner_id": "public-author", "body": "public post",
         "content_type": "text", "visibility": "public", "status": "published", "moderation_status": "approved",
         "version": 1, "created_at": now.isoformat(), "updated_at": now.isoformat(), "published_at": now.isoformat()},
        {"id": "00000000-0000-0000-0000-000000000102", "owner_id": "private-author", "body": "followers only",
         "content_type": "text", "visibility": "followers", "status": "published", "moderation_status": "approved",
         "version": 1, "created_at": now.isoformat(), "updated_at": now.isoformat(), "published_at": now.isoformat()},
        {"id": "00000000-0000-0000-0000-000000000103", "owner_id": "private-author", "body": "public post from private profile",
         "content_type": "text", "visibility": "public", "status": "published", "moderation_status": "approved",
         "version": 1, "created_at": now.isoformat(), "updated_at": now.isoformat(), "published_at": now.isoformat()},
    ]
    calls = []

    async def fake_db(method, table, *, params=None, body=None, prefer=None):
        params = params or {}
        calls.append((method, table, params))
        if table == "content_items":
            assert params.get("visibility") == "eq.public"
            return [row for row in rows if row["visibility"] == "public"]
        if table == "profiles":
            return [{"id": "public-author", "username": "public_author", "display_name": "Public Author",
                     "avatar_url": None, "bio": "", "visibility": "public"}]
        if table in {"content_reactions", "content_comments", "content_saves", "content_shares", "content_media"}:
            return []
        raise AssertionError(f"guest feed must not query {table}")

    async def no_signed_url(path: str, *, expires_in: int = 300):
        raise AssertionError("fixture has no media")

    monkeypatch.setattr(feed_api, "_server_db", fake_db)
    monkeypatch.setattr(feed_api, "_signed_media_preview_url", no_signed_url)
    response = TestClient(app).get("/v1/feed?mode=for_you&limit=10")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert [item["body"] for item in payload["items"]] == ["public post"]
    assert payload["mode"] == "recent"
    assert payload["personalization_enabled"] is False
    assert payload["items"][0]["viewer_reaction"] is None
    assert payload["items"][0]["saved"] is False
    assert not any(table == "social_edges" for _, table, _ in calls)

def test_guest_comments_and_shared_item_hide_inactive_public_profile(monkeypatch):
    content_id = "00000000-0000-0000-0000-000000000191"
    now = datetime.now(timezone.utc).isoformat()
    content = {
        "id": content_id, "owner_id": "inactive-public-owner", "body": "previously public",
        "content_type": "text", "visibility": "public", "status": "published",
        "moderation_status": "approved", "version": 1, "created_at": now,
        "updated_at": now, "published_at": now,
    }

    async def fake_db(method, table, *, params=None, body=None, prefer=None):
        if table == "content_items":
            return [content]
        if table == "profiles":
            return [{
                "id": "inactive-public-owner", "username": "inactive_owner",
                "display_name": "Inactive Owner", "avatar_url": None, "bio": "",
                "visibility": "public", "account_status": "deactivation_requested",
            }]
        raise AssertionError(f"guest access must stop before querying {table}")

    monkeypatch.setattr(feed_api, "_server_db", fake_db)
    client = TestClient(app)
    comments = client.get(f"/v1/feed/{content_id}/comments")
    shared = client.get(f"/v1/feed/item/{content_id}")
    assert comments.status_code == 404, comments.text
    assert shared.status_code == 404, shared.text


def test_public_creator_recommendations_require_real_public_profiles_and_posts(monkeypatch):
    now = datetime.now(timezone.utc).isoformat()
    public_id = "00000000-0000-0000-0000-000000000201"
    no_public_posts_id = "00000000-0000-0000-0000-000000000202"

    async def fake_db(method, table, *, params=None, body=None, prefer=None):
        params = params or {}
        if table == "content_items":
            assert params.get("visibility") == "eq.public"
            return [{"owner_id": public_id, "published_at": now}, {"owner_id": public_id, "published_at": now}]
        if table == "profiles":
            assert public_id in params.get("id", "")
            assert params.get("visibility") == "eq.public"
            return [{"id": public_id, "username": "public_creator", "display_name": "Public Creator",
                     "avatar_url": None, "bio": "Real public profile", "visibility": "public"}]
        raise AssertionError(f"unexpected table {table}")

    monkeypatch.setattr(feed_api, "_server_db", fake_db)
    response = TestClient(app).get("/v1/recommendations/creators?limit=10")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert len(payload["items"]) == 1
    assert payload["items"][0]["id"] == public_id
    assert payload["items"][0]["public_post_count"] == 2
    assert "verified" not in payload["items"][0]
    assert "followers" not in payload["items"][0]


def test_follow_public_profile_is_idempotent_and_uses_server_actor(monkeypatch):
    target_id = "00000000-0000-0000-0000-000000000203"
    actor_id = "00000000-0000-0000-0000-000000000204"
    calls = []

    async def fake_user(request: Request):
        request.state.user_id = actor_id
        return {"id": actor_id}

    async def fake_db(method, table, *, params=None, body=None, prefer=None):
        calls.append((method, table, params or {}, body, prefer))
        if table == "profiles":
            return [{"id": target_id, "visibility": "public"}]
        if table == "social_edges" and method == "GET":
            return []
        if table == "social_edges" and method == "POST":
            assert body["actor_user_id"] == actor_id
            assert body["target_user_id"] == target_id
            return [{"id": "edge-id", "target_user_id": target_id, "status": "active", "created_at": datetime.now(timezone.utc).isoformat()}]
        raise AssertionError((method, table, params))

    monkeypatch.setattr(feed_api, "_server_db", fake_db)
    app.dependency_overrides[current_user] = fake_user
    try:
        response = TestClient(app).put(f"/v1/social/follow/{target_id}")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "active"
    assert response.json()["created"] is True


def test_unfollow_is_idempotent_and_actor_scoped(monkeypatch):
    target_id = "00000000-0000-0000-0000-000000000205"
    actor_id = "00000000-0000-0000-0000-000000000206"
    calls = []

    async def fake_user(request: Request):
        request.state.user_id = actor_id
        return {"id": actor_id}

    async def fake_db(method, table, *, params=None, body=None, prefer=None):
        calls.append((method, table, params or {}))
        assert method == "DELETE" and table == "social_edges"
        assert params["actor_user_id"] == f"eq.{actor_id}"
        assert params["target_user_id"] == f"eq.{target_id}"
        assert params["edge_type"] == "eq.follow"
        return []

    monkeypatch.setattr(feed_api, "_server_db", fake_db)
    app.dependency_overrides[current_user] = fake_user
    try:
        response = TestClient(app).delete(f"/v1/social/follow/{target_id}")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()["status"] == "not_following"

def test_anonymous_can_read_comments_only_on_public_published_content(monkeypatch):
    content_id = "00000000-0000-0000-0000-000000000091"
    now = datetime.now(timezone.utc).isoformat()
    content = {
        "id": content_id, "owner_id": "public-author", "visibility": "public",
        "status": "published", "moderation_status": "approved", "published_at": now,
    }
    calls = []

    async def fake_db(method, table, *, params=None, body=None, prefer=None):
        params = params or {}
        calls.append((method, table, params))
        if table == "content_items":
            return [content] if params.get("id") == f"eq.{content_id}" else []
        if table == "profiles":
            return [{"id": "public-author", "username": "public_author", "display_name": "Public Author",
                     "avatar_url": None, "bio": "", "visibility": "public"}]
        if table == "content_comments":
            assert params.get("select") == "id,content_id,body,status,created_at,updated_at"
            return [{"id": "comment-1", "content_id": content_id, "body": "Public comment",
                     "status": "visible", "created_at": now, "updated_at": now}]
        raise AssertionError(f"anonymous comment read must not query {table}")

    monkeypatch.setattr(feed_api, "_server_db", fake_db)
    app.dependency_overrides.clear()
    try:
        response = TestClient(app).get(f"/v1/feed/{content_id}/comments")
        assert response.status_code == 200, response.text
        item = response.json()["items"][0]
        assert item["body"] == "Public comment"
        assert "actor_user_id" not in item
        assert not any(table == "content_mentions" for _, table, _ in calls)
    finally:
        app.dependency_overrides.clear()


def test_anonymous_cannot_read_comments_for_non_public_content(monkeypatch):
    content_id = "00000000-0000-0000-0000-000000000092"

    async def fake_db(method, table, *, params=None, body=None, prefer=None):
        if table == "content_items":
            return []
        raise AssertionError(f"private/unpublished content must be rejected before querying {table}")

    monkeypatch.setattr(feed_api, "_server_db", fake_db)
    app.dependency_overrides.clear()
    try:
        response = TestClient(app).get(f"/v1/feed/{content_id}/comments")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "FEED_CONTENT_NOT_FOUND"
    finally:
        app.dependency_overrides.clear()


def test_create_social_edge_replay_returns_existing_edge_without_duplicate_write(monkeypatch):
    actor_id = "00000000-0000-0000-0000-000000000301"
    target_id = "00000000-0000-0000-0000-000000000302"
    existing = {
        "id": "00000000-0000-0000-0000-000000000303",
        "actor_user_id": actor_id,
        "target_user_id": target_id,
        "edge_type": "follow",
        "status": "active",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    calls = []

    async def fake_user(request: Request):
        request.state.supabase_access_token = "social-edge-test-token"
        return {"id": actor_id}

    async def fake_db(method, path, access_token, *, params=None, body=None, prefer=None):
        calls.append((method, path, params or {}, body, prefer))
        assert access_token == "social-edge-test-token"
        assert method == "GET" and path == "social_edges"
        assert params["actor_user_id"] == f"eq.{actor_id}"
        assert params["target_user_id"] == f"eq.{target_id}"
        assert params["edge_type"] == "eq.follow"
        return [existing]

    monkeypatch.setattr(main_api, "user_db_request", fake_db)
    app.dependency_overrides[current_user] = fake_user
    try:
        response = TestClient(app).post(
            "/v1/me/social-edges",
            json={"target_user_id": target_id, "edge_type": "follow"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["edge"]["id"] == existing["id"]
    assert payload["idempotent_replay"] is True
    assert payload["outcome"] == "follow_active"
    assert len(calls) == 1  # no duplicate POST was attempted


def test_create_social_edge_reports_private_follow_as_pending(monkeypatch):
    actor_id = "00000000-0000-0000-0000-000000000304"
    target_id = "00000000-0000-0000-0000-000000000305"
    created = {
        "id": "00000000-0000-0000-0000-000000000306",
        "actor_user_id": actor_id,
        "target_user_id": target_id,
        "edge_type": "follow",
        "status": "requested",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    calls = []

    async def fake_user(request: Request):
        request.state.supabase_access_token = "social-edge-test-token"
        return {"id": actor_id}

    async def fake_db(method, path, access_token, *, params=None, body=None, prefer=None):
        calls.append((method, path, params or {}, body, prefer))
        if method == "GET" and path == "social_edges":
            return []
        if method == "GET" and path == "profiles":
            assert params["select"] == "id,visibility,account_status"
            return [{"id": target_id, "visibility": "private", "account_status": "active"}]
        assert method == "POST" and path == "social_edges"
        assert body["actor_user_id"] == actor_id
        assert body["target_user_id"] == target_id
        assert body["edge_type"] == "follow"
        assert body["status"] == "requested", "private-profile follow must not become active before owner approval"
        return [created]

    monkeypatch.setattr(main_api, "user_db_request", fake_db)
    app.dependency_overrides[current_user] = fake_user
    try:
        response = TestClient(app).post(
            "/v1/me/social-edges",
            json={"target_user_id": target_id, "edge_type": "follow"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["idempotent_replay"] is False
    assert payload["outcome"] == "follow_request_created"
    assert len(calls) == 5  # existing edge, target profile, two block directions, insert


def test_canonical_social_edge_rejects_deactivated_profile_before_relationship_write(monkeypatch):
    actor_id = "00000000-0000-0000-0000-000000000307"
    target_id = "00000000-0000-0000-0000-000000000308"
    calls = []

    async def fake_user(request: Request):
        request.state.supabase_access_token = "social-edge-inactive-test-token"
        return {"id": actor_id}

    async def fake_db(method, path, access_token, *, params=None, body=None, prefer=None):
        calls.append((method, path, params or {}, body))
        if path == "social_edges":
            assert method == "GET"
            return []
        if path == "profiles":
            assert method == "GET"
            return [{"id": target_id, "visibility": "public", "account_status": "deactivation_requested"}]
        raise AssertionError(f"follow must stop before writing to {path}")

    monkeypatch.setattr(main_api, "user_db_request", fake_db)
    app.dependency_overrides[current_user] = fake_user
    try:
        response = TestClient(app).post(
            "/v1/me/social-edges",
            json={"target_user_id": target_id, "edge_type": "follow"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404, response.text
    assert response.json()["detail"]["code"] == "PUBLIC_PROFILE_NOT_FOUND"
    assert not any(method == "POST" for method, _, _, _ in calls)


def test_follow_rejects_deactivated_profile_before_relationship_write(monkeypatch):
    target_id = "22222222-2222-4222-8222-222222222222"
    calls = []

    async def fake_db(method, table, *, params=None, body=None, prefer=None):
        calls.append((method, table, params or {}, body))
        if table == "profiles":
            assert method == "GET"
            assert params["select"] == "id,visibility,account_status"
            return [{
                "id": target_id,
                "visibility": "public",
                "account_status": "deactivation_requested",
            }]
        raise AssertionError(f"relationship access must stop before {table}")

    monkeypatch.setattr(feed_api, "_server_db", fake_db)
    app.dependency_overrides[current_user] = _fixture_user
    try:
        response = TestClient(app).put(f"/v1/social/follow/{target_id}")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "PUBLIC_PROFILE_NOT_FOUND"
    assert len(calls) == 1
    assert calls[0][1] == "profiles"


def test_inactive_profile_content_cannot_receive_interactions(monkeypatch):
    content_id = "00000000-0000-0000-0000-000000000901"
    owner_id = "eng-p14-deactivated-owner"
    now = datetime.now(timezone.utc).isoformat()
    content = {"id": content_id, "owner_id": owner_id, "body": "old content", "content_type": "text",
               "visibility": "public", "status": "published", "moderation_status": "approved",
               "version": 1, "created_at": now, "updated_at": now, "published_at": now}

    async def fake_db(method, table, *, params=None, body=None, prefer=None):
        if table == "content_items":
            return [content]
        if table == "social_edges":
            return []
        if table == "profiles":
            return [{"id": owner_id, "visibility": "public", "account_status": "deactivation_requested"}]
        raise AssertionError(f"interaction must stop before {method} {table}")

    monkeypatch.setattr(feed_api, "_server_db", fake_db)
    app.dependency_overrides[current_user] = _fixture_user
    try:
        response = TestClient(app).put(f"/v1/feed/{content_id}/reaction", json={"reaction": "like"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "FEED_CONTENT_NOT_FOUND"


def test_private_profile_public_content_requires_active_follow_for_interactions(monkeypatch):
    content_id = "00000000-0000-0000-0000-000000000902"
    owner_id = "eng-p14-private-owner"
    now = datetime.now(timezone.utc).isoformat()
    content = {"id": content_id, "owner_id": owner_id, "body": "private owner content", "content_type": "text",
               "visibility": "public", "status": "published", "moderation_status": "approved",
               "version": 1, "created_at": now, "updated_at": now, "published_at": now}

    async def fake_db(method, table, *, params=None, body=None, prefer=None):
        if table == "content_items":
            return [content]
        if table == "social_edges":
            return []
        if table == "profiles":
            return [{"id": owner_id, "visibility": "private", "account_status": "active"}]
        raise AssertionError(f"interaction must stop before {method} {table}")

    monkeypatch.setattr(feed_api, "_server_db", fake_db)
    app.dependency_overrides[current_user] = _fixture_user
    try:
        response = TestClient(app).put(f"/v1/feed/{content_id}/reaction", json={"reaction": "like"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "FEED_CONTENT_NOT_FOUND"


def test_username_discovery_respects_saved_preference_status_and_private_projection(monkeypatch):
    public_id = "eng-p04-discovery-public"
    private_id = "eng-p04-discovery-private"
    opted_out_id = "eng-p04-discovery-opted-out"
    inactive_id = "eng-p04-discovery-inactive"
    profiles = [
        {"id": public_id, "username": "alice_public", "display_name": "Alice Public", "avatar_url": "/alice.png",
         "bio": "Public bio", "visibility": "public", "account_status": "active"},
        {"id": private_id, "username": "alice_private", "display_name": "Alice Private", "avatar_url": "/private.png",
         "bio": "Private bio", "visibility": "private", "account_status": "active"},
        {"id": opted_out_id, "username": "alice_hidden", "display_name": "Alice Hidden", "avatar_url": "/hidden.png",
         "bio": "Hidden bio", "visibility": "public", "account_status": "active"},
        {"id": inactive_id, "username": "alice_inactive", "display_name": "Alice Inactive", "avatar_url": "/inactive.png",
         "bio": "Inactive bio", "visibility": "public", "account_status": "deactivation_requested"},
    ]

    async def fake_db(method, table, *, params=None, body=None, prefer=None):
        params = params or {}
        if table == "profiles":
            return profiles
        if table == "user_settings":
            return [
                {"user_id": public_id, "privacy_settings": {"discoverable_by_username": True}},
                {"user_id": private_id, "privacy_settings": {"discoverable_by_username": True}},
                {"user_id": opted_out_id, "privacy_settings": {"discoverable_by_username": False}},
            ]
        if table == "social_edges":
            return []
        raise AssertionError(f"unexpected {method} {table}")

    monkeypatch.setattr(feed_api, "_server_db", fake_db)
    app.dependency_overrides[current_user] = _fixture_user
    try:
        response = TestClient(app).get("/v1/social/discover-users?q=alice")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200, response.text
    items = {item["id"]: item for item in response.json()["items"]}
    assert set(items) == {public_id, private_id}
    assert items[public_id]["avatar_url"] == "/alice.png"
    assert items[private_id]["avatar_url"] is None
    assert items[private_id]["bio"] == ""
    assert items[private_id]["visibility"] == "private"


def test_username_discovery_excludes_accounts_hidden_by_block_or_mute(monkeypatch):
    hidden_id = "eng-p04-discovery-blocked"
    visible_id = "eng-p04-discovery-visible"
    profiles = [
        {"id": hidden_id, "username": "alex_blocked", "display_name": "Alex Blocked", "avatar_url": None,
         "bio": "", "visibility": "public", "account_status": "active"},
        {"id": visible_id, "username": "alex_visible", "display_name": "Alex Visible", "avatar_url": None,
         "bio": "", "visibility": "public", "account_status": "active"},
    ]

    async def fake_db(method, table, *, params=None, body=None, prefer=None):
        params = params or {}
        if table == "profiles":
            return profiles
        if table == "user_settings":
            return [{"user_id": profile["id"], "privacy_settings": {"discoverable_by_username": True}} for profile in profiles]
        if table == "social_edges":
            if params.get("edge_type") == "in.(follow,block,mute)":
                return [{"target_user_id": hidden_id, "edge_type": "block", "status": "active"}]
            return []
        raise AssertionError(f"unexpected {method} {table}")

    monkeypatch.setattr(feed_api, "_server_db", fake_db)
    app.dependency_overrides[current_user] = _fixture_user
    try:
        response = TestClient(app).get("/v1/social/discover-users?q=alex")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200, response.text
    assert [item["id"] for item in response.json()["items"]] == [visible_id]

def test_legacy_follow_route_persists_private_profile_follow_as_requested(monkeypatch):
    target_id = "22222222-2222-4222-8222-222222222223"
    writes = []
    async def fake_db(method, table, *, params=None, body=None, prefer=None):
        if table == "profiles":
            return [{"id": target_id, "visibility": "private", "account_status": "active"}]
        if table == "social_edges" and method == "GET":
            return []
        if table == "social_edges" and method == "POST":
            writes.append(body)
            return [{"id": "legacy-private-follow", "target_user_id": target_id, "status": body["status"],
                     "created_at": datetime.now(timezone.utc).isoformat()}]
        raise AssertionError(f"unexpected relationship operation {method} {table}")
    monkeypatch.setattr(feed_api, "_server_db", fake_db)
    app.dependency_overrides[current_user] = _fixture_user
    try:
        response = TestClient(app).put(f"/v1/social/follow/{target_id}")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "requested"
    assert writes and writes[0]["status"] == "requested"

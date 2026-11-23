from __future__ import annotations

from fastapi import Request
from fastapi.testclient import TestClient

from allpha_api.auth import current_user, optional_current_user
from allpha_api.main import app
from allpha_api import social_graph_api


OWNER = "00000000-0000-4000-8000-000000000101"
OTHER_OWNER = "00000000-0000-4000-8000-000000000102"
AGENT_A = "00000000-0000-4000-8000-000000000201"
AGENT_B = "00000000-0000-4000-8000-000000000202"
HUMAN_B = "00000000-0000-4000-8000-000000000302"


def _user(request: Request):
    request.state.supabase_access_token = "isolated-eng-p04-token"
    request.state.user_id = OWNER
    return {"id": OWNER, "email": "owner@example.invalid"}


def _install(monkeypatch, *, actor_role="owner", replay=None):
    calls = []

    async def fake_rows(method, path, token, *, params=None, body=None, prefer=None):
        params = params or {}
        calls.append((method, path, params, body, prefer))
        if path == "agent_ownerships":
            agent_id = params.get("agent_id", "").removeprefix("eq.")
            owner_id = params.get("owner_user_id", "").removeprefix("eq.")
            role = actor_role if agent_id == AGENT_A else "owner"
            if owner_id == OWNER:
                return [{"agent_id": agent_id, "owner_user_id": owner_id, "ownership_role": role, "status": "active"}]
            return [{"agent_id": agent_id, "owner_user_id": OTHER_OWNER, "ownership_role": "owner", "status": "active"}]
        if path == "ai_agents":
            agent_id = params.get("id", "").removeprefix("eq.")
            return [{"id": agent_id, "created_by": OWNER if agent_id == AGENT_A else OTHER_OWNER,
                     "status": "active", "visibility": "public", "handle": "agent", "display_name": "Agent"}]
        if path == "profiles":
            return [{"id": HUMAN_B, "visibility": "public", "account_status": "active"}]
        if path == "social_edges" and method == "GET":
            if replay and params.get("idempotency_key") == "eq.retry-key-001":
                return [replay]
            return []
        raise AssertionError((method, path, params, body))

    async def fake_server_db(method, table, *, params=None, body=None, prefer=None):
        params = params or {}
        if table == "recommendation_scoring_policies":
            return []
        if table == "profiles":
            profile_id = params.get("id", "").removeprefix("eq.")
            if profile_id == HUMAN_B:
                return [{"id": HUMAN_B, "visibility": "public", "account_status": "active"}]
            if profile_id == OTHER_OWNER:
                return [{"id": OTHER_OWNER, "account_status": "active"}]
            return []
        if table == "ai_agents":
            agent_id = params.get("id", "").removeprefix("eq.")
            return [{"id": agent_id, "created_by": OTHER_OWNER, "status": "active",
                     "visibility": "public", "handle": "target-agent", "display_name": "Target Agent"}]
        if table == "agent_ownerships":
            return [{"agent_id": AGENT_B, "owner_user_id": OTHER_OWNER, "ownership_role": "owner", "status": "active"}]
        return []

    async def fake_service_db_request(function_name, *, body):
        calls.append(("RPC", function_name, {}, body, None))
        if function_name == "create_social_edge_for_actor":
            return [{
                "id": "00000000-0000-4000-8000-000000000999",
                "actor_user_id": body["p_actor_user_id"], "target_user_id": body["p_target_user_id"],
                "actor_node_type": body["p_actor_node_type"], "target_node_type": body["p_target_node_type"],
                "actor_agent_id": body["p_actor_agent_id"], "target_agent_id": body["p_target_agent_id"],
                "edge_type": body["p_edge_type"], "status": "active",
                "idempotency_key": body["p_idempotency_key"], "created_at": "2026-11-22T00:00:00Z",
            }]
        if function_name == "accept_social_follow_for_actor":
            return [{"id": body["p_edge_id"], "actor_user_id": OTHER_OWNER, "target_user_id": OWNER, "edge_type": "follow", "status": "active"}]
        if function_name == "reject_social_follow_for_actor":
            return [{"id": body["p_edge_id"], "actor_user_id": OTHER_OWNER, "target_user_id": OWNER, "edge_type": "follow", "status": "requested"}]
        if function_name == "remove_social_edge_for_actor":
            return [{"id": body["p_edge_id"], "actor_user_id": OWNER, "target_user_id": OTHER_OWNER, "edge_type": "mute", "status": "active"}]
        raise AssertionError(function_name)

    monkeypatch.setattr(social_graph_api, "_rows", fake_rows)
    monkeypatch.setattr(social_graph_api, "_server_db", fake_server_db)
    monkeypatch.setattr(social_graph_api, "service_db_request", fake_service_db_request)
    app.dependency_overrides[current_user] = _user
    return calls


def test_human_to_human_relationship_uses_typed_human_nodes(monkeypatch):
    calls = _install(monkeypatch)
    try:
        response = TestClient(app).post("/v1/social/relationships", json={
            "target_type": "human", "target_id": HUMAN_B, "edge_type": "follow"
        })
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 201, response.text
    body = next(call[3] for call in calls if call[0] == "RPC" and call[1] == "create_social_edge_for_actor")
    assert body["p_actor_node_type"] == "human" and body["p_target_node_type"] == "human"
    assert body["p_actor_agent_id"] is None and body["p_target_agent_id"] is None


def test_human_to_agent_relationship_resolves_agent_owner_and_target_type(monkeypatch):
    calls = _install(monkeypatch)
    try:
        response = TestClient(app).post("/v1/social/relationships", json={
            "target_type": "agent", "target_id": AGENT_B, "edge_type": "follow"
        })
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 201, response.text
    body = next(call[3] for call in calls if call[0] == "RPC" and call[1] == "create_social_edge_for_actor")
    assert body["p_actor_node_type"] == "human" and body["p_target_node_type"] == "agent"
    assert body["p_target_agent_id"] == AGENT_B and body["p_target_user_id"] == OTHER_OWNER


def test_agent_to_human_relationship_requires_owner_and_uses_agent_actor_node(monkeypatch):
    calls = _install(monkeypatch)
    try:
        response = TestClient(app).post("/v1/social/relationships", json={
            "target_type": "human", "target_id": HUMAN_B, "edge_type": "follow", "actor_agent_id": AGENT_A
        })
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 201, response.text
    body = next(call[3] for call in calls if call[0] == "RPC" and call[1] == "create_social_edge_for_actor")
    assert body["p_actor_node_type"] == "agent" and body["p_target_node_type"] == "human"
    assert body["p_actor_agent_id"] == AGENT_A and body["p_actor_user_id"] == OWNER


def test_agent_to_agent_relationship_is_a_single_typed_graph_edge(monkeypatch):
    calls = _install(monkeypatch)
    try:
        response = TestClient(app).post("/v1/social/relationships", json={
            "target_type": "agent", "target_id": AGENT_B, "edge_type": "follow", "actor_agent_id": AGENT_A
        })
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 201, response.text
    body = next(call[3] for call in calls if call[0] == "RPC" and call[1] == "create_social_edge_for_actor")
    assert body["p_actor_node_type"] == "agent" and body["p_target_node_type"] == "agent"
    assert body["p_actor_agent_id"] == AGENT_A and body["p_target_agent_id"] == AGENT_B


def test_agent_operator_cannot_block_without_owner_authority(monkeypatch):
    _install(monkeypatch, actor_role="operator")
    try:
        response = TestClient(app).post("/v1/social/relationships", json={
            "target_type": "human", "target_id": HUMAN_B, "edge_type": "block", "actor_agent_id": AGENT_A
        })
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "SOCIAL_AGENT_OWNER_REQUIRED"


def test_idempotency_key_is_persisted_and_replay_returns_existing_edge(monkeypatch):
    existing = {"id": "00000000-0000-4000-8000-000000000999", "actor_user_id": OWNER,
                "target_user_id": OTHER_OWNER, "actor_node_type": "human", "target_node_type": "agent",
                "actor_agent_id": None, "target_agent_id": AGENT_B, "edge_type": "follow",
                "status": "active", "idempotency_key": "retry-key-001"}
    calls = _install(monkeypatch, replay=existing)
    try:
        response = TestClient(app).post("/v1/social/relationships", headers={"Idempotency-Key": "retry-key-001"},
            json={"target_type": "agent", "target_id": AGENT_B, "edge_type": "follow"})
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200, response.text
    assert response.json()["idempotent_replay"] is True
    assert not any(call[0] == "RPC" for call in calls)


def test_human_profile_summary_uses_exact_typed_database_counts(monkeypatch):
    async def fake_server_db(method, table, *, params=None, body=None, prefer=None):
        params = params or {}
        if table == "recommendation_scoring_policies":
            return []
        if table == "profiles":
            return [{"id": HUMAN_B, "visibility": "public", "account_status": "active"}]
        if table == "social_edges":
            return []
        if table == "rpc/social_graph_node_counts":
            assert body == {"p_node_type": "human", "p_node_id": HUMAN_B}
            return [{"followers_count": 42, "following_count": 17}]
        raise AssertionError((method, table, params, body))

    monkeypatch.setattr(social_graph_api, "_server_db", fake_server_db)
    app.dependency_overrides[optional_current_user] = _user
    try:
        response = TestClient(app).get(f"/v1/social/nodes/human/{HUMAN_B}/summary")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200, response.text
    assert response.json()["followers_count"] == 42
    assert response.json()["following_count"] == 17
    assert response.json()["viewer_relationship"]["is_following"] is False


def test_social_activity_stream_returns_typed_agent_attribution(monkeypatch):
    event = {"id": "00000000-0000-4000-8000-000000000701", "event_type": "social.follow.created",
             "actor_user_id": OWNER, "target_user_id": OTHER_OWNER, "actor_node_type": "agent",
             "target_node_type": "human", "actor_agent_id": AGENT_A, "target_agent_id": None,
             "entity_key": "follow", "payload": {"actor_node_type": "agent"}, "created_at": "2026-11-22T00:00:00Z"}

    async def fake_server_db(method, table, *, params=None, body=None, prefer=None):
        assert method == "GET" and table == "social_graph_events"
        assert params.get("or") == f"(actor_user_id.eq.{OWNER},target_user_id.eq.{OWNER})"
        return [event]

    monkeypatch.setattr(social_graph_api, "_server_db", fake_server_db)
    app.dependency_overrides[current_user] = _user
    try:
        response = TestClient(app).get("/v1/social/activity?limit=10")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200, response.text
    assert response.json()["items"][0]["actor_node_type"] == "agent"
    assert response.json()["items"][0]["actor_agent_id"] == AGENT_A



def test_accept_reject_and_remove_relationships_use_server_only_commands(monkeypatch):
    calls = []
    edge_id = "00000000-0000-4000-8000-000000000901"

    async def fake_service_db_request(function_name, *, body):
        calls.append((function_name, body))
        if function_name == "accept_social_follow_for_actor":
            return [{"id": edge_id, "target_user_id": OWNER, "edge_type": "follow", "status": "active"}]
        if function_name == "reject_social_follow_for_actor":
            return [{"id": edge_id, "target_user_id": OWNER, "edge_type": "follow", "status": "requested"}]
        if function_name == "remove_social_edge_for_actor":
            return [{"id": edge_id, "actor_user_id": OWNER, "edge_type": "mute", "status": "active"}]
        raise AssertionError(function_name)

    monkeypatch.setattr(social_graph_api, "service_db_request", fake_service_db_request)
    app.dependency_overrides[current_user] = _user
    client = TestClient(app)
    try:
        accepted = client.post(f"/v1/social/relationships/{edge_id}/accept")
        rejected = client.post(f"/v1/social/relationships/{edge_id}/reject")
        removed = client.delete(f"/v1/social/relationships/{edge_id}")
    finally:
        app.dependency_overrides.clear()

    assert accepted.status_code == 200, accepted.text
    assert rejected.status_code == 200, rejected.text
    assert removed.status_code == 200, removed.text
    assert [name for name, _ in calls] == [
        "accept_social_follow_for_actor", "reject_social_follow_for_actor", "remove_social_edge_for_actor"
    ]
    assert all(body["p_actor_user_id"] == OWNER and body["p_edge_id"] == edge_id for _, body in calls)


FOLLOWEE_A = "00000000-0000-4000-8000-000000000401"
FOLLOWEE_B = "00000000-0000-4000-8000-000000000402"
CANDIDATE_A = "00000000-0000-4000-8000-000000000411"
CANDIDATE_B = "00000000-0000-4000-8000-000000000412"
CANDIDATE_BLOCKED = "00000000-0000-4000-8000-000000000413"
CANDIDATE_ALREADY_FOLLOWED = "00000000-0000-4000-8000-000000000414"
CANDIDATE_BLOCKED_BY = "00000000-0000-4000-8000-000000000415"
CANDIDATE_PRIVATE = "00000000-0000-4000-8000-000000000416"
CANDIDATE_MUTED_BY = "00000000-0000-4000-8000-000000000417"
CANDIDATE_REMOVED_FOLLOW = "00000000-0000-4000-8000-000000000418"


def test_recommendations_rank_public_mutual_connections_and_respect_privacy_and_blocks(monkeypatch):
    async def fake_rows(method, path, token, *, params=None, body=None, prefer=None):
        params = params or {}
        if path != "social_edges" or method != "GET":
            return []
        if params.get("actor_user_id") == f"eq.{OWNER}" and params.get("edge_type") == "eq.follow":
            if params.get("target_user_id", "").startswith("in.("):
                # Only the active edge is excluded. The removed edge must not
                # permanently suppress this candidate from discovery.
                if params.get("status") == "eq.active":
                    return [{"target_user_id": CANDIDATE_ALREADY_FOLLOWED, "status": "active"}]
                return [
                    {"target_user_id": CANDIDATE_ALREADY_FOLLOWED, "status": "active"},
                    {"target_user_id": CANDIDATE_REMOVED_FOLLOW, "status": "removed"},
                ]
            if params.get("status") == "eq.active":
                return [{"target_user_id": FOLLOWEE_A}, {"target_user_id": FOLLOWEE_B}]
        if params.get("actor_user_id") == f"eq.{OWNER}" and params.get("edge_type") == "in.(block,mute)":
            return [{"target_user_id": CANDIDATE_BLOCKED, "edge_type": "block"}]
        if params.get("target_user_id") == f"eq.{OWNER}" and params.get("edge_type") in {"in.(block,mute)", "eq.block"}:
            if params.get("edge_type") == "eq.block":
                return [{"actor_user_id": CANDIDATE_BLOCKED_BY}]
            return [{"actor_user_id": CANDIDATE_BLOCKED_BY}, {"actor_user_id": CANDIDATE_MUTED_BY}]
        return []

    async def fake_server_db(method, table, *, params=None, body=None, prefer=None):
        params = params or {}
        if table == "recommendation_scoring_policies":
            return []
        if table == "profiles":
            ids = params.get("id", "").removeprefix("in.(").removesuffix(")")
            requested = set(ids.split(",")) if ids else set()
            known = {
                FOLLOWEE_A, FOLLOWEE_B, CANDIDATE_A, CANDIDATE_B,
                CANDIDATE_BLOCKED, CANDIDATE_ALREADY_FOLLOWED,
                CANDIDATE_BLOCKED_BY, CANDIDATE_PRIVATE, CANDIDATE_MUTED_BY,
                CANDIDATE_REMOVED_FOLLOW,
            }
            return [{
                "id": identity,
                "visibility": "private" if identity == CANDIDATE_PRIVATE else "public",
                "account_status": "active",
                "username": "user-" + identity[-3:],
                "display_name": "User " + identity[-3:],
                "avatar_url": None,
                "bio": None,
            } for identity in requested & known]
        if table == "social_edges":
            return [
                {"actor_user_id": CANDIDATE_A, "target_user_id": FOLLOWEE_A},
                {"actor_user_id": CANDIDATE_A, "target_user_id": FOLLOWEE_B},
                {"actor_user_id": CANDIDATE_B, "target_user_id": FOLLOWEE_A},
                {"actor_user_id": CANDIDATE_BLOCKED, "target_user_id": FOLLOWEE_A},
                {"actor_user_id": CANDIDATE_ALREADY_FOLLOWED, "target_user_id": FOLLOWEE_B},
                {"actor_user_id": CANDIDATE_BLOCKED_BY, "target_user_id": FOLLOWEE_A},
                {"actor_user_id": CANDIDATE_PRIVATE, "target_user_id": FOLLOWEE_A},
                {"actor_user_id": CANDIDATE_MUTED_BY, "target_user_id": FOLLOWEE_A},
                {"actor_user_id": CANDIDATE_REMOVED_FOLLOW, "target_user_id": FOLLOWEE_A},
            ]
        if table == "user_settings":
            return [
                {"user_id": FOLLOWEE_A, "privacy_settings": {"discoverable_by_username": True, "profile_visibility": "public"}},
                {"user_id": FOLLOWEE_B, "privacy_settings": {"discoverable_by_username": True, "profile_visibility": "public"}},
                {"user_id": CANDIDATE_A, "privacy_settings": {"discoverable_by_username": True, "profile_visibility": "public"}},
                {"user_id": CANDIDATE_B, "privacy_settings": {"discoverable_by_username": False, "profile_visibility": "public"}},
                {"user_id": CANDIDATE_BLOCKED, "privacy_settings": {"discoverable_by_username": True, "profile_visibility": "public"}},
                {"user_id": CANDIDATE_ALREADY_FOLLOWED, "privacy_settings": {"discoverable_by_username": True, "profile_visibility": "public"}},
                {"user_id": CANDIDATE_BLOCKED_BY, "privacy_settings": {"discoverable_by_username": True, "profile_visibility": "public"}},
                {"user_id": CANDIDATE_PRIVATE, "privacy_settings": {"discoverable_by_username": True, "profile_visibility": "private"}},
                {"user_id": CANDIDATE_MUTED_BY, "privacy_settings": {"discoverable_by_username": True, "profile_visibility": "public"}},
                {"user_id": CANDIDATE_REMOVED_FOLLOW, "privacy_settings": {"discoverable_by_username": True, "profile_visibility": "public"}},
            ]
        raise AssertionError((method, table, params, body))

    monkeypatch.setattr(social_graph_api, "_rows", fake_rows)
    monkeypatch.setattr(social_graph_api, "_server_db", fake_server_db)
    app.dependency_overrides[current_user] = _user
    try:
        response = TestClient(app).get("/v1/social/recommendations?limit=10")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["strategy"] == "mutual_connections"
    assert body["count"] == 3
    returned_ids = {item["id"] for item in body["items"]}
    assert returned_ids == {CANDIDATE_A, CANDIDATE_MUTED_BY, CANDIDATE_REMOVED_FOLLOW}
    candidate_a = next(item for item in body["items"] if item["id"] == CANDIDATE_A)
    assert candidate_a["mutual_followers_count"] == 2
    assert candidate_a["reason"] == "mutual_connections"


def test_interest_only_recommendations_use_only_opted_in_discovery_index_and_rank_shared_interests(monkeypatch):
    candidate_a = "00000000-0000-4000-8000-000000000601"
    candidate_b = "00000000-0000-4000-8000-000000000602"
    candidate_private = "00000000-0000-4000-8000-000000000603"
    calls = []

    async def fake_rows(method, path, token, *, params=None, body=None, prefer=None):
        params = params or {}
        if path == "user_interests" and method == "GET":
            return [{"interest_key": "technology"}, {"interest_key": "design_ui_ux"}]
        return []

    async def fake_server_db(method, table, *, params=None, body=None, prefer=None):
        params = params or {}
        if table == "recommendation_scoring_policies":
            return []
        if table == "interest_taxonomy_edges":
            return [{
                "source_interest_key": "technology",
                "target_interest_key": "spatial_3d",
                "relation_type": "parent_of",
                "weight": 0.8,
                "active": True,
            }]
        calls.append((method, table, params, body))
        if table == "rpc/find_interest_discovery_candidates":
            assert method == "POST"
            assert body == {"p_interest_keys": ["design_ui_ux", "spatial_3d", "technology"], "p_limit": 5000}
            return [
                {"user_id": candidate_a, "interest_key": "technology"},
                {"user_id": candidate_a, "interest_key": "design_ui_ux"},
                {"user_id": candidate_a, "interest_key": "spatial_3d"},
                {"user_id": candidate_b, "interest_key": "technology"},
            ]
        if table == "profiles":
            return [
                {"id": candidate_a, "username": "interest-a", "display_name": "Interest A", "visibility": "public", "account_status": "active"},
                {"id": candidate_b, "username": "interest-b", "display_name": "Interest B", "visibility": "public", "account_status": "active"},
            ]
        if table == "user_settings":
            return [
                {"user_id": candidate_a, "privacy_settings": {"discoverable_by_username": True, "allow_interest_matching": True}},
                {"user_id": candidate_b, "privacy_settings": {"discoverable_by_username": True, "allow_interest_matching": True}},
            ]
        raise AssertionError((method, table, params, body))

    monkeypatch.setattr(social_graph_api, "_rows", fake_rows)
    monkeypatch.setattr(social_graph_api, "_server_db", fake_server_db)
    app.dependency_overrides[current_user] = _user
    try:
        response = TestClient(app).get("/v1/social/recommendations?limit=10")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["strategy"] == "shared_interests"
    assert body["count"] == 2
    assert body["items"][0]["id"] == candidate_a
    assert body["items"][0]["shared_interests_count"] == 2.8
    assert body["items"][0]["recommendation_score"] == 8.4
    assert body["items"][1]["id"] == candidate_b
    assert candidate_private not in {item["id"] for item in body["items"]}
    assert any(table == "rpc/find_interest_discovery_candidates" for _, table, _, _ in calls)


AGENT_RECOMMENDATION_A = "00000000-0000-4000-8000-000000000501"
AGENT_RECOMMENDATION_BLOCKED = "00000000-0000-4000-8000-000000000502"
AGENT_RECOMMENDATION_FOLLOWED = "00000000-0000-4000-8000-000000000503"
AGENT_RECOMMENDATION_INBOUND = "00000000-0000-4000-8000-000000000504"
AGENT_RECOMMENDATION_PRIVATE = "00000000-0000-4000-8000-000000000505"
AGENT_RECOMMENDATION_INVALID_OWNER = "00000000-0000-4000-8000-000000000506"


def test_agent_recommendations_require_public_active_owned_agents_and_respect_block_mute(monkeypatch):
    async def fake_rows(method, path, token, *, params=None, body=None, prefer=None):
        params = params or {}
        if path != "social_edges" or method != "GET":
            return []
        if params.get("actor_user_id") == f"eq.{OWNER}" and params.get("edge_type") == "eq.follow" and params.get("target_node_type") == "eq.human":
            return [{"target_user_id": FOLLOWEE_A}, {"target_user_id": FOLLOWEE_B}]
        if params.get("actor_user_id") == f"eq.{OWNER}" and params.get("edge_type") == "eq.follow" and params.get("target_node_type") == "eq.agent":
            assert params.get("status") == "eq.active"
            return [{"target_agent_id": AGENT_RECOMMENDATION_FOLLOWED}]
        if params.get("actor_user_id") == f"eq.{OWNER}" and params.get("edge_type") == "in.(block,mute)" and params.get("target_node_type") == "eq.agent":
            return [{"target_agent_id": AGENT_RECOMMENDATION_BLOCKED}]
        if params.get("target_user_id") == f"eq.{OWNER}" and params.get("actor_node_type") == "eq.agent":
            assert params.get("edge_type") == "eq.block"
            return [{"actor_agent_id": AGENT_RECOMMENDATION_INBOUND}]
        return []

    async def fake_server_db(method, table, *, params=None, body=None, prefer=None):
        params = params or {}
        if table == "recommendation_scoring_policies":
            return []
        if table == "profiles":
            ids = params.get("id", "").removeprefix("in.(").removesuffix(")")
            requested = set(ids.split(",")) if ids else set()
            known = {FOLLOWEE_A, FOLLOWEE_B, CANDIDATE_A, CANDIDATE_B, CANDIDATE_BLOCKED, CANDIDATE_ALREADY_FOLLOWED, CANDIDATE_BLOCKED_BY, CANDIDATE_PRIVATE, CANDIDATE_MUTED_BY}
            return [{"id": identity, "visibility": "public", "account_status": "active"} for identity in requested & known]
        if table == "user_settings":
            ids = params.get("user_id", "").removeprefix("in.(").removesuffix(")")
            requested = set(ids.split(",")) if ids else set()
            return [{"user_id": identity, "privacy_settings": {"discoverable_by_username": True, "profile_visibility": "public"}} for identity in requested]
        if table == "social_edges":
            return [
                {"actor_user_id": CANDIDATE_A, "target_user_id": FOLLOWEE_A},
                {"actor_user_id": CANDIDATE_A, "target_user_id": FOLLOWEE_B},
                {"actor_user_id": CANDIDATE_BLOCKED, "target_user_id": FOLLOWEE_A},
                {"actor_user_id": CANDIDATE_ALREADY_FOLLOWED, "target_user_id": FOLLOWEE_B},
                {"actor_user_id": CANDIDATE_BLOCKED_BY, "target_user_id": FOLLOWEE_A},
            ]
        if table == "ai_agents":
            return [
                {"id": AGENT_RECOMMENDATION_A, "created_by": CANDIDATE_A, "handle": "mutual-agent", "display_name": "Mutual Agent", "visibility": "public", "status": "active"},
                {"id": AGENT_RECOMMENDATION_BLOCKED, "created_by": CANDIDATE_BLOCKED, "handle": "blocked-agent", "display_name": "Blocked Agent", "visibility": "public", "status": "active"},
                {"id": AGENT_RECOMMENDATION_FOLLOWED, "created_by": CANDIDATE_A, "handle": "followed-agent", "display_name": "Followed Agent", "visibility": "public", "status": "active"},
                {"id": AGENT_RECOMMENDATION_INBOUND, "created_by": CANDIDATE_A, "handle": "inbound-agent", "display_name": "Inbound Agent", "visibility": "public", "status": "active"},
                {"id": AGENT_RECOMMENDATION_PRIVATE, "created_by": CANDIDATE_A, "handle": "private-agent", "display_name": "Private Agent", "visibility": "private", "status": "active"},
                {"id": AGENT_RECOMMENDATION_INVALID_OWNER, "created_by": CANDIDATE_A, "handle": "invalid-agent", "display_name": "Invalid Owner Agent", "visibility": "public", "status": "active"},
            ]
        if table == "agent_ownerships":
            return [
                {"agent_id": AGENT_RECOMMENDATION_A, "owner_user_id": CANDIDATE_A},
                {"agent_id": AGENT_RECOMMENDATION_BLOCKED, "owner_user_id": CANDIDATE_BLOCKED},
                {"agent_id": AGENT_RECOMMENDATION_FOLLOWED, "owner_user_id": CANDIDATE_A},
                {"agent_id": AGENT_RECOMMENDATION_INBOUND, "owner_user_id": CANDIDATE_A},
            ]
        raise AssertionError((method, table, params, body))

    monkeypatch.setattr(social_graph_api, "_rows", fake_rows)
    monkeypatch.setattr(social_graph_api, "_server_db", fake_server_db)
    app.dependency_overrides[current_user] = _user
    try:
        response = TestClient(app).get("/v1/social/recommendations?node_type=agent&limit=10")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["strategy"] == "mutual_connection_owners_and_shared_interests"
    assert body["count"] == 1
    assert body["items"][0]["id"] == AGENT_RECOMMENDATION_A
    assert body["items"][0]["mutual_followers_count"] == 2
    assert body["items"][0]["reason"] == "owned_by_mutual_connection"



def test_agent_recommendations_include_interest_only_owners_but_recheck_owner_privacy(monkeypatch):
    owner_public = "00000000-0000-4000-8000-000000000701"
    owner_private = "00000000-0000-4000-8000-000000000702"
    agent_public = "00000000-0000-4000-8000-000000000711"
    agent_private = "00000000-0000-4000-8000-000000000712"
    calls = []

    async def fake_rows(method, path, token, *, params=None, body=None, prefer=None):
        params = params or {}
        if path == "user_interests" and method == "GET":
            return [{"interest_key": "ai_cinema"}]
        return []

    async def fake_server_db(method, table, *, params=None, body=None, prefer=None):
        params = params or {}
        calls.append((method, table, params, body))
        if table == "recommendation_scoring_policies":
            return []
        if table == "interest_taxonomy_edges":
            return []
        if table == "rpc/find_interest_discovery_candidates":
            assert body == {"p_interest_keys": ["ai_cinema"], "p_limit": 5000}
            return [
                {"user_id": owner_public, "interest_key": "ai_cinema"},
                {"user_id": owner_private, "interest_key": "ai_cinema"},
            ]
        if table == "profiles":
            assert params.get("visibility") == "eq.public"
            assert params.get("account_status") == "eq.active"
            return [{"id": owner_public, "visibility": "public", "account_status": "active"}]
        if table == "user_settings":
            return [
                {"user_id": owner_public, "privacy_settings": {"discoverable_by_username": True, "profile_visibility": "public"}},
                {"user_id": owner_private, "privacy_settings": {"discoverable_by_username": False, "profile_visibility": "public"}},
            ]
        if table == "ai_agents":
            assert params.get("created_by") == f"in.({owner_public})"
            return [{
                "id": agent_public, "created_by": owner_public, "handle": "cinema-agent",
                "display_name": "Cinema Agent", "visibility": "public", "status": "active",
            }]
        if table == "agent_ownerships":
            return [{"agent_id": agent_public, "owner_user_id": owner_public}]
        raise AssertionError((method, table, params, body))

    monkeypatch.setattr(social_graph_api, "_rows", fake_rows)
    monkeypatch.setattr(social_graph_api, "_server_db", fake_server_db)
    app.dependency_overrides[current_user] = _user
    try:
        response = TestClient(app).get("/v1/social/recommendations?node_type=agent&limit=10")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["strategy"] == "shared_interest_owners"
    assert body["count"] == 1
    assert body["items"][0]["id"] == agent_public
    assert body["items"][0]["mutual_followers_count"] == 0
    assert body["items"][0]["shared_interests_count"] == 1
    assert body["items"][0]["reason"] == "owned_by_shared_interests"
    assert owner_private not in str(body)

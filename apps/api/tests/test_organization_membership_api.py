"""ENG-P02 organization mutation routes use server-authorized RPC contracts."""
from fastapi import Request
from fastapi.testclient import TestClient

from allpha_api.auth import current_user
from allpha_api.main import app

OWNER = {"id": "11111111-1111-4111-8111-111111111111"}
ORG = "22222222-2222-4222-8222-222222222222"
TARGET = "33333333-3333-4333-8333-333333333333"


async def _owner(request: Request):
    request.state.supabase_access_token = "verified-test-access-token"
    return OWNER


def _client(monkeypatch, rpc, *, membership_role="owner"):
    monkeypatch.setattr("allpha_api.main.service_db_request", rpc)

    async def membership_lookup(method, path, access_token, *, params=None, body=None, prefer=None):
        assert method == "GET"
        assert path == "organization_memberships"
        assert access_token == "verified-test-access-token"
        assert params["organization_id"] == f"eq.{ORG}"
        assert params["user_id"] == f"eq.{OWNER['id']}"
        return [] if membership_role is None else [{"organization_id": ORG, "user_id": OWNER["id"], "role": membership_role}]

    monkeypatch.setattr("allpha_api.auth.user_db_request", membership_lookup)
    app.dependency_overrides[current_user] = _owner
    return TestClient(app)


def test_create_organization_uses_server_actor_not_client_owner(monkeypatch):
    calls = []
    async def rpc(name, *, body):
        calls.append((name, body))
        return [{"id": ORG, "owner_id": OWNER["id"], "name": "Acme", "slug": "acme"}]
    client = _client(monkeypatch, rpc)
    try:
        response = client.post("/v1/organizations", json={"name": "Acme", "slug": "acme"})
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 201
    assert response.json()["organization"]["owner_id"] == OWNER["id"]
    assert calls == [("create_organization_for_user", {"p_actor_user_id": OWNER["id"], "p_name": "Acme", "p_slug": "acme"})]


def test_create_organization_rejects_client_supplied_owner(monkeypatch):
    calls = []
    async def rpc(name, *, body):
        calls.append((name, body))
        return []
    client = _client(monkeypatch, rpc)
    try:
        response = client.post("/v1/organizations", json={"name": "Acme", "slug": "acme", "owner_id": TARGET})
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 422
    assert calls == []


def test_add_member_uses_authenticated_actor_and_target_scope(monkeypatch):
    calls = []
    async def rpc(name, *, body):
        calls.append((name, body))
        return [{"organization_id": ORG, "user_id": TARGET, "role": "member"}]
    client = _client(monkeypatch, rpc)
    try:
        response = client.post(f"/v1/organizations/{ORG}/memberships", json={"user_id": TARGET, "role": "member"})
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 201
    assert calls == [("add_organization_member_for_actor", {"p_organization_id": ORG, "p_actor_user_id": OWNER["id"], "p_target_user_id": TARGET, "p_role": "member"})]


def test_member_role_update_uses_authenticated_actor(monkeypatch):
    calls = []
    async def rpc(name, *, body):
        calls.append((name, body))
        return [{"organization_id": ORG, "user_id": TARGET, "role": "admin"}]
    client = _client(monkeypatch, rpc)
    try:
        response = client.patch(f"/v1/organizations/{ORG}/memberships/{TARGET}", json={"role": "admin"})
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    assert calls == [("update_organization_member_role_for_actor", {"p_organization_id": ORG, "p_actor_user_id": OWNER["id"], "p_target_user_id": TARGET, "p_role": "admin"})]


def test_remove_member_uses_authenticated_actor(monkeypatch):
    calls = []
    async def rpc(name, *, body):
        calls.append((name, body))
        return True
    client = _client(monkeypatch, rpc)
    try:
        response = client.delete(f"/v1/organizations/{ORG}/memberships/{TARGET}")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json() == {"removed": True}
    assert calls == [("remove_organization_member_for_actor", {"p_organization_id": ORG, "p_actor_user_id": OWNER["id"], "p_target_user_id": TARGET})]


def test_non_member_cannot_read_organization_memberships(monkeypatch):
    calls = []
    async def rpc(name, *, body):
        calls.append((name, body))
        return []
    client = _client(monkeypatch, rpc, membership_role=None)
    try:
        response = client.get(f"/v1/organizations/{ORG}/memberships")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 404
    assert calls == []


def test_regular_member_cannot_invoke_admin_membership_mutations(monkeypatch):
    calls = []
    async def rpc(name, *, body):
        calls.append((name, body))
        return []
    client = _client(monkeypatch, rpc, membership_role="member")
    try:
        response = client.post(
            f"/v1/organizations/{ORG}/memberships",
            json={"user_id": TARGET, "role": "member"},
        )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 403
    assert calls == []

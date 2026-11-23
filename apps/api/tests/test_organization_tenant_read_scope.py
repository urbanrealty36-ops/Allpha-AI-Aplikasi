from fastapi import Request
from fastapi.testclient import TestClient

from allpha_api.auth import current_user
from allpha_api.main import app

OWNER = {"id": "11111111-1111-4111-8111-111111111111"}
ORG = "22222222-2222-4222-8222-222222222222"
OTHER_ORG = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
TARGET = "33333333-3333-4333-8333-333333333333"


async def _verified_owner(request: Request):
    request.state.supabase_access_token = "verified-test-access-token"
    request.state.user_id = OWNER["id"]
    return OWNER


def test_organization_list_is_scoped_to_verified_users_memberships(monkeypatch):
    calls = []

    async def db_request(method, path, access_token, *, params=None, body=None, prefer=None):
        calls.append((method, path, access_token, params))
        if path == "organization_memberships":
            return [
                {"organization_id": ORG, "user_id": OWNER["id"]},
                {"organization_id": OTHER_ORG, "user_id": TARGET},
            ]
        if path == "organizations":
            return [
                {"id": ORG, "name": "Owned tenant", "slug": "owned-tenant"},
                {"id": OTHER_ORG, "name": "Foreign tenant", "slug": "foreign-tenant"},
            ]
        raise AssertionError(f"Unexpected database path: {path}")

    monkeypatch.setattr("allpha_api.main.user_db_request", db_request)
    app.dependency_overrides[current_user] = _verified_owner
    try:
        response = TestClient(app).get("/v1/organizations")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert [row["id"] for row in response.json()["items"]] == [ORG]
    membership_call = calls[0]
    assert membership_call[1] == "organization_memberships"
    assert membership_call[2] == "verified-test-access-token"
    assert membership_call[3]["user_id"] == f"eq.{OWNER['id']}"
    organization_call = calls[1]
    assert organization_call[3]["id"] == f"in.({ORG})"


def test_regular_member_receives_only_own_membership_even_if_rls_response_is_broad(monkeypatch):
    async def membership_guard_lookup(method, path, access_token, *, params=None, body=None, prefer=None):
        assert path == "organization_memberships"
        assert params["organization_id"] == f"eq.{ORG}"
        assert params["user_id"] == f"eq.{OWNER['id']}"
        return [{"organization_id": ORG, "user_id": OWNER["id"], "role": "member"}]

    async def broad_roster_response(method, path, access_token, *, params=None, body=None, prefer=None):
        assert path == "organization_memberships"
        return [
            {"organization_id": ORG, "user_id": OWNER["id"], "role": "member"},
            {"organization_id": ORG, "user_id": TARGET, "role": "admin"},
            {"organization_id": OTHER_ORG, "user_id": TARGET, "role": "owner"},
        ]

    monkeypatch.setattr("allpha_api.auth.user_db_request", membership_guard_lookup)
    monkeypatch.setattr("allpha_api.main.user_db_request", broad_roster_response)
    app.dependency_overrides[current_user] = _verified_owner
    try:
        response = TestClient(app).get(f"/v1/organizations/{ORG}/memberships")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["items"] == [
        {"organization_id": ORG, "user_id": OWNER["id"], "role": "member"}
    ]


def test_membership_guard_rejects_foreign_tenant_row_from_database(monkeypatch):
    calls = []

    async def mismatched_membership_lookup(method, path, access_token, *, params=None, body=None, prefer=None):
        calls.append((method, path, params))
        return [{"organization_id": OTHER_ORG, "user_id": OWNER["id"], "role": "owner"}]

    async def unexpected_roster_query(*args, **kwargs):
        raise AssertionError("A foreign tenant membership row must be rejected before roster reads")

    monkeypatch.setattr("allpha_api.auth.user_db_request", mismatched_membership_lookup)
    monkeypatch.setattr("allpha_api.main.user_db_request", unexpected_roster_query)
    app.dependency_overrides[current_user] = _verified_owner
    try:
        response = TestClient(app).get(f"/v1/organizations/{ORG}/memberships")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ORGANIZATION_NOT_FOUND"
    assert len(calls) == 1


def test_create_organization_rejects_service_response_with_foreign_owner(monkeypatch):
    async def service_rpc(function_name, *, body=None):
        assert function_name == "create_organization_for_user"
        assert body["p_actor_user_id"] == OWNER["id"]
        return [{
            "id": ORG,
            "name": "Foreign owner organization",
            "slug": "foreign-owner",
            "owner_id": TARGET,
        }]

    monkeypatch.setattr("allpha_api.main.service_db_request", service_rpc)
    app.dependency_overrides[current_user] = _verified_owner
    try:
        response = TestClient(app).post(
            "/v1/organizations",
            json={"name": "Tenant Boundary", "slug": "tenant-boundary"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "CREATE_FAILED"


def test_add_membership_rejects_service_response_from_another_tenant(monkeypatch):
    async def membership_guard_lookup(method, path, access_token, *, params=None, body=None, prefer=None):
        assert path == "organization_memberships"
        assert params["organization_id"] == f"eq.{ORG}"
        assert params["user_id"] == f"eq.{OWNER['id']}"
        return [{"organization_id": ORG, "user_id": OWNER["id"], "role": "owner"}]

    async def service_rpc(function_name, *, body=None):
        assert function_name == "add_organization_member_for_actor"
        assert body["p_organization_id"] == ORG
        return [{
            "organization_id": OTHER_ORG,
            "user_id": TARGET,
            "role": "member",
            "invited_by": OWNER["id"],
        }]

    monkeypatch.setattr("allpha_api.auth.user_db_request", membership_guard_lookup)
    monkeypatch.setattr("allpha_api.main.service_db_request", service_rpc)
    app.dependency_overrides[current_user] = _verified_owner
    try:
        response = TestClient(app).post(
            f"/v1/organizations/{ORG}/memberships",
            json={"user_id": TARGET, "role": "member"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "MEMBERSHIP_CREATE_FAILED"


def test_update_membership_rejects_service_response_from_another_tenant(monkeypatch):
    async def membership_guard_lookup(method, path, access_token, *, params=None, body=None, prefer=None):
        assert path == "organization_memberships"
        assert params["organization_id"] == f"eq.{ORG}"
        assert params["user_id"] == f"eq.{OWNER['id']}"
        return [{"organization_id": ORG, "user_id": OWNER["id"], "role": "owner"}]

    async def service_rpc(function_name, *, body=None):
        assert function_name == "update_organization_member_role_for_actor"
        assert body["p_organization_id"] == ORG
        return [{
            "organization_id": OTHER_ORG,
            "user_id": TARGET,
            "role": "admin",
            "invited_by": OWNER["id"],
        }]

    monkeypatch.setattr("allpha_api.auth.user_db_request", membership_guard_lookup)
    monkeypatch.setattr("allpha_api.main.service_db_request", service_rpc)
    app.dependency_overrides[current_user] = _verified_owner
    try:
        response = TestClient(app).patch(
            f"/v1/organizations/{ORG}/memberships/{TARGET}",
            json={"role": "admin"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "ORGANIZATION_MEMBER_SCOPE_MISMATCH"

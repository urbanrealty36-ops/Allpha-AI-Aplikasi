from pathlib import Path
import uuid

from fastapi import Request
from fastapi.testclient import TestClient

from allpha_api.auth import current_user
from allpha_api.main import app

client = TestClient(app)
AGENT_ID = "00000000-0000-0000-0000-000000000010"
SKILL_ID = "00000000-0000-0000-0000-000000000020"


def auth_as(user_id="owner-a"):
    async def fake_current_user(request: Request):
        request.state.supabase_access_token = f"token-{user_id}"
        return {"id": user_id, "email": f"{user_id}@example.invalid"}
    return fake_current_user


def test_skill_budget_limits_are_bounded():
    from allpha_api.main import AgentSkillCreate, AgentSkillUpdate
    import pytest

    assert AgentSkillCreate(slug="safe_skill", name="Safe Skill").budget_limits["max_runtime_seconds"] == 30
    with pytest.raises(ValueError):
        AgentSkillCreate(slug="safe_skill", name="Safe Skill", budget_limits={"max_runtime_seconds": 99999, "max_tool_calls": 5})
    with pytest.raises(ValueError):
        AgentSkillCreate(slug="safe_skill", name="Safe Skill", budget_limits={"max_runtime_seconds": 30, "max_tool_calls": 1000})
    with pytest.raises(ValueError):
        AgentSkillUpdate(budget_limits={"max_runtime_seconds": 0, "max_tool_calls": 5})


def test_skill_and_capability_routes_require_authentication():
    assert client.get(f"/v1/agents/{AGENT_ID}/skills").status_code == 401
    assert client.post(f"/v1/agents/{AGENT_ID}/skills", json={"slug": "summarize_text", "name": "Summarize"}).status_code == 401
    assert client.get(f"/v1/agents/{AGENT_ID}/capabilities").status_code == 401


def test_skill_create_is_owner_scoped_and_starts_as_draft(monkeypatch):
    calls = []

    async def fake_db(method, path, token, **kwargs):
        calls.append((method, path, token, kwargs))
        if path == "agent_ownerships":
            return [{"agent_id": AGENT_ID}]
        if path == "agent_skills":
            assert method == "POST"
            assert kwargs["body"]["created_by"] == "owner-a"
            assert kwargs["body"]["agent_id"] == AGENT_ID
            assert kwargs["body"]["status"] == "draft"
            assert kwargs["body"]["version"] == 1
            return [{"id": SKILL_ID, **kwargs["body"]}]
        raise AssertionError(path)

    monkeypatch.setattr("allpha_api.main.user_db_request", fake_db)
    app.dependency_overrides[current_user] = auth_as()
    try:
        response = client.post(f"/v1/agents/{AGENT_ID}/skills", headers={"Authorization": "Bearer test"}, json={
            "slug": "summarize_text", "name": "Summarize Text",
            "instructions": "Summarize only authorized input.",
            "required_permission_scopes": ["content:read"],
            "budget_limits": {"max_runtime_seconds": 20, "max_tool_calls": 3},
        })
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201
    assert response.json()["skill"]["status"] == "draft"
    assert calls[0][1] == "agent_ownerships"
    assert calls[1][1] == "agent_skills"


def test_skill_routes_hide_agent_from_non_owner(monkeypatch):
    calls = []

    async def fake_db(method, path, token, **kwargs):
        calls.append((method, path, token, kwargs))
        return []

    monkeypatch.setattr("allpha_api.main.user_db_request", fake_db)
    app.dependency_overrides[current_user] = auth_as("owner-b")
    try:
        response = client.get(f"/v1/agents/{AGENT_ID}/skills", headers={"Authorization": "Bearer test"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert [call[1] for call in calls] == ["agent_ownerships"]


def test_skill_update_increments_version_and_rejects_authority_fields(monkeypatch):
    calls = []

    async def fake_db(method, path, token, **kwargs):
        calls.append((method, path, token, kwargs))
        if path == "agent_ownerships":
            return [{"agent_id": AGENT_ID}]
        if method == "GET" and path == "agent_skills":
            return [{"id": SKILL_ID, "agent_id": AGENT_ID, "version": 3, "status": "draft"}]
        if method == "PATCH" and path == "agent_skills":
            return [{"id": SKILL_ID, "agent_id": AGENT_ID, "version": kwargs["body"]["version"], "name": "Updated Skill"}]
        raise AssertionError((method, path))

    monkeypatch.setattr("allpha_api.main.user_db_request", fake_db)
    app.dependency_overrides[current_user] = auth_as()
    try:
        response = client.patch(f"/v1/agents/{AGENT_ID}/skills/{SKILL_ID}", headers={"Authorization": "Bearer test"}, json={"name": "Updated Skill"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["skill"]["version"] == 4
    assert calls[-1][3]["body"]["version"] == 4

    app.dependency_overrides[current_user] = auth_as()
    try:
        rejected = client.patch(f"/v1/agents/{AGENT_ID}/skills/{SKILL_ID}", headers={"Authorization": "Bearer test"}, json={"created_by": "owner-b"})
    finally:
        app.dependency_overrides.clear()
    assert rejected.status_code == 422


def test_capability_request_is_declarative_and_not_runtime_authority(monkeypatch):
    calls = []

    async def fake_db(method, path, token, **kwargs):
        calls.append((method, path, token, kwargs))
        if path == "agent_ownerships":
            return [{"agent_id": AGENT_ID}]
        if path == "agent_capabilities":
            body = kwargs["body"]
            assert body["created_by"] == "owner-a"
            assert body["status"] == "requested"
            return [{"id": "cap-1", **body}]
        raise AssertionError(path)

    monkeypatch.setattr("allpha_api.main.user_db_request", fake_db)
    app.dependency_overrides[current_user] = auth_as()
    try:
        response = client.post(f"/v1/agents/{AGENT_ID}/capabilities", headers={"Authorization": "Bearer test"}, json={
            "capability_key": "calendar.read", "description": "Read connected calendar",
            "required_permission_scopes": ["calendar:read"], "risk_level": "medium",
        })
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201
    assert response.json()["capability"]["status"] == "requested"
    assert response.json()["runtime_authorized"] is False


def test_capability_request_cannot_forge_status_or_creator():
    app.dependency_overrides[current_user] = auth_as()
    try:
        response = client.post(f"/v1/agents/{AGENT_ID}/capabilities", headers={"Authorization": "Bearer test"}, json={
            "capability_key": "calendar.read", "created_by": "owner-b", "status": "approved",
        })
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 422


def test_eng_p06_migration_declares_owner_rls_versioning_and_no_runtime_grant():
    migration_path = Path(__file__).parents[1] / "supabase" / "migrations" / "20261014073741_eng_p06_agent_studio_skills_capabilities.sql"
    sql = migration_path.read_text(encoding="utf-8").lower()
    assert "create table if not exists public.agent_skills" in sql
    assert "create table if not exists public.agent_skill_versions" in sql
    assert "create table if not exists public.agent_capabilities" in sql
    assert "alter table public.agent_skills enable row level security" in sql
    assert "alter table public.agent_capabilities enable row level security" in sql
    assert "agent_skills_owner_insert" in sql
    assert "agent_capabilities_owner_insert" in sql
    assert "status = 'requested'" in sql
    assert "revoke all on public.agent_skills, public.agent_capabilities from anon, public" in sql
    assert "security invoker" in sql
    assert "security definer" not in sql
    assert "immutable owner-scoped snapshots" in sql
    assert "before update on public.agent_skills" in sql
    assert "after insert or update on public.agent_skills" in sql
    assert "revoke all on function public.prepare_agent_skill_update() from public, anon, authenticated" in sql
    assert "revoke all on function public.capture_agent_skill_version() from public, anon, authenticated" in sql
    assert "status in ('requested','revoked')" in sql
    assert "grant select, insert, update on public.agent_capabilities to authenticated" in sql
    assert "grant update on public.agent_capabilities" not in sql


def test_skill_version_history_is_owner_scoped_and_checks_skill_membership(monkeypatch):
    calls = []

    async def fake_db(method, path, token, **kwargs):
        calls.append((method, path, token, kwargs))
        if path == "agent_ownerships":
            return [{"agent_id": AGENT_ID}]
        if path == "agent_skills":
            assert kwargs["params"]["id"] == f"eq.{SKILL_ID}"
            assert kwargs["params"]["agent_id"] == f"eq.{AGENT_ID}"
            return [{"id": SKILL_ID}]
        if path == "agent_skill_versions":
            return [{"id": "version-1", "skill_id": SKILL_ID, "agent_id": AGENT_ID,
                     "version": 2, "snapshot": {"name": "Skill v2"}, "created_at": "2026-10-14T00:00:00Z"}]
        raise AssertionError(path)

    monkeypatch.setattr("allpha_api.main.user_db_request", fake_db)
    app.dependency_overrides[current_user] = auth_as()
    try:
        response = client.get(
            f"/v1/agents/{AGENT_ID}/skills/{SKILL_ID}/versions",
            headers={"Authorization": "Bearer test"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["items"][0]["version"] == 2
    assert [call[1] for call in calls] == ["agent_ownerships", "agent_skills", "agent_skill_versions"]


def test_skill_version_history_hides_foreign_agent(monkeypatch):
    calls = []

    async def fake_db(method, path, token, **kwargs):
        calls.append(path)
        return []

    monkeypatch.setattr("allpha_api.main.user_db_request", fake_db)
    app.dependency_overrides[current_user] = auth_as("owner-b")
    try:
        response = client.get(
            f"/v1/agents/{AGENT_ID}/skills/{SKILL_ID}/versions",
            headers={"Authorization": "Bearer test"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert calls == ["agent_ownerships"]

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
            assert kwargs["params"]["status"] == "eq.draft"
            assert kwargs["params"]["version"] == "eq.3"
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


def test_published_skill_can_roll_into_owner_draft_without_mutating_public_snapshot(monkeypatch):
    calls = []

    async def fake_db(method, path, token, **kwargs):
        calls.append((method, path, kwargs))
        if path == "agent_ownerships":
            return [{"agent_id": AGENT_ID}]
        if method == "GET" and path == "agent_skills":
            return [{"id": SKILL_ID, "agent_id": AGENT_ID, "version": 5, "status": "published"}]
        if method == "PATCH" and path == "agent_skills":
            assert kwargs["body"] == {"status": "draft"}
            return [{"id": SKILL_ID, "agent_id": AGENT_ID, "version": 6, "status": "draft"}]
        raise AssertionError((method, path, kwargs))

    monkeypatch.setattr("allpha_api.main.user_db_request", fake_db)
    app.dependency_overrides[current_user] = auth_as()
    try:
        response = client.post(
            f"/v1/agents/{AGENT_ID}/skills/{SKILL_ID}/draft",
            headers={"Authorization": "Bearer token-owner-a"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201, response.text
    assert response.json()["based_on_version"] == 5
    assert response.json()["draft_version"] == 6
    assert calls[-1][2]["params"]["status"] == "eq.published"
    assert calls[-1][2]["params"]["version"] == "eq.5"


def test_skill_publication_returns_actual_trigger_created_version_and_digest(monkeypatch):
    import asyncio
    import hashlib
    import json
    from allpha_api.main import AgentSkillPublicationReview, publish_agent_skill

    draft = {
        "id": SKILL_ID, "agent_id": AGENT_ID, "created_by": "owner-a",
        "slug": "safe_skill", "name": "Safe Skill", "description": "Reviewed",
        "category": "general", "inputs_schema": {"type": "object"},
        "outputs_schema": {"type": "object"}, "instructions": "safe",
        "constraints": {}, "tool_dependencies": [], "required_permission_scopes": [],
        "model_requirements": {}, "budget_limits": {"max_runtime_seconds": 30, "max_tool_calls": 5},
        "tests": [{"case": "basic"}], "evaluation_rubric": {"quality": 1},
        "provenance": {}, "version": 4, "changelog": "draft v4",
        "publication_terms": {"license": "owner"}, "status": "draft",
        "created_at": "2026-10-14T00:00:00+00:00", "updated_at": "2026-10-14T00:01:00+00:00",
    }
    published = {**draft, "version": 5, "status": "published", "updated_at": "2026-10-14T00:02:00+00:00"}
    draft_digest = hashlib.sha256(json.dumps(draft, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()
    published_digest = hashlib.sha256(json.dumps(published, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()

    async def fake_privileged(method, table, *, params=None, body=None, prefer=None):
        if method == "GET" and table == "agent_skills":
            return [draft]
        if method == "GET" and table == "agent_skill_versions":
            return [{"snapshot": draft}]
        if method == "PATCH" and table == "agent_skills":
            return [published]
        raise AssertionError((method, table, params, body))

    async def fake_audit(*args, **kwargs):
        return None

    monkeypatch.setattr("allpha_api.main.privileged_rest_request", fake_privileged)
    monkeypatch.setattr("allpha_api.main.write_operator_audit", fake_audit)
    request = Request({
        "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
        "method": "POST", "scheme": "https", "path": "/", "raw_path": b"/",
        "query_string": b"", "headers": [], "client": ("127.0.0.1", 1234),
        "server": ("localhost", 443),
    })
    payload = AgentSkillPublicationReview(
        expected_version=4, snapshot_digest=draft_digest, reason="Review the complete version four skill",
    )
    result = asyncio.run(publish_agent_skill(
        uuid.UUID(AGENT_ID), uuid.UUID(SKILL_ID), payload, request, {"id": "operator-1"},
    ))

    assert result["published_version"] == 5
    assert result["snapshot_digest"] == published_digest
    assert result["reviewed_draft_version"] == 4
    assert result["reviewed_draft_digest"] == draft_digest


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
    assert "snapshot = (" in sql
    assert "s.version = agent_skill_versions.version" in sql
    assert "s.created_by = agent_skill_versions.created_by" in sql
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


def test_eng_p06_forward_migration_guards_lifecycle_and_public_snapshot_view():
    migration_path = Path(__file__).parents[1] / "supabase" / "migrations" / "20261122154257_eng_p06_skill_version_rollover_runtime_pinning.sql"
    sql = migration_path.read_text(encoding="utf-8").lower()
    assert "guard_agent_skill_lifecycle" in sql
    assert "before insert or update on public.agent_skills" in sql
    assert "current_user = 'authenticated'" in sql
    assert "current_user = 'service_role'" in sql
    assert "agent_skill_publications" in sql
    assert "security_barrier = true" in sql
    assert "v.snapshot ->> 'status' = 'published'" in sql
    assert "s.status <> 'archived'" in sql
    assert "security definer" in sql
    assert "create or replace function public.capture_agent_skill_version()" in sql
    assert "revoke insert, update, delete, truncate, references, trigger on table public.agent_skill_versions" in sql
    assert "revoke delete, truncate, references, trigger on table public.agent_skills" in sql
    assert "drop policy if exists agent_skills_owner_delete" in sql


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


def test_public_skill_publications_use_server_only_projection(monkeypatch):
    calls=[]
    async def fake_privileged(method, table, **kwargs):
        calls.append((method,table,kwargs))
        return [{"id":SKILL_ID,"agent_id":AGENT_ID,"slug":"public_skill","name":"Public Skill",
                 "description":"Public metadata only","category":"general","version":3,
                 "status":"published","publication_terms":{"license":"owner"}}]
    async def forbidden_user_db(*args,**kwargs):
        raise AssertionError("Public Skill projection must not be queried with an anonymous REST role")
    monkeypatch.setattr("allpha_api.main.privileged_rest_request",fake_privileged)
    monkeypatch.setattr("allpha_api.main.user_db_request",forbidden_user_db)
    response=client.get("/v1/agent-skills/publications?limit=20&offset=5")
    assert response.status_code==200
    assert response.json()["items"][0]["id"]==SKILL_ID
    assert calls[0][0:2]==("GET","agent_skill_publications")
    assert calls[0][2]["params"]["limit"]=="20"
    assert calls[0][2]["params"]["offset"]=="5"


def test_public_skill_projection_is_service_only_and_security_invoker():
    migration=Path(__file__).parents[1]/"supabase"/"migrations"/"20261124040000_eng_p06_public_skill_projection_service_only.sql"
    sql=migration.read_text(encoding="utf-8")
    assert "security_invoker = true" in sql
    assert "revoke all on public.agent_skill_publications from public, anon, authenticated" in sql
    assert "grant select on public.agent_skill_publications to service_role" in sql

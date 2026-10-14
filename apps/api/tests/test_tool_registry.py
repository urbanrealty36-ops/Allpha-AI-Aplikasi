from fastapi import Request
from fastapi.testclient import TestClient

from allpha_api.auth import current_user
from allpha_api.main import app
from allpha_api.tool_registry import (
    ToolInputError,
    UnknownToolError,
    execute_tool,
    get_tool,
    list_tools,
    validate_tool_dependencies,
)

client = TestClient(app)
AGENT_ID = "00000000-0000-0000-0000-000000000010"
SKILL_ID = "00000000-0000-0000-0000-000000000020"


def auth_as(user_id="owner-a"):
    async def fake_current_user(request: Request):
        request.state.supabase_access_token = f"token-{user_id}"
        return {"id": user_id, "email": f"{user_id}@example.invalid"}
    return fake_current_user


def test_registry_contains_only_concrete_executable_handlers():
    tools = list_tools()
    assert [tool["key"] for tool in tools] == ["text.normalize"]
    assert all(tool["executable"] is True for tool in tools)
    assert execute_tool("text.normalize", {"text": "  hello\n  allpha  "}) == {"text": "hello allpha"}


def test_registry_rejects_unknown_tool_and_invalid_inputs():
    import pytest

    with pytest.raises(UnknownToolError):
        get_tool("unknown.tool")
    with pytest.raises(UnknownToolError):
        validate_tool_dependencies(["unknown.tool"])
    with pytest.raises(ValueError, match="duplicates"):
        validate_tool_dependencies(["text.normalize", "text.normalize"])
    with pytest.raises(ToolInputError, match="missing required"):
        execute_tool("text.normalize", {})
    with pytest.raises(ToolInputError, match="unexpected input"):
        execute_tool("text.normalize", {"text": "ok", "extra": True})
    with pytest.raises(ToolInputError, match="4000"):
        execute_tool("text.normalize", {"text": "x" * 4001})


def test_tool_catalog_requires_authentication():
    assert client.get("/v1/tools").status_code == 401


def test_tool_catalog_exposes_handler_metadata_not_runtime_authority():
    app.dependency_overrides[current_user] = auth_as()
    try:
        response = client.get("/v1/tools")
        assert response.status_code == 200
        assert response.json()["runtime_mode"] == "owner_preview_only"
        assert response.json()["agent_autonomy_enabled"] is False
        assert response.json()["items"][0]["key"] == "text.normalize"
    finally:
        app.dependency_overrides.clear()


def test_skill_create_rejects_unknown_tool_before_database_insert(monkeypatch):
    calls = []

    async def fake_db(method, path, token, **kwargs):
        calls.append((method, path, token, kwargs))
        if path == "agent_ownerships":
            return [{"agent_id": AGENT_ID}]
        return []

    monkeypatch.setattr("allpha_api.main.user_db_request", fake_db)
    app.dependency_overrides[current_user] = auth_as()
    try:
        response = client.post(
            f"/v1/agents/{AGENT_ID}/skills",
            json={"slug": "unknown_tool", "name": "Unknown Tool", "tool_dependencies": ["not.registered"]},
        )
        assert response.status_code == 422
        assert response.json()["detail"]["code"] == "UNKNOWN_TOOL_DEPENDENCY"
        assert not any(path == "agent_skills" and method == "POST" for method, path, _, _ in calls)
    finally:
        app.dependency_overrides.clear()


def test_skill_tool_preview_requires_declared_tool_and_owner(monkeypatch):
    async def fake_db(method, path, token, **kwargs):
        if path == "agent_ownerships":
            return [{"agent_id": AGENT_ID}]
        if path == "agent_skills":
            return [{
                "id": SKILL_ID,
                "tool_dependencies": ["text.normalize"],
                "budget_limits": {"max_tool_calls": 1},
                "status": "draft",
            }]
        return []

    monkeypatch.setattr("allpha_api.main.user_db_request", fake_db)
    app.dependency_overrides[current_user] = auth_as()
    try:
        response = client.post(
            f"/v1/agents/{AGENT_ID}/skills/{SKILL_ID}/execute-tool",
            json={"tool_key": "text.normalize", "inputs": {"text": "  hello   world "}},
        )
        assert response.status_code == 200
        assert response.json()["result"] == {"text": "hello world"}
        assert response.json()["execution_mode"] == "owner_preview"
        assert response.json()["agent_runtime_authorized"] is False

        undeclared = client.post(
            f"/v1/agents/{AGENT_ID}/skills/{SKILL_ID}/execute-tool",
            json={"tool_key": "unknown.tool", "inputs": {}},
        )
        assert undeclared.status_code == 422
        assert undeclared.json()["detail"]["code"] == "UNKNOWN_TOOL_DEPENDENCY"
    finally:
        app.dependency_overrides.clear()

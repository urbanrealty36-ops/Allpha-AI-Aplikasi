import copy
import uuid

from fastapi.testclient import TestClient

from allpha_api.agent_runtime_api import router
from allpha_api.auth import current_user
from allpha_api.main import app


OWNER = "11111111-1111-4111-8111-111111111111"
AGENT = "22222222-2222-4222-8222-222222222222"
SESSION = "33333333-3333-4333-8333-333333333333"
SKILL = "44444444-4444-4444-8444-444444444444"
TASK = "55555555-5555-4555-8555-555555555555"


class FakeRuntimeStore:
    sessions = {}
    tasks = {}
    capability = {"id": "cap-1", "capability_key": "text.normalize",
                  "required_permission_scopes": [], "status": "approved",
                  "policy_version": "runtime-policy-v1", "updated_at": "2026-10-15T00:00:00Z"}

    @classmethod
    def from_environment(cls):
        return cls()

    async def get_agent(self, owner_id, agent_id):
        if owner_id == OWNER and agent_id == AGENT:
            return {"id": AGENT, "version": 1, "status": "active", "updated_at": "2026-10-15T00:00:00Z"}
        return None

    async def owner_has_agent(self, owner_id, agent_id):
        return owner_id == OWNER and agent_id == AGENT

    async def get_skill(self, owner_id, agent_id, skill_id):
        if await self.owner_has_agent(owner_id, agent_id) and skill_id == SKILL:
            return {"id": SKILL, "agent_id": AGENT, "version": 1, "status": "published",
                    "tool_dependencies": ["text.normalize"], "required_permission_scopes": [],
                    "budget_limits": {"max_runtime_seconds": 3, "max_tool_calls": 1}}
        return None

    async def get_approved_capability(self, agent_id, tool_key):
        return copy.deepcopy(self.capability) if agent_id == AGENT and tool_key == "text.normalize" else None

    async def create_session(self, body):
        row = {"id": SESSION, **body, "status": "active", "created_at": "now", "updated_at": "now"}
        self.sessions[SESSION] = row
        return row

    async def list_sessions(self, owner_id, limit=50):
        return [r for r in self.sessions.values() if r["owner_user_id"] == owner_id][:limit]

    async def get_session(self, owner_id, session_id):
        row = self.sessions.get(session_id)
        return copy.deepcopy(row) if row and row["owner_user_id"] == owner_id else None

    async def list_tasks(self, owner_id, session_id, limit=50):
        return [copy.deepcopy(r) for r in self.tasks.values()
                if r["owner_user_id"] == owner_id and r["session_id"] == session_id][:limit]

    async def create_task(self, body):
        for row in self.tasks.values():
            if row["owner_user_id"] == body["owner_user_id"] and row["idempotency_key"] == body["idempotency_key"]:
                from allpha_api.agent_runtime_store import AgentRuntimePersistenceError
                raise AgentRuntimePersistenceError("duplicate")
        task_id = TASK if TASK not in self.tasks else str(uuid.uuid4())
        row = {"id": task_id, "task_version": 1, "cancel_requested": False, **body,
               "created_at": "now", "updated_at": "now"}
        self.tasks[task_id] = row
        return copy.deepcopy(row)

    async def get_task(self, owner_id, task_id):
        row = self.tasks.get(task_id)
        return copy.deepcopy(row) if row and row["owner_user_id"] == owner_id else None

    async def find_task_by_idempotency(self, owner_id, key):
        return next((copy.deepcopy(r) for r in self.tasks.values()
                     if r["owner_user_id"] == owner_id and r["idempotency_key"] == key), None)

    async def update_task(self, owner_id, task_id, body, *, expected_state=None):
        row = self.tasks.get(task_id)
        if not row or row["owner_user_id"] != owner_id or (expected_state and row["state"] != expected_state):
            return None
        row.update(body)
        return copy.deepcopy(row)


def client(monkeypatch, *, user_id=OWNER):
    import allpha_api.agent_runtime_api as runtime_api
    monkeypatch.setattr(runtime_api, "AgentRuntimeStore", FakeRuntimeStore)
    app.dependency_overrides[current_user] = lambda: {"id": user_id}
    return TestClient(app)


def setup_function():
    FakeRuntimeStore.sessions = {}
    FakeRuntimeStore.tasks = {}
    FakeRuntimeStore.capability = {"id": "cap-1", "capability_key": "text.normalize",
                                   "required_permission_scopes": [], "status": "approved",
                                   "policy_version": "runtime-policy-v1", "updated_at": "2026-10-15T00:00:00Z"}


def teardown_function():
    app.dependency_overrides.pop(current_user, None)


def create_session(client):
    response = client.post("/v1/agent-runtime/sessions", json={"agent_id": AGENT, "title": "Tes runtime"})
    assert response.status_code == 201
    return response.json()["session"]["id"]


def create_task(client, session_id, *, key="task-idem-001", inputs=None):
    return client.post("/v1/agent-runtime/tasks", json={
        "session_id": session_id, "skill_id": SKILL, "tool_key": "text.normalize",
        "inputs": inputs if inputs is not None else {"text": "hello"}, "idempotency_key": key,
    })


def test_runtime_routes_require_authentication():
    response = TestClient(app).get("/v1/agent-runtime/sessions")
    assert response.status_code == 401


def test_session_owner_is_derived_from_verified_identity(monkeypatch):
    c = client(monkeypatch)
    try:
        response = c.post("/v1/agent-runtime/sessions", json={"agent_id": AGENT, "title": "Sesi saya"})
        assert response.status_code == 201
        assert response.json()["session"]["owner_user_id"] == OWNER
    finally:
        app.dependency_overrides.pop(current_user, None)


def test_task_creation_idempotency_replays_same_payload_and_rejects_conflict(monkeypatch):
    c = client(monkeypatch)
    try:
        sid = create_session(c)
        first = create_task(c, sid)
        replay = create_task(c, sid)
        conflict = create_task(c, sid, inputs={"text": "different"})
        assert first.status_code == 201 and replay.status_code == 201
        assert replay.json()["idempotent_replay"] is True
        assert replay.json()["task"]["id"] == first.json()["task"]["id"]
        assert conflict.status_code == 409
        assert conflict.json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"
    finally:
        app.dependency_overrides.pop(current_user, None)


def test_task_cancellation_is_durable_and_idempotent(monkeypatch):
    c = client(monkeypatch)
    try:
        sid = create_session(c)
        task = create_task(c, sid).json()["task"]
        response = c.post(f"/v1/agent-runtime/tasks/{task['id']}/cancel")
        repeated = c.post(f"/v1/agent-runtime/tasks/{task['id']}/cancel")
        assert response.status_code == 200 and response.json()["cancelled"] is True
        assert response.json()["task"]["state"] == "cancelled"
        assert repeated.status_code == 200 and repeated.json()["cancelled"] is True
    finally:
        app.dependency_overrides.pop(current_user, None)


def test_task_can_be_recovered_by_owner_after_creation(monkeypatch):
    c = client(monkeypatch)
    try:
        sid = create_session(c)
        task = create_task(c, sid).json()["task"]
        recovered = c.get(f"/v1/agent-runtime/tasks/{task['id']}")
        assert recovered.status_code == 200
        assert recovered.json()["task"]["id"] == task["id"]
        assert recovered.json()["task"]["state"] == "created"
    finally:
        app.dependency_overrides.pop(current_user, None)


def test_other_owner_cannot_read_or_cancel_task(monkeypatch):
    c = client(monkeypatch)
    sid = create_session(c)
    task = create_task(c, sid).json()["task"]
    app.dependency_overrides[current_user] = lambda: {"id": "99999999-9999-4999-8999-999999999999"}
    try:
        assert c.get(f"/v1/agent-runtime/tasks/{task['id']}").status_code == 404
        assert c.post(f"/v1/agent-runtime/tasks/{task['id']}/cancel").status_code == 404
    finally:
        app.dependency_overrides.pop(current_user, None)


def test_execution_requires_explicit_versioned_approved_capability(monkeypatch):
    c = client(monkeypatch)
    try:
        sid = create_session(c)
        task = create_task(c, sid).json()["task"]
        FakeRuntimeStore.capability = None
        response = c.post(f"/v1/agent-runtime/tasks/{task['id']}/execute")
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "RUNTIME_POLICY_UNAVAILABLE"
        assert FakeRuntimeStore.tasks[task["id"]]["state"] == "created"
    finally:
        app.dependency_overrides.pop(current_user, None)


def test_approved_tool_execution_persists_result_and_replay(monkeypatch):
    c = client(monkeypatch)
    try:
        sid = create_session(c)
        task = create_task(c, sid).json()["task"]
        response = c.post(f"/v1/agent-runtime/tasks/{task['id']}/execute")
        repeated = c.post(f"/v1/agent-runtime/tasks/{task['id']}/execute")
        assert response.status_code == 200
        assert response.json()["task"]["state"] == "succeeded"
        assert response.json()["task"]["output_payload"]["result"] == {"text": "hello"}
        assert repeated.status_code == 200
        assert repeated.json()["idempotent_replay"] is True
    finally:
        app.dependency_overrides.pop(current_user, None)


def test_recovery_does_not_replay_created_task(monkeypatch):
    c = client(monkeypatch)
    try:
        sid = create_session(c)
        task = create_task(c, sid).json()["task"]
        response = c.post(f"/v1/agent-runtime/tasks/{task['id']}/recover")
        assert response.status_code == 200
        assert response.json()["recovered"] is True
        assert response.json()["replay_performed"] is False
        assert response.json()["task"]["state"] == "created"
    finally:
        app.dependency_overrides.pop(current_user, None)


def test_recovery_marks_stale_unknown_execution_without_replay(monkeypatch):
    from datetime import datetime, timedelta, timezone
    c = client(monkeypatch)
    try:
        sid = create_session(c)
        task = create_task(c, sid).json()["task"]
        row = FakeRuntimeStore.tasks[task["id"]]
        row["state"] = "executing"
        row["updated_at"] = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
        response = c.post(f"/v1/agent-runtime/tasks/{task['id']}/recover")
        assert response.status_code == 200
        assert response.json()["replay_performed"] is False
        assert response.json()["task"]["state"] == "failed"
        assert response.json()["task"]["error_code"] == "EXECUTION_OUTCOME_UNKNOWN"
    finally:
        app.dependency_overrides.pop(current_user, None)

import copy
import hashlib
import json
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
    capability = {"id": "cap-1", "agent_id": AGENT, "capability_key": "text.normalize",
                  "required_permission_scopes": [], "status": "approved",
                  "policy_version": "runtime-policy-v1", "runtime_policy_id": "policy-1",
                  "updated_at": "2026-10-15T00:00:00Z"}
    policy_document = {"policy_version": "runtime-policy-v1", "approved_tool_keys": ["text.normalize"],
                       "required_permission_scopes": []}
    policy = {"id": "policy-1", "agent_id": AGENT, "policy_version": "runtime-policy-v1",
              "policy_document": policy_document,
              "policy_digest": hashlib.sha256(json.dumps(policy_document, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
              "approved_tool_keys": ["text.normalize"], "required_permission_scopes": [],
              "risk_constraints": {}, "status": "approved"}

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

    async def get_approved_runtime_policy(self, agent_id, policy_id):
        return copy.deepcopy(self.policy) if agent_id == AGENT and policy_id == self.policy["id"] and self.policy["status"] == "approved" else None

    async def claim_task(self, owner_id, task_id, lease_token, *, lease_seconds=60):
        row = self.tasks.get(task_id)
        if not row or row["owner_user_id"] != owner_id:
            return None
        if row["state"] not in {"created", "queued", "retrying"} and not (
            row["state"] == "executing" and row.get("effect_outcome") not in {"started", "unknown"}
        ):
            return None
        row.update({"state": "executing", "task_version": row["task_version"] + 1,
                    "execution_lease_token": lease_token, "lease_expires_at": "fake-future",
                    "event_log": list(row.get("event_log") or []) + [{"event": "execution_claimed", "at": "now", "trace_id": row["trace_id"]}]})
        return copy.deepcopy(row)

    async def append_checkpoint(self, owner_id, task_id, lease_token, task_version, sequence, step_key,
                                input_fingerprint, checkpoint_hash, result_payload):
        row = self.tasks.get(task_id)
        if not row or row.get("execution_lease_token") != lease_token or row["task_version"] != task_version:
            return None
        row["checkpoint_seq"] = sequence
        row["checkpoint_hash"] = checkpoint_hash
        row["current_step_key"] = step_key
        row["effect_outcome"] = "completed"
        receipt = {"task_id": task_id, "task_version": task_version, "sequence": sequence, "step_key": step_key,
                   "input_fingerprint": input_fingerprint, "checkpoint_hash": checkpoint_hash,
                   "result_payload": copy.deepcopy(result_payload)}
        row["checkpoint"] = copy.deepcopy(receipt)
        return receipt

    async def get_latest_checkpoint(self, task_id):
        row = self.tasks.get(task_id)
        return copy.deepcopy(row.get("checkpoint")) if row else None

    async def finalize_task(self, owner_id, task_id, lease_token, task_version, *, state, output_payload,
                            error_code, event_log):
        row = self.tasks.get(task_id)
        if not row or row["owner_user_id"] != owner_id or row.get("execution_lease_token") != lease_token or row["task_version"] != task_version:
            return None
        row.update({"state": state, "output_payload": output_payload, "error_code": error_code,
                    "event_log": event_log, "completed_at": "now", "updated_at": "now",
                    "execution_lease_token": None, "lease_expires_at": None, "task_version": row["task_version"] + 1})
        return copy.deepcopy(row)

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
    FakeRuntimeStore.capability = {"id": "cap-1", "agent_id": AGENT, "capability_key": "text.normalize",
                                   "required_permission_scopes": [], "status": "approved",
                                   "policy_version": "runtime-policy-v1", "runtime_policy_id": "policy-1",
                                   "updated_at": "2026-10-15T00:00:00Z"}
    FakeRuntimeStore.policy = {"id": "policy-1", "agent_id": AGENT, "policy_version": "runtime-policy-v1",
                               "policy_document": {"policy_version": "runtime-policy-v1", "approved_tool_keys": ["text.normalize"],
                                                   "required_permission_scopes": []},
                               "policy_digest": hashlib.sha256(json.dumps({"policy_version": "runtime-policy-v1",
                                   "approved_tool_keys": ["text.normalize"], "required_permission_scopes": []},
                                   sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
                               "approved_tool_keys": ["text.normalize"], "required_permission_scopes": [],
                               "risk_constraints": {}, "status": "approved"}


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


def test_cancel_race_with_execution_claim_does_not_overwrite_running_state(monkeypatch):
    c = client(monkeypatch)
    try:
        sid = create_session(c)
        task = create_task(c, sid).json()["task"]
        original_update = FakeRuntimeStore.update_task

        async def race_claim(self, owner_id, task_id, body, *, expected_state=None):
            # Simulate the executor winning the state CAS after cancellation read.
            if body.get("state") == "cancelled":
                FakeRuntimeStore.tasks[task_id]["state"] = "executing"
            return await original_update(self, owner_id, task_id, body, expected_state=expected_state)

        monkeypatch.setattr(FakeRuntimeStore, "update_task", race_claim)
        response = c.post(f"/v1/agent-runtime/tasks/{task['id']}/cancel")
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "TASK_STATE_CHANGED"
        assert FakeRuntimeStore.tasks[task["id"]]["state"] == "executing"
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


def test_runtime_rejects_policy_digest_mismatch_before_claim(monkeypatch):
    c = client(monkeypatch)
    try:
        sid = create_session(c)
        task = create_task(c, sid).json()["task"]
        FakeRuntimeStore.policy["policy_digest"] = "0" * 64
        response = c.post(f"/v1/agent-runtime/tasks/{task['id']}/execute")
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "RUNTIME_POLICY_DIGEST_MISMATCH"
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
        events = response.json()["task"]["event_log"]
        state_sequence = [event["state"] for event in events if "state" in event]
        assert state_sequence == [
            "created", "policy_check", "budget_reserved", "context_building",
            "planning", "executing", "validating", "succeeded",
        ]
        claim_index = next(i for i, event in enumerate(events) if event.get("event") == "execution_claimed")
        assert claim_index == 1
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


def test_execute_resumes_from_matching_checkpoint_without_reinvoking_tool(monkeypatch):
    from datetime import datetime, timedelta, timezone
    c = client(monkeypatch)
    try:
        sid = create_session(c)
        task = create_task(c, sid).json()["task"]
        row = FakeRuntimeStore.tasks[task["id"]]
        result = {
            "state": "succeeded", "result": {"text": "hello"},
            "provider_execution": False, "persistence": "durable_checkpoint",
            "events": [{"state": "succeeded", "trace_id": row["trace_id"]}],
        }
        encoded = json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
        row.update({
            "state": "executing", "task_version": 2,
            "lease_expires_at": (datetime.now(timezone.utc) - timedelta(seconds=5)).isoformat(),
            "effect_outcome": "completed", "checkpoint_seq": 1,
            "checkpoint": {
                "task_id": task["id"], "task_version": 2, "sequence": 1,
                "step_key": "tool:text.normalize", "input_fingerprint": row["request_fingerprint"],
                "checkpoint_hash": hashlib.sha256(encoded).hexdigest(), "result_payload": result,
            },
        })
        async def must_not_execute(*args, **kwargs):
            raise AssertionError("a verified checkpoint must be resumed without re-running the tool")
        monkeypatch.setattr("allpha_api.agent_runtime_api._runtime.execute_tool", must_not_execute)
        response = c.post(f"/v1/agent-runtime/tasks/{task['id']}/execute")
        assert response.status_code == 200
        assert response.json()["task"]["state"] == "succeeded"
        assert response.json()["task"]["output_payload"]["result"] == {"text": "hello"}
        assert FakeRuntimeStore.tasks[task["id"]]["execution_lease_token"] is None
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

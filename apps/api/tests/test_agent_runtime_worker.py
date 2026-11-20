import asyncio

from fastapi import HTTPException

from allpha_api import agent_runtime_worker as worker
from allpha_api.agent_runtime_store import AgentRuntimePersistenceError


class FakeStore:
    def __init__(self, rows):
        self.rows = rows
        self.unknown = []
        self.fail_unknown = False
        self.reaped = 0
        self.failed_unclaimed = []
        self.readiness = {"ready": True, "missing_tables": [], "missing_columns": [], "missing_functions": []}

    async def runtime_schema_readiness(self):
        return self.readiness

    async def reap_retry_exhaustion(self):
        self.reaped += 1
        return 0

    async def fail_unclaimed_task(self, owner_id, task_id, task_version, error_code, lease_token=None):
        self.failed_unclaimed.append((owner_id, task_id, task_version, error_code, lease_token))
        return {"id": task_id, "state": "failed"}

    async def list_runnable_planned_tasks(self, *, limit=10):
        return self.rows[:limit]

    async def mark_unknown_effect(self, owner_id, task_id):
        if self.fail_unknown:
            raise AgentRuntimePersistenceError("unknown outcome")
        self.unknown.append((owner_id, task_id))
        return {"id": task_id, "state": "failed"}


def test_worker_routes_planned_unknown_effects_to_reconciliation_executor(monkeypatch):
    store = FakeStore([
        {"id": "task-unknown", "owner_user_id": "owner-1", "state": "executing", "effect_outcome": "unknown", "input_payload": {"_runtime_plan_version": 1}},
        {"id": "task-created", "owner_user_id": "owner-1", "state": "created", "effect_outcome": None},
    ])
    executed = []

    async def fake_execute(received_store, owner_id, task_id, row):
        executed.append((owner_id, task_id, row.get("effect_outcome")))
        return {"task": {"id": task_id, "state": "succeeded"}}

    monkeypatch.setattr(worker, "_execute_planned_task", fake_execute)
    processed = asyncio.run(worker.run_once(store))

    assert processed == 2
    assert store.reaped == 1
    assert store.unknown == []
    assert executed == [("owner-1", "task-unknown", "unknown"), ("owner-1", "task-created", None)]


def test_worker_stops_batch_when_unknown_effect_cannot_be_terminalized(monkeypatch):
    store = FakeStore([
        {"id": "task-unknown", "owner_user_id": "owner-1", "state": "executing", "effect_outcome": "started", "input_payload": {"_native_orchestration_version": 1}},
        {"id": "task-created", "owner_user_id": "owner-1", "state": "created", "effect_outcome": None},
    ])
    store.fail_unknown = True
    executed = []

    async def fake_execute(received_store, owner_id, task_id, row):
        executed.append(task_id)

    monkeypatch.setattr(worker, "_execute_planned_task", fake_execute)
    processed = asyncio.run(worker.run_once(store))

    assert processed == 0
    assert store.reaped == 1
    assert executed == []



def test_worker_terminalizes_unclaimed_preflight_failures(monkeypatch):
    store = FakeStore([
        {"id": "task-denied", "owner_user_id": "owner-1", "state": "created", "task_version": 4},
    ])

    async def reject_before_claim(received_store, owner_id, task_id, row):
        raise HTTPException(status_code=403, detail={
            "code": "RUNTIME_POLICY_SCOPE_DENIED",
            "message": "Policy scope tidak mengizinkan tool.",
        })

    monkeypatch.setattr(worker, "_execute_planned_task", reject_before_claim)
    processed = asyncio.run(worker.run_once(store))

    assert processed == 1
    assert store.failed_unclaimed == [
        ("owner-1", "task-denied", 4, "RUNTIME_POLICY_SCOPE_DENIED", None)
    ]



def test_worker_does_not_claim_tasks_when_canonical_schema_is_incomplete(monkeypatch):
    store = FakeStore([
        {"id": "task-1", "owner_user_id": "owner-1", "state": "created"},
    ])
    store.readiness = {
        "ready": False,
        "missing_tables": ["agent_runtime_tool_plans"],
        "missing_columns": ["agent_runtime_tasks.execution_attempts"],
        "missing_functions": ["public.heartbeat_agent_runtime_task(uuid,uuid,uuid,integer,integer)"],
    }
    executed = []

    async def must_not_execute(received_store, owner_id, task_id, row):
        executed.append(task_id)

    monkeypatch.setattr(worker, "_execute_planned_task", must_not_execute)
    processed = asyncio.run(worker.run_once(store))

    assert processed == 0
    assert store.reaped == 0
    assert executed == []


def test_worker_still_terminalizes_unknown_native_effects(monkeypatch):
    store = FakeStore([
        {"id": "native-unknown", "owner_user_id": "owner-1", "state": "executing",
         "effect_outcome": "unknown", "input_payload": {"_native_orchestration_version": 1}},
        {"id": "planned", "owner_user_id": "owner-1", "state": "created",
         "input_payload": {"_runtime_plan_version": 1}},
    ])
    executed = []

    async def fake_execute(received_store, owner_id, task_id, row):
        executed.append(task_id)

    monkeypatch.setattr(worker, "_execute_planned_task", fake_execute)
    processed = asyncio.run(worker.run_once(store))
    assert processed == 2
    assert store.unknown == [("owner-1", "native-unknown")]
    assert executed == ["planned"]

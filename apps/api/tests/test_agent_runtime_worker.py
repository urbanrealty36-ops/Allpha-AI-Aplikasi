import asyncio

import pytest

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
    monkeypatch.setenv("ALLPHA_AGENT_RUNTIME_WORKER_CONCURRENCY", "1")
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



def test_wp06_social_tasks_stay_queued_until_social_schema_readiness(monkeypatch):
    monkeypatch.setenv("ALLPHA_AGENT_SOCIAL_AUTOMATION_SCHEMA_ENABLED", "true")
    monkeypatch.setenv("ALLPHA_AGENT_SOCIAL_AUTOMATION_WORKER_ENABLED", "true")

    class SocialGateStore(FakeStore):
        def __init__(self, rows):
            super().__init__(rows)
            self.readiness_calls = 0

        async def request(self, method, path, body=None):
            assert method == "POST"
            assert path == "rpc/agent_social_automation_schema_readiness"
            self.readiness_calls += 1
            return {"ready": False, "missing_tables": ["agent_social_automation_events"],
                    "missing_functions": [], "missing_privileges": []}

    store = SocialGateStore([
        {"id": "social-task", "owner_user_id": "owner-1", "state": "created",
         "input_payload": {"_agent_social_reply_version": 1}},
        {"id": "ordinary-task", "owner_user_id": "owner-1", "state": "created",
         "input_payload": {"_runtime_plan_version": 1}},
    ])
    executed = []

    async def fake_execute(received_store, owner_id, task_id, row):
        executed.append(task_id)

    async def forbidden_social(*args, **kwargs):
        raise AssertionError("social intake must not run before WP-06 schema readiness")

    monkeypatch.setattr(worker, "_execute_planned_task", fake_execute)
    monkeypatch.setattr(worker, "run_social_events_once", forbidden_social)
    monkeypatch.setattr(worker, "reconcile_social_reply_approvals", forbidden_social)

    processed = asyncio.run(worker.run_once(store))

    assert store.readiness_calls == 1
    assert processed == 1
    assert executed == ["ordinary-task"]


def test_wp06_social_worker_requires_both_explicit_activation_flags(monkeypatch):
    monkeypatch.setenv("ALLPHA_AGENT_SOCIAL_AUTOMATION_SCHEMA_ENABLED", "true")
    monkeypatch.setenv("ALLPHA_AGENT_SOCIAL_AUTOMATION_WORKER_ENABLED", "false")

    class NoRpcStore(FakeStore):
        async def request(self, *args, **kwargs):
            raise AssertionError("disabled WP-06 consumer must not query readiness")

    assert asyncio.run(worker._social_schema_ready(NoRpcStore([]))) is False


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



def test_worker_processes_independent_tasks_with_bounded_concurrency(monkeypatch):
    monkeypatch.setenv("ALLPHA_AGENT_RUNTIME_WORKER_CONCURRENCY", "3")
    store = FakeStore([
        {"id": "task-1", "owner_user_id": "owner-1", "state": "created",
         "input_payload": {"_runtime_plan_version": 1}},
        {"id": "task-2", "owner_user_id": "owner-1", "state": "created",
         "input_payload": {"_runtime_plan_version": 1}},
        {"id": "task-3", "owner_user_id": "owner-1", "state": "created",
         "input_payload": {"_runtime_plan_version": 1}},
    ])
    active = 0
    peak = 0

    async def fake_execute(received_store, owner_id, task_id, row):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.01)
        active -= 1
        return {"task": {"id": task_id, "state": "succeeded"}}

    async def no_social_events(*args, **kwargs):
        return 0

    async def no_approval_reconciliation(*args, **kwargs):
        return 0

    monkeypatch.setattr(worker, "_execute_planned_task", fake_execute)
    monkeypatch.setattr(worker, "run_social_events_once", no_social_events)
    monkeypatch.setattr(worker, "reconcile_social_reply_approvals", no_approval_reconciliation)

    processed = asyncio.run(worker.run_once(store))

    assert processed == 3
    assert peak == 3



def test_disabled_worker_remains_idle_without_opening_runtime_store(monkeypatch):
    monkeypatch.setenv("ALLPHA_AGENT_RUNTIME_WORKER_ENABLED", "false")

    def forbidden_store():
        raise AssertionError("disabled worker must not initialize a database connection")

    monkeypatch.setattr(worker.AgentRuntimeStore, "from_environment", forbidden_store)

    async def check_idle():
        task = asyncio.create_task(worker.serve())
        await asyncio.sleep(0)
        assert not task.done()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(check_idle())

from datetime import datetime, timezone
import asyncio

import pytest

from allpha_api.workflow_store import WorkflowPersistenceError
from allpha_api.workflow_worker import (
    WorkflowApprovalRequired, WorkflowNodeError, WorkflowOutcomeUnknown,
    evaluate_deterministic_node, execute_agent_task_node, process_next_step,
)


def run(**overrides):
    body = {
        "id": "run-1", "status": "running", "created_at": "2026-10-16T23:00:00+00:00",
        "started_at": "2026-10-16T23:00:00+00:00", "max_runtime_seconds": None,
        "input_payload": {"name": "Ada"}, "steps": [],
    }
    body.update(overrides)
    return body


def step(**overrides):
    body = {
        "id": "step-1", "node_key": "greet", "node_kind": "input",
        "node_config": {"field": "name"}, "depends_on": [], "attempts": 1,
        "max_attempts": 2, "status": "running",
    }
    body.update(overrides)
    return body


def test_deterministic_input_and_constant_nodes_produce_checkpoint():
    output = evaluate_deterministic_node(step(), run())
    assert output["output_payload"] == {"value": "Ada"}
    assert output["checkpoint"]["output"] == {"value": "Ada"}
    assert evaluate_deterministic_node(step(node_kind="constant", node_config={"value": 7}), run())["output_payload"] == {"value": 7}


def test_concat_uses_dependency_order_and_only_scalar_values():
    source = step(id="s1", node_key="left", node_kind="constant", node_config={"value": "A"})
    other = step(id="s2", node_key="right", node_kind="constant", node_config={"value": "B"})
    target = step(node_kind="concat", node_config={"separator": "-"}, depends_on=["right", "left"])
    result = evaluate_deterministic_node(target, run(steps=[
        {**source, "status": "succeeded", "output_payload": {"value": "A"}},
        {**other, "status": "succeeded", "output_payload": {"value": "B"}},
    ]))
    assert result["output_payload"] == {"value": "B-A"}


def test_missing_input_fails_without_arbitrary_execution():
    with pytest.raises(WorkflowNodeError):
        evaluate_deterministic_node(step(node_config={"field": "absent"}), run())


class FakeStore:
    def __init__(self, *, claim=None, finalize=None, latest=None, timeout=None):
        self.claimed = claim
        self.finalized = finalize
        self.latest = latest or run()
        self.finalize_error = finalize if isinstance(finalize, Exception) else None
        self.timeout_result = timeout
        self.finalize_calls = 0
        self.heartbeat_calls = []
        self.heartbeat_result = {"status": "running"}
        self.heartbeat_error = None

    async def get_run(self, owner_id, run_id):
        return self.latest

    async def claim_step(self, owner_id, run_id, lease_token, *, lease_seconds=30):
        return self.claimed

    async def heartbeat_step(self, owner_id, run_id, step_id, lease_token, *, lease_seconds=30):
        self.heartbeat_calls.append((owner_id, run_id, step_id, lease_token, lease_seconds))
        if self.heartbeat_error:
            raise self.heartbeat_error
        return self.heartbeat_result

    async def finalize_step(self, **kwargs):
        self.finalize_calls += 1
        if self.finalize_error:
            raise self.finalize_error
        return self.finalized

    async def timeout_run(self, owner_id, run_id):
        return self.timeout_result


def test_no_claim_returns_idle_without_mutating_state():
    store = FakeStore()
    result = asyncio.run(process_next_step(store, owner_id="owner", run_id="run-1"))
    assert result == {"outcome": "idle", "run_status": "running"}


def test_finalize_unknown_outcome_is_reconciled_if_checkpoint_was_committed():
    claimed = step()
    latest = run(steps=[{**claimed, "status": "succeeded", "output_payload": {"value": "Ada"}}])
    store = FakeStore(claim=claimed, finalize=WorkflowPersistenceError("timeout"), latest=latest)
    result = asyncio.run(process_next_step(store, owner_id="owner", run_id="run-1"))
    assert result["outcome"] == "reconciled"
    assert result["step_status"] == "succeeded"
    assert store.finalize_calls == 1


def test_finalize_unknown_outcome_is_not_replayed_when_not_observable():
    claimed = step()
    store = FakeStore(claim=claimed, finalize=WorkflowPersistenceError("timeout"), latest=run(steps=[claimed]))
    with pytest.raises(WorkflowOutcomeUnknown):
        asyncio.run(process_next_step(store, owner_id="owner", run_id="run-1"))
    assert store.finalize_calls == 1


def test_expired_runtime_requests_atomic_timeout_instead_of_running_node():
    store = FakeStore(timeout={"status": "timed_out"})
    store.latest = run(created_at="2026-10-16T00:00:00+00:00", started_at="2026-10-16T00:00:00+00:00", max_runtime_seconds=10)
    result = asyncio.run(process_next_step(store, owner_id="owner", run_id="run-1", now=datetime(2026, 10, 16, 0, 1, tzinfo=timezone.utc)))
    assert result == {"outcome": "terminal", "run_status": "timed_out"}


def test_terminal_run_is_never_claimed():
    store = FakeStore(latest=run(status="cancelled"))
    result = asyncio.run(process_next_step(store, owner_id="owner", run_id="run-1"))
    assert result == {"outcome": "terminal", "run_status": "cancelled"}


def test_retryable_deterministic_runtime_error_is_bounded_by_attempt_count(monkeypatch):
    import allpha_api.workflow_worker as worker
    claimed = step(attempts=1, max_attempts=2)
    monkeypatch.setattr(worker, "evaluate_deterministic_node", lambda *_: (_ for _ in ()).throw(RuntimeError("temporary")))
    store = FakeStore(claim=claimed, finalize={"status": "retrying"})
    result = asyncio.run(process_next_step(store, owner_id="owner", run_id="run-1"))
    assert result["step_status"] == "retrying"


def test_retry_limit_forces_terminal_failure(monkeypatch):
    import allpha_api.workflow_worker as worker
    claimed = step(attempts=2, max_attempts=2)
    monkeypatch.setattr(worker, "evaluate_deterministic_node", lambda *_: (_ for _ in ()).throw(RuntimeError("temporary")))
    store = FakeStore(claim=claimed, finalize={"status": "failed"})
    result = asyncio.run(process_next_step(store, owner_id="owner", run_id="run-1"))
    assert result["step_status"] == "failed"


def test_claimed_step_persists_output_and_checkpoint_with_same_lease():
    claimed = step()
    store = FakeStore(claim=claimed, finalize={
        "status": "succeeded", "run_status": "running",
    })
    captured = {}

    async def finalize(**kwargs):
        captured.update(kwargs)
        store.finalize_calls += 1
        return store.finalized

    store.finalize_step = finalize
    result = asyncio.run(process_next_step(store, owner_id="owner", run_id="run-1"))

    assert result["step_status"] == "succeeded"
    assert captured["terminal_state"] == "succeeded"
    assert captured["output_payload"] == {"value": "Ada"}
    assert captured["checkpoint"] == {
        "node_key": "greet", "output": {"value": "Ada"},
    }
    assert captured["lease_token"]


def test_claim_unknown_outcome_does_not_execute_or_finalize():
    class ClaimUnknownStore(FakeStore):
        async def claim_step(self, owner_id, run_id, lease_token, *, lease_seconds=30):
            raise WorkflowPersistenceError("claim response timed out")

    store = ClaimUnknownStore(claim=step())
    with pytest.raises(WorkflowOutcomeUnknown, match="claim"):
        asyncio.run(process_next_step(store, owner_id="owner", run_id="run-1"))
    assert store.finalize_calls == 0


def test_cancellation_observed_after_claim_never_finalizes_step():
    class CancelAfterClaimStore(FakeStore):
        def __init__(self):
            super().__init__(claim=step(), latest=run())
            self.read_count = 0

        async def get_run(self, owner_id, run_id):
            self.read_count += 1
            if self.read_count == 1:
                return run()
            return run(status="cancelled", cancel_requested=True)

    store = CancelAfterClaimStore()
    result = asyncio.run(process_next_step(store, owner_id="owner", run_id="run-1"))

    assert result["outcome"] == "terminal"
    assert result["run_status"] == "cancelled"
    assert store.finalize_calls == 0


def test_completed_step_is_not_reexecuted_when_claim_returns_none():
    completed = {
        **step(),
        "status": "succeeded",
        "output_payload": {"value": "Ada"},
        "checkpoint": {"node_key": "greet", "output": {"value": "Ada"}},
    }
    store = FakeStore(claim=None, latest=run(steps=[completed]))
    result = asyncio.run(process_next_step(store, owner_id="owner", run_id="run-1"))

    assert result["outcome"] == "idle"
    assert store.finalize_calls == 0


def test_long_running_node_renews_its_lease_until_completion(monkeypatch):
    import allpha_api.workflow_worker as worker

    monkeypatch.setattr(worker, "_heartbeat_interval", lambda _seconds: 0.01)
    claimed = step(node_kind="agent_task")
    store = FakeStore(claim=claimed, finalize={"status": "succeeded", "run_status": "running"})

    async def slow_node(*_args):
        await asyncio.sleep(0.05)
        return {"output_payload": {"value": "done"}, "checkpoint": {"node_key": "greet"}}

    monkeypatch.setattr(worker, "execute_agent_task_node", slow_node)
    result = asyncio.run(process_next_step(store, owner_id="owner", run_id="run-1", lease_seconds=5))

    assert result["step_status"] == "succeeded"
    assert len(store.heartbeat_calls) >= 1
    assert store.finalize_calls == 1
    assert store.heartbeat_calls[0][0:3] == ("owner", "run-1", "step-1")
    assert store.heartbeat_calls[0][4] == 5


def test_lost_workflow_lease_cancels_node_and_never_finalizes(monkeypatch):
    import allpha_api.workflow_worker as worker

    monkeypatch.setattr(worker, "_heartbeat_interval", lambda _seconds: 0.01)
    claimed = step(node_kind="agent_task")
    store = FakeStore(claim=claimed)
    store.heartbeat_result = None
    cancelled = asyncio.Event()

    async def slow_node(*_args):
        try:
            await asyncio.sleep(1)
        finally:
            cancelled.set()
        return {"output_payload": {"value": "unsafe"}, "checkpoint": {"node_key": "greet"}}

    monkeypatch.setattr(worker, "execute_agent_task_node", slow_node)
    with pytest.raises(WorkflowOutcomeUnknown, match="lease was lost"):
        asyncio.run(process_next_step(store, owner_id="owner", run_id="run-1", lease_seconds=5))

    assert cancelled.is_set()
    assert store.finalize_calls == 0


def test_uncertain_workflow_heartbeat_never_finalizes_or_retries_node(monkeypatch):
    import allpha_api.workflow_worker as worker

    monkeypatch.setattr(worker, "_heartbeat_interval", lambda _seconds: 0.01)
    claimed = step(node_kind="agent_task")
    store = FakeStore(claim=claimed)
    store.heartbeat_error = WorkflowPersistenceError("heartbeat response timeout")

    async def slow_node(*_args):
        await asyncio.sleep(1)
        return {"output_payload": {"value": "unknown"}, "checkpoint": {"node_key": "greet"}}

    monkeypatch.setattr(worker, "execute_agent_task_node", slow_node)
    with pytest.raises(WorkflowOutcomeUnknown, match="heartbeat outcome is unknown"):
        asyncio.run(process_next_step(store, owner_id="owner", run_id="run-1", lease_seconds=5))
    assert store.finalize_calls == 0



class FakeAgentRuntimeStore:
    def __init__(self, occurrence_status="outcome_unknown", runtime_task_id=None):
        self.schedule = {
            "id": "schedule-1", "owner_user_id": "owner-1", "status": "active",
            "require_approval": False, "agent_id": "agent-1", "skill_id": "skill-1",
            "created_by_agent_version": 1, "created_by_skill_version": 1,
            "session_id": "session-1", "tool_key": "text.normalize",
            "input_payload": {"text": "hello"}, "budget_limit": {},
        }
        self.occurrence = {
            "id": "schedule-run-1", "schedule_id": "schedule-1", "owner_user_id": "owner-1",
            "status": occurrence_status, "runtime_task_id": runtime_task_id,
            "idempotency_key": "schedule-run-idem-1", "trace_id": "trace-schedule-1",
            "approved_at": None, "started_at": None,
        }
        self.patches = []

    async def request(self, method, path, *, params=None, body=None, prefer=None):
        if method == "GET" and path == "agent_task_schedules":
            return [self.schedule]
        if method == "GET" and path == "agent_task_schedule_runs":
            return [self.occurrence]
        if method == "PATCH" and path == "agent_task_schedule_runs":
            self.patches.append((path, body))
            self.occurrence.update(body or {})
            return [self.occurrence]
        if method == "PATCH" and path == "agent_task_schedules":
            self.patches.append((path, body))
            self.schedule.update(body or {})
            return [self.schedule]
        raise AssertionError(f"unexpected Agent Runtime persistence request: {method} {path}")

    async def get_agent(self, owner_id, agent_id):
        return {"id": agent_id, "version": 1}

    async def get_skill(self, owner_id, agent_id, skill_id):
        return {"id": skill_id, "version": 1, "status": "published"}

    async def get_approved_capability(self, agent_id, tool_key):
        return {"risk_level": "low"}


def test_agent_task_node_reconciles_outcome_unknown_occurrence_with_same_idempotency_key(monkeypatch):
    runtime_store = FakeAgentRuntimeStore(occurrence_status="outcome_unknown")
    monkeypatch.setattr(
        "allpha_api.workflow_worker.AgentRuntimeStore.from_environment",
        lambda: runtime_store,
    )
    created = {}

    async def fake_create_task(payload, request, user):
        created["idempotency_key"] = payload.idempotency_key
        created["owner_id"] = user["id"]
        return {"task": {"id": "22222222-2222-4222-8222-222222222222"}}

    async def fake_execute_task(task_id, user):
        assert str(task_id) == "22222222-2222-4222-8222-222222222222"
        return {"task": {"state": "succeeded", "output_payload": {"summary": "done"}}}

    monkeypatch.setattr("allpha_api.workflow_worker.create_task", fake_create_task)
    monkeypatch.setattr("allpha_api.workflow_worker.execute_task", fake_execute_task)

    result = asyncio.run(execute_agent_task_node(
        {"node_config": {"schedule_id": "schedule-1"}, "node_key": "agent"},
        {"input_payload": {"schedule_run_id": "schedule-run-1"}},
        "owner-1",
    ))
    assert created == {"idempotency_key": "schedule-run-idem-1", "owner_id": "owner-1"}
    assert result["output_payload"]["runtime_task_id"] == "22222222-2222-4222-8222-222222222222"
    assert runtime_store.occurrence["status"] == "succeeded"


def test_agent_task_node_preserves_unknown_execution_for_reconciliation(monkeypatch):
    runtime_store = FakeAgentRuntimeStore(
        occurrence_status="running",
        runtime_task_id="22222222-2222-4222-8222-222222222222",
    )
    monkeypatch.setattr(
        "allpha_api.workflow_worker.AgentRuntimeStore.from_environment",
        lambda: runtime_store,
    )

    async def fail_unknown(*args):
        raise RuntimeError("Agent Runtime response was lost")

    monkeypatch.setattr("allpha_api.workflow_worker.execute_task", fail_unknown)

    async def scenario():
        with pytest.raises(WorkflowOutcomeUnknown, match="same persisted task/idempotency identity"):
            await execute_agent_task_node(
                {"node_config": {"schedule_id": "schedule-1"}, "node_key": "agent"},
                {"input_payload": {"schedule_run_id": "schedule-run-1"}},
                "owner-1",
            )

    asyncio.run(scenario())
    assert runtime_store.occurrence["status"] == "outcome_unknown"


def test_agent_task_node_pauses_workflow_for_agent_runtime_approval(monkeypatch):
    runtime_store = FakeAgentRuntimeStore(
        occurrence_status="running",
        runtime_task_id="22222222-2222-4222-8222-222222222222",
    )
    monkeypatch.setattr(
        "allpha_api.workflow_worker.AgentRuntimeStore.from_environment",
        lambda: runtime_store,
    )

    async def waiting_for_approval(*args):
        return {"task": {"state": "waiting_for_approval", "output_payload": {}}}

    monkeypatch.setattr("allpha_api.workflow_worker.execute_task", waiting_for_approval)

    async def scenario():
        with pytest.raises(WorkflowApprovalRequired) as exc:
            await execute_agent_task_node(
                {"node_config": {"schedule_id": "schedule-1"}, "node_key": "agent"},
                {"input_payload": {"schedule_run_id": "schedule-run-1"}},
                "owner-1",
            )
        assert exc.value.context["runtime_state"] == "waiting_for_approval"
        assert exc.value.context["approval_surface"] == "agent_runtime"

    asyncio.run(scenario())
    assert runtime_store.occurrence["status"] == "waiting_for_approval"



def test_unknown_agent_runtime_task_outcome_does_not_finalize_workflow_step(monkeypatch):
    import allpha_api.workflow_worker as worker
    store = FakeStore(claim=step(node_kind="agent_task"), finalize={"status": "failed"})

    async def unknown(*args):
        raise WorkflowOutcomeUnknown("Agent Runtime outcome is unknown")

    monkeypatch.setattr(worker, "execute_agent_task_node", unknown)

    with pytest.raises(WorkflowOutcomeUnknown, match="Agent Runtime outcome"):
        asyncio.run(process_next_step(store, owner_id="owner", run_id="run-1"))
    assert store.finalize_calls == 0



def test_approval_node_pauses_and_persists_owner_decision_context():
    claimed = step(
        node_kind="approval",
        node_config={"message": "Approve the publish action", "context": {"artifact_id": "artifact-1"}},
    )
    captured = {}

    async def finalize(**kwargs):
        captured.update(kwargs)
        return {"status": kwargs["terminal_state"], "run_status": "waiting_for_approval"}

    store = FakeStore(claim=claimed, finalize={"status": "waiting_for_approval"})
    store.finalize_step = finalize
    result = asyncio.run(process_next_step(store, owner_id="owner", run_id="run-1"))
    assert result["step_status"] == "waiting_for_approval"
    assert captured["terminal_state"] == "waiting_for_approval"
    assert captured["error_code"] == "APPROVAL_REQUIRED"
    assert captured["checkpoint"]["approval_message"] == "Approve the publish action"
    assert captured["checkpoint"]["approval_context"] == {"artifact_id": "artifact-1"}


def test_approved_workflow_step_resumes_from_durable_approval_checkpoint():
    claimed = step(
        node_kind="approval",
        node_config={"message": "Approve the publish action", "context": {}},
        checkpoint={
            "approval_status": "approved",
            "approval_id": "approval-1",
            "approval_decision_note": "Reviewed",
        },
    )
    captured = {}

    async def finalize(**kwargs):
        captured.update(kwargs)
        return {"status": kwargs["terminal_state"], "run_status": "running"}

    store = FakeStore(claim=claimed, finalize={"status": "succeeded"})
    store.finalize_step = finalize
    result = asyncio.run(process_next_step(store, owner_id="owner", run_id="run-1"))
    assert result["step_status"] == "succeeded"
    assert captured["output_payload"] == {
        "value": {"approved": True, "approval_id": "approval-1", "decision_note": "Reviewed"},
    }

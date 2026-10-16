from datetime import datetime, timezone

import pytest

from allpha_api.workflow_store import WorkflowPersistenceError
from allpha_api.workflow_worker import (
    WorkflowNodeError, WorkflowOutcomeUnknown, evaluate_deterministic_node, process_next_step,
)


def run(**overrides):
    body = {
        "id": "run-1", "status": "running", "created_at": "2026-10-16T23:00:00+00:00",
        "started_at": "2026-10-16T23:00:00+00:00", "max_runtime_seconds": 120,
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

    async def get_run(self, owner_id, run_id):
        return self.latest

    async def claim_step(self, owner_id, run_id, lease_token, *, lease_seconds=30):
        return self.claimed

    async def finalize_step(self, **kwargs):
        self.finalize_calls += 1
        if self.finalize_error:
            raise self.finalize_error
        return self.finalized

    async def timeout_run(self, owner_id, run_id):
        return self.timeout_result


@pytest.mark.asyncio
async def test_no_claim_returns_idle_without_mutating_state():
    store = FakeStore()
    result = await process_next_step(store, owner_id="owner", run_id="run-1")
    assert result == {"outcome": "idle", "run_status": "running"}


@pytest.mark.asyncio
async def test_finalize_unknown_outcome_is_reconciled_if_checkpoint_was_committed():
    claimed = step()
    latest = run(steps=[{**claimed, "status": "succeeded", "output_payload": {"value": "Ada"}}])
    store = FakeStore(claim=claimed, finalize=WorkflowPersistenceError("timeout"), latest=latest)
    result = await process_next_step(store, owner_id="owner", run_id="run-1")
    assert result["outcome"] == "reconciled"
    assert result["step_status"] == "succeeded"
    assert store.finalize_calls == 1


@pytest.mark.asyncio
async def test_finalize_unknown_outcome_is_not_replayed_when_not_observable():
    claimed = step()
    store = FakeStore(claim=claimed, finalize=WorkflowPersistenceError("timeout"), latest=run(steps=[claimed]))
    with pytest.raises(WorkflowOutcomeUnknown):
        await process_next_step(store, owner_id="owner", run_id="run-1")
    assert store.finalize_calls == 1


@pytest.mark.asyncio
async def test_expired_runtime_requests_atomic_timeout_instead_of_running_node():
    store = FakeStore(timeout={"status": "timed_out"})
    store.latest = run(created_at="2026-10-16T00:00:00+00:00", started_at="2026-10-16T00:00:00+00:00", max_runtime_seconds=10)
    result = await process_next_step(store, owner_id="owner", run_id="run-1", now=datetime(2026, 10, 16, 0, 1, tzinfo=timezone.utc))
    assert result == {"outcome": "terminal", "run_status": "timed_out"}


@pytest.mark.asyncio
async def test_terminal_run_is_never_claimed():
    store = FakeStore(latest=run(status="cancelled"))
    result = await process_next_step(store, owner_id="owner", run_id="run-1")
    assert result == {"outcome": "terminal", "run_status": "cancelled"}


@pytest.mark.asyncio
async def test_retryable_deterministic_runtime_error_is_bounded_by_attempt_count(monkeypatch):
    import allpha_api.workflow_worker as worker
    claimed = step(attempts=1, max_attempts=2)
    monkeypatch.setattr(worker, "evaluate_deterministic_node", lambda *_: (_ for _ in ()).throw(RuntimeError("temporary")))
    store = FakeStore(claim=claimed, finalize={"status": "retrying"})
    result = await process_next_step(store, owner_id="owner", run_id="run-1")
    assert result["step_status"] == "retrying"


@pytest.mark.asyncio
async def test_retry_limit_forces_terminal_failure(monkeypatch):
    import allpha_api.workflow_worker as worker
    claimed = step(attempts=2, max_attempts=2)
    monkeypatch.setattr(worker, "evaluate_deterministic_node", lambda *_: (_ for _ in ()).throw(RuntimeError("temporary")))
    store = FakeStore(claim=claimed, finalize={"status": "failed"})
    result = await process_next_step(store, owner_id="owner", run_id="run-1")
    assert result["step_status"] == "failed"

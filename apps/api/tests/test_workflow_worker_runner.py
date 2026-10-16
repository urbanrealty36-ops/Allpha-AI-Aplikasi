import asyncio

import pytest

from allpha_api.workflow_store import WorkflowPersistenceError
from allpha_api.workflow_worker import WorkflowOutcomeUnknown
import allpha_api.workflow_worker_runner as runner


class CandidateStore:
    def __init__(self, candidates):
        self.candidates = candidates
        self.limit_seen = None

    async def list_runnable_runs(self, *, limit=25):
        self.limit_seen = limit
        return self.candidates


def test_poll_batch_invokes_one_step_per_runnable_candidate(monkeypatch):
    store = CandidateStore([
        {"id": "run-a", "owner_user_id": "owner-a", "status": "queued"},
        {"id": "run-b", "owner_user_id": "owner-b", "status": "running"},
    ])
    calls = []

    async def process(store_arg, *, owner_id, run_id, lease_seconds):
        calls.append((owner_id, run_id, lease_seconds))
        return {"outcome": "step_finalized", "step_status": "succeeded"}

    monkeypatch.setattr(runner, "process_next_step", process)
    summary = asyncio.run(runner.process_runnable_batch(store, limit=2, lease_seconds=45))

    assert store.limit_seen == 2
    assert calls == [("owner-a", "run-a", 45), ("owner-b", "run-b", 45)]
    assert summary == {
        "candidates": 2, "processed": 2, "idle": 0, "terminal": 0,
        "unknown": 0, "errors": 0,
    }


def test_unknown_outcome_is_not_retried_in_same_batch(monkeypatch):
    store = CandidateStore([{"id": "run-a", "owner_user_id": "owner-a"}])
    calls = 0

    async def process(*args, **kwargs):
        nonlocal calls
        calls += 1
        raise WorkflowOutcomeUnknown("unknown")

    monkeypatch.setattr(runner, "process_next_step", process)
    summary = asyncio.run(runner.process_runnable_batch(store))

    assert calls == 1
    assert summary["unknown"] == 1
    assert summary["processed"] == 0


def test_poll_batch_isolates_persistence_error_to_candidate(monkeypatch):
    store = CandidateStore([
        {"id": "run-a", "owner_user_id": "owner-a"},
        {"id": "run-b", "owner_user_id": "owner-b"},
    ])

    async def process(store_arg, *, owner_id, run_id, lease_seconds):
        if run_id == "run-a":
            raise WorkflowPersistenceError("temporary")
        return {"outcome": "idle", "run_status": "running"}

    monkeypatch.setattr(runner, "process_next_step", process)
    summary = asyncio.run(runner.process_runnable_batch(store))

    assert summary["errors"] == 1
    assert summary["idle"] == 1


def test_poll_batch_skips_malformed_candidate_without_guessing_owner(monkeypatch):
    store = CandidateStore([{"id": "run-a"}, {"owner_user_id": "owner-b"}])
    calls = []

    async def process(*args, **kwargs):
        calls.append((args, kwargs))
        return {"outcome": "idle", "run_status": "running"}

    monkeypatch.setattr(runner, "process_next_step", process)
    summary = asyncio.run(runner.process_runnable_batch(store))

    assert calls == []
    assert summary["errors"] == 2


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"limit": 0}, "limit"),
        ({"limit": 101}, "limit"),
        ({"lease_seconds": 4}, "lease_seconds"),
        ({"lease_seconds": 121}, "lease_seconds"),
    ],
)
def test_poll_batch_rejects_unbounded_parameters(kwargs, message):
    with pytest.raises(ValueError, match=message):
        asyncio.run(runner.process_runnable_batch(CandidateStore([]), **kwargs))

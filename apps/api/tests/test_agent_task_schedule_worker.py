from datetime import datetime, timedelta, timezone
import uuid

import pytest

from allpha_api.agent_task_schedule_worker import process_due_schedules
from allpha_api.workflow_engine import WorkflowDefinition, WorkflowNode


class FakeRuntimeStore:
    def __init__(self, schedule):
        self.schedule = schedule
        self.occurrences = []
        self.schedule_patches = []

    async def request(self, method, path, *, params=None, body=None, prefer=None):
        params, body = params or {}, body or {}
        if method == "POST" and path == "rpc/claim_due_agent_task_schedules":
            self.schedule["lease_token"] = body["p_lease_token"]
            return [dict(self.schedule)]
        if method == "GET" and path == "agent_task_schedule_runs":
            rows = [row for row in self.occurrences
                    if row["schedule_id"] == params.get("schedule_id", "").removeprefix("eq.")
                    and row["scheduled_for"] == params.get("scheduled_for", "").removeprefix("eq.")]
            return rows[:1]
        if method == "POST" and path == "agent_task_schedule_runs":
            row = {"id": str(uuid.uuid4()), **body}
            self.occurrences.append(row)
            return [row]
        if method == "PATCH" and path == "agent_task_schedule_runs":
            row = next(row for row in self.occurrences
                       if row["id"] == params["id"].removeprefix("eq."))
            row.update(body)
            return [row]
        if method == "PATCH" and path == "agent_task_schedules":
            self.schedule.update(body)
            self.schedule_patches.append(dict(body))
            return [self.schedule]
        raise AssertionError(f"unexpected runtime store request: {method} {path}")


class FakeWorkflowStore:
    def __init__(self, definition):
        self.definition = definition
        self.created = []

    async def get_run(self, owner_id, run_id):
        return None

    async def request(self, method, path, *, params=None, body=None, prefer=None):
        assert (method, path) == ("GET", "workflow_runs")
        return []

    async def get_definition(self, owner_id, definition_id):
        assert owner_id == self.definition["owner_user_id"]
        assert definition_id == self.definition["id"]
        return self.definition

    async def create_run(self, owner_id, definition, input_payload, trace_id):
        row = {"id": str(uuid.uuid4()), "owner_user_id": owner_id,
               "definition_id": definition["id"], "input_payload": input_payload,
               "trace_id": trace_id, "status": "queued"}
        self.created.append(row)
        return row


@pytest.mark.asyncio
async def test_due_schedule_creates_canonical_workflow_run_and_never_executes_tool_directly():
    owner_id, schedule_id, definition_id = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
    definition = WorkflowDefinition(
        workflow_key="agent-task-test", version=1,
        nodes=[WorkflowNode(key="execute-agent-task", kind="agent_task", config={"schedule_id": schedule_id})],
        edges=[], max_runtime_seconds=60, max_retries=0,
    )
    workflow_definition = {
        "id": definition_id, "owner_user_id": owner_id, "definition": definition.model_dump(mode="json"),
        "digest": definition.digest(), "status": "active",
    }
    due = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    schedule = {
        "id": schedule_id, "owner_user_id": owner_id, "workflow_definition_id": definition_id,
        "next_run_at": due, "schedule_kind": "once", "timezone_name": "Asia/Jakarta",
        "local_time": "18:00", "weekdays": [], "require_approval": False, "run_count": 0,
    }
    runtime = FakeRuntimeStore(schedule)
    workflows = FakeWorkflowStore(workflow_definition)

    result = await process_due_schedules(runtime, workflows, limit=5, lease_seconds=30)

    assert result["claimed"] == 1 and result["dispatched"] == 1
    assert len(workflows.created) == 1
    run = workflows.created[0]
    assert run["input_payload"]["schedule_id"] == schedule_id
    assert run["input_payload"]["schedule_run_id"] == runtime.occurrences[0]["id"]
    assert run["trace_id"] == f"agent-task-schedule:{runtime.occurrences[0]['id']}"
    assert runtime.occurrences[0]["workflow_run_id"] == run["id"]
    assert runtime.occurrences[0]["status"] == "running"
    assert runtime.schedule["status"] == "completed"
    assert runtime.schedule["last_workflow_run_id"] == run["id"]
    assert runtime.schedule["lease_token"] is None


@pytest.mark.asyncio
async def test_due_schedule_waits_for_owner_approval_without_workflow_dispatch():
    owner_id, schedule_id, definition_id = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
    schedule = {
        "id": schedule_id, "owner_user_id": owner_id, "workflow_definition_id": definition_id,
        "next_run_at": (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat(),
        "schedule_kind": "once", "timezone_name": "Asia/Jakarta", "local_time": "18:00",
        "weekdays": [], "require_approval": True, "run_count": 0,
    }
    runtime = FakeRuntimeStore(schedule)
    workflows = FakeWorkflowStore({})
    result = await process_due_schedules(runtime, workflows, limit=5, lease_seconds=30)
    assert result["waiting_for_approval"] == 1
    assert not workflows.created
    assert runtime.occurrences[0]["status"] == "waiting_for_approval"
    assert runtime.schedule["status"] == "needs_approval"
    assert runtime.schedule["lease_token"] is None

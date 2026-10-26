import asyncio
import uuid

import pytest
from fastapi import HTTPException

from allpha_api.agent_task_schedule_api import TaskScheduleCreate, _verify_runtime_binding


OWNER = str(uuid.uuid4())
AGENT = str(uuid.uuid4())
SESSION = str(uuid.uuid4())
SKILL = str(uuid.uuid4())


class FakeScheduleBindingStore:
    def __init__(self):
        self.capability_lookup_count = 0

    async def get_session(self, owner_id, session_id):
        return {"id": session_id, "owner_id": owner_id, "agent_id": AGENT, "status": "active"}

    async def get_agent(self, owner_id, agent_id):
        return {"id": agent_id, "owner_id": owner_id, "version": 1, "status": "active"}

    async def get_skill(self, owner_id, agent_id, skill_id):
        return {
            "id": skill_id, "agent_id": agent_id, "version": 1, "status": "published",
            "tool_dependencies": ["text.normalize"], "required_permission_scopes": [],
            "budget_limits": {"max_runtime_seconds": 30, "max_tool_calls": 1},
        }

    async def get_approved_capability(self, agent_id, tool_key):
        self.capability_lookup_count += 1
        return None


def make_payload(input_payload):
    return TaskScheduleCreate(
        agent_id=AGENT,
        session_id=SESSION,
        skill_id=SKILL,
        tool_key="text.normalize",
        title="Normalize text",
        instructions="Normalize the provided text.",
        task_type="SKILL_EXECUTION",
        schedule_kind="daily",
        timezone_name="UTC",
        local_time="09:00",
        input_payload=input_payload,
    )


def test_schedule_rejects_invalid_tool_input_before_policy_or_persistence():
    store = FakeScheduleBindingStore()
    with pytest.raises(HTTPException) as exc:
        asyncio.run(_verify_runtime_binding(store, OWNER, make_payload({"text": 42})))
    assert exc.value.status_code == 422
    assert exc.value.detail["code"] == "INVALID_TASK_TOOL_INPUT"
    assert store.capability_lookup_count == 0


def test_schedule_validates_tool_input_before_policy_gate():
    store = FakeScheduleBindingStore()
    with pytest.raises(HTTPException) as exc:
        asyncio.run(_verify_runtime_binding(store, OWNER, make_payload({"text": "hello"})))
    # Valid Tool input proceeds to the next required gate (approved runtime policy).
    assert exc.value.status_code == 409
    assert exc.value.detail["code"] == "APPROVED_RUNTIME_POLICY_REQUIRED"
    assert store.capability_lookup_count == 1

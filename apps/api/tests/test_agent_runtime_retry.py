import asyncio
import time

import pytest

from allpha_api import agent_runtime as runtime


def test_deterministic_tool_timeout_is_classified_as_retryable(monkeypatch):
    async def timeout(*args, **kwargs):
        raise asyncio.TimeoutError

    monkeypatch.setattr(runtime.asyncio, "to_thread", timeout)
    envelope = runtime.AgentTaskEnvelope(
        task_id="task-1",
        task_version=2,
        requester_id="owner-1",
        agent_id="agent-1",
        agent_version=1,
        owner_id="owner-1",
        skill_id="skill-1",
        skill_version=1,
        input_classification="user_input",
        allowed_memory_scope=(),
        allowed_tool_keys=("text.normalize",),
        capability_scopes=(),
        idempotency_key="runtime-test-001",
        trace_id="trace-test-001",
        deadline_monotonic=time.monotonic() + 30,
        max_tool_calls=1,
        max_runtime_seconds=30,
    )
    authorization = runtime.RuntimeAuthorization(
        authenticated_owner_id="owner-1",
        owned_agent_id="agent-1",
        agent_version=1,
        skill_id="skill-1",
        skill_version=1,
        skill_published=True,
        policy_approved=True,
        policy_version="policy-v1",
        approved_tool_keys=("text.normalize",),
        granted_scopes=(),
    )

    with pytest.raises(runtime.AgentRuntimeRetryable, match="TOOL_TIMEOUT"):
        asyncio.run(runtime.AgentRuntime().execute_tool(
            runtime.AgentTask(envelope), authorization,
            tool_key="text.normalize", inputs={"text": "hello"},
        ))

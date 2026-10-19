import asyncio
import time

import pytest

from allpha_api.agent_runtime import (
    AgentRuntime, AgentRuntimeBlocked, AgentTask, AgentTaskEnvelope, AgentTaskState,
    RuntimeAuthorization, AgentConsumerAuthorization,
)


def envelope(**changes):
    values = dict(
        task_id="task-1", task_version=1, requester_id="user-1", agent_id="agent-1",
        agent_version=3, owner_id="user-1", skill_id="skill-1", skill_version=2,
        input_classification="public", allowed_memory_scope=(), allowed_tool_keys=("text.normalize",),
        capability_scopes=(), idempotency_key="idem-1", trace_id="trace-1",
        deadline_monotonic=time.monotonic() + 5, max_tool_calls=1,
        max_runtime_seconds=3, max_output_bytes=1024,
    )
    values.update(changes)
    return AgentTaskEnvelope(**values)


def authorization(**changes):
    values = dict(
        authenticated_owner_id="user-1", owned_agent_id="agent-1", agent_version=3,
        skill_id="skill-1", skill_version=2, skill_published=True, policy_approved=True,
        policy_version="runtime-policy-v1", approved_tool_keys=("text.normalize",), granted_scopes=(),
    )
    values.update(changes)
    return RuntimeAuthorization(**values)


def test_runtime_executes_only_pinned_authorized_registered_tool():
    task = AgentTask(envelope())
    result = asyncio.run(AgentRuntime().execute_tool(
        task, authorization(), tool_key="text.normalize", inputs={"text": "  hello   world "},
    ))
    assert result["result"] == {"text": "hello world"}
    assert result["state"] == "succeeded"
    assert result["provider_execution"] is False
    assert result["persistence"] == "not_configured"
    assert [e["state"] for e in result["events"]] == [
        "policy_check", "budget_reserved", "context_building", "planning",
        "executing", "validating", "succeeded",
    ]


@pytest.mark.parametrize("auth,match", [
    (authorization(authenticated_owner_id="user-2"), "owner context mismatch"),
    (authorization(owned_agent_id="agent-2"), "Agent ownership mismatch"),
    (authorization(agent_version=4), "Agent version changed"),
    (authorization(skill_published=False), "Skill is not published"),
    (authorization(policy_approved=False), "approved runtime policy"),
    (authorization(approved_tool_keys=()), "tool is not approved"),
])
def test_runtime_fails_closed_before_tool_execution(auth, match):
    task = AgentTask(envelope())
    with pytest.raises(AgentRuntimeBlocked, match=match):
        asyncio.run(AgentRuntime().execute_tool(task, auth, tool_key="text.normalize", inputs={"text": "x"}))
    assert task.result is None


def test_runtime_rejects_tool_not_in_pinned_envelope():
    task = AgentTask(envelope(allowed_tool_keys=()))
    with pytest.raises(AgentRuntimeBlocked, match="no tools are authorized"):
        asyncio.run(AgentRuntime().execute_tool(task, authorization(), tool_key="text.normalize", inputs={"text": "x"}))


def test_runtime_rejects_excessive_tool_call_budget():
    task = AgentTask(envelope(max_tool_calls=100))
    with pytest.raises(AgentRuntimeBlocked, match="outside runtime limits"):
        asyncio.run(AgentRuntime().execute_tool(task, authorization(), tool_key="text.normalize", inputs={"text": "x"}))


def test_runtime_rejects_expired_deadline():
    task = AgentTask(envelope(deadline_monotonic=time.monotonic() - 1))
    with pytest.raises(AgentRuntimeBlocked, match="deadline has expired"):
        asyncio.run(AgentRuntime().execute_tool(task, authorization(), tool_key="text.normalize", inputs={"text": "x"}))


def test_runtime_enforces_output_size():
    task = AgentTask(envelope(max_output_bytes=128))
    with pytest.raises(AgentRuntimeBlocked, match="output exceeded"):
        asyncio.run(AgentRuntime().execute_tool(
            task, authorization(), tool_key="text.normalize", inputs={"text": "x" * 4000},
        ))
    assert task.state == AgentTaskState.FAILED
    assert task.error_code == "TOOL_OUTPUT_TOO_LARGE"


def test_task_state_machine_rejects_invalid_transition():
    task = AgentTask(envelope())
    with pytest.raises(AgentRuntimeBlocked, match="invalid task transition"):
        task.transition(AgentTaskState.SUCCEEDED)


@pytest.mark.parametrize("terminal_state", [
    AgentTaskState.SUCCEEDED,
    AgentTaskState.PARTIALLY_SUCCEEDED,
    AgentTaskState.FAILED,
    AgentTaskState.CANCELLED,
    AgentTaskState.TIMED_OUT,
    AgentTaskState.BUDGET_EXHAUSTED,
])
def test_terminal_task_states_are_immutable(terminal_state):
    task = AgentTask(envelope(), state=terminal_state)
    with pytest.raises(AgentRuntimeBlocked, match="invalid task transition"):
        task.transition(AgentTaskState.POLICY_CHECK)
    assert task.state == terminal_state


def test_consumer_generation_requires_explicit_owner_approved_grant():
    runtime = AgentRuntime()
    with pytest.raises(AgentRuntimeBlocked, match="consumer authorization is required"):
        asyncio.run(runtime.execute_skill_generation(
            requester_id="consumer-1", owner_id="owner-1", agent_id="agent-1",
            agent_version=3, skill_id="skill-1", skill_version=2, skill_published=True,
            policy_version="public-v1", router=None, request=None,
        ))


@pytest.mark.parametrize("changes,match", [
    ({"grant_active": False}, "owner-approved consumer grant"),
    ({"policy_approved": False}, "owner-approved consumer grant"),
    ({"allowed_memory_scope": ("owner_private",)}, "owner-private memory"),
    ({"budget_reserved": False}, "budget reservation and metering"),
    ({"metering_ready": False}, "budget reservation and metering"),
    ({"agent_public": False}, "active public Agents"),
    ({"skill_published": False}, "active public Agents"),
])
def test_consumer_generation_fails_closed_before_provider_call(changes, match):
    auth_values = dict(
        requester_id="consumer-1", owner_id="owner-1", agent_id="agent-1",
        agent_version=3, skill_id="skill-1", skill_version=2,
        agent_public=True, agent_active=True, skill_published=True,
        grant_active=True, policy_approved=True, policy_version="public-v1",
        granted_scopes=(), allowed_memory_scope=(), budget_reserved=True, metering_ready=True,
    )
    auth_values.update(changes)
    auth = AgentConsumerAuthorization(**auth_values)
    with pytest.raises(AgentRuntimeBlocked, match=match):
        asyncio.run(AgentRuntime().execute_skill_generation(
            requester_id="consumer-1", owner_id="owner-1", agent_id="agent-1",
            agent_version=3, skill_id="skill-1", skill_version=2, skill_published=True,
            policy_version="public-v1", router=None, request=None,
            consumer_authorization=auth,
        ))

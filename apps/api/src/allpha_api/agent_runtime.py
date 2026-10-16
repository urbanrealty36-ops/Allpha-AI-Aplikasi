"""Policy-bound, bounded Agent Runtime primitives for ENG-P10.

This module intentionally does not invoke an LLM or provide autonomous authority.
The trusted API supplies a verified owner, pinned Agent/Skill versions, and an
approved runtime policy. Model output is never treated as authorization.
"""
from __future__ import annotations

import asyncio
import json
import time
import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Awaitable, Callable

from allpha_api.tool_registry import ToolInputError, UnknownToolError, execute_tool, get_tool
from allpha_api.model_router import CanonicalTextGenerationRouter, TextGenerationEvidence, TextGenerationRequest, TextGenerationResponse, TextGenerationRouterUnavailable


class AgentTaskState(StrEnum):
    CREATED = "created"
    POLICY_CHECK = "policy_check"
    BUDGET_RESERVED = "budget_reserved"
    CONTEXT_BUILDING = "context_building"
    PLANNING = "planning"
    EXECUTING = "executing"
    VALIDATING = "validating"
    SUCCEEDED = "succeeded"
    WAITING_FOR_APPROVAL = "waiting_for_approval"
    WAITING_FOR_INPUT = "waiting_for_input"
    RETRYING = "retrying"
    PARTIALLY_SUCCEEDED = "partially_succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"
    BUDGET_EXHAUSTED = "budget_exhausted"


TERMINAL_STATES = {
    AgentTaskState.SUCCEEDED, AgentTaskState.PARTIALLY_SUCCEEDED,
    AgentTaskState.FAILED, AgentTaskState.CANCELLED,
    AgentTaskState.TIMED_OUT, AgentTaskState.BUDGET_EXHAUSTED,
}
_ALLOWED_TRANSITIONS: dict[AgentTaskState, set[AgentTaskState]] = {
    AgentTaskState.CREATED: {AgentTaskState.POLICY_CHECK, AgentTaskState.CANCELLED},
    AgentTaskState.POLICY_CHECK: {AgentTaskState.BUDGET_RESERVED, AgentTaskState.WAITING_FOR_APPROVAL,
                                  AgentTaskState.WAITING_FOR_INPUT, AgentTaskState.BUDGET_EXHAUSTED,
                                  AgentTaskState.FAILED, AgentTaskState.CANCELLED},
    AgentTaskState.BUDGET_RESERVED: {AgentTaskState.CONTEXT_BUILDING, AgentTaskState.FAILED,
                                     AgentTaskState.CANCELLED, AgentTaskState.TIMED_OUT},
    AgentTaskState.CONTEXT_BUILDING: {AgentTaskState.PLANNING, AgentTaskState.FAILED,
                                      AgentTaskState.CANCELLED, AgentTaskState.TIMED_OUT},
    AgentTaskState.PLANNING: {AgentTaskState.EXECUTING, AgentTaskState.WAITING_FOR_APPROVAL,
                              AgentTaskState.WAITING_FOR_INPUT, AgentTaskState.FAILED,
                              AgentTaskState.CANCELLED, AgentTaskState.TIMED_OUT},
    AgentTaskState.EXECUTING: {AgentTaskState.VALIDATING, AgentTaskState.RETRYING,
                               AgentTaskState.PARTIALLY_SUCCEEDED, AgentTaskState.FAILED,
                               AgentTaskState.CANCELLED, AgentTaskState.TIMED_OUT},
    AgentTaskState.RETRYING: {AgentTaskState.EXECUTING, AgentTaskState.FAILED,
                              AgentTaskState.CANCELLED, AgentTaskState.TIMED_OUT},
    AgentTaskState.VALIDATING: {AgentTaskState.SUCCEEDED, AgentTaskState.PARTIALLY_SUCCEEDED,
                                AgentTaskState.FAILED},
    AgentTaskState.WAITING_FOR_APPROVAL: {AgentTaskState.POLICY_CHECK, AgentTaskState.CANCELLED,
                                          AgentTaskState.FAILED},
    AgentTaskState.WAITING_FOR_INPUT: {AgentTaskState.POLICY_CHECK, AgentTaskState.CANCELLED,
                                       AgentTaskState.FAILED},
    AgentTaskState.PARTIALLY_SUCCEEDED: set(), AgentTaskState.SUCCEEDED: set(),
    AgentTaskState.FAILED: set(), AgentTaskState.CANCELLED: set(),
    AgentTaskState.TIMED_OUT: set(), AgentTaskState.BUDGET_EXHAUSTED: set(),
}


class AgentRuntimeBlocked(ValueError):
    """Runtime must not execute when an authorization/policy invariant is absent."""


@dataclass(frozen=True)
class AgentTaskEnvelope:
    task_id: str
    task_version: int
    requester_id: str
    agent_id: str
    agent_version: int
    owner_id: str
    skill_id: str
    skill_version: int
    input_classification: str
    allowed_memory_scope: tuple[str, ...]
    allowed_tool_keys: tuple[str, ...]
    capability_scopes: tuple[str, ...]
    idempotency_key: str
    trace_id: str
    deadline_monotonic: float
    max_tool_calls: int
    max_runtime_seconds: int
    max_output_bytes: int = 16_384


@dataclass(frozen=True)
class RuntimeAuthorization:
    authenticated_owner_id: str
    owned_agent_id: str
    agent_version: int
    skill_id: str
    skill_version: int
    skill_published: bool
    policy_approved: bool
    policy_version: str | None
    approved_tool_keys: tuple[str, ...]
    granted_scopes: tuple[str, ...]


@dataclass
class AgentTask:
    envelope: AgentTaskEnvelope
    state: AgentTaskState = AgentTaskState.CREATED
    events: list[dict[str, Any]] = field(default_factory=list)
    result: dict[str, Any] | None = None
    error_code: str | None = None

    def transition(self, next_state: AgentTaskState, *, reason: str | None = None) -> None:
        if next_state not in _ALLOWED_TRANSITIONS[self.state]:
            raise AgentRuntimeBlocked(f"invalid task transition: {self.state} -> {next_state}")
        self.state = next_state
        self.events.append({
            "state": next_state.value,
            "at_monotonic": time.monotonic(),
            "reason_code": reason,
            "trace_id": self.envelope.trace_id,
        })


@dataclass(frozen=True)
class RuntimeLimits:
    max_tool_calls: int = 5
    max_runtime_seconds: int = 30
    max_output_bytes: int = 16_384


class AgentRuntime:
    """Runs only explicitly registered, policy-authorized deterministic tools."""

    def __init__(self, limits: RuntimeLimits = RuntimeLimits()):
        self._limits = limits

    def authorize(self, envelope: AgentTaskEnvelope, auth: RuntimeAuthorization) -> None:
        if not auth.authenticated_owner_id or auth.authenticated_owner_id != envelope.owner_id:
            raise AgentRuntimeBlocked("owner context mismatch")
        if auth.owned_agent_id != envelope.agent_id:
            raise AgentRuntimeBlocked("Agent ownership mismatch")
        if auth.agent_version != envelope.agent_version:
            raise AgentRuntimeBlocked("Agent version changed; task must be re-planned")
        if auth.skill_id != envelope.skill_id or auth.skill_version != envelope.skill_version:
            raise AgentRuntimeBlocked("Skill version mismatch")
        if not auth.skill_published:
            raise AgentRuntimeBlocked("Skill is not published")
        if not auth.policy_approved or not auth.policy_version:
            raise AgentRuntimeBlocked("approved runtime policy is required")
        if not envelope.idempotency_key or not envelope.trace_id:
            raise AgentRuntimeBlocked("idempotency and trace identifiers are required")
        if not envelope.allowed_tool_keys:
            raise AgentRuntimeBlocked("no tools are authorized for this task")
        if envelope.max_tool_calls < 1 or envelope.max_tool_calls > self._limits.max_tool_calls:
            raise AgentRuntimeBlocked("tool-call budget is outside runtime limits")
        if envelope.max_runtime_seconds < 1 or envelope.max_runtime_seconds > self._limits.max_runtime_seconds:
            raise AgentRuntimeBlocked("runtime budget is outside runtime limits")
        if envelope.max_output_bytes < 128 or envelope.max_output_bytes > self._limits.max_output_bytes:
            raise AgentRuntimeBlocked("output budget is outside runtime limits")
        for key in envelope.allowed_tool_keys:
            tool = get_tool(key)
            if key not in auth.approved_tool_keys:
                raise AgentRuntimeBlocked(f"tool is not approved by runtime policy: {key}")
            if not set(tool.required_permission_scopes).issubset(auth.granted_scopes):
                raise AgentRuntimeBlocked(f"required permission scope is missing: {key}")
        if time.monotonic() >= envelope.deadline_monotonic:
            raise AgentRuntimeBlocked("task deadline has expired")

    async def execute_tool(
        self,
        task: AgentTask,
        auth: RuntimeAuthorization,
        *,
        tool_key: str,
        inputs: dict[str, Any],
    ) -> dict[str, Any]:
        self.authorize(task.envelope, auth)
        if task.state == AgentTaskState.CREATED:
            task.transition(AgentTaskState.POLICY_CHECK)
        if task.state == AgentTaskState.POLICY_CHECK:
            task.transition(AgentTaskState.BUDGET_RESERVED)
            task.transition(AgentTaskState.CONTEXT_BUILDING)
            task.transition(AgentTaskState.PLANNING)
        if task.state != AgentTaskState.PLANNING:
            raise AgentRuntimeBlocked("task is not ready for execution")
        if tool_key not in task.envelope.allowed_tool_keys:
            raise AgentRuntimeBlocked("tool is not in the pinned task envelope")
        task.transition(AgentTaskState.EXECUTING)
        remaining = min(
            task.envelope.deadline_monotonic - time.monotonic(),
            float(task.envelope.max_runtime_seconds),
        )
        if remaining <= 0:
            task.transition(AgentTaskState.TIMED_OUT, reason="deadline_expired")
            raise AgentRuntimeBlocked("task deadline has expired")
        try:
            result = await asyncio.wait_for(asyncio.to_thread(execute_tool, tool_key, inputs), timeout=remaining)
        except asyncio.TimeoutError as exc:
            task.transition(AgentTaskState.TIMED_OUT, reason="tool_timeout")
            task.error_code = "TOOL_TIMEOUT"
            raise AgentRuntimeBlocked("tool execution timed out") from exc
        except (ToolInputError, UnknownToolError) as exc:
            task.transition(AgentTaskState.FAILED, reason="tool_contract_error")
            task.error_code = "TOOL_CONTRACT_ERROR"
            raise AgentRuntimeBlocked("tool input or registry contract rejected the call") from exc
        encoded = json.dumps(result, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        if len(encoded) > task.envelope.max_output_bytes:
            task.transition(AgentTaskState.FAILED, reason="output_limit_exceeded")
            task.error_code = "TOOL_OUTPUT_TOO_LARGE"
            raise AgentRuntimeBlocked("tool output exceeded the task output limit")
        task.transition(AgentTaskState.VALIDATING)
        task.result = result
        task.transition(AgentTaskState.SUCCEEDED)
        return {
            "task_id": task.envelope.task_id,
            "task_version": task.envelope.task_version,
            "agent_id": task.envelope.agent_id,
            "agent_version": task.envelope.agent_version,
            "skill_id": task.envelope.skill_id,
            "skill_version": task.envelope.skill_version,
            "tool_key": tool_key,
            "result": result,
            "state": task.state.value,
            "policy_version": auth.policy_version,
            "trace_id": task.envelope.trace_id,
            "idempotency_key": task.envelope.idempotency_key,
            "events": list(task.events),
            "persistence": "not_configured",
            "provider_execution": False,
        }


    async def execute_skill_generation(
        self,
        *,
        requester_id: str,
        owner_id: str,
        agent_id: str,
        agent_version: int,
        skill_id: str,
        skill_version: int,
        skill_published: bool,
        policy_version: str,
        router: CanonicalTextGenerationRouter,
        request: TextGenerationRequest,
    ) -> tuple[TextGenerationResponse, TextGenerationEvidence]:
        """Execute one pinned Skill generation through the canonical Model Router."""
        if not requester_id or requester_id != owner_id:
            raise AgentRuntimeBlocked("requester is not the authenticated Agent owner")
        if not agent_id or agent_version < 1 or not skill_id or skill_version < 1:
            raise AgentRuntimeBlocked("canonical Agent and Skill identity/version are required")
        if not skill_published:
            raise AgentRuntimeBlocked("only a published Skill version can execute")
        if request.task_id == "" or not request.idempotency_key or not request.trace_id:
            raise AgentRuntimeBlocked("generation task, trace and idempotency identities are required")
        try:
            active_policy_version = router.policy_version_for(request.sensitivity)
            router.require_runtime_ready(request.sensitivity)
        except TextGenerationRouterUnavailable as exc:
            raise AgentRuntimeBlocked("approved Model Router route, policy and metering are required") from exc
        if not policy_version or policy_version != active_policy_version:
            raise AgentRuntimeBlocked("pinned Model Router policy version changed")
        remaining = min(float(request.timeout_ms) / 1000, 30.0)
        if remaining <= 0:
            raise AgentRuntimeBlocked("generation deadline has expired")
        try:
            return await asyncio.wait_for(router.generate(request), timeout=remaining)
        except asyncio.TimeoutError as exc:
            raise AgentRuntimeBlocked("Skill generation exceeded the runtime deadline") from exc

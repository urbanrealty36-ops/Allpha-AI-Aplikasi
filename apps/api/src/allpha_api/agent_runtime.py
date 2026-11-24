"""Policy-bound, bounded Agent Runtime primitives for ENG-P10.

This module intentionally does not invoke an LLM or provide autonomous authority.
The trusted API supplies a verified owner, pinned Agent/Skill versions, and an
approved runtime policy. Model output is never treated as authorization.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import time
import uuid
from dataclasses import dataclass, field, replace
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


class AgentRuntimeOutcomeUnknown(RuntimeError):
    """Provider invocation may have started; the caller must reconcile, never replay."""


class AgentRuntimeRetryable(RuntimeError):
    """A bounded retryable failure for a deterministic, side-effect-free tool."""


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
    knowledge_context_refs: tuple[dict[str, Any], ...] = ()
    knowledge_context_sha256: str | None = None
    knowledge_context_state: str = "not_configured"


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


@dataclass(frozen=True)
class AgentConsumerAuthorization:
    """Trusted, server-resolved grant for a consumer to invoke a public Agent.

    This object must only be constructed after the API verifies a durable,
    owner-approved grant and current published Agent/Skill/runtime policy.
    """
    requester_id: str
    owner_id: str
    agent_id: str
    agent_version: int
    skill_id: str
    skill_version: int
    agent_public: bool
    agent_active: bool
    skill_published: bool
    grant_active: bool
    policy_approved: bool
    policy_version: str
    granted_scopes: tuple[str, ...] = ()
    allowed_tool_keys: tuple[str, ...] = ()
    max_tool_calls: int = 0
    max_tool_runtime_seconds: int = 0
    allowed_memory_scope: tuple[str, ...] = ()
    budget_reserved: bool = False
    metering_ready: bool = False


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
        if not isinstance(envelope.knowledge_context_state, str) or envelope.knowledge_context_state not in {"not_configured", "empty", "available"}:
            raise AgentRuntimeBlocked("Knowledge context state is invalid")
        if not isinstance(envelope.knowledge_context_refs, tuple) or len(envelope.knowledge_context_refs) > 8:
            raise AgentRuntimeBlocked("Knowledge context reference count exceeds runtime limits")
        if (envelope.knowledge_context_state == "available") != bool(envelope.knowledge_context_refs):
            raise AgentRuntimeBlocked("Knowledge context state and references are inconsistent")
        if envelope.knowledge_context_state == "available":
            digest = envelope.knowledge_context_sha256
            if not isinstance(digest, str) or len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
                raise AgentRuntimeBlocked("Knowledge context digest is invalid")
            for ref in envelope.knowledge_context_refs:
                if not isinstance(ref, dict) or "content" in ref:
                    raise AgentRuntimeBlocked("Knowledge context references must be content-free")
                try:
                    uuid.UUID(ref.get("source_id", ""))
                    uuid.UUID(ref.get("chunk_id", ""))
                except (ValueError, TypeError, AttributeError):
                    raise AgentRuntimeBlocked("Knowledge context source/chunk identifiers are invalid")
                location = ref.get("source_location")
                if (
                    not isinstance(ref.get("source_version"), int)
                    or isinstance(ref.get("source_version"), bool) or ref["source_version"] < 1
                    or not isinstance(ref.get("content_sha256"), str) or len(ref["content_sha256"]) != 64
                    or any(char not in "0123456789abcdef" for char in ref["content_sha256"])
                    or not isinstance(ref.get("retrieved_content_sha256"), str) or len(ref["retrieved_content_sha256"]) != 64
                    or any(char not in "0123456789abcdef" for char in ref["retrieved_content_sha256"])
                    or not isinstance(ref.get("sensitivity"), str)
                    or ref["sensitivity"] not in {"public", "internal", "confidential", "restricted"}
                    or not isinstance(ref.get("retrieval_method"), str)
                    or ref["retrieval_method"] not in {"vector", "keyword", "hybrid"}
                    or not isinstance(location, dict) or set(location) != {"kind", "index"}
                    or not isinstance(location.get("kind"), str)
                    or location["kind"] not in {"document", "page", "paragraph"}
                    or not isinstance(location.get("index"), int)
                    or isinstance(location.get("index"), bool) or location["index"] < 1
                ):
                    raise AgentRuntimeBlocked("Knowledge context citation metadata is invalid")
        else:
            empty_digest = hashlib.sha256(b"[]").hexdigest()
            if envelope.knowledge_context_refs or (
                envelope.knowledge_context_sha256 is not None
                and envelope.knowledge_context_sha256 != empty_digest
            ):
                raise AgentRuntimeBlocked("Empty Knowledge context cannot carry references or a non-empty digest")
        if time.monotonic() >= envelope.deadline_monotonic:
            raise AgentRuntimeBlocked("task deadline has expired")

    async def execute_tool(
        self,
        task: AgentTask,
        auth: RuntimeAuthorization,
        *,
        tool_key: str,
        inputs: dict[str, Any],
        event_sink: Callable[[dict[str, Any]], Awaitable[None]] | None = None,
        step_key: str = "tool",
    ) -> dict[str, Any]:
        """Execute one registered tool and durably emit each state transition when a sink is supplied."""
        self.authorize(task.envelope, auth)

        async def transition(next_state: AgentTaskState, *, reason: str | None = None) -> None:
            task.transition(next_state, reason=reason)
            event = dict(task.events[-1])
            event["tool_key"] = tool_key
            event["step_key"] = step_key if step_key != "tool" else "tool:" + tool_key
            if event_sink is not None:
                await event_sink(event)

        if task.state == AgentTaskState.CREATED:
            await transition(AgentTaskState.POLICY_CHECK)
        if task.state == AgentTaskState.POLICY_CHECK:
            await transition(AgentTaskState.BUDGET_RESERVED)
            await transition(AgentTaskState.CONTEXT_BUILDING)
            await transition(AgentTaskState.PLANNING)
        if task.state != AgentTaskState.PLANNING:
            raise AgentRuntimeBlocked("task is not ready for execution")
        if tool_key not in task.envelope.allowed_tool_keys:
            raise AgentRuntimeBlocked("tool is not in the pinned task envelope")
        await transition(AgentTaskState.EXECUTING)
        remaining = min(
            task.envelope.deadline_monotonic - time.monotonic(),
            float(task.envelope.max_runtime_seconds),
        )
        if remaining <= 0:
            await transition(AgentTaskState.TIMED_OUT, reason="deadline_expired")
            raise AgentRuntimeBlocked("task deadline has expired")
        try:
            result = await asyncio.wait_for(asyncio.to_thread(execute_tool, tool_key, inputs), timeout=remaining)
        except asyncio.TimeoutError as exc:
            await transition(AgentTaskState.TIMED_OUT, reason="tool_timeout")
            task.error_code = "TOOL_TIMEOUT"
            raise AgentRuntimeRetryable("TOOL_TIMEOUT") from exc
        except (ToolInputError, UnknownToolError) as exc:
            await transition(AgentTaskState.FAILED, reason="tool_contract_error")
            task.error_code = "TOOL_CONTRACT_ERROR"
            raise AgentRuntimeBlocked("tool input or registry contract rejected the call") from exc
        encoded = json.dumps(result, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")
        if len(encoded) > task.envelope.max_output_bytes:
            await transition(AgentTaskState.FAILED, reason="output_limit_exceeded")
            task.error_code = "TOOL_OUTPUT_TOO_LARGE"
            raise AgentRuntimeBlocked("tool output exceeded the task output limit")
        await transition(AgentTaskState.VALIDATING)
        task.result = result
        await transition(AgentTaskState.SUCCEEDED)
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
            "persistence": "durable_event_sink" if event_sink is not None else "not_configured",
            "provider_execution": False,
            "knowledge_context_refs": list(task.envelope.knowledge_context_refs),
            "knowledge_context_sha256": task.envelope.knowledge_context_sha256,
            "knowledge_context_state": task.envelope.knowledge_context_state,
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
        consumer_authorization: AgentConsumerAuthorization | None = None,
        skill_tool_dependencies: tuple[str, ...] = (),
        runtime_authorization: RuntimeAuthorization | None = None,
        skill_budget_limits: dict[str, Any] | None = None,
        skill_tool_inputs: dict[str, dict[str, Any]] | None = None,
    ) -> tuple[TextGenerationResponse, TextGenerationEvidence]:
        """Execute a pinned Skill through Model Router under owner or explicit consumer authorization."""
        if not requester_id or not owner_id:
            raise AgentRuntimeBlocked("verified requester and owner identities are required")
        if requester_id != owner_id:
            auth = consumer_authorization
            if auth is None:
                raise AgentRuntimeBlocked("public Agent consumer authorization is required")
            if (auth.requester_id != requester_id or auth.owner_id != owner_id
                    or auth.agent_id != agent_id or auth.agent_version != agent_version
                    or auth.skill_id != skill_id or auth.skill_version != skill_version):
                raise AgentRuntimeBlocked("consumer authorization identity or pinned version mismatch")
            if not auth.agent_public or not auth.agent_active or not auth.skill_published:
                raise AgentRuntimeBlocked("only active public Agents and published Skills can serve consumers")
            if not auth.grant_active or not auth.policy_approved or not auth.policy_version:
                raise AgentRuntimeBlocked("owner-approved consumer grant and runtime policy are required")
            if auth.policy_version != policy_version:
                raise AgentRuntimeBlocked("consumer authorization policy version mismatch")
            if not auth.budget_reserved or not auth.metering_ready:
                raise AgentRuntimeBlocked("consumer budget reservation and metering must be ready")
            if (auth.allowed_memory_scope
                    or any(scope in {"private_memory_read", "owner_private_memory", "memory.private.read"}
                           or scope.startswith("memory.") for scope in auth.granted_scopes)):
                raise AgentRuntimeBlocked("consumer generation cannot access owner-private memory by default")
            if request.sensitivity != "public" or request.owner_id != owner_id:
                raise AgentRuntimeBlocked("consumer generation must use the public route with the canonical owner context")
            if request.agent_id != agent_id or request.source_id != skill_id or request.source_version != skill_version:
                raise AgentRuntimeBlocked("generation request does not match the authorized Agent/Skill version")
        if not agent_id or agent_version < 1 or not skill_id or skill_version < 1:
            raise AgentRuntimeBlocked("canonical Agent and Skill identity/version are required")
        if not skill_published:
            raise AgentRuntimeBlocked("only a published Skill version can execute")
        preflight_dependencies = tuple(skill_tool_dependencies)
        if requester_id != owner_id and preflight_dependencies:
            consumer = consumer_authorization
            if consumer is None or "tool_invoke" not in consumer.granted_scopes:
                raise AgentRuntimeBlocked("external Consumer tool execution requires an explicit tool-scoped grant")
            if set(preflight_dependencies) != set(consumer.allowed_tool_keys):
                raise AgentRuntimeBlocked("external Consumer grant must match the exact pinned Skill tool set")
            if set(skill_tool_inputs or {}) != set(preflight_dependencies):
                raise AgentRuntimeBlocked("external Consumer must provide typed inputs for every granted Skill tool")
        if request.task_id == "" or not request.idempotency_key or not request.trace_id:
            raise AgentRuntimeBlocked("generation task, trace and idempotency identities are required")
        try:
            active_policy_version = router.policy_version_for(request.sensitivity)
            router.require_runtime_ready(request.sensitivity)
        except TextGenerationRouterUnavailable as exc:
            raise AgentRuntimeBlocked("approved Model Router route, policy and metering are required") from exc
        if not policy_version or policy_version != active_policy_version:
            raise AgentRuntimeBlocked("pinned Model Router policy version changed")

        # Generation Skills may declare only registered deterministic tools.
        # Model-driven arbitrary function calls are not inferred from Skill text.
        dependencies = tuple(skill_tool_dependencies)
        if len(dependencies) > self._limits.max_tool_calls or len(set(dependencies)) != len(dependencies):
            raise AgentRuntimeBlocked("Skill tool dependency count or uniqueness is invalid")
        if dependencies:
            if requester_id != owner_id:
                consumer = consumer_authorization
                if consumer is None or "tool_invoke" not in consumer.granted_scopes:
                    raise AgentRuntimeBlocked("external Consumer tool execution requires an explicit tool-scoped grant")
                if set(dependencies) != set(consumer.allowed_tool_keys):
                    raise AgentRuntimeBlocked("external Consumer grant must match the exact pinned Skill tool set")
                if set(skill_tool_inputs or {}) != set(dependencies):
                    raise AgentRuntimeBlocked("external Consumer must provide typed inputs for every granted Skill tool")
                if (not isinstance(consumer.max_tool_calls, int) or isinstance(consumer.max_tool_calls, bool)
                        or not 1 <= consumer.max_tool_calls <= 5
                        or not isinstance(consumer.max_tool_runtime_seconds, int)
                        or isinstance(consumer.max_tool_runtime_seconds, bool)
                        or not 1 <= consumer.max_tool_runtime_seconds <= 30):
                    raise AgentRuntimeBlocked("external Consumer tool budget is invalid")
            auth = runtime_authorization
            if auth is None:
                raise AgentRuntimeBlocked("approved runtime tool policy is required")
            if (auth.authenticated_owner_id != owner_id or auth.owned_agent_id != agent_id
                    or auth.agent_version != agent_version or auth.skill_id != skill_id
                    or auth.skill_version != skill_version or not auth.skill_published
                    or not auth.policy_approved or auth.policy_version != policy_version):
                raise AgentRuntimeBlocked("runtime tool authorization does not match the pinned Agent/Skill")
            limits = skill_budget_limits if isinstance(skill_budget_limits, dict) else {}
            max_calls = limits.get("max_tool_calls", len(dependencies))
            max_runtime = limits.get("max_runtime_seconds", 30)
            if (not isinstance(max_calls, int) or isinstance(max_calls, bool)
                    or not isinstance(max_runtime, int) or isinstance(max_runtime, bool)):
                raise AgentRuntimeBlocked("Skill tool budget is invalid")
            if requester_id != owner_id:
                max_calls = min(max_calls, consumer_authorization.max_tool_calls)
                max_runtime = min(max_runtime, consumer_authorization.max_tool_runtime_seconds)
            if (max_calls < len(dependencies) or max_calls > self._limits.max_tool_calls
                    or max_runtime < 1 or max_runtime > self._limits.max_runtime_seconds):
                raise AgentRuntimeBlocked("Skill or Consumer tool budget is outside runtime limits")
            supplied_tool_inputs = skill_tool_inputs if isinstance(skill_tool_inputs, dict) else {}
            if set(supplied_tool_inputs) - set(dependencies):
                raise AgentRuntimeBlocked("tool input payload contains a tool outside the pinned Skill dependencies")
            transformed_prompt = request.prompt
            structured_tool_outputs: list[dict[str, Any]] = []
            tool_deadline = time.monotonic() + min(float(max_runtime), 30.0)
            for index, key in enumerate(dependencies):
                tool = get_tool(key)
                if getattr(tool, "execution_class", "side_effecting") != "pure":
                    raise AgentRuntimeBlocked(f"side-effecting Skill tool is not enabled: {key}")
                if requester_id != owner_id and (
                    consumer_authorization is None or key not in consumer_authorization.allowed_tool_keys
                ):
                    raise AgentRuntimeBlocked(f"tool is not present in the external Consumer grant: {key}")
                if key not in auth.approved_tool_keys:
                    raise AgentRuntimeBlocked(f"tool is not approved by runtime policy: {key}")
                if not set(tool.required_permission_scopes).issubset(auth.granted_scopes):
                    raise AgentRuntimeBlocked(f"required permission scope is missing: {key}")
                properties = tool.input_schema.get("properties") if isinstance(tool.input_schema, dict) else None
                required = tool.input_schema.get("required") if isinstance(tool.input_schema, dict) else None
                if not isinstance(properties, dict) or not isinstance(required, list):
                    raise AgentRuntimeBlocked(f"tool input schema is invalid: {key}")
                raw_inputs = supplied_tool_inputs.get(key)
                if raw_inputs is None:
                    if requester_id != owner_id:
                        raise AgentRuntimeBlocked(f"external Consumer tool inputs are required: {key}")
                    raw_inputs = {}
                if not isinstance(raw_inputs, dict):
                    raise AgentRuntimeBlocked(f"tool inputs must be an object: {key}")
                tool_inputs = dict(raw_inputs)
                if requester_id == owner_id and "text" in properties and "text" in required and "text" not in tool_inputs:
                    tool_inputs["text"] = transformed_prompt
                envelope = AgentTaskEnvelope(
                    task_id=f"{request.task_id}:skill-tool:{index}",
                    task_version=1,
                    requester_id=requester_id,
                    agent_id=agent_id,
                    agent_version=agent_version,
                    owner_id=owner_id,
                    skill_id=skill_id,
                    skill_version=skill_version,
                    input_classification=request.sensitivity,
                    allowed_memory_scope=(),
                    allowed_tool_keys=(key,),
                    capability_scopes=tuple(auth.granted_scopes),
                    idempotency_key=f"{request.idempotency_key}:skill-tool:{index}:{key}",
                    trace_id=request.trace_id,
                    deadline_monotonic=tool_deadline,
                    max_tool_calls=1,
                    max_runtime_seconds=min(max_runtime, 30),
                    max_output_bytes=max(1024, min(8192, 16_384 // max(1, len(dependencies)))),
                )
                task = AgentTask(envelope)
                tool_result = await self.execute_tool(task, auth, tool_key=key, inputs=tool_inputs)
                result_value = tool_result.get("result")
                if isinstance(result_value, dict) and isinstance(result_value.get("text"), str):
                    if not result_value["text"].strip():
                        raise AgentRuntimeBlocked(f"tool returned an empty text result: {key}")
                    transformed_prompt = result_value["text"]
                else:
                    structured_tool_outputs.append({"tool_key": key, "output": result_value})
            if structured_tool_outputs:
                tool_context = json.dumps(structured_tool_outputs, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                if len(tool_context.encode("utf-8")) > 16_384:
                    raise AgentRuntimeBlocked("combined deterministic tool output exceeds the generation context limit")
                transformed_prompt += "\n\nApproved deterministic Skill tool outputs (JSON data):\n" + tool_context
            request = replace(request, prompt=transformed_prompt)

        remaining = min(float(request.timeout_ms) / 1000, 30.0)
        if remaining <= 0:
            raise AgentRuntimeBlocked("generation deadline has expired")
        try:
            return await asyncio.wait_for(router.generate(request), timeout=remaining)
        except asyncio.TimeoutError as exc:
            # The provider may have accepted the request before the local deadline
            # elapsed. Callers must reconcile the outcome instead of releasing or replaying.
            raise AgentRuntimeOutcomeUnknown("Skill generation provider outcome is unknown after runtime deadline") from exc

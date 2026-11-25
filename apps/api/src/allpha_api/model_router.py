from __future__ import annotations

"""Canonical provider-neutral embedding router core.

Provider SDKs belong in registered adapters, never in domain feature modules.
No default provider/model is selected: deployment policy must configure both.
"""
import asyncio
from dataclasses import dataclass
from typing import Protocol
from allpha_api.cost_policy import CostBudget, CostEstimate, CostPolicyApproval, CostPolicyApprovalVerifier, authorize_cost, validate_actual_cost
from allpha_api.metering_contract import IdempotentMeteringSink, build_metering_record
from allpha_api.embedding_contract import EmbeddingFailure, EmbeddingRequest, EmbeddingResponse, validate_response_matches_request

class ModelRouterUnavailable(RuntimeError):
    """The canonical router or requested capability is not configured."""

class ModelRouterRejected(RuntimeError):
    """A terminal router or contract error."""
    def __init__(self, failure: EmbeddingFailure):
        self.failure = failure
        super().__init__(failure.code)

class ModelRouterTransient(RuntimeError):
    """Adapter failure with an explicit statement about whether execution is known not to have started."""

    def __init__(
        self, message: str, *, safe_to_retry: bool = False,
        retry_after_ms: int | None = None,
    ) -> None:
        self.safe_to_retry = safe_to_retry
        self.retry_after_ms = (
            max(0, min(int(retry_after_ms), 30_000))
            if retry_after_ms is not None else None
        )
        super().__init__(message)

class EmbeddingAdapter(Protocol):
    async def embed(self, request: EmbeddingRequest, *, model_id: str) -> EmbeddingResponse:
        """Call one provider/model using the adapter's server-side credentials."""

@dataclass(frozen=True)
class EmbeddingRoute:
    provider_id: str
    model_id: str
    model_version: str
    max_attempts: int = 3
    dimensions: int | None = None
    def __post_init__(self):
        if not self.provider_id.strip() or not self.model_id.strip() or not self.model_version.strip():
            raise ValueError("embedding route identity fields must be configured")
        if self.dimensions is not None and not 1 <= self.dimensions <= 8192:
            raise ValueError("embedding route dimensions must be between 1 and 8192")
        if not 1 <= self.max_attempts <= 8:
            raise ValueError("max_attempts must be between 1 and 8")

class CanonicalModelRouter:
    """Own policy route selection, bounded timeout/retry and usage/cost metering.

    routes is deployment-owned policy keyed by sensitivity. Missing entries fail
    closed. adapters are registered server-side provider integrations. No provider,
    model, dimension or fallback is guessed by this module.
    """
    def __init__(self, *, routes: dict[str, EmbeddingRoute], adapters: dict[str, EmbeddingAdapter], metering_sink: IdempotentMeteringSink | None = None, cost_budgets: dict[str, CostBudget] | None = None, cost_estimates: dict[str, CostEstimate] | None = None, cost_policy_approval: CostPolicyApproval | None = None, cost_policy_verifier: CostPolicyApprovalVerifier | None = None, retry_delay_seconds: float = 0.15):
        self._routes = dict(routes)
        self._adapters = dict(adapters)
        self._metering_sink = metering_sink
        self._cost_budgets = dict(cost_budgets or {})
        self._cost_estimates = dict(cost_estimates or {})
        self._cost_policy_approval = cost_policy_approval
        self._cost_policy_verifier = cost_policy_verifier
        self._cost_policy_enabled = cost_budgets is not None or cost_estimates is not None or cost_policy_approval is not None
        if self._cost_policy_enabled and (cost_budgets is None or cost_estimates is None):
            raise ValueError("cost_budgets and cost_estimates must be configured together")
        self._retry_delay_seconds = max(0.0, min(retry_delay_seconds, 2.0))

    @property
    def has_approved_cost_policy(self) -> bool:
        if not (self._cost_policy_enabled and self._cost_budgets and self._cost_estimates and self._cost_policy_approval and self._cost_policy_verifier):
            return False
        try:
            return self._cost_policy_verifier.is_approved(self._cost_policy_approval) is True
        except Exception:
            return False

    @property
    def has_durable_metering_contract(self) -> bool:
        return self._metering_sink is not None and callable(getattr(self._metering_sink, "write_idempotent", None))

    def require_runtime_ready(self) -> None:
        """Enforce runtime-only prerequisites without forcing test-only router construction."""
        if not self.has_approved_cost_policy:
            raise ModelRouterUnavailable("runtime requires cost budgets, route estimates, and a verifier-confirmed active cost policy approval")
        if not self.has_durable_metering_contract:
            raise ModelRouterUnavailable("runtime requires a durable idempotent metering sink")
        if any(route.dimensions is None for route in self._routes.values()):
            raise ModelRouterUnavailable("runtime requires an explicitly approved embedding dimension for every route")

    async def embed(self, request: EmbeddingRequest) -> EmbeddingResponse:
        route = self._routes.get(request.sensitivity)
        if route is None:
            raise ModelRouterUnavailable(f"No approved embedding route for sensitivity={request.sensitivity}")
        if route.dimensions is None:
            raise ModelRouterUnavailable("approved embedding route must pin an explicit vector dimension")
        cost_authorization = None
        if self._cost_policy_enabled:
            if not self.has_approved_cost_policy:
                raise ModelRouterUnavailable("cost policy approval is missing, unverified, or inactive")
            estimate = self._cost_estimates.get(request.sensitivity)
            if estimate is not None and (estimate.provider_id != route.provider_id or estimate.model_id != route.model_id or estimate.model_version != route.model_version):
                raise ModelRouterUnavailable("cost estimate does not match the selected provider/model version")
            try:
                cost_authorization = authorize_cost(sensitivity=request.sensitivity, estimate=estimate, budgets=self._cost_budgets)
            except (ValueError, RuntimeError) as exc:
                raise ModelRouterUnavailable("approved cost policy is unavailable or rejects this request") from exc
        adapter = self._adapters.get(route.provider_id)
        if adapter is None:
            raise ModelRouterUnavailable(f"No provider adapter registered for provider_id={route.provider_id}")
        last_error: Exception | None = None
        for attempt in range(min(route.max_attempts, 8)):
            attempt_delay_seconds = self._retry_delay_seconds * (attempt + 1)
            try:
                response = await asyncio.wait_for(adapter.embed(request, model_id=route.model_id), timeout=request.timeout_ms / 1000)
                if response.provider_id != route.provider_id or response.model_id != route.model_id:
                    raise ModelRouterRejected(EmbeddingFailure(task_id=request.task_id, code="MODEL_ROUTER_ROUTE_IDENTITY_MISMATCH", retryable=False, trace_id=request.trace_id))
                if response.model_version != route.model_version:
                    raise ModelRouterRejected(EmbeddingFailure(task_id=request.task_id, code="MODEL_ROUTER_MODEL_VERSION_MISMATCH", retryable=False, trace_id=request.trace_id))
                if route.dimensions is not None and response.dimensions != route.dimensions:
                    raise ModelRouterRejected(EmbeddingFailure(task_id=request.task_id, code="MODEL_ROUTER_DIMENSION_MISMATCH", retryable=False, trace_id=request.trace_id))
                try:
                    validate_response_matches_request(request, response)
                except ValueError as exc:
                    raise ModelRouterRejected(EmbeddingFailure(task_id=request.task_id, code="MODEL_ROUTER_RESPONSE_INVALID", retryable=False, trace_id=request.trace_id)) from exc
                if cost_authorization is not None:
                    if (response.usage_unit, response.cost_unit, response.pricing_version) != (cost_authorization.usage_unit, cost_authorization.cost_unit, cost_authorization.pricing_version):
                        raise ModelRouterRejected(EmbeddingFailure(task_id=request.task_id, code="MODEL_ROUTER_COST_UNIT_MISMATCH", retryable=False, trace_id=request.trace_id))
                    try:
                        validate_actual_cost(
                            authorization=cost_authorization,
                            actual_usage_units=response.usage_units,
                            actual_cost_microunits=response.cost_microunits,
                            budget=self._cost_budgets[request.sensitivity],
                        )
                    except (ValueError, RuntimeError) as exc:
                        raise ModelRouterRejected(EmbeddingFailure(task_id=request.task_id, code="MODEL_ROUTER_COST_POLICY_REJECTED", retryable=False, trace_id=request.trace_id)) from exc
                if self._metering_sink is not None:
                    try:
                        record = build_metering_record(request, response)
                        await self._metering_sink.write_idempotent(record)
                    except Exception as exc:
                        # A provider response may already be billable. Never retry
                        # the provider call when durable usage persistence is uncertain.
                        raise ModelRouterRejected(EmbeddingFailure(
                            task_id=request.task_id,
                            code="MODEL_ROUTER_METERING_UNCONFIRMED",
                            retryable=False,
                            trace_id=request.trace_id,
                        )) from exc
                return response
            except ModelRouterRejected:
                raise
            except asyncio.TimeoutError as exc:
                # The provider may have accepted and billed the request before the
                # response timed out. Never replay an outcome-unknown embedding call.
                raise ModelRouterRejected(EmbeddingFailure(
                    task_id=request.task_id,
                    code="MODEL_ROUTER_OUTCOME_UNKNOWN",
                    retryable=False,
                    trace_id=request.trace_id,
                )) from exc
            except ModelRouterTransient as exc:
                if not exc.safe_to_retry:
                    raise ModelRouterRejected(EmbeddingFailure(
                        task_id=request.task_id,
                        code="MODEL_ROUTER_OUTCOME_UNKNOWN",
                        retryable=False,
                        trace_id=request.trace_id,
                    )) from exc
                last_error = exc
                if exc.retry_after_ms is not None:
                    attempt_delay_seconds = exc.retry_after_ms / 1000
            if attempt + 1 < min(route.max_attempts, 8):
                await asyncio.sleep(max(0.0, min(attempt_delay_seconds, 30.0)))
        retry_after_ms = (
            last_error.retry_after_ms
            if isinstance(last_error, ModelRouterTransient) and last_error.retry_after_ms is not None
            else int(self._retry_delay_seconds * 1000)
        )
        raise ModelRouterRejected(EmbeddingFailure(
            task_id=request.task_id,
            code="MODEL_ROUTER_TRANSIENT_FAILURE",
            retryable=True,
            retry_after_ms=retry_after_ms,
            trace_id=request.trace_id,
        )) from last_error

async def route_embedding(router: EmbeddingRouter | None, request: EmbeddingRequest) -> EmbeddingResponse:
    """Shared entry point; fail closed and validate provenance at the boundary."""
    if router is None:
        raise ModelRouterUnavailable("Canonical AI Gateway/Model Router embedding capability is not configured")
    response = await router.embed(request)
    try:
        validate_response_matches_request(request, response)
    except ValueError as exc:
        raise ModelRouterRejected(EmbeddingFailure(task_id=request.task_id, code="MODEL_ROUTER_RESPONSE_INVALID", retryable=False, trace_id=request.trace_id)) from exc
    return response

class EmbeddingRouter(Protocol):
    async def embed(self, request: EmbeddingRequest) -> EmbeddingResponse:
        """The canonical router contract consumed by feature modules."""


# Text-generation capability for Agent/Skill execution. Kept in the canonical
# Model Router module so domain features cannot create provider-specific bypasses.
import hashlib
import json
import time
from datetime import datetime, timezone
from dataclasses import asdict
from typing import Any, Awaitable, Callable, Literal, Protocol


@dataclass(frozen=True)
class TextGenerationRequest:
    task_id: str
    trace_id: str
    idempotency_key: str
    sensitivity: str
    prompt: str
    max_output_tokens: int
    timeout_ms: int
    owner_id: str | None = None
    agent_id: str | None = None
    source_id: str | None = None
    source_version: int = 1
    billing_account_id: str | None = None
    system_prompt: str = ""
    response_format: Literal["json_object"] | None = None
    tool_definitions: tuple[dict[str, Any], ...] = ()
    max_tool_calls: int = 5
    conversation_messages: tuple[dict[str, Any], ...] = ()

    def prompt_material(self) -> str:
        return json.dumps({
            "system_prompt": self.system_prompt,
            "prompt": self.prompt,
            "conversation_messages": list(self.conversation_messages),
        }, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)

    def __post_init__(self) -> None:
        if not self.task_id.strip() or not self.trace_id.strip() or not self.idempotency_key.strip():
            raise ValueError("text generation task, trace and idempotency identifiers are required")
        if not self.sensitivity.strip():
            raise ValueError("text generation sensitivity is required")
        if not self.prompt.strip() and not self.conversation_messages:
            raise ValueError("text generation requires a prompt or conversation messages")
        if not isinstance(self.conversation_messages, tuple) or len(self.conversation_messages) > 32:
            raise ValueError("conversation messages must be a tuple of at most 32 entries")
        pending_tool_call_ids: set[str] = set()
        for message in self.conversation_messages:
            if not isinstance(message, dict) or message.get("role") not in {"system", "user", "assistant", "tool"}:
                raise ValueError("conversation message role is invalid")
            if set(message) - {"role", "content", "tool_calls", "tool_call_id", "name"}:
                raise ValueError("conversation message contains unsupported fields")
            content = message.get("content")
            if content is not None and not isinstance(content, str):
                raise ValueError("conversation message content must be text or null")
            if isinstance(content, str) and len(content.encode("utf-8")) > 16_384:
                raise ValueError("conversation message content exceeds 16 KiB")
            if message["role"] == "assistant" and "tool_calls" in message:
                calls = message.get("tool_calls")
                if not isinstance(calls, list) or not 1 <= len(calls) <= self.max_tool_calls:
                    raise ValueError("assistant tool_calls must be a bounded non-empty list")
                for call in calls:
                    if (not isinstance(call, dict) or set(call) != {"id", "type", "function"}
                            or call.get("type") != "function"
                            or not isinstance(call.get("id"), str) or not call["id"].strip()
                            or call["id"] in pending_tool_call_ids
                            or not isinstance(call.get("function"), dict)
                            or set(call["function"]) != {"name", "arguments"}
                            or not isinstance(call["function"].get("name"), str)
                            or not call["function"]["name"].strip()):
                        raise ValueError("assistant tool_call structure is invalid")
                    arguments = call["function"]["arguments"]
                    if not isinstance(arguments, (str, dict)):
                        raise ValueError("assistant tool_call arguments must be JSON text or an object")
                    if isinstance(arguments, str):
                        try:
                            parsed_arguments = json.loads(arguments)
                        except (TypeError, ValueError) as exc:
                            raise ValueError("assistant tool_call arguments must be valid JSON") from exc
                        if not isinstance(parsed_arguments, dict):
                            raise ValueError("assistant tool_call arguments must decode to an object")
                    elif not isinstance(arguments, dict):
                        raise ValueError("assistant tool_call arguments must be an object")
                    pending_tool_call_ids.add(call["id"])
            elif message["role"] == "tool":
                call_id = message.get("tool_call_id")
                if not isinstance(call_id, str) or call_id not in pending_tool_call_ids:
                    raise ValueError("tool result messages require a tool_call_id matching a preceding assistant tool_call")
                if not isinstance(message.get("name"), str) or not message["name"].strip():
                    raise ValueError("tool result messages require the registered tool name")
                pending_tool_call_ids.remove(call_id)
            elif "tool_call_id" in message or "name" in message:
                raise ValueError("tool result metadata is valid only on tool messages")
        if pending_tool_call_ids:
            raise ValueError("conversation contains assistant tool_calls without matching tool results")
        try:
            combined_prompt = self.prompt_material()
        except (TypeError, ValueError) as exc:
            raise ValueError("conversation messages must be valid JSON values") from exc
        if len(combined_prompt.encode("utf-8")) > 32_768:
            raise ValueError("combined system, user and conversation context must be at most 32 KiB")
        if not 1 <= self.max_output_tokens <= 16_384:
            raise ValueError("max_output_tokens must be between 1 and 16384")
        if not 100 <= self.timeout_ms <= 120_000:
            raise ValueError("timeout_ms must be between 100 and 120000")
        context = (self.owner_id, self.agent_id, self.source_id)
        if any(value is not None for value in context) and not all(isinstance(value, str) and value.strip() for value in context):
            raise ValueError("generation owner, agent and source context must be supplied together")
        if self.source_version < 1:
            raise ValueError("source_version must be positive")
        if self.billing_account_id is not None and not self.billing_account_id.strip():
            raise ValueError("billing_account_id must be non-empty when supplied")
        if not 1 <= self.max_tool_calls <= 5:
            raise ValueError("max_tool_calls must be between 1 and 5")
        names: set[str] = set()
        for definition in self.tool_definitions:
            if not isinstance(definition, dict) or definition.get("type") != "function":
                raise ValueError("tool definitions must use the function contract")
            function = definition.get("function")
            if not isinstance(function, dict):
                raise ValueError("tool definition function must be an object")
            name = function.get("name")
            parameters = function.get("parameters")
            if not isinstance(name, str) or not name or len(name) > 100 or name in names:
                raise ValueError("tool names must be unique non-empty identifiers")
            if not isinstance(parameters, dict) or parameters.get("type") != "object":
                raise ValueError("tool parameters must declare an object JSON schema")
            names.add(name)


@dataclass(frozen=True)
class TextGenerationToolCall:
    call_id: str
    name: str
    arguments: dict[str, Any]

    def __post_init__(self) -> None:
        if not self.call_id.strip() or not self.name.strip() or not isinstance(self.arguments, dict):
            raise ValueError("tool call identity and object arguments are required")


@dataclass(frozen=True)
class TextGenerationResponse:
    task_id: str
    trace_id: str
    provider_id: str
    model_id: str
    model_version: str
    output_text: str
    input_tokens: int
    output_tokens: int
    cost_microunits: int
    cost_unit: str
    pricing_version: str
    tool_calls: tuple[TextGenerationToolCall, ...] = ()

    def __post_init__(self) -> None:
        if not all(value.strip() for value in (self.task_id, self.trace_id, self.provider_id, self.model_id, self.model_version, self.cost_unit, self.pricing_version)):
            raise ValueError("generation response identity and cost fields are required")
        if not self.output_text.strip() and not self.tool_calls:
            raise ValueError("generation response requires text or tool calls")
        if len(self.tool_calls) > 5 or len({call.call_id for call in self.tool_calls}) != len(self.tool_calls):
            raise ValueError("tool call count and identifiers must be bounded and unique")
        if min(self.input_tokens, self.output_tokens, self.cost_microunits) < 0:
            raise ValueError("generation usage and cost must be non-negative")


class TextGenerationAdapter(Protocol):
    async def generate(self, request: TextGenerationRequest, *, model_id: str) -> TextGenerationResponse:
        """Use server-side credentials and return provider-reported usage/cost metadata."""


@dataclass(frozen=True)
class TextGenerationRoute:
    provider_id: str
    model_id: str
    model_version: str
    max_attempts: int = 1

    def __post_init__(self) -> None:
        if not all(value.strip() for value in (self.provider_id, self.model_id, self.model_version)):
            raise ValueError("text generation route identity fields must be configured")
        if not 1 <= self.max_attempts <= 3:
            raise ValueError("text generation max_attempts must be between 1 and 3")


@dataclass(frozen=True)
class TextGenerationPolicy:
    policy_id: str
    policy_version: str
    approved: bool
    max_prompt_bytes: int
    max_output_tokens: int
    max_cost_microunits: int
    max_latency_ms: int
    cost_unit: str
    pricing_version: str

    def __post_init__(self) -> None:
        if not all(value.strip() for value in (self.policy_id, self.policy_version, self.cost_unit, self.pricing_version)):
            raise ValueError("text generation policy identity and pricing contract are required")
        if not self.approved:
            raise ValueError("text generation policy must be approved")
        if not 1 <= self.max_prompt_bytes <= 32_768:
            raise ValueError("max_prompt_bytes must be between 1 and 32768")
        if not 1 <= self.max_output_tokens <= 16_384 or self.max_cost_microunits < 0:
            raise ValueError("text generation output and cost bounds are invalid")
        if not 100 <= self.max_latency_ms <= 120_000:
            raise ValueError("max_latency_ms must be between 100 and 120000")


@dataclass(frozen=True)
class TextGenerationEvidence:
    task_id: str
    trace_id: str
    idempotency_key: str
    policy_id: str
    policy_version: str
    provider_id: str
    model_id: str
    model_version: str
    prompt_sha256: str
    output_sha256: str
    input_tokens: int
    output_tokens: int
    cost_microunits: int
    cost_unit: str
    pricing_version: str
    latency_ms: int
    latency_budget_ms: int
    cost_budget_microunits: int
    status: str
    owner_id: str | None
    agent_id: str | None
    source_id: str | None
    source_version: int
    sensitivity: str
    evidence_sha256: str
    billing_account_id: str | None = None
    completed_at: str = ""
    usage_units: int = 0
    usage_unit: str = "tokens_total"


class TextGenerationMeteringSink(Protocol):
    async def write_idempotent(self, evidence: TextGenerationEvidence) -> None:
        """Persist usage with a unique task/idempotency identity; must be durable."""


class TextGenerationCreditLedger(Protocol):
    async def reserve(self, request: TextGenerationRequest, policy: TextGenerationPolicy) -> Any:
        """Atomically reserve one approved billable generation unit."""

    async def settle(self, reservation: Any, evidence: TextGenerationEvidence) -> None:
        """Settle only after durable model usage evidence exists."""

    async def release(self, reservation: Any, reason_code: str) -> None:
        """Release only when every provider confirms pre-execution failure."""

    async def mark_pending(self, reservation: Any, reason_code: str) -> None:
        """Keep credits reserved when provider outcome or settlement is unknown."""


class TextGenerationRouterUnavailable(RuntimeError):
    """No approved text-generation route, adapter, policy or durable sink is available."""

    def __init__(self, message: str, *, category: str = "runtime_unavailable") -> None:
        self.category = category
        super().__init__(message)


class TextGenerationRouterRejected(RuntimeError):
    """The provider response violated the canonical text-generation contract."""


class TextGenerationProviderTransient(RuntimeError):
    """Provider explicitly confirms that no generation was executed."""

    def __init__(self, message: str, *, safe_to_retry: bool, retry_after_ms: int | None = None) -> None:
        self.safe_to_retry = safe_to_retry is True
        self.retry_after_ms = max(0, min(int(retry_after_ms), 30_000)) if retry_after_ms is not None else None
        super().__init__(message)


class CanonicalTextGenerationRouter:
    """Provider-neutral text-generation path for Agent/Skill execution.

    Route, approved policy and provider adapters are supplied by deployment-owned
    configuration. Ordered fallbacks are allowed only for the same quoted model id,
    model version and pricing/policy contract. Failover is preflight-only; a provider
    call with an unknown outcome is never replayed. Runtime use requires durable metering.
    """

    def __init__(
        self,
        *,
        routes: dict[str, TextGenerationRoute],
        adapters: dict[str, TextGenerationAdapter],
        policies: dict[str, TextGenerationPolicy],
        metering_sink: TextGenerationMeteringSink | None,
        retry_delay_seconds: float = 0.1,
        runtime_preflight: Callable[[str, TextGenerationRoute, TextGenerationPolicy], Awaitable[None]] | None = None,
        fallback_routes: dict[str, tuple[TextGenerationRoute, ...]] | None = None,
        credit_ledger: TextGenerationCreditLedger | None = None,
    ) -> None:
        self._routes = dict(routes)
        self._adapters = dict(adapters)
        self._policies = dict(policies)
        self._fallback_routes = {key: tuple(value) for key, value in (fallback_routes or {}).items()}
        self._metering_sink = metering_sink
        self._retry_delay_seconds = max(0.0, min(retry_delay_seconds, 1.0))
        self._runtime_preflight = runtime_preflight
        self._credit_ledger = credit_ledger
        for sensitivity, fallbacks in self._fallback_routes.items():
            primary = self._routes.get(sensitivity)
            policy = self._policies.get(sensitivity)
            if primary is None or policy is None or not policy.approved:
                raise ValueError("fallback routes require a configured primary route and approved policy")
            seen = {primary.provider_id}
            for fallback in fallbacks:
                if fallback.provider_id in seen:
                    raise ValueError("text-generation fallback provider identities must be unique")
                if (fallback.model_id, fallback.model_version) != (primary.model_id, primary.model_version):
                    raise ValueError("fallback routes must preserve the quoted model id and version")
                seen.add(fallback.provider_id)

    def _candidate_routes(self, sensitivity: str) -> tuple[TextGenerationRoute, ...]:
        primary = self._routes.get(sensitivity)
        if primary is None:
            return ()
        return (primary, *self._fallback_routes.get(sensitivity, ()))

    def _candidate_snapshot(self, sensitivity: str, route: TextGenerationRoute, rank: int) -> dict[str, Any]:
        policy = self._policies[sensitivity]
        return {
            "provider_id": route.provider_id, "model_id": route.model_id,
            "model_version": route.model_version, "policy_id": policy.policy_id,
            "policy_version": policy.policy_version, "cost_unit": policy.cost_unit,
            "pricing_version": policy.pricing_version,
            "max_prompt_bytes": policy.max_prompt_bytes,
            "max_output_tokens": policy.max_output_tokens,
            "max_cost_microunits": policy.max_cost_microunits,
            "max_latency_ms": policy.max_latency_ms,
            "fallback_rank": rank, "fallback_used": rank > 0,
        }

    async def _select_preflight_route(self, sensitivity: str) -> tuple[TextGenerationRoute, int]:
        if self._runtime_preflight is None:
            raise TextGenerationRouterUnavailable("runtime policy and active tariff verifier are not configured", category="runtime_policy")
        candidates = self._candidate_routes(sensitivity)
        failures: list[TextGenerationRouterUnavailable] = []
        for rank, route in enumerate(candidates):
            if route.provider_id not in self._adapters:
                failures.append(TextGenerationRouterUnavailable("registered text-generation provider adapter is missing", category="provider_route"))
                continue
            try:
                await self._runtime_preflight(sensitivity, route, self._policies[sensitivity])
                return route, rank
            except TextGenerationRouterUnavailable as exc:
                failures.append(exc)
            except Exception as exc:
                failures.append(TextGenerationRouterUnavailable(
                    "active model-cost configuration could not be verified; provider execution is blocked",
                    category=getattr(exc, "category", "runtime_policy"),
                ))
        if len(candidates) == 1 and failures:
            raise failures[0]
        if failures:
            last = failures[-1]
            raise TextGenerationRouterUnavailable(
                "no configured approved text-generation route passed policy and active-tariff preflight; provider execution is blocked",
                category=last.category,
            ) from last
        raise TextGenerationRouterUnavailable("no configured text-generation route candidate is available", category="provider_route")

    def require_runtime_ready(self, sensitivity: str) -> None:
        route = self._routes.get(sensitivity)
        policy = self._policies.get(sensitivity)
        if route is None or policy is None or not policy.approved:
            raise TextGenerationRouterUnavailable("no approved text-generation route and policy for this sensitivity", category="runtime_policy")
        if not any(candidate.provider_id in self._adapters for candidate in self._candidate_routes(sensitivity)):
            raise TextGenerationRouterUnavailable("no registered text-generation provider adapter is available for primary or fallback route", category="provider_route")
        if self._metering_sink is None or not callable(getattr(self._metering_sink, "write_idempotent", None)):
            raise TextGenerationRouterUnavailable("runtime requires a durable idempotent text-generation metering sink", category="metering_sink")
        if self._fallback_routes and self._runtime_preflight is None:
            raise TextGenerationRouterUnavailable("provider fallback requires per-candidate policy and tariff preflight", category="runtime_policy")
        if self._runtime_preflight is not None and self._credit_ledger is None:
            raise TextGenerationRouterUnavailable("production text-generation requires an atomic credit reservation and settlement ledger", category="credit_ledger")

    async def preflight(self, sensitivity: str) -> dict[str, Any]:
        """Select the first approved route whose provider, policy, active tariff and metering are ready."""
        self.require_runtime_ready(sensitivity)
        route, rank = await self._select_preflight_route(sensitivity)
        return {
            "status": "ready",
            "route": self._candidate_snapshot(sensitivity, route, rank),
            "fallback_routes": [
                {"provider_id": item.provider_id, "model_id": item.model_id, "model_version": item.model_version}
                for item in self._fallback_routes.get(sensitivity, ())
            ],
            "metering_sink": "configured",
            "runtime_policy": "approved",
            "active_tariff": "verified",
        }

    def max_output_tokens_for(self, sensitivity: str) -> int:
        policy = self._policies.get(sensitivity)
        if policy is None or not policy.approved:
            raise TextGenerationRouterUnavailable("no approved text-generation policy for this sensitivity")
        return policy.max_output_tokens

    def policy_version_for(self, sensitivity: str) -> str:
        policy = self._policies.get(sensitivity)
        if policy is None or not policy.approved:
            raise TextGenerationRouterUnavailable("no approved text-generation policy for this sensitivity")
        return policy.policy_version

    def route_snapshot_for(self, sensitivity: str) -> dict[str, Any]:
        self.require_runtime_ready(sensitivity)
        candidates = self._candidate_routes(sensitivity)
        selected_rank = next((i for i, route in enumerate(candidates) if route.provider_id in self._adapters), 0)
        selected = candidates[selected_rank]
        return {
            **self._candidate_snapshot(sensitivity, selected, selected_rank),
            "fallback_routes": [
                {"provider_id": item.provider_id, "model_id": item.model_id, "model_version": item.model_version}
                for item in self._fallback_routes.get(sensitivity, ())
            ],
        }

    async def generate(self, request: TextGenerationRequest) -> tuple[TextGenerationResponse, TextGenerationEvidence]:
        self.require_runtime_ready(request.sensitivity)
        policy = self._policies[request.sensitivity]
        if request.timeout_ms > policy.max_latency_ms:
            raise TextGenerationRouterRejected("request timeout exceeds approved latency budget")
        if self._runtime_preflight is not None and not all((request.owner_id, request.agent_id, request.source_id)):
            raise TextGenerationRouterRejected("runtime generation requires trusted owner, Agent and Skill attribution before provider execution")
        combined_prompt = request.prompt_material()
        if len(combined_prompt.encode("utf-8")) > policy.max_prompt_bytes:
            raise TextGenerationRouterRejected("combined system and user prompt exceeds approved policy bound")
        if request.max_output_tokens > policy.max_output_tokens:
            raise TextGenerationRouterRejected("requested output tokens exceed approved policy bound")

        candidates = self._candidate_routes(request.sensitivity)
        if self._runtime_preflight is not None:
            _initial_route, start_rank = await self._select_preflight_route(request.sensitivity)
        else:
            start_rank = next(
                (rank for rank, candidate in enumerate(candidates) if candidate.provider_id in self._adapters),
                -1,
            )
            if start_rank < 0:
                raise TextGenerationRouterUnavailable("no configured provider adapter is available", category="provider_route")

        last_safe_failure: TextGenerationProviderTransient | None = None
        for rank in range(start_rank, len(candidates)):
            route = candidates[rank]
            if route.provider_id not in self._adapters:
                continue
            if rank > start_rank and self._runtime_preflight is not None:
                try:
                    await self._runtime_preflight(request.sensitivity, route, policy)
                except Exception:
                    # An unverified fallback is never called. Continue only to a
                    # separately configured candidate with its own tariff proof.
                    continue

            adapter = self._adapters[route.provider_id]
            for attempt in range(route.max_attempts):
                started = time.monotonic()
                try:
                    response = await asyncio.wait_for(
                        adapter.generate(request, model_id=route.model_id),
                        timeout=request.timeout_ms / 1000,
                    )
                    latency_ms = max(0, int((time.monotonic() - started) * 1000))
                    policy_rejection: str | None = None
                    if (response.task_id != request.task_id or response.trace_id != request.trace_id
                            or response.provider_id != route.provider_id or response.model_id != route.model_id
                            or response.model_version != route.model_version):
                        policy_rejection = "provider response identity does not match the approved route"
                    elif response.output_tokens > request.max_output_tokens:
                        policy_rejection = "provider output exceeded requested token limit"
                    elif response.tool_calls and not request.tool_definitions:
                        policy_rejection = "provider returned tool calls when no tools were authorized for this request"
                    elif len(response.tool_calls) > request.max_tool_calls:
                        policy_rejection = "provider returned more tool calls than the request limit"
                    else:
                        allowed_tool_names = {item["function"]["name"] for item in request.tool_definitions}
                        if any(call.name not in allowed_tool_names for call in response.tool_calls):
                            policy_rejection = "provider returned a tool name outside the request allowlist"
                    if response.cost_unit != policy.cost_unit or response.pricing_version != policy.pricing_version:
                        policy_rejection = policy_rejection or "provider usage does not match approved pricing contract"
                    if response.cost_microunits > policy.max_cost_microunits:
                        policy_rejection = policy_rejection or "provider cost exceeded approved policy budget"
                    if latency_ms > policy.max_latency_ms:
                        policy_rejection = policy_rejection or "provider latency exceeded approved policy budget"
                    # Provider execution may already be billable even when its result
                    # violates a request/policy limit. Persist the usage evidence first.
                    prompt_hash = hashlib.sha256(request.prompt_material().encode("utf-8")).hexdigest()
                    output_material = response.output_text if response.output_text.strip() else json.dumps(
                        [{"id": call.call_id, "name": call.name, "arguments": call.arguments} for call in response.tool_calls],
                        sort_keys=True, separators=(",", ":"), allow_nan=False,
                    )
                    output_hash = hashlib.sha256(output_material.encode("utf-8")).hexdigest()
                    evidence_payload = {
                        "task_id": request.task_id, "trace_id": request.trace_id,
                        "idempotency_key": request.idempotency_key, "policy_id": policy.policy_id,
                        "policy_version": policy.policy_version, "provider_id": response.provider_id,
                        "model_id": response.model_id, "model_version": response.model_version,
                        "prompt_sha256": prompt_hash, "output_sha256": output_hash,
                        "input_tokens": response.input_tokens, "output_tokens": response.output_tokens,
                        "cost_microunits": response.cost_microunits, "cost_unit": response.cost_unit,
                        "pricing_version": response.pricing_version, "latency_ms": latency_ms,
                        "latency_budget_ms": policy.max_latency_ms,
                        "cost_budget_microunits": policy.max_cost_microunits, "status": "succeeded",
                        "owner_id": request.owner_id, "agent_id": request.agent_id,
                        "source_id": request.source_id, "source_version": request.source_version,
                        "sensitivity": request.sensitivity,
                        "billing_account_id": request.billing_account_id or request.owner_id,
                        "completed_at": datetime.now(timezone.utc).isoformat(),
                    }
                    digest = hashlib.sha256(json.dumps(evidence_payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
                    evidence = TextGenerationEvidence(**evidence_payload, evidence_sha256=digest)
                    try:
                        await self._metering_sink.write_idempotent(evidence)  # type: ignore[union-attr]
                    except Exception as exc:
                        # The provider may already have charged for this generation. Never
                        # retry the provider call just because durable evidence persistence failed.
                        raise TextGenerationRouterUnavailable(
                            "generation completed but durable usage evidence could not be recorded; automatic replay is blocked"
                        ) from exc
                    if policy_rejection:
                        raise TextGenerationRouterRejected(policy_rejection)
                    return response, evidence
                except TextGenerationProviderTransient as exc:
                    if not exc.safe_to_retry:
                        raise TextGenerationRouterUnavailable(
                            "text-generation provider outcome is unknown; automatic replay is blocked"
                        ) from exc
                    last_safe_failure = exc
                    if attempt + 1 < route.max_attempts:
                        delay_ms = exc.retry_after_ms if exc.retry_after_ms is not None else int(self._retry_delay_seconds * 1000)
                        if delay_ms:
                            await asyncio.sleep(min(delay_ms, 30_000) / 1000)
                        continue
                    # The provider explicitly rejected/never received this call;
                    # fail over only after the next candidate passes its own preflight.
                    break
                except (TextGenerationRouterRejected, TextGenerationRouterUnavailable):
                    raise
                except asyncio.TimeoutError as exc:
                    # A timed-out generation may have completed remotely. Without an
                    # adapter-verified idempotent replay contract, never issue a second call.
                    raise TextGenerationRouterUnavailable(
                        "text-generation outcome is unknown after timeout; automatic replay is blocked"
                    ) from exc
                except Exception as exc:
                    raise TextGenerationRouterUnavailable(
                        "text-generation provider outcome is unknown; automatic replay is blocked"
                    ) from exc

        if last_safe_failure is not None:
            raise TextGenerationRouterUnavailable(
                "all approved text-generation providers were unavailable before generation; fallback exhausted",
                category="provider_route",
            ) from last_safe_failure
        raise TextGenerationRouterUnavailable("no configured approved text-generation route candidate is available", category="provider_route")

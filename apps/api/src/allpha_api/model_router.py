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
    """An adapter failure that policy permits retrying."""

class EmbeddingAdapter(Protocol):
    async def embed(self, request: EmbeddingRequest, *, model_id: str) -> EmbeddingResponse:
        """Call one provider/model using the adapter's server-side credentials."""

@dataclass(frozen=True)
class EmbeddingRoute:
    provider_id: str
    model_id: str
    model_version: str
    max_attempts: int = 3
    def __post_init__(self):
        if not self.provider_id.strip() or not self.model_id.strip() or not self.model_version.strip():
            raise ValueError("embedding route identity fields must be configured")
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

    async def embed(self, request: EmbeddingRequest) -> EmbeddingResponse:
        route = self._routes.get(request.sensitivity)
        if route is None:
            raise ModelRouterUnavailable(f"No approved embedding route for sensitivity={request.sensitivity}")
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
            try:
                response = await asyncio.wait_for(adapter.embed(request, model_id=route.model_id), timeout=request.timeout_ms / 1000)
                if response.provider_id != route.provider_id or response.model_id != route.model_id:
                    raise ModelRouterRejected(EmbeddingFailure(task_id=request.task_id, code="MODEL_ROUTER_ROUTE_IDENTITY_MISMATCH", retryable=False, trace_id=request.trace_id))
                if response.model_version != route.model_version:
                    raise ModelRouterRejected(EmbeddingFailure(task_id=request.task_id, code="MODEL_ROUTER_MODEL_VERSION_MISMATCH", retryable=False, trace_id=request.trace_id))
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
                    record = build_metering_record(request, response)
                    await self._metering_sink.write_idempotent(record)
                return response
            except ModelRouterRejected:
                raise
            except asyncio.TimeoutError as exc:
                last_error = exc
            except ModelRouterTransient as exc:
                last_error = exc
            if attempt + 1 < min(route.max_attempts, 8):
                await asyncio.sleep(self._retry_delay_seconds * (attempt + 1))
        code = "MODEL_ROUTER_TIMEOUT" if isinstance(last_error, asyncio.TimeoutError) else "MODEL_ROUTER_TRANSIENT_FAILURE"
        raise ModelRouterRejected(EmbeddingFailure(task_id=request.task_id, code=code, retryable=True, retry_after_ms=int(self._retry_delay_seconds * 1000), trace_id=request.trace_id)) from last_error

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
from dataclasses import asdict
from typing import Any


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

    def __post_init__(self) -> None:
        if not self.task_id.strip() or not self.trace_id.strip() or not self.idempotency_key.strip():
            raise ValueError("text generation task, trace and idempotency identifiers are required")
        if not self.sensitivity.strip():
            raise ValueError("text generation sensitivity is required")
        if not self.prompt.strip() or len(self.prompt.encode("utf-8")) > 32_768:
            raise ValueError("text generation prompt must be non-empty and at most 32 KiB")
        if not 1 <= self.max_output_tokens <= 16_384:
            raise ValueError("max_output_tokens must be between 1 and 16384")
        if not 100 <= self.timeout_ms <= 120_000:
            raise ValueError("timeout_ms must be between 100 and 120000")
        context = (self.owner_id, self.agent_id, self.source_id)
        if any(value is not None for value in context) and not all(isinstance(value, str) and value.strip() for value in context):
            raise ValueError("generation owner, agent and source context must be supplied together")
        if self.source_version < 1:
            raise ValueError("source_version must be positive")


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

    def __post_init__(self) -> None:
        if not all(value.strip() for value in (self.task_id, self.trace_id, self.provider_id, self.model_id, self.model_version, self.cost_unit, self.pricing_version)):
            raise ValueError("generation response identity and cost fields are required")
        if not self.output_text.strip():
            raise ValueError("generation response output must not be empty")
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


class TextGenerationMeteringSink(Protocol):
    async def write_idempotent(self, evidence: TextGenerationEvidence) -> None:
        """Persist usage with a unique task/idempotency identity; must be durable."""


class TextGenerationRouterUnavailable(RuntimeError):
    """No approved text-generation route, adapter, policy or durable sink is available."""


class TextGenerationRouterRejected(RuntimeError):
    """The provider response violated the canonical text-generation contract."""


class CanonicalTextGenerationRouter:
    """Provider-neutral text-generation path for Agent/Skill execution.

    Route, approved policy and provider adapters are supplied by deployment-owned
    configuration. This class deliberately chooses no provider, model, tariff or
    fallback. Runtime use requires an idempotent metering sink.
    """

    def __init__(
        self,
        *,
        routes: dict[str, TextGenerationRoute],
        adapters: dict[str, TextGenerationAdapter],
        policies: dict[str, TextGenerationPolicy],
        metering_sink: TextGenerationMeteringSink | None,
        retry_delay_seconds: float = 0.1,
    ) -> None:
        self._routes = dict(routes)
        self._adapters = dict(adapters)
        self._policies = dict(policies)
        self._metering_sink = metering_sink
        self._retry_delay_seconds = max(0.0, min(retry_delay_seconds, 1.0))

    def require_runtime_ready(self, sensitivity: str) -> None:
        route = self._routes.get(sensitivity)
        policy = self._policies.get(sensitivity)
        if route is None or policy is None or not policy.approved:
            raise TextGenerationRouterUnavailable("no approved text-generation route and policy for this sensitivity")
        if route.provider_id not in self._adapters:
            raise TextGenerationRouterUnavailable("registered text-generation provider adapter is missing")
        if self._metering_sink is None or not callable(getattr(self._metering_sink, "write_idempotent", None)):
            raise TextGenerationRouterUnavailable("runtime requires a durable idempotent text-generation metering sink")

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
        route = self._routes[sensitivity]
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
        }

    async def generate(self, request: TextGenerationRequest) -> tuple[TextGenerationResponse, TextGenerationEvidence]:
        self.require_runtime_ready(request.sensitivity)
        route = self._routes[request.sensitivity]
        policy = self._policies[request.sensitivity]
        if len(request.prompt.encode("utf-8")) > policy.max_prompt_bytes:
            raise TextGenerationRouterRejected("prompt exceeds approved policy bound")
        if request.max_output_tokens > policy.max_output_tokens:
            raise TextGenerationRouterRejected("requested output tokens exceed approved policy bound")
        adapter = self._adapters[route.provider_id]
        last_error: Exception | None = None
        for attempt in range(route.max_attempts):
            started = time.monotonic()
            try:
                response = await asyncio.wait_for(
                    adapter.generate(request, model_id=route.model_id),
                    timeout=request.timeout_ms / 1000,
                )
                latency_ms = max(0, int((time.monotonic() - started) * 1000))
                if (response.task_id != request.task_id or response.trace_id != request.trace_id
                        or response.provider_id != route.provider_id or response.model_id != route.model_id
                        or response.model_version != route.model_version):
                    raise TextGenerationRouterRejected("provider response identity does not match the approved route")
                if response.output_tokens > request.max_output_tokens:
                    raise TextGenerationRouterRejected("provider output exceeded requested token limit")
                if response.cost_unit != policy.cost_unit or response.pricing_version != policy.pricing_version:
                    raise TextGenerationRouterRejected("provider usage does not match approved pricing contract")
                if response.cost_microunits > policy.max_cost_microunits:
                    raise TextGenerationRouterRejected("provider cost exceeded approved policy budget")
                prompt_hash = hashlib.sha256(request.prompt.encode("utf-8")).hexdigest()
                output_hash = hashlib.sha256(response.output_text.encode("utf-8")).hexdigest()
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
                return response, evidence
            except (TextGenerationRouterRejected, TextGenerationRouterUnavailable):
                raise
            except asyncio.TimeoutError as exc:
                # A timed-out generation may have completed remotely. Without an adapter-
                # verified idempotent replay contract, never issue a second billable call.
                raise TextGenerationRouterUnavailable(
                    "text-generation outcome is unknown after timeout; automatic replay is blocked"
                ) from exc
            except Exception as exc:
                # The adapter must classify failures before adding any safe retry strategy.
                raise TextGenerationRouterUnavailable(
                    "text-generation provider outcome is unknown; automatic replay is blocked"
                ) from exc
        if last_error is not None:
            raise TextGenerationRouterUnavailable("approved text-generation route failed") from last_error
        raise TextGenerationRouterUnavailable("approved text-generation route failed without a response")

from __future__ import annotations

"""Canonical provider-neutral embedding router core.

Provider SDKs belong in registered adapters, never in domain feature modules.
No default provider/model is selected: deployment policy must configure both.
"""
import asyncio
from dataclasses import dataclass
from typing import Awaitable, Callable, Protocol

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

MeteringSink = Callable[[EmbeddingRequest, EmbeddingResponse], Awaitable[None]]

class CanonicalModelRouter:
    """Own route selection, bounded timeout/retry and successful-call metering.

    routes is deployment-owned policy keyed by sensitivity. Missing entries fail
    closed. adapters are registered server-side provider integrations. The router
    does not guess a provider, model, dimension or fallback.
    """
    def __init__(self, *, routes: dict[str, EmbeddingRoute], adapters: dict[str, EmbeddingAdapter], metering_sink: MeteringSink | None = None, retry_delay_seconds: float = 0.15):
        self._routes = dict(routes)
        self._adapters = dict(adapters)
        self._metering_sink = metering_sink
        self._retry_delay_seconds = max(0.0, min(retry_delay_seconds, 2.0))

    async def embed(self, request: EmbeddingRequest) -> EmbeddingResponse:
        route = self._routes.get(request.sensitivity)
        if route is None:
            raise ModelRouterUnavailable(f"No approved embedding route for sensitivity={request.sensitivity}")
        adapter = self._adapters.get(route.provider_id)
        if adapter is None:
            raise ModelRouterUnavailable(f"No provider adapter registered for provider_id={route.provider_id}")
        attempts = min(route.max_attempts, 8)
        last_error: Exception | None = None
        for attempt in range(attempts):
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
                if self._metering_sink is not None:
                    await self._metering_sink(request, response)
                return response
            except ModelRouterRejected:
                raise
            except asyncio.TimeoutError as exc:
                last_error = exc
            except ModelRouterTransient as exc:
                last_error = exc
            if attempt + 1 < attempts:
                await asyncio.sleep(self._retry_delay_seconds * (attempt + 1))
        code = "MODEL_ROUTER_TIMEOUT" if isinstance(last_error, asyncio.TimeoutError) else "MODEL_ROUTER_TRANSIENT_FAILURE"
        failure = EmbeddingFailure(task_id=request.task_id, code=code, retryable=True, retry_after_ms=int(self._retry_delay_seconds * 1000), trace_id=request.trace_id)
        raise ModelRouterRejected(failure) from last_error

async def route_embedding(router: CanonicalModelRouter | None, request: EmbeddingRequest) -> EmbeddingResponse:
    """Shared entry point for domain modules; fail closed without canonical router."""
    if router is None:
        raise ModelRouterUnavailable("Canonical AI Gateway/Model Router embedding capability is not configured")
    return await router.embed(request)

from __future__ import annotations

"""Provider-neutral boundary for embedding requests routed by the canonical Model Router."""
from typing import Protocol
from allpha_api.embedding_contract import EmbeddingFailure, EmbeddingRequest, EmbeddingResponse, validate_response_matches_request


class ModelRouterUnavailable(RuntimeError):
    """The canonical router has not been wired into this API runtime."""


class ModelRouterRejected(RuntimeError):
    """The router response did not satisfy the embedding contract."""

    def __init__(self, failure: EmbeddingFailure):
        self.failure = failure
        super().__init__(failure.code)


class EmbeddingRouter(Protocol):
    async def embed(self, request: EmbeddingRequest) -> EmbeddingResponse:
        """Route through the canonical gateway; never a feature-owned provider client."""


async def route_embedding(router: EmbeddingRouter | None, request: EmbeddingRequest) -> EmbeddingResponse:
    """Fail closed without a router and reject mismatched chunk provenance."""
    if router is None:
        raise ModelRouterUnavailable("Canonical AI Gateway/Model Router embedding capability is not configured")
    response = await router.embed(request)
    try:
        validate_response_matches_request(request, response)
    except ValueError as exc:
        failure = EmbeddingFailure(task_id=request.task_id, code="MODEL_ROUTER_RESPONSE_INVALID", retryable=False, trace_id=request.trace_id)
        raise ModelRouterRejected(failure) from exc
    return response

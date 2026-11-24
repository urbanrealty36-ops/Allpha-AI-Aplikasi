"""Generic OpenAI-compatible embedding provider adapter for the canonical Model Router.

The adapter is provider-neutral: endpoint, provider/model identity, immutable
model version, dimensions and tariff are deployment policy. No provider or
model is selected by default. Credentials are server-side only.
"""
from __future__ import annotations

import math
import os
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlsplit

import httpx

from allpha_api.embedding_contract import (
    EmbeddingFailure,
    EmbeddingRequest,
    EmbeddingResponse,
)
from allpha_api.model_router import ModelRouterRejected, ModelRouterTransient


class EmbeddingProviderConfigurationError(ValueError):
    """The provider adapter is missing a deployment-owned configuration value."""


class OpenAICompatibleEmbeddingAdapter:
    """Adapter for the OpenAI-compatible POST /embeddings response contract."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        provider_id: str,
        model_version: str,
        expected_dimensions: int,
        pricing_version: str | None = None,
        cost_unit: str | None = None,
        input_cost_microunits_per_token: int | None = None,
        max_input_bytes: int | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        parts = urlsplit(base_url.strip())
        if (
            parts.scheme != "https"
            or not parts.netloc
            or parts.username
            or parts.password
            or parts.query
            or parts.fragment
        ):
            raise EmbeddingProviderConfigurationError(
                "embedding base URL must be an HTTPS origin/path without credentials, query or fragment"
            )
        if not all(value.strip() for value in (api_key, provider_id, model_version)):
            raise EmbeddingProviderConfigurationError("embedding provider credentials and identity are required")
        if not 1 <= expected_dimensions <= 8192:
            raise EmbeddingProviderConfigurationError("expected_dimensions must be between 1 and 8192")
        pricing = (pricing_version, cost_unit, input_cost_microunits_per_token)
        if any(value is not None for value in pricing) and any(value is None for value in pricing):
            raise EmbeddingProviderConfigurationError("embedding pricing version, cost unit and input rate must be configured together")
        if input_cost_microunits_per_token is not None and input_cost_microunits_per_token < 0:
            raise EmbeddingProviderConfigurationError("embedding input token rate must be non-negative")
        if max_input_bytes is not None and not 1 <= max_input_bytes <= 1_000_000:
            raise EmbeddingProviderConfigurationError("max_input_bytes must be between 1 and 1000000")

        self._url = base_url.rstrip("/") + "/embeddings"
        self._api_key = api_key
        self._provider_id = provider_id
        self._model_version = model_version
        self._dimensions = expected_dimensions
        self._pricing_version = pricing_version
        self._cost_unit = cost_unit
        self._input_rate = input_cost_microunits_per_token
        self._max_input_bytes = max_input_bytes
        self._transport = transport

    async def embed(self, request: EmbeddingRequest, *, model_id: str) -> EmbeddingResponse:
        if not model_id.strip():
            raise EmbeddingProviderConfigurationError("Model Router must supply a model ID")
        input_texts = [chunk.text for chunk in request.chunks]
        if self._max_input_bytes is not None:
            total_input_bytes = sum(len(text.encode("utf-8")) for text in input_texts)
            if total_input_bytes > self._max_input_bytes:
                raise ModelRouterRejected(EmbeddingFailure(
                    task_id=request.task_id,
                    code="EMBEDDING_INPUT_LIMIT_EXCEEDED",
                    retryable=False,
                    trace_id=request.trace_id,
                ))
        body = {
            "model": model_id,
            "input": input_texts,
        }
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(request.timeout_ms / 1000, connect=min(5.0, request.timeout_ms / 1000)),
                transport=self._transport,
            ) as client:
                response = await client.post(
                    self._url,
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                        "Accept": "application/json",
                    },
                    json=body,
                )
        except httpx.TimeoutException as exc:
            raise ModelRouterTransient("embedding provider timed out") from exc
        except httpx.RequestError as exc:
            raise ModelRouterTransient("embedding provider transport failed") from exc

        if response.status_code in {408, 425, 429} or response.status_code >= 500:
            raise ModelRouterTransient(f"embedding provider returned retryable HTTP {response.status_code}")
        if response.status_code < 200 or response.status_code >= 300:
            raise ModelRouterRejected(EmbeddingFailure(
                task_id=request.task_id,
                code="EMBEDDING_PROVIDER_REQUEST_REJECTED",
                retryable=False,
                trace_id=request.trace_id,
            ))
        try:
            payload = response.json()
        except ValueError as exc:
            raise ModelRouterRejected(EmbeddingFailure(
                task_id=request.task_id,
                code="EMBEDDING_PROVIDER_INVALID_JSON",
                retryable=False,
                trace_id=request.trace_id,
            )) from exc

        try:
            returned_model = payload["model"]
            rows = payload["data"]
            if returned_model != model_id or not isinstance(rows, list) or len(rows) != len(request.chunks):
                raise ValueError("provider model or vector cardinality mismatch")
            indexed: dict[int, list[float]] = {}
            for row in rows:
                index = row["index"]
                values = row["embedding"]
                if isinstance(index, bool) or not isinstance(index, int) or not 0 <= index < len(request.chunks):
                    raise ValueError("provider returned an invalid vector index")
                if index in indexed or not isinstance(values, list) or len(values) != self._dimensions:
                    raise ValueError("provider returned duplicate or wrong-dimension vectors")
                vector = [float(value) for value in values]
                if not all(math.isfinite(value) for value in vector):
                    raise ValueError("provider returned a non-finite vector value")
                indexed[index] = vector
            if set(indexed) != set(range(len(request.chunks))):
                raise ValueError("provider response omitted a requested chunk")
            vectors = [
                {
                    "chunk_id": chunk.chunk_id,
                    "content_sha256": chunk.content_sha256,
                    "values": indexed[index],
                }
                for index, chunk in enumerate(request.chunks)
            ]
            usage_units: int | None = None
            cost_microunits: int | None = None
            usage_unit: str | None = None
            cost_unit: str | None = None
            pricing_version: str | None = None
            if self._input_rate is not None:
                usage_units = int(payload["usage"]["prompt_tokens"])
                if usage_units < 0:
                    raise ValueError("provider usage must be non-negative")
                cost_microunits = usage_units * self._input_rate
                usage_unit = "input_tokens"
                cost_unit = self._cost_unit
                pricing_version = self._pricing_version
            return EmbeddingResponse(
                task_id=request.task_id,
                provider_id=self._provider_id,
                model_id=model_id,
                model_version=self._model_version,
                dimensions=self._dimensions,
                vectors=vectors,
                usage_units=usage_units,
                usage_unit=usage_unit,
                cost_microunits=cost_microunits,
                cost_unit=cost_unit,
                pricing_version=pricing_version,
                trace_id=request.trace_id,
                completed_at=datetime.now(timezone.utc),
            )
        except (KeyError, TypeError, ValueError, OverflowError) as exc:
            raise ModelRouterRejected(EmbeddingFailure(
                task_id=request.task_id,
                code="EMBEDDING_PROVIDER_RESPONSE_INVALID",
                retryable=False,
                trace_id=request.trace_id,
            )) from exc


def build_embedding_adapter_from_environment(
    *, transport: httpx.AsyncBaseTransport | None = None,
) -> tuple[str, OpenAICompatibleEmbeddingAdapter] | None:
    """Build one adapter only when its complete explicit deployment profile exists."""
    base_url = os.getenv("ALLPHA_EMBEDDING_BASE_URL", "").strip()
    api_key = os.getenv("ALLPHA_EMBEDDING_API_KEY", "").strip()
    provider_id = os.getenv("ALLPHA_EMBEDDING_PROVIDER_ID", "").strip()
    model_version = os.getenv("ALLPHA_EMBEDDING_MODEL_VERSION", "").strip()
    dimensions_raw = os.getenv("ALLPHA_EMBEDDING_DIMENSIONS", "").strip()
    if not any((base_url, api_key, provider_id, model_version, dimensions_raw)):
        return None
    required = (base_url, api_key, provider_id, model_version, dimensions_raw)
    if not all(required):
        raise EmbeddingProviderConfigurationError("embedding provider profile is partially configured")
    try:
        dimensions = int(dimensions_raw)
        rate_raw = os.getenv("ALLPHA_EMBEDDING_INPUT_COST_MICROUNITS_PER_TOKEN", "").strip()
        rate = int(rate_raw) if rate_raw else None
    except ValueError as exc:
        raise EmbeddingProviderConfigurationError("embedding dimensions and token rate must be integers") from exc
    max_input_bytes_raw = os.getenv("ALLPHA_EMBEDDING_MAX_PROMPT_BYTES", "").strip()
    try:
        max_input_bytes = int(max_input_bytes_raw) if max_input_bytes_raw else None
    except ValueError as exc:
        raise EmbeddingProviderConfigurationError("ALLPHA_EMBEDDING_MAX_PROMPT_BYTES must be an integer") from exc
    adapter = OpenAICompatibleEmbeddingAdapter(
        base_url=base_url,
        api_key=api_key,
        provider_id=provider_id,
        model_version=model_version,
        expected_dimensions=dimensions,
        pricing_version=os.getenv("ALLPHA_EMBEDDING_PRICING_VERSION") or None,
        cost_unit=os.getenv("ALLPHA_EMBEDDING_COST_UNIT") or None,
        input_cost_microunits_per_token=rate,
        max_input_bytes=max_input_bytes,
        transport=transport,
    )
    return provider_id, adapter

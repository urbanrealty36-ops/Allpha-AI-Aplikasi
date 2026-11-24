"""Deployment-owned composition of the embedding provider, policy and metering.

This builder has no provider defaults. It returns None when no profile is
configured and fails closed when a partially configured or unapproved profile
is present. It never enables a route from tariff activation alone.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone

import httpx

from allpha_api.cost_policy import (
    CostBudget,
    CostEstimate,
    CostPolicyApproval,
    CostPolicyApprovalVerifier,
)
from allpha_api.embedding_adapters import (
    EmbeddingProviderConfigurationError,
    build_embedding_adapter_from_environment,
)
from allpha_api.embedding_metering import SupabaseEmbeddingMeteringSink
from allpha_api.model_router import CanonicalModelRouter, EmbeddingRoute, ModelRouterUnavailable


_PROFILE_FIELDS = (
    "ALLPHA_EMBEDDING_BASE_URL",
    "ALLPHA_EMBEDDING_API_KEY",
    "ALLPHA_EMBEDDING_PROVIDER_ID",
    "ALLPHA_EMBEDDING_MODEL_ID",
    "ALLPHA_EMBEDDING_MODEL_VERSION",
    "ALLPHA_EMBEDDING_DIMENSIONS",
    "ALLPHA_EMBEDDING_POLICY_ID",
    "ALLPHA_EMBEDDING_POLICY_VERSION",
    "ALLPHA_EMBEDDING_POLICY_APPROVAL_REFERENCE",
    "ALLPHA_EMBEDDING_PRICING_VERSION",
    "ALLPHA_EMBEDDING_COST_UNIT",
    "ALLPHA_EMBEDDING_INPUT_COST_MICROUNITS_PER_TOKEN",
    "ALLPHA_EMBEDDING_MAX_INPUT_TOKENS",
    "ALLPHA_EMBEDDING_MAX_COST_MICROUNITS",
    "ALLPHA_EMBEDDING_MAX_PROMPT_BYTES",
    "ALLPHA_EMBEDDING_MAX_LATENCY_MS",
    "ALLPHA_EMBEDDING_ALLOWED_SENSITIVITIES",
    "SUPABASE_URL",
    "SUPABASE_SERVICE_ROLE_KEY",
)


class _VerifiedApproval(CostPolicyApprovalVerifier):
    def __init__(self, approval: CostPolicyApproval) -> None:
        self._approval = approval
        self._verified = False

    def mark_verified(self) -> None:
        self._verified = True

    def is_approved(self, approval: CostPolicyApproval) -> bool:
        return self._verified and approval == self._approval


class SupabaseActiveEmbeddingCostVerifier:
    """Verify one exact, active, operator-approved embedding tariff in Postgres."""

    def __init__(
        self, *, supabase_url: str, service_role_key: str, policy_id: str,
        policy_version: str, approval_reference: str, provider_id: str,
        model_id: str, model_version: str, pricing_version: str,
        cost_unit: str, input_rate: int, max_cost_microunits: int,
        max_prompt_bytes: int, max_latency_ms: int,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._url = supabase_url.rstrip("/") + "/rest/v1/ai_model_cost_configs"
        self._key = service_role_key
        self._expected = {
            "id": policy_id,
            "capability": "embedding",
            "policy_version": policy_version,
            "provider_id": provider_id,
            "model_id": model_id,
            "model_version": model_version,
            "pricing_version": pricing_version,
            "cost_unit": cost_unit,
            "input_micro_cost_per_token": input_rate,
            "output_micro_cost_per_token": 0,
            "max_cost_microunits": max_cost_microunits,
            "max_prompt_bytes": max_prompt_bytes,
            "max_latency_ms": max_latency_ms,
            "policy_approved": True,
            "status": "active",
        }
        self._approval_reference = approval_reference
        self._transport = transport

    async def verify(self) -> None:
        now = datetime.now(timezone.utc)
        params = {
            "select": ",".join((*self._expected.keys(), "effective_at", "policy_approval_reference", "policy_approved_by", "policy_approved_at")),
            "id": "eq." + str(self._expected["id"]),
            "capability": "eq.embedding",
            "provider_id": "eq." + str(self._expected["provider_id"]),
            "model_id": "eq." + str(self._expected["model_id"]),
            "model_version": "eq." + str(self._expected["model_version"]),
            "pricing_version": "eq." + str(self._expected["pricing_version"]),
            "policy_version": "eq." + str(self._expected["policy_version"]),
            "status": "eq.active",
            "policy_approved": "eq.true",
            "effective_at": "lte." + now.isoformat(),
            "limit": "2",
        }
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(5.0, connect=2.0), transport=self._transport,
            ) as client:
                response = await client.get(
                    self._url,
                    params=params,
                    headers={
                        "apikey": self._key,
                        "Authorization": "Bearer " + self._key,
                        "Accept": "application/json",
                    },
                )
                response.raise_for_status()
                rows = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ModelRouterUnavailable("embedding cost-policy registry is unavailable") from exc
        if not isinstance(rows, list) or len(rows) != 1:
            raise ModelRouterUnavailable("exactly one approved active embedding cost-policy row is required")
        row = rows[0]
        if not isinstance(row, dict):
            raise ModelRouterUnavailable("embedding cost-policy row is invalid")
        for field, expected in self._expected.items():
            if row.get(field) != expected:
                raise ModelRouterUnavailable(f"embedding cost-policy field {field} does not match deployment profile")
        reference = row.get("policy_approval_reference")
        actor = row.get("policy_approved_by")
        approved_at = row.get("policy_approved_at")
        effective_at = row.get("effective_at")
        if reference != self._approval_reference or not isinstance(actor, str) or not actor.strip():
            raise ModelRouterUnavailable("embedding policy approval reference or actor is invalid")
        if not isinstance(approved_at, str) or not isinstance(effective_at, str):
            raise ModelRouterUnavailable("embedding policy approval timestamps are absent")
        try:
            approved_time = datetime.fromisoformat(approved_at.replace("Z", "+00:00"))
            effective_time = datetime.fromisoformat(effective_at.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ModelRouterUnavailable("embedding policy approval timestamp is invalid") from exc
        if (
            approved_time.tzinfo is None or effective_time.tzinfo is None
            or approved_time > now or effective_time > now
        ):
            raise ModelRouterUnavailable("embedding policy approval is not effective")


async def build_embedding_router_from_environment(
    *, transport: httpx.AsyncBaseTransport | None = None,
) -> CanonicalModelRouter | None:
    """Build a runtime-ready embedding router only from a complete approved profile."""
    configured = [os.getenv(name, "").strip() for name in _PROFILE_FIELDS]
    if not any(configured):
        return None
    if not all(configured):
        missing = [name for name in _PROFILE_FIELDS if not os.getenv(name, "").strip()]
        raise EmbeddingProviderConfigurationError(
            "embedding deployment profile is incomplete: " + ", ".join(missing)
        )

    def integer(name: str) -> int:
        try:
            value = int(os.environ[name])
        except (KeyError, ValueError) as exc:
            raise EmbeddingProviderConfigurationError(f"{name} must be an integer") from exc
        if value < 0:
            raise EmbeddingProviderConfigurationError(f"{name} must be non-negative")
        return value

    provider_id = os.environ["ALLPHA_EMBEDDING_PROVIDER_ID"].strip()
    model_id = os.environ["ALLPHA_EMBEDDING_MODEL_ID"].strip()
    model_version = os.environ["ALLPHA_EMBEDDING_MODEL_VERSION"].strip()
    pricing_version = os.environ["ALLPHA_EMBEDDING_PRICING_VERSION"].strip()
    cost_unit = os.environ["ALLPHA_EMBEDDING_COST_UNIT"].strip()
    dimensions = integer("ALLPHA_EMBEDDING_DIMENSIONS")
    input_rate = integer("ALLPHA_EMBEDDING_INPUT_COST_MICROUNITS_PER_TOKEN")
    max_input_tokens = integer("ALLPHA_EMBEDDING_MAX_INPUT_TOKENS")
    max_cost = integer("ALLPHA_EMBEDDING_MAX_COST_MICROUNITS")
    max_prompt_bytes = integer("ALLPHA_EMBEDDING_MAX_PROMPT_BYTES")
    max_latency_ms = integer("ALLPHA_EMBEDDING_MAX_LATENCY_MS")
    if min(dimensions, max_input_tokens, max_prompt_bytes, max_latency_ms) < 1:
        raise EmbeddingProviderConfigurationError("embedding dimensions, request limits and latency must be positive")
    if max_input_tokens * input_rate > max_cost:
        raise EmbeddingProviderConfigurationError("embedding token reservation exceeds the approved per-request cost cap")
    sensitivities = tuple(
        item.strip().lower()
        for item in os.environ["ALLPHA_EMBEDDING_ALLOWED_SENSITIVITIES"].split(",")
        if item.strip()
    )
    allowed = {"public", "internal", "confidential", "restricted"}
    if not sensitivities or len(set(sensitivities)) != len(sensitivities) or set(sensitivities) - allowed:
        raise EmbeddingProviderConfigurationError("embedding allowed sensitivities must be an explicit unique allow-list")

    adapter_profile = build_embedding_adapter_from_environment(transport=transport)
    if adapter_profile is None:
        raise EmbeddingProviderConfigurationError("embedding provider adapter profile is unavailable")
    registered_provider, adapter = adapter_profile
    if registered_provider != provider_id:
        raise EmbeddingProviderConfigurationError("embedding adapter and cost-policy provider IDs differ")

    policy_id = os.environ["ALLPHA_EMBEDDING_POLICY_ID"].strip()
    policy_version = os.environ["ALLPHA_EMBEDDING_POLICY_VERSION"].strip()
    approval_reference = os.environ["ALLPHA_EMBEDDING_POLICY_APPROVAL_REFERENCE"].strip()
    approval = CostPolicyApproval(
        policy_id=policy_id, version=policy_version, approval_reference=approval_reference,
    )
    verifier = _VerifiedApproval(approval)
    registry = SupabaseActiveEmbeddingCostVerifier(
        supabase_url=os.environ["SUPABASE_URL"],
        service_role_key=os.environ["SUPABASE_SERVICE_ROLE_KEY"],
        policy_id=policy_id,
        policy_version=policy_version,
        approval_reference=approval_reference,
        provider_id=provider_id,
        model_id=model_id,
        model_version=model_version,
        pricing_version=pricing_version,
        cost_unit=cost_unit,
        input_rate=input_rate,
        max_cost_microunits=max_cost,
        max_prompt_bytes=max_prompt_bytes,
        max_latency_ms=max_latency_ms,
        transport=transport,
    )
    await registry.verify()
    verifier.mark_verified()

    usage_unit = "input_tokens"
    estimate = CostEstimate(
        provider_id=provider_id,
        model_id=model_id,
        model_version=model_version,
        usage_units=max_input_tokens,
        cost_microunits=max_input_tokens * input_rate,
        usage_unit=usage_unit,
        cost_unit=cost_unit,
        pricing_version=pricing_version,
    )
    budgets = {
        sensitivity: CostBudget(
            sensitivity=sensitivity,
            max_usage_units=max_input_tokens,
            max_cost_microunits=max_cost,
            usage_unit=usage_unit,
            cost_unit=cost_unit,
            pricing_version=pricing_version,
            require_actual_cost=True,
        )
        for sensitivity in sensitivities
    }
    estimates = {sensitivity: estimate for sensitivity in sensitivities}
    router = CanonicalModelRouter(
        routes={
            sensitivity: EmbeddingRoute(
                provider_id=provider_id,
                model_id=model_id,
                model_version=model_version,
                dimensions=dimensions,
                max_attempts=min(8, max(1, integer("ALLPHA_EMBEDDING_MAX_ATTEMPTS") if os.getenv("ALLPHA_EMBEDDING_MAX_ATTEMPTS") else 3),
            )
            for sensitivity in sensitivities
        },
        adapters={provider_id: adapter},
        metering_sink=SupabaseEmbeddingMeteringSink.from_environment(),
        cost_budgets=budgets,
        cost_estimates=estimates,
        cost_policy_approval=approval,
        cost_policy_verifier=verifier,
    )
    router.require_runtime_ready()
    return router

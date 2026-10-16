"""Deployment-configured OpenAI-compatible text generation and durable usage metering.

No provider, model, pricing, or budget is selected by default. The router stays
unavailable until every required production setting and explicit policy approval
is present. Provider credentials remain server-side in the API process.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from typing import Any

import httpx

from allpha_api.model_router import (
    CanonicalTextGenerationRouter,
    TextGenerationEvidence,
    TextGenerationPolicy,
    TextGenerationRequest,
    TextGenerationResponse,
    TextGenerationRoute,
)


class TextGenerationProviderError(RuntimeError):
    """Provider call failed or did not return the required usage contract."""


class OpenAICompatibleTextGenerationAdapter:
    """Adapter for providers implementing the OpenAI Chat Completions contract.

    ALLPHA_TEXTGEN_BASE_URL must be the provider API base, including its version
    prefix where required (for example, a provider's /v1 base URL).
    """

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        provider_id: str,
        model_version: str,
        pricing_version: str,
        cost_unit: str,
        input_cost_microunits_per_token: int,
        output_cost_microunits_per_token: int,
    ) -> None:
        if not all(v.strip() for v in (base_url, api_key, provider_id, model_version, pricing_version, cost_unit)):
            raise ValueError("text-generation adapter configuration is incomplete")
        if min(input_cost_microunits_per_token, output_cost_microunits_per_token) < 0:
            raise ValueError("token prices must be non-negative")
        self._url = base_url.rstrip("/") + "/chat/completions"
        self._key = api_key
        self._provider_id = provider_id
        self._model_version = model_version
        self._pricing_version = pricing_version
        self._cost_unit = cost_unit
        self._input_rate = input_cost_microunits_per_token
        self._output_rate = output_cost_microunits_per_token

    async def generate(self, request: TextGenerationRequest, *, model_id: str) -> TextGenerationResponse:
        headers = {
            "Authorization": f"Bearer {self._key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        body = {
            "model": model_id,
            "messages": [{"role": "user", "content": request.prompt}],
            "max_tokens": request.max_output_tokens,
            "stream": False,
        }
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(request.timeout_ms / 1000, connect=min(5.0, request.timeout_ms / 1000))) as client:
                response = await client.post(self._url, headers=headers, json=body)
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            # The request may have reached the provider. The caller must not blindly replay.
            raise TextGenerationProviderError("provider call failed or returned invalid JSON; outcome may be unknown") from exc

        try:
            choices = payload["choices"]
            message = choices[0]["message"]
            text = message["content"]
            usage = payload["usage"]
            input_tokens = int(usage["prompt_tokens"])
            output_tokens = int(usage["completion_tokens"])
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise TextGenerationProviderError("provider response is missing content or usage accounting") from exc
        if not isinstance(text, str) or not text.strip():
            raise TextGenerationProviderError("provider returned empty or unsupported structured content")
        if input_tokens < 0 or output_tokens < 0 or output_tokens > request.max_output_tokens:
            raise TextGenerationProviderError("provider returned invalid token usage")
        cost = input_tokens * self._input_rate + output_tokens * self._output_rate
        return TextGenerationResponse(
            task_id=request.task_id,
            trace_id=request.trace_id,
            provider_id=self._provider_id,
            model_id=model_id,
            model_version=self._model_version,
            output_text=text,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_microunits=cost,
            cost_unit=self._cost_unit,
            pricing_version=self._pricing_version,
        )


class SupabaseTextGenerationMeteringSink:
    """Persist idempotent generation evidence through the canonical Postgres RPC."""

    def __init__(self, *, supabase_url: str, service_role_key: str) -> None:
        if not supabase_url.strip() or not service_role_key.strip():
            raise ValueError("server-side Supabase URL and service-role key are required")
        self._url = supabase_url.rstrip("/") + "/rest/v1/rpc/record_agent_model_usage_metering"
        self._key = service_role_key

    @classmethod
    def from_environment(cls) -> "SupabaseTextGenerationMeteringSink":
        return cls(
            supabase_url=os.getenv("SUPABASE_URL", ""),
            service_role_key=os.getenv("SUPABASE_SERVICE_ROLE_KEY", ""),
        )

    async def write_idempotent(self, evidence: TextGenerationEvidence) -> None:
        if not all((evidence.owner_id, evidence.agent_id, evidence.source_id)):
            raise RuntimeError("durable usage evidence requires trusted owner, Agent and Skill context")
        record: dict[str, Any] = {
            "idempotency_key": evidence.idempotency_key,
            "task_id": evidence.task_id,
            "trace_id": evidence.trace_id,
            "owner_id": evidence.owner_id,
            "agent_id": evidence.agent_id,
            "source_id": evidence.source_id,
            "source_version": evidence.source_version,
            "sensitivity": evidence.sensitivity,
            "provider_id": evidence.provider_id,
            "model_id": evidence.model_id,
            "model_version": evidence.model_version,
            "usage_units": evidence.input_tokens + evidence.output_tokens,
            "usage_unit": "tokens_total",
            "cost_microunits": evidence.cost_microunits,
            "cost_unit": evidence.cost_unit,
            "pricing_version": evidence.pricing_version,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "payload_fingerprint": evidence.evidence_sha256,
        }
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(10.0, connect=3.0)) as client:
                response = await client.post(
                    self._url,
                    headers={
                        "apikey": self._key,
                        "Authorization": f"Bearer {self._key}",
                        "Content-Type": "application/json",
                        "Accept": "application/json",
                    },
                    json={"p_record": record},
                )
                response.raise_for_status()
                result = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise RuntimeError("usage metering could not be durably confirmed; automatic provider replay is blocked") from exc
        if result is not True:
            raise RuntimeError("usage metering RPC did not confirm idempotent persistence")


def build_text_generation_router_from_environment() -> CanonicalTextGenerationRouter | None:
    """Return a live router only when explicit provider, policy, pricing and DB config exist."""
    required = (
        "ALLPHA_TEXTGEN_BASE_URL",
        "ALLPHA_TEXTGEN_API_KEY",
        "ALLPHA_TEXTGEN_PROVIDER_ID",
        "ALLPHA_TEXTGEN_MODEL_ID",
        "ALLPHA_TEXTGEN_MODEL_VERSION",
        "ALLPHA_TEXTGEN_POLICY_ID",
        "ALLPHA_TEXTGEN_POLICY_VERSION",
        "ALLPHA_TEXTGEN_PRICING_VERSION",
        "ALLPHA_TEXTGEN_COST_UNIT",
        "ALLPHA_TEXTGEN_INPUT_MICRO_COST_PER_TOKEN",
        "ALLPHA_TEXTGEN_OUTPUT_MICRO_COST_PER_TOKEN",
        "ALLPHA_TEXTGEN_MAX_COST_MICROUNITS",
        "ALLPHA_TEXTGEN_POLICY_APPROVED",
        "SUPABASE_URL",
        "SUPABASE_SERVICE_ROLE_KEY",
    )
    if any(not os.getenv(name, "").strip() for name in required):
        return None
    if os.getenv("ALLPHA_TEXTGEN_POLICY_APPROVED", "").strip().lower() != "true":
        return None
    try:
        provider_id = os.environ["ALLPHA_TEXTGEN_PROVIDER_ID"].strip()
        model_id = os.environ["ALLPHA_TEXTGEN_MODEL_ID"].strip()
        model_version = os.environ["ALLPHA_TEXTGEN_MODEL_VERSION"].strip()
        pricing_version = os.environ["ALLPHA_TEXTGEN_PRICING_VERSION"].strip()
        cost_unit = os.environ["ALLPHA_TEXTGEN_COST_UNIT"].strip()
        input_rate = int(os.environ["ALLPHA_TEXTGEN_INPUT_MICRO_COST_PER_TOKEN"])
        output_rate = int(os.environ["ALLPHA_TEXTGEN_OUTPUT_MICRO_COST_PER_TOKEN"])
        max_cost = int(os.environ["ALLPHA_TEXTGEN_MAX_COST_MICROUNITS"])
        max_prompt_bytes = int(os.getenv("ALLPHA_TEXTGEN_MAX_PROMPT_BYTES", "16384"))
        max_output_tokens = int(os.getenv("ALLPHA_TEXTGEN_MAX_OUTPUT_TOKENS", "1024"))
        max_latency_ms = int(os.getenv("ALLPHA_TEXTGEN_MAX_LATENCY_MS", "30000"))
        if min(input_rate, output_rate, max_cost) < 0:
            return None
        adapter = OpenAICompatibleTextGenerationAdapter(
            base_url=os.environ["ALLPHA_TEXTGEN_BASE_URL"].strip(),
            api_key=os.environ["ALLPHA_TEXTGEN_API_KEY"],
            provider_id=provider_id,
            model_version=model_version,
            pricing_version=pricing_version,
            cost_unit=cost_unit,
            input_cost_microunits_per_token=input_rate,
            output_cost_microunits_per_token=output_rate,
        )
        policy = TextGenerationPolicy(
            policy_id=os.environ["ALLPHA_TEXTGEN_POLICY_ID"].strip(),
            policy_version=os.environ["ALLPHA_TEXTGEN_POLICY_VERSION"].strip(),
            approved=True,
            max_prompt_bytes=max_prompt_bytes,
            max_output_tokens=max_output_tokens,
            max_cost_microunits=max_cost,
            max_latency_ms=max_latency_ms,
            cost_unit=cost_unit,
            pricing_version=pricing_version,
        )
        router = CanonicalTextGenerationRouter(
            routes={"private": TextGenerationRoute(provider_id, model_id, model_version, max_attempts=1)},
            adapters={provider_id: adapter},
            policies={"private": policy},
            metering_sink=SupabaseTextGenerationMeteringSink.from_environment(),
        )
        router.require_runtime_ready("private")
        return router
    except (KeyError, TypeError, ValueError, RuntimeError):
        return None

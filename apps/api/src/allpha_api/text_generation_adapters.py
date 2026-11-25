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

from allpha_api.text_generation_credits import SupabaseTextGenerationCreditLedger
from allpha_api.model_router import (
    CanonicalTextGenerationRouter,
    TextGenerationEvidence,
    TextGenerationPolicy,
    TextGenerationRequest,
    TextGenerationResponse,
    TextGenerationRoute,
    TextGenerationRouterUnavailable,
    TextGenerationProviderTransient,
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
        transport: httpx.AsyncBaseTransport | None = None,
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
        self._transport = transport

    async def generate(self, request: TextGenerationRequest, *, model_id: str) -> TextGenerationResponse:
        headers = {
            "Authorization": f"Bearer {self._key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        messages = []
        if request.system_prompt.strip():
            messages.append({"role": "system", "content": request.system_prompt})
        if request.conversation_messages:
            # The canonical request validates role and message shape. Copy the
            # immutable conversation in order so assistant tool calls and their
            # matching tool results survive the next Model Router turn.
            messages.extend(json.loads(json.dumps(
                list(request.conversation_messages), ensure_ascii=False, allow_nan=False,
            )))
        if request.prompt.strip():
            messages.append({"role": "user", "content": request.prompt})
        body = {
            "model": model_id,
            "messages": messages,
            "max_tokens": request.max_output_tokens,
            "stream": False,
            **({"response_format": {"type": request.response_format}} if request.response_format else {}),
            **({"tools": list(request.tool_definitions), "tool_choice": "auto"} if request.tool_definitions else {}),
        }
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(request.timeout_ms / 1000, connect=min(5.0, request.timeout_ms / 1000)),
                transport=self._transport, follow_redirects=False, trust_env=False,
            ) as client:
                response = await client.post(self._url, headers=headers, json=body)
                response.raise_for_status()
                payload = response.json()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 429:
                retry_after_ms = None
                raw_retry_after = exc.response.headers.get("retry-after", "").strip()
                if raw_retry_after:
                    try:
                        retry_after_ms = max(0, min(int(float(raw_retry_after) * 1000), 30_000))
                    except (TypeError, ValueError, OverflowError):
                        retry_after_ms = None
                raise TextGenerationProviderTransient(
                    "provider explicitly rate-limited the request before generation",
                    safe_to_retry=True,
                    retry_after_ms=retry_after_ms,
                ) from exc
            # Other HTTP responses may follow partial provider execution.
            raise TextGenerationProviderError("provider HTTP failure; outcome may be unknown") from exc
        except (httpx.ConnectError, httpx.ConnectTimeout, httpx.PoolTimeout) as exc:
            # No request body reached the provider: connection establishment or
            # pool acquisition failed before dispatch, so an approved fallback is safe.
            raise TextGenerationProviderTransient(
                "provider connection failed before request dispatch",
                safe_to_retry=True,
            ) from exc
        except (httpx.HTTPError, ValueError) as exc:
            # Read/write/protocol failures can happen after dispatch; never replay them.
            raise TextGenerationProviderError("provider call failed or returned invalid JSON; outcome may be unknown") from exc

        try:
            choices = payload["choices"]
            message = choices[0]["message"]
            text = message.get("content") or ""
            raw_tool_calls = message.get("tool_calls") or []
            usage = payload["usage"]
            input_tokens = int(usage["prompt_tokens"])
            output_tokens = int(usage["completion_tokens"])
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise TextGenerationProviderError("provider response is missing content or usage accounting") from exc
        if not isinstance(text, str) or (not text.strip() and not raw_tool_calls):
            raise TextGenerationProviderError("provider returned neither text nor tool calls")
        if not isinstance(raw_tool_calls, list) or len(raw_tool_calls) > request.max_tool_calls:
            raise TextGenerationProviderError("provider returned an invalid or excessive tool-call list")
        from allpha_api.model_router import TextGenerationToolCall
        allowed_names = {item["function"]["name"] for item in request.tool_definitions}
        parsed_calls = []
        seen_ids: set[str] = set()
        for raw_call in raw_tool_calls:
            try:
                call_id = raw_call["id"]
                function = raw_call["function"]
                name = function["name"]
                raw_arguments = function["arguments"]
                arguments = json.loads(raw_arguments) if isinstance(raw_arguments, str) else raw_arguments
            except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
                raise TextGenerationProviderError("provider returned a malformed tool call") from exc
            if (not isinstance(call_id, str) or not call_id or call_id in seen_ids
                    or not isinstance(name, str) or name not in allowed_names
                    or not isinstance(arguments, dict)):
                raise TextGenerationProviderError("provider tool call is outside the authorized request contract")
            seen_ids.add(call_id)
            parsed_calls.append(TextGenerationToolCall(call_id=call_id, name=name, arguments=arguments))
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
            tool_calls=tuple(parsed_calls),
        )


class SupabaseTextGenerationMeteringSink:
    """Persist idempotent generation evidence through the canonical Postgres RPC."""

    def __init__(self, *, supabase_url: str, service_role_key: str, transport: httpx.AsyncBaseTransport | None = None) -> None:
        if not supabase_url.strip() or not service_role_key.strip():
            raise ValueError("server-side Supabase URL and service-role key are required")
        self._url = supabase_url.rstrip("/") + "/rest/v1/rpc/record_agent_model_usage_metering"
        self._key = service_role_key
        self._transport = transport

    @classmethod
    def from_environment(cls) -> "SupabaseTextGenerationMeteringSink":
        return cls(
            supabase_url=os.getenv("SUPABASE_URL", ""),
            service_role_key=(os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip() or os.getenv("SUPABASE_SECRET_KEY", "").strip()),
        )

    async def write_idempotent(self, evidence: TextGenerationEvidence) -> None:
        if not all((evidence.owner_id, evidence.agent_id, evidence.source_id)):
            raise RuntimeError("durable usage evidence requires trusted owner, Agent and Skill context")
        record: dict[str, Any] = {
            "idempotency_key": evidence.idempotency_key,
            "task_id": evidence.task_id,
            "trace_id": evidence.trace_id,
            "owner_id": evidence.owner_id,
            "billing_account_id": evidence.billing_account_id or evidence.owner_id,
            "agent_id": evidence.agent_id,
            "source_id": evidence.source_id,
            "source_version": evidence.source_version,
            "sensitivity": evidence.sensitivity,
            "provider_id": evidence.provider_id,
            "model_id": evidence.model_id,
            "model_version": evidence.model_version,
            "usage_units": evidence.usage_units,
            "usage_unit": evidence.usage_unit,
            "input_tokens": evidence.input_tokens,
            "output_tokens": evidence.output_tokens,
            "cost_microunits": evidence.cost_microunits,
            "cost_unit": evidence.cost_unit,
            "pricing_version": evidence.pricing_version,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "payload_fingerprint": evidence.evidence_sha256,
        }
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(10.0, connect=3.0), transport=self._transport,
                follow_redirects=False, trust_env=False,
            ) as client:
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


class SupabaseApprovedRuntimePolicyVerifier:
    """Verify one effective, explicitly approved model execution policy in Supabase.

    The tariff row is the canonical policy identity. An active price alone never
    grants permission to execute a provider route.
    """

    def __init__(
        self, *, supabase_url: str, service_role_key: str,
        policy_id: str, policy_version: str,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        required = (supabase_url, service_role_key, policy_id, policy_version)
        if not all(isinstance(value, str) and value.strip() for value in required):
            raise ValueError("approved runtime policy verifier configuration is incomplete")
        self._url = supabase_url.rstrip("/") + "/rest/v1/ai_model_cost_configs"
        self._key = service_role_key
        self._policy_id = policy_id
        self._policy_version = policy_version
        self._transport = transport

    async def verify(self) -> None:
        now = datetime.now(timezone.utc)
        params = {
            "select": "id,policy_version,status,policy_approved,effective_at,policy_approval_reference,policy_approved_by,policy_approved_at",
            "id": "eq." + self._policy_id,
            "policy_version": "eq." + self._policy_version,
            "status": "eq.active",
            "policy_approved": "eq.true",
            "effective_at": "lte." + now.isoformat(),
            "limit": "2",
        }
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(5.0, connect=2.0), transport=self._transport,
                follow_redirects=False, trust_env=False,
            ) as client:
                response = await client.get(
                    self._url, params=params,
                    headers={
                        "apikey": self._key,
                        "Authorization": "Bearer " + self._key,
                        "Accept": "application/json",
                    },
                )
                response.raise_for_status()
                rows = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise RuntimeError("approved model runtime policy registry is unavailable") from exc
        if not isinstance(rows, list) or len(rows) != 1:
            raise RuntimeError("exactly one matching approved runtime policy and exactly one effective active tariff are required")
        row = rows[0]
        if (not isinstance(row, dict)
                or row.get("id") != self._policy_id
                or row.get("policy_version") != self._policy_version
                or row.get("status") != "active"
                or row.get("policy_approved") is not True):
            raise RuntimeError("matching runtime policy is not explicitly approved and active")
        reference = row.get("policy_approval_reference")
        actor = row.get("policy_approved_by")
        approved_at = row.get("policy_approved_at")
        if (not isinstance(reference, str) or not 8 <= len(reference.strip()) <= 200
                or not isinstance(actor, str) or not actor.strip()
                or not isinstance(approved_at, str) or not approved_at.strip()):
            raise RuntimeError("runtime policy approval evidence is incomplete")
        try:
            approved_time = datetime.fromisoformat(approved_at.replace("Z", "+00:00"))
        except ValueError as exc:
            raise RuntimeError("runtime policy approval timestamp is invalid") from exc
        if approved_time.tzinfo is None or approved_time > now:
            raise RuntimeError("runtime policy approval timestamp is invalid")


class SupabaseActiveModelCostVerifier(SupabaseApprovedRuntimePolicyVerifier):
    """Require the active operator-managed tariff to match the approved deployment route.

    The exact database tariff row is also the canonical model execution policy.
    Pricing activation alone is insufficient: a high-risk operator approval with
    durable actor, timestamp and reference evidence is required.
    """

    def __init__(
        self, *, supabase_url: str, service_role_key: str, provider_id: str,
        model_id: str, model_version: str, pricing_version: str, cost_unit: str,
        input_cost_microunits_per_token: int, output_cost_microunits_per_token: int,
        max_cost_microunits: int, policy_id: str, policy_version: str,
        max_prompt_bytes: int, max_output_tokens: int, max_latency_ms: int,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        super().__init__(
            supabase_url=supabase_url, service_role_key=service_role_key,
            policy_id=policy_id, policy_version=policy_version, transport=transport,
        )
        required = (provider_id, model_id, model_version, pricing_version, cost_unit)
        if not all(value.strip() for value in required):
            raise ValueError("active model-cost verifier configuration is incomplete")
        self._expected = {
            "id": policy_id,
            "capability": "text_generation",
            "policy_version": policy_version,
            "provider_id": provider_id,
            "model_id": model_id,
            "model_version": model_version,
            "pricing_version": pricing_version,
            "cost_unit": cost_unit,
            "input_micro_cost_per_token": input_cost_microunits_per_token,
            "output_micro_cost_per_token": output_cost_microunits_per_token,
            "max_cost_microunits": max_cost_microunits,
            "max_prompt_bytes": max_prompt_bytes,
            "max_output_tokens": max_output_tokens,
            "max_latency_ms": max_latency_ms,
            "policy_approved": True,
        }
        self._transport = transport

    async def verify(self) -> None:
        await super().verify()
        now = datetime.now(timezone.utc).isoformat()
        params = {
            "select": ",".join((*self._expected.keys(), "status", "effective_at", "policy_approval_reference", "policy_approved_by", "policy_approved_at")),
            "id": "eq." + str(self._expected["id"]),
            "policy_version": "eq." + str(self._expected["policy_version"]),
            "capability": "eq.text_generation",
            "provider_id": "eq." + str(self._expected["provider_id"]),
            "model_id": "eq." + str(self._expected["model_id"]),
            "model_version": "eq." + str(self._expected["model_version"]),
            "pricing_version": "eq." + str(self._expected["pricing_version"]),
            "status": "eq.active",
            "effective_at": "lte." + now,
            "limit": "2",
        }
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(5.0, connect=2.0), transport=self._transport,
                follow_redirects=False, trust_env=False,
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
            raise RuntimeError("active model-cost registry is unavailable") from exc
        if not isinstance(rows, list) or len(rows) != 1:
            raise RuntimeError("exactly one effective active tariff is required")
        row = rows[0]
        if not isinstance(row, dict) or row.get("status") != "active":
            raise RuntimeError("active tariff state is invalid")
        if (not isinstance(row.get("policy_approval_reference"), str)
                or not row["policy_approval_reference"].strip()
                or not isinstance(row.get("policy_approved_by"), str)
                or not row["policy_approved_by"].strip()
                or not isinstance(row.get("policy_approved_at"), str)
                or not row["policy_approved_at"].strip()):
            raise RuntimeError("model execution policy approval evidence is incomplete")
        for field, expected in self._expected.items():
            actual = row.get(field)
            if isinstance(expected, bool):
                if actual is not expected:
                    raise RuntimeError("active tariff is not explicitly approved in the canonical registry")
            elif isinstance(expected, int):
                if isinstance(actual, bool) or not isinstance(actual, int) or actual != expected:
                    raise RuntimeError("active tariff does not match the approved deployment configuration")
            elif actual != expected:
                raise RuntimeError("active tariff does not match the approved deployment configuration")



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
        "SUPABASE_URL",
        "ALLPHA_TEXTGEN_CREDIT_POLICY_VERSION",
        "ALLPHA_TEXTGEN_CREDIT_SCHEME_VERSION",
        "ALLPHA_TEXTGEN_CREDIT_POLICY_APPROVAL_REFERENCE",
        "ALLPHA_TEXTGEN_CREDIT_CAPABILITY_ID",
        "ALLPHA_TEXTGEN_CREDIT_TARIFF_VERSION",
        "ALLPHA_TEXTGEN_CREDIT_ENTITLEMENT_VERSION",
    )
    service_role_key = (
        os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
        or os.getenv("SUPABASE_SECRET_KEY", "").strip()
    )
    if any(not os.getenv(name, "").strip() for name in required) or not service_role_key:
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
        tariff_verifiers = {}
        tariff_verifiers[(provider_id, model_id, model_version)] = SupabaseActiveModelCostVerifier(
            supabase_url=os.environ["SUPABASE_URL"],
            service_role_key=service_role_key,
            provider_id=provider_id,
            model_id=model_id,
            model_version=model_version,
            pricing_version=pricing_version,
            cost_unit=cost_unit,
            input_cost_microunits_per_token=input_rate,
            output_cost_microunits_per_token=output_rate,
            max_cost_microunits=max_cost,
            policy_id=os.environ["ALLPHA_TEXTGEN_POLICY_ID"].strip(),
            policy_version=os.environ["ALLPHA_TEXTGEN_POLICY_VERSION"].strip(),
            max_prompt_bytes=max_prompt_bytes,
            max_output_tokens=max_output_tokens,
            max_latency_ms=max_latency_ms,
        )
        adapters = {provider_id: adapter}
        fallback_routes = []
        seen_providers = {provider_id}
        for slot in range(1, 4):
            prefix = f"ALLPHA_TEXTGEN_FALLBACK_{slot}_"
            base_url = os.getenv(prefix + "BASE_URL", "").strip()
            api_key = os.getenv(prefix + "API_KEY", "")
            fallback_provider_id = os.getenv(prefix + "PROVIDER_ID", "").strip()
            configured = bool(base_url or api_key or fallback_provider_id)
            if not configured:
                continue
            if not all((base_url, api_key.strip(), fallback_provider_id)):
                return None
            if fallback_provider_id in seen_providers:
                return None
            fallback_adapter = OpenAICompatibleTextGenerationAdapter(
                base_url=base_url,
                api_key=api_key,
                provider_id=fallback_provider_id,
                model_version=model_version,
                pricing_version=pricing_version,
                cost_unit=cost_unit,
                input_cost_microunits_per_token=input_rate,
                output_cost_microunits_per_token=output_rate,
            )
            adapters[fallback_provider_id] = fallback_adapter
            fallback_routes.append(TextGenerationRoute(
                fallback_provider_id, model_id, model_version, max_attempts=1,
            ))
            tariff_verifiers[(fallback_provider_id, model_id, model_version)] = SupabaseActiveModelCostVerifier(
                supabase_url=os.environ["SUPABASE_URL"],
                service_role_key=service_role_key,
                provider_id=fallback_provider_id,
                model_id=model_id,
                model_version=model_version,
                pricing_version=pricing_version,
                cost_unit=cost_unit,
                input_cost_microunits_per_token=input_rate,
                output_cost_microunits_per_token=output_rate,
                max_cost_microunits=max_cost,
                policy_id=os.environ["ALLPHA_TEXTGEN_POLICY_ID"].strip(),
                policy_version=os.environ["ALLPHA_TEXTGEN_POLICY_VERSION"].strip(),
                max_prompt_bytes=max_prompt_bytes,
                max_output_tokens=max_output_tokens,
                max_latency_ms=max_latency_ms,
            )
            seen_providers.add(fallback_provider_id)

        async def verify_active_tariff(sensitivity, selected_route, selected_policy):
            if sensitivity != "private":
                raise RuntimeError("no active tariff verifier is configured for this sensitivity")
            identity = (selected_route.provider_id, selected_route.model_id, selected_route.model_version)
            verifier = tariff_verifiers.get(identity)
            if verifier is None:
                raise TextGenerationRouterUnavailable("no active tariff verifier is configured for selected route", category="active_tariff")
            if (selected_policy.cost_unit, selected_policy.pricing_version, selected_policy.max_cost_microunits) != (cost_unit, pricing_version, max_cost):
                raise RuntimeError("selected model policy differs from the verified tariff")
            try:
                await verifier.verify()
            except Exception as exc:
                raise TextGenerationRouterUnavailable(
                    "active model tariff verification failed",
                    category="active_tariff",
                ) from exc

        router = CanonicalTextGenerationRouter(
            routes={"private": TextGenerationRoute(provider_id, model_id, model_version, max_attempts=1)},
            fallback_routes={"private": tuple(fallback_routes)},
            adapters=adapters,
            policies={"private": policy},
            metering_sink=SupabaseTextGenerationMeteringSink.from_environment(),
            runtime_preflight=verify_active_tariff,
            credit_ledger=SupabaseTextGenerationCreditLedger.from_environment(),
        )
        router.require_runtime_ready("private")
        return router
    except (KeyError, TypeError, ValueError, RuntimeError):
        return None

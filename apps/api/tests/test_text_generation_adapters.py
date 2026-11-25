from __future__ import annotations

import pytest

import asyncio
import httpx
from dataclasses import replace

from allpha_api.model_router import (
    CanonicalTextGenerationRouter,
    TextGenerationPolicy,
    TextGenerationRequest,
    TextGenerationRoute,
    TextGenerationProviderTransient,
)
from allpha_api.text_generation_adapters import (
    OpenAICompatibleTextGenerationAdapter,
    SupabaseTextGenerationMeteringSink,
    SupabaseActiveModelCostVerifier,
    build_text_generation_router_from_environment,
)


def request() -> TextGenerationRequest:
    return TextGenerationRequest(
        task_id="challenge-1",
        trace_id="trace-1",
        idempotency_key="challenge-key-1",
        sensitivity="private",
        prompt='Return {"ok":true}',
        max_output_tokens=16,
        timeout_ms=1000,
        owner_id="owner-1",
        agent_id="agent-1",
        source_id="skill-1",
        source_version=3,
    )


def test_openai_compatible_adapter_reports_usage_and_configured_cost():
    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/v1/chat/completions"
        assert req.headers["Authorization"] == "Bearer test-secret"
        body = __import__("json").loads(req.content)
        assert body["model"] == "model-test"
        return httpx.Response(200, json={
            "choices": [{"message": {"content": '{"ok":true}'}}],
            "usage": {"prompt_tokens": 2, "completion_tokens": 4},
        })

    adapter = OpenAICompatibleTextGenerationAdapter(
        base_url="https://provider.invalid/v1",
        api_key="test-secret",
        provider_id="provider-test",
        model_version="model-version-1",
        pricing_version="price-v1",
        cost_unit="USD",
        input_cost_microunits_per_token=3,
        output_cost_microunits_per_token=5,
        transport=httpx.MockTransport(handler),
    )
    result = asyncio.run(adapter.generate(request(), model_id="model-test"))
    assert result.output_text == '{"ok":true}'
    assert result.input_tokens == 2
    assert result.output_tokens == 4
    assert result.cost_microunits == 26
    assert result.provider_id == "provider-test"


def test_openai_compatible_adapter_classifies_http_429_as_safe_pre_execution_failure():
    adapter = OpenAICompatibleTextGenerationAdapter(
        base_url="https://provider.invalid/v1", api_key="test-secret",
        provider_id="provider-test", model_version="model-version-1",
        pricing_version="price-v1", cost_unit="USD",
        input_cost_microunits_per_token=3, output_cost_microunits_per_token=5,
        transport=httpx.MockTransport(lambda req: httpx.Response(429, headers={"Retry-After": "2"})),
    )

    async def run():
        with pytest.raises(TextGenerationProviderTransient) as caught:
            await adapter.generate(request(), model_id="model-test")
        assert caught.value.safe_to_retry is True
        assert caught.value.retry_after_ms == 2000

    asyncio.run(run())


def test_openai_compatible_adapter_classifies_connect_failure_as_safe():
    def handler(req: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=req)

    adapter = OpenAICompatibleTextGenerationAdapter(
        base_url="https://provider.invalid/v1", api_key="test-secret",
        provider_id="provider-test", model_version="model-version-1",
        pricing_version="price-v1", cost_unit="USD",
        input_cost_microunits_per_token=3, output_cost_microunits_per_token=5,
        transport=httpx.MockTransport(handler),
    )

    async def run():
        with pytest.raises(TextGenerationProviderTransient) as caught:
            await adapter.generate(request(), model_id="model-test")
        assert caught.value.safe_to_retry is True

    asyncio.run(run())


def test_supabase_metering_sink_persists_owner_and_skill_context():
    received = {}

    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/rest/v1/rpc/record_agent_model_usage_metering"
        assert req.headers["Authorization"] == "Bearer service-test"
        received.update(__import__("json").loads(req.content)["p_record"])
        return httpx.Response(200, json=True)

    async def run():
        adapter = OpenAICompatibleTextGenerationAdapter(
            base_url="https://provider.invalid/v1", api_key="test-secret",
            provider_id="provider-test", model_version="model-version-1",
            pricing_version="price-v1", cost_unit="USD",
            input_cost_microunits_per_token=3, output_cost_microunits_per_token=5,
            transport=httpx.MockTransport(lambda req: httpx.Response(200, json={
                "choices": [{"message": {"content": '{"ok":true}'}}],
                "usage": {"prompt_tokens": 2, "completion_tokens": 4},
            })),
        )
        sink = SupabaseTextGenerationMeteringSink(
            supabase_url="https://db.invalid", service_role_key="service-test",
            transport=httpx.MockTransport(handler),
        )
        router = CanonicalTextGenerationRouter(
            routes={"private": TextGenerationRoute("provider-test", "model-test", "model-version-1")},
            adapters={"provider-test": adapter},
            policies={"private": TextGenerationPolicy(
                policy_id="policy-test", policy_version="policy-v1", approved=True,
                max_prompt_bytes=1024, max_output_tokens=16, max_cost_microunits=100,
                max_latency_ms=5000, cost_unit="USD", pricing_version="price-v1",
            )},
            metering_sink=sink,
        )
        _, evidence = await router.generate(request())
        assert evidence.owner_id == "owner-1"
        assert evidence.agent_id == "agent-1"
        assert evidence.source_id == "skill-1"
        assert evidence.source_version == 3
        assert received["owner_id"] == "owner-1"
        assert received["agent_id"] == "agent-1"
        assert received["source_id"] == "skill-1"
        assert received["source_version"] == 3
        assert received["usage_units"] == 6
        assert received["payload_fingerprint"] == evidence.evidence_sha256

    asyncio.run(run())


def test_router_factory_fails_closed_without_deployment_configuration(monkeypatch):
    for key in (
        "ALLPHA_TEXTGEN_BASE_URL", "ALLPHA_TEXTGEN_API_KEY",
        "ALLPHA_TEXTGEN_PROVIDER_ID", "ALLPHA_TEXTGEN_MODEL_ID",
        "ALLPHA_TEXTGEN_MODEL_VERSION", "ALLPHA_TEXTGEN_POLICY_ID",
        "ALLPHA_TEXTGEN_POLICY_VERSION", "ALLPHA_TEXTGEN_PRICING_VERSION",
        "ALLPHA_TEXTGEN_COST_UNIT", "ALLPHA_TEXTGEN_INPUT_MICRO_COST_PER_TOKEN",
        "ALLPHA_TEXTGEN_OUTPUT_MICRO_COST_PER_TOKEN", "ALLPHA_TEXTGEN_MAX_COST_MICROUNITS",
        "SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY",
    ):
        monkeypatch.delenv(key, raising=False)
    assert build_text_generation_router_from_environment() is None


def test_active_model_cost_verifier_accepts_only_matching_effective_active_tariff():
    seen = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["path"] = req.url.path
        seen["auth"] = req.headers.get("Authorization")
        seen["params"] = dict(req.url.params)
        return httpx.Response(200, json=[{
            "id": "policy-config-1",
            "capability": "text_generation",
            "policy_version": "v1",
            "provider_id": "provider-test",
            "model_id": "model-test",
            "model_version": "model-version-1",
            "pricing_version": "price-v1",
            "cost_unit": "USD",
            "input_micro_cost_per_token": 3,
            "output_micro_cost_per_token": 5,
            "max_cost_microunits": 100,
            "max_prompt_bytes": 16384,
            "max_output_tokens": 1024,
            "max_latency_ms": 30000,
            "policy_approved": True,
            "policy_approval_reference": "MODEL-POLICY-APPROVAL-01",
            "policy_approved_by": "11111111-1111-4111-8111-111111111111",
            "policy_approved_at": "2026-10-16T00:00:00+00:00",
            "status": "active",
            "effective_at": "2026-10-16T00:00:00+00:00",
        }])

    verifier = SupabaseActiveModelCostVerifier(
        supabase_url="https://db.invalid", service_role_key="service-test",
        provider_id="provider-test", model_id="model-test",
        model_version="model-version-1", pricing_version="price-v1",
        cost_unit="USD", input_cost_microunits_per_token=3,
        output_cost_microunits_per_token=5, max_cost_microunits=100,
        policy_id="policy-config-1",policy_version="v1",
        max_prompt_bytes=16384,max_output_tokens=1024,max_latency_ms=30000,
        transport=httpx.MockTransport(handler),
    )
    asyncio.run(verifier.verify())
    assert seen["path"] == "/rest/v1/ai_model_cost_configs"
    assert seen["auth"] == "Bearer service-test"
    assert seen["params"]["status"] == "eq.active"
    assert seen["params"]["capability"] == "eq.text_generation"
    assert seen["params"]["limit"] == "2"


def test_active_model_cost_verifier_fails_closed_without_an_active_tariff():
    verifier = SupabaseActiveModelCostVerifier(
        supabase_url="https://db.invalid", service_role_key="service-test",
        provider_id="provider-test", model_id="model-test",
        model_version="model-version-1", pricing_version="price-v1",
        cost_unit="USD", input_cost_microunits_per_token=3,
        output_cost_microunits_per_token=5, max_cost_microunits=100,
        policy_id="policy-config-1",policy_version="v1",
        max_prompt_bytes=16384,max_output_tokens=1024,max_latency_ms=30000,
        transport=httpx.MockTransport(lambda req: httpx.Response(200, json=[])),
    )
    try:
        asyncio.run(verifier.verify())
    except RuntimeError as exc:
        assert "exactly one effective active tariff" in str(exc)
    else:
        raise AssertionError("missing active tariff must block runtime")


def test_active_model_cost_verifier_requires_auditable_policy_approval_evidence():
    verifier = SupabaseActiveModelCostVerifier(
        supabase_url="https://db.invalid", service_role_key="service-test",
        provider_id="provider-test", model_id="model-test",
        model_version="model-version-1", pricing_version="price-v1",
        cost_unit="USD", input_cost_microunits_per_token=3,
        output_cost_microunits_per_token=5, max_cost_microunits=100,
        policy_id="policy-config-1",policy_version="v1",
        max_prompt_bytes=16384,max_output_tokens=1024,max_latency_ms=30000,
        transport=httpx.MockTransport(lambda req: httpx.Response(200,json=[{
            "id":"policy-config-1","capability":"text_generation","policy_version":"v1","provider_id":"provider-test",
            "model_id":"model-test","model_version":"model-version-1","pricing_version":"price-v1",
            "cost_unit":"USD","input_micro_cost_per_token":3,"output_micro_cost_per_token":5,
            "max_cost_microunits":100,"max_prompt_bytes":16384,"max_output_tokens":1024,
            "max_latency_ms":30000,"policy_approved":True,"policy_approval_reference":"",
            "policy_approved_by":None,"policy_approved_at":None,"status":"active",
            "effective_at":"2026-10-16T00:00:00+00:00"
        }])),
    )
    try:
        asyncio.run(verifier.verify())
    except RuntimeError as exc:
        assert "approval evidence is incomplete" in str(exc)
    else:
        raise AssertionError("missing model policy approval evidence must block runtime")

def test_approved_runtime_policy_verifier_fails_closed_when_policy_not_approved():
    from allpha_api.text_generation_adapters import SupabaseApprovedRuntimePolicyVerifier

    verifier = SupabaseApprovedRuntimePolicyVerifier(
        supabase_url="https://db.invalid",
        service_role_key="service-test",
        policy_id="policy-1",
        policy_version="v1",
        transport=httpx.MockTransport(lambda req: httpx.Response(200, json=[])),
    )
    with pytest.raises(RuntimeError, match="exactly one matching approved runtime policy"):
        asyncio.run(verifier.verify())


def test_openai_compatible_adapter_requests_json_object_mode():
    observed = {}

    def handler(req: httpx.Request) -> httpx.Response:
        observed.update(__import__("json").loads(req.content))
        return httpx.Response(200, json={
            "choices": [{"message": {"content": '{"steps":[]}'}}],
            "usage": {"prompt_tokens": 2, "completion_tokens": 3},
        })

    adapter = OpenAICompatibleTextGenerationAdapter(
        base_url="https://provider.invalid/v1", api_key="test-secret",
        provider_id="provider-test", model_version="model-version-1",
        pricing_version="price-v1", cost_unit="USD",
        input_cost_microunits_per_token=1, output_cost_microunits_per_token=1,
        transport=httpx.MockTransport(handler),
    )
    asyncio.run(adapter.generate(replace(request(), response_format="json_object"), model_id="model-test"))
    assert observed["response_format"] == {"type": "json_object"}


def test_openai_compatible_adapter_submits_and_parses_authorized_tool_calls():
    from allpha_api.model_router import TextGenerationToolCall
    observed = {}

    def handler(req: httpx.Request) -> httpx.Response:
        observed.update(__import__("json").loads(req.content))
        return httpx.Response(200, json={
            "choices": [{"message": {"content": None, "tool_calls": [{
                "id": "call-1", "type": "function",
                "function": {"name": "text.normalize", "arguments": '{"text":"hello"}'},
            }]}}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 3},
        })

    tools = ({"type": "function", "function": {
        "name": "text.normalize", "description": "Normalize text",
        "parameters": {"type": "object", "properties": {"text": {"type": "string"}},
                      "required": ["text"], "additionalProperties": False},
    }},)
    adapter = OpenAICompatibleTextGenerationAdapter(
        base_url="https://provider.invalid/v1", api_key="test-secret",
        provider_id="provider-test", model_version="model-version-1",
        pricing_version="price-v1", cost_unit="USD",
        input_cost_microunits_per_token=1, output_cost_microunits_per_token=1,
        transport=httpx.MockTransport(handler),
    )
    result = asyncio.run(adapter.generate(replace(request(), tool_definitions=tools), model_id="model-test"))
    assert observed["tool_choice"] == "auto"
    assert observed["tools"] == list(tools)
    assert result.output_text == ""
    assert result.tool_calls == (TextGenerationToolCall("call-1", "text.normalize", {"text": "hello"}),)


def test_openai_compatible_adapter_rejects_tool_call_outside_request_allowlist():
    tools = ({"type": "function", "function": {"name": "text.normalize", "parameters": {"type": "object"}}},)
    adapter = OpenAICompatibleTextGenerationAdapter(
        base_url="https://provider.invalid/v1", api_key="test-secret",
        provider_id="provider-test", model_version="model-version-1",
        pricing_version="price-v1", cost_unit="USD",
        input_cost_microunits_per_token=1, output_cost_microunits_per_token=1,
        transport=httpx.MockTransport(lambda req: httpx.Response(200, json={
            "choices": [{"message": {"content": None, "tool_calls": [{
                "id": "call-1", "type": "function",
                "function": {"name": "admin.delete", "arguments": "{}"},
            }]}}], "usage": {"prompt_tokens": 2, "completion_tokens": 2},
        })),
    )
    with pytest.raises(Exception, match="outside the authorized request contract"):
        asyncio.run(adapter.generate(replace(request(), tool_definitions=tools), model_id="model-test"))


def test_openai_compatible_adapter_preserves_assistant_tool_call_and_tool_result_turns():
    observed = {}
    tools = ({"type": "function", "function": {
        "name": "text.normalize", "description": "Normalize text",
        "parameters": {"type": "object", "properties": {"text": {"type": "string"}},
                       "required": ["text"], "additionalProperties": False},
    }},)
    conversation = (
        {"role": "assistant", "content": None, "tool_calls": [{
            "id": "call-1", "type": "function",
            "function": {"name": "text.normalize", "arguments": '{"text":"hello"}'},
        }]},
        {"role": "tool", "tool_call_id": "call-1", "name": "text.normalize",
         "content": '{"normalized":"hello"}'},
    )

    def handler(req: httpx.Request) -> httpx.Response:
        observed.update(__import__("json").loads(req.content))
        return httpx.Response(200, json={
            "choices": [{"message": {"content": "The normalized result is hello."}}],
            "usage": {"prompt_tokens": 7, "completion_tokens": 5},
        })

    adapter = OpenAICompatibleTextGenerationAdapter(
        base_url="https://provider.invalid/v1", api_key="test-secret",
        provider_id="provider-test", model_version="model-version-1",
        pricing_version="price-v1", cost_unit="USD",
        input_cost_microunits_per_token=1, output_cost_microunits_per_token=1,
        transport=httpx.MockTransport(handler),
    )
    result = asyncio.run(adapter.generate(
        replace(request(), prompt="", system_prompt="system", tool_definitions=tools, conversation_messages=conversation),
        model_id="model-test",
    ))
    assert observed["messages"] == [
        {"role": "system", "content": "system"},
        *conversation,
    ]
    assert result.output_text == "The normalized result is hello."
    assert result.tool_calls == ()


def test_text_generation_request_rejects_unmatched_or_unbounded_conversation_messages():
    from allpha_api.model_router import TextGenerationRequest

    with pytest.raises(ValueError, match="tool result messages require a tool_call_id matching a preceding assistant tool_call"):
        replace(request(), prompt="", conversation_messages=({"role": "tool", "content": "orphan"},))
    with pytest.raises(ValueError, match="at most 32 entries"):
        replace(request(), conversation_messages=tuple({"role": "user", "content": "x"} for _ in range(33)))


def test_text_generation_router_uses_database_policy_approval_not_environment_boolean(monkeypatch):
    values={
        "ALLPHA_TEXTGEN_BASE_URL":"https://provider.invalid/v1",
        "ALLPHA_TEXTGEN_API_KEY":"server-only-test-secret",
        "ALLPHA_TEXTGEN_PROVIDER_ID":"provider-test",
        "ALLPHA_TEXTGEN_MODEL_ID":"model-test",
        "ALLPHA_TEXTGEN_MODEL_VERSION":"model-v1",
        "ALLPHA_TEXTGEN_POLICY_ID":"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        "ALLPHA_TEXTGEN_POLICY_VERSION":"policy-v1",
        "ALLPHA_TEXTGEN_PRICING_VERSION":"pricing-v1",
        "ALLPHA_TEXTGEN_COST_UNIT":"USD",
        "ALLPHA_TEXTGEN_INPUT_MICRO_COST_PER_TOKEN":"1",
        "ALLPHA_TEXTGEN_OUTPUT_MICRO_COST_PER_TOKEN":"2",
        "ALLPHA_TEXTGEN_MAX_COST_MICROUNITS":"1000",
        "ALLPHA_TEXTGEN_MAX_PROMPT_BYTES":"16384",
        "ALLPHA_TEXTGEN_MAX_OUTPUT_TOKENS":"1024",
        "ALLPHA_TEXTGEN_MAX_LATENCY_MS":"30000",
        "SUPABASE_URL":"https://db.invalid",
        "SUPABASE_SERVICE_ROLE_KEY":"service-test",
        "ALLPHA_TEXTGEN_POLICY_APPROVED":"false",
    }
    for key,value in values.items():
        monkeypatch.setenv(key,value)
    router=build_text_generation_router_from_environment()
    assert router is not None
    snapshot=router.route_snapshot_for("private")
    assert snapshot["provider_id"]=="provider-test"
    assert snapshot["model_id"]=="model-test"
    assert snapshot["policy_id"]=="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"


def test_approved_runtime_policy_verifier_accepts_only_effective_audited_policy():
    from allpha_api.text_generation_adapters import SupabaseApprovedRuntimePolicyVerifier

    observed = {}
    def handler(req: httpx.Request) -> httpx.Response:
        observed["path"] = req.url.path
        observed["params"] = dict(req.url.params)
        observed["authorization"] = req.headers.get("Authorization")
        return httpx.Response(200, json=[{
            "id": "policy-1",
            "policy_version": "v1",
            "status": "active",
            "policy_approved": True,
            "effective_at": "2026-10-16T00:00:00+00:00",
            "policy_approval_reference": "MODEL-POLICY-APPROVAL-01",
            "policy_approved_by": "11111111-1111-4111-8111-111111111111",
            "policy_approved_at": "2026-10-16T00:00:00+00:00",
        }])

    verifier = SupabaseApprovedRuntimePolicyVerifier(
        supabase_url="https://db.invalid",
        service_role_key="service-test",
        policy_id="policy-1",
        policy_version="v1",
        transport=httpx.MockTransport(handler),
    )
    asyncio.run(verifier.verify())
    assert observed["path"] == "/rest/v1/ai_model_cost_configs"
    assert observed["authorization"] == "Bearer service-test"
    assert observed["params"]["id"] == "eq.policy-1"
    assert observed["params"]["policy_version"] == "eq.v1"
    assert observed["params"]["status"] == "eq.active"
    assert observed["params"]["policy_approved"] == "eq.true"
    assert observed["params"]["limit"] == "2"


def test_approved_runtime_policy_verifier_rejects_unapproved_or_incomplete_policy():
    from allpha_api.text_generation_adapters import SupabaseApprovedRuntimePolicyVerifier

    for row in (
        {
            "id": "policy-1", "policy_version": "v1", "status": "active",
            "policy_approved": False, "policy_approval_reference": "MODEL-POLICY-APPROVAL-01",
            "policy_approved_by": "11111111-1111-4111-8111-111111111111",
            "policy_approved_at": "2026-10-16T00:00:00+00:00",
        },
        {
            "id": "policy-1", "policy_version": "v1", "status": "active",
            "policy_approved": True, "policy_approval_reference": "",
            "policy_approved_by": None, "policy_approved_at": None,
        },
    ):
        verifier = SupabaseApprovedRuntimePolicyVerifier(
            supabase_url="https://db.invalid",
            service_role_key="service-test",
            policy_id="policy-1",
            policy_version="v1",
            transport=httpx.MockTransport(lambda req, item=row: httpx.Response(200, json=[item])),
        )
        with pytest.raises(RuntimeError):
            asyncio.run(verifier.verify())


def test_router_factory_registers_explicit_same_model_provider_fallback(monkeypatch):
    from allpha_api.text_generation_adapters import build_text_generation_router_from_environment
    values = {
        "ALLPHA_TEXTGEN_BASE_URL":"https://provider.invalid/v1",
        "ALLPHA_TEXTGEN_API_KEY":"server-only-test-secret",
        "ALLPHA_TEXTGEN_PROVIDER_ID":"provider-test",
        "ALLPHA_TEXTGEN_MODEL_ID":"model-test",
        "ALLPHA_TEXTGEN_MODEL_VERSION":"model-v1",
        "ALLPHA_TEXTGEN_POLICY_ID":"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        "ALLPHA_TEXTGEN_POLICY_VERSION":"policy-v1",
        "ALLPHA_TEXTGEN_PRICING_VERSION":"pricing-v1",
        "ALLPHA_TEXTGEN_COST_UNIT":"USD",
        "ALLPHA_TEXTGEN_INPUT_MICRO_COST_PER_TOKEN":"1",
        "ALLPHA_TEXTGEN_OUTPUT_MICRO_COST_PER_TOKEN":"2",
        "ALLPHA_TEXTGEN_MAX_COST_MICROUNITS":"1000",
        "ALLPHA_TEXTGEN_MAX_PROMPT_BYTES":"16384",
        "ALLPHA_TEXTGEN_MAX_OUTPUT_TOKENS":"1024",
        "ALLPHA_TEXTGEN_MAX_LATENCY_MS":"30000",
        "SUPABASE_URL":"https://db.invalid",
        "SUPABASE_SERVICE_ROLE_KEY":"service-test",
        "ALLPHA_TEXTGEN_POLICY_APPROVED":"false",
        "ALLPHA_TEXTGEN_FALLBACK_1_BASE_URL":"https://fallback.invalid/v1",
        "ALLPHA_TEXTGEN_FALLBACK_1_API_KEY":"fallback-server-secret",
        "ALLPHA_TEXTGEN_FALLBACK_1_PROVIDER_ID":"provider-fallback",
    }
    for key, value in values.items():
        monkeypatch.setenv(key, value)
    router = build_text_generation_router_from_environment()
    assert router is not None
    snapshot = router.route_snapshot_for("private")
    assert snapshot["fallback_routes"] == [{
        "provider_id": "provider-fallback", "model_id": "model-test", "model_version": "model-v1",
    }]


def test_router_factory_fails_closed_on_partial_fallback_configuration(monkeypatch):
    from allpha_api.text_generation_adapters import build_text_generation_router_from_environment
    values = {
        "ALLPHA_TEXTGEN_BASE_URL":"https://provider.invalid/v1",
        "ALLPHA_TEXTGEN_API_KEY":"server-only-test-secret",
        "ALLPHA_TEXTGEN_PROVIDER_ID":"provider-test",
        "ALLPHA_TEXTGEN_MODEL_ID":"model-test",
        "ALLPHA_TEXTGEN_MODEL_VERSION":"model-v1",
        "ALLPHA_TEXTGEN_POLICY_ID":"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        "ALLPHA_TEXTGEN_POLICY_VERSION":"policy-v1",
        "ALLPHA_TEXTGEN_PRICING_VERSION":"pricing-v1",
        "ALLPHA_TEXTGEN_COST_UNIT":"USD",
        "ALLPHA_TEXTGEN_INPUT_MICRO_COST_PER_TOKEN":"1",
        "ALLPHA_TEXTGEN_OUTPUT_MICRO_COST_PER_TOKEN":"2",
        "ALLPHA_TEXTGEN_MAX_COST_MICROUNITS":"1000",
        "ALLPHA_TEXTGEN_MAX_PROMPT_BYTES":"16384",
        "ALLPHA_TEXTGEN_MAX_OUTPUT_TOKENS":"1024",
        "ALLPHA_TEXTGEN_MAX_LATENCY_MS":"30000",
        "SUPABASE_URL":"https://db.invalid",
        "SUPABASE_SERVICE_ROLE_KEY":"service-test",
        "ALLPHA_TEXTGEN_POLICY_APPROVED":"false",
        "ALLPHA_TEXTGEN_FALLBACK_1_BASE_URL":"https://fallback.invalid/v1",
    }
    for key, value in values.items():
        monkeypatch.setenv(key, value)
    assert build_text_generation_router_from_environment() is None

def test_text_generation_router_factory_accepts_supabase_secret_key_only(monkeypatch):
    values = {
        "ALLPHA_TEXTGEN_BASE_URL": "https://provider.invalid/v1",
        "ALLPHA_TEXTGEN_API_KEY": "provider-secret",
        "ALLPHA_TEXTGEN_PROVIDER_ID": "provider-test",
        "ALLPHA_TEXTGEN_MODEL_ID": "model-test",
        "ALLPHA_TEXTGEN_MODEL_VERSION": "model-v1",
        "ALLPHA_TEXTGEN_POLICY_ID": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        "ALLPHA_TEXTGEN_POLICY_VERSION": "policy-v1",
        "ALLPHA_TEXTGEN_PRICING_VERSION": "pricing-v1",
        "ALLPHA_TEXTGEN_COST_UNIT": "USD",
        "ALLPHA_TEXTGEN_INPUT_MICRO_COST_PER_TOKEN": "1",
        "ALLPHA_TEXTGEN_OUTPUT_MICRO_COST_PER_TOKEN": "2",
        "ALLPHA_TEXTGEN_MAX_COST_MICROUNITS": "1000",
        "SUPABASE_URL": "https://db.invalid",
        "SUPABASE_SECRET_KEY": "canonical-server-secret",
    }
    for key, value in values.items():
        monkeypatch.setenv(key, value)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)

    router = build_text_generation_router_from_environment()
    sink = SupabaseTextGenerationMeteringSink.from_environment()

    assert router is not None
    assert sink._key == "canonical-server-secret"

from __future__ import annotations

import asyncio
import httpx

from allpha_api.model_router import (
    CanonicalTextGenerationRouter,
    TextGenerationPolicy,
    TextGenerationRequest,
    TextGenerationRoute,
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
        "ALLPHA_TEXTGEN_POLICY_APPROVED", "SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY",
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
            "provider_id": "provider-test",
            "model_id": "model-test",
            "model_version": "model-version-1",
            "pricing_version": "price-v1",
            "cost_unit": "USD",
            "input_micro_cost_per_token": 3,
            "output_micro_cost_per_token": 5,
            "max_cost_microunits": 100,
            "status": "active",
            "effective_at": "2026-10-16T00:00:00+00:00",
        }])

    verifier = SupabaseActiveModelCostVerifier(
        supabase_url="https://db.invalid", service_role_key="service-test",
        provider_id="provider-test", model_id="model-test",
        model_version="model-version-1", pricing_version="price-v1",
        cost_unit="USD", input_cost_microunits_per_token=3,
        output_cost_microunits_per_token=5, max_cost_microunits=100,
        transport=httpx.MockTransport(handler),
    )
    asyncio.run(verifier.verify())
    assert seen["path"] == "/rest/v1/ai_model_cost_configs"
    assert seen["auth"] == "Bearer service-test"
    assert seen["params"]["status"] == "eq.active"
    assert seen["params"]["limit"] == "2"


def test_active_model_cost_verifier_fails_closed_without_an_active_tariff():
    verifier = SupabaseActiveModelCostVerifier(
        supabase_url="https://db.invalid", service_role_key="service-test",
        provider_id="provider-test", model_id="model-test",
        model_version="model-version-1", pricing_version="price-v1",
        cost_unit="USD", input_cost_microunits_per_token=3,
        output_cost_microunits_per_token=5, max_cost_microunits=100,
        transport=httpx.MockTransport(lambda req: httpx.Response(200, json=[])),
    )
    try:
        asyncio.run(verifier.verify())
    except RuntimeError as exc:
        assert "exactly one effective active tariff" in str(exc)
    else:
        raise AssertionError("missing active tariff must block runtime")


def test_approved_runtime_policy_verifier_requires_exact_approved_registry_row():
    import pytest
    from allpha_api.text_generation_adapters import SupabaseApprovedRuntimePolicyVerifier

    observed = {}

    def handler(req: httpx.Request) -> httpx.Response:
        observed["path"] = req.url.path
        observed["params"] = dict(req.url.params)
        return httpx.Response(200, json=[{
            "id": "policy-1",
            "policy_version": "v1",
            "status": "approved",
            "policy_digest": "a" * 64,
            "approved_at": "2026-10-18T05:50:56Z",
        }])

    verifier = SupabaseApprovedRuntimePolicyVerifier(
        supabase_url="https://db.invalid",
        service_role_key="service-test",
        policy_id="policy-1",
        policy_version="v1",
        transport=httpx.MockTransport(handler),
    )
    asyncio.run(verifier.verify())
    assert observed["path"] == "/rest/v1/agent_runtime_policies"
    assert observed["params"]["id"] == "eq.policy-1"
    assert observed["params"]["policy_version"] == "eq.v1"
    assert observed["params"]["status"] == "eq.approved"


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

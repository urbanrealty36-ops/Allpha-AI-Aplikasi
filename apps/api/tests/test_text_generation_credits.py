from __future__ import annotations

import asyncio
import uuid
from dataclasses import replace

import httpx
import pytest

from allpha_api.model_router import TextGenerationEvidence, TextGenerationPolicy, TextGenerationRequest
from allpha_api.text_generation_credits import SupabaseTextGenerationCreditLedger


OWNER = "00000000-0000-4000-8000-000000000001"
RESERVATION = "00000000-0000-4000-8000-000000000010"


def policy():
    return TextGenerationPolicy(
        policy_id="model-policy-v1", policy_version="model-policy-v1", approved=True,
        max_prompt_bytes=1024, max_output_tokens=256, max_cost_microunits=100,
        max_latency_ms=5000, cost_unit="USD", pricing_version="pricing-v1",
    )


def request():
    return TextGenerationRequest(
        task_id="task-1", trace_id="trace-1", idempotency_key="generation-key-1",
        sensitivity="private", prompt="Test request", max_output_tokens=64, timeout_ms=1000,
        owner_id=OWNER, agent_id="00000000-0000-4000-8000-000000000002",
        source_id="00000000-0000-4000-8000-000000000003",
        billing_account_id=OWNER,
    )


def policy_row(*, usage_unit="request", max_cost=100):
    return {
        "policy_version": "credit-v1",
        "credit_scheme_version": "scheme-v1",
        "approval_reference": "CREDIT-POLICY-APPROVAL-01",
        "status": "approved",
        "effective_at": "2026-01-01T00:00:00+00:00",
        "expires_at": None,
        "configuration": {
            "allow_success_settlement": True,
            "allow_definitive_failure_release": True,
            "capabilities": {
                "text_generation": {
                    "tariff_version": "tariff-v1",
                    "usage_unit": usage_unit,
                    "credits_per_usage_unit": 5,
                    "max_cost_microunits": max_cost,
                    "cost_unit": "USD",
                    "cost_pricing_version": "pricing-v1",
                }
            },
            "entitlements": {
                "entitlement-v1": {
                    "max_credits_per_request": 10,
                    "max_concurrent_reservations": 2,
                }
            },
        },
    }


def ledger(handler):
    return SupabaseTextGenerationCreditLedger(
        supabase_url="https://db.invalid",
        service_role_key="service-role-secret",
        policy_version="credit-v1",
        credit_scheme_version="scheme-v1",
        approval_reference="CREDIT-POLICY-APPROVAL-01",
        capability_id="text_generation",
        tariff_version="tariff-v1",
        entitlement_version="entitlement-v1",
        transport=httpx.MockTransport(handler),
    )


def evidence():
    return TextGenerationEvidence(
        task_id="task-1", trace_id="trace-1", idempotency_key="generation-key-1",
        policy_id="model-policy-v1", policy_version="model-policy-v1",
        provider_id="provider-a", model_id="model-a", model_version="model-v1",
        prompt_sha256="a" * 64, output_sha256="b" * 64,
        input_tokens=11, output_tokens=7, cost_microunits=30, cost_unit="USD",
        pricing_version="pricing-v1", latency_ms=20, latency_budget_ms=5000,
        cost_budget_microunits=100, status="succeeded", owner_id=OWNER,
        agent_id="00000000-0000-4000-8000-000000000002",
        source_id="00000000-0000-4000-8000-000000000003", source_version=1,
        sensitivity="private", evidence_sha256="c" * 64, billing_account_id=OWNER,
        usage_units=1, usage_unit="request",
    )


def test_credit_ledger_reserves_and_settles_only_after_usage_metering():
    observed = []

    def handler(req: httpx.Request) -> httpx.Response:
        observed.append((req.method, req.url.path, req.read().decode() if req.method == "POST" else None))
        if req.method == "GET":
            return httpx.Response(200, json=[policy_row()])
        if req.url.path.endswith("/credit_ledger_reserve"):
            return httpx.Response(200, json={
                "reservation_id": RESERVATION, "account_id": OWNER,
                "task_id": "task-1", "reserved_credits": 5, "state": "reserved",
            })
        if req.url.path.endswith("/credit_ledger_settle"):
            return httpx.Response(200, json={"reservation_id": RESERVATION, "state": "settled"})
        return httpx.Response(404)

    async def scenario():
        service = ledger(handler)
        reservation = await service.reserve(request(), policy())
        assert reservation.reservation_id == str(uuid.UUID(RESERVATION))
        assert reservation.reserved_credits == 5
        await service.settle(reservation, evidence())

    asyncio.run(scenario())
    reserve_body = next(json for method, path, json in observed if path.endswith("/credit_ledger_reserve"))
    settle_body = next(json for method, path, json in observed if path.endswith("/credit_ledger_settle"))
    assert '"usage_unit":"request"' in reserve_body
    assert '"estimated_usage_units":1' in reserve_body
    assert '"actual_usage_units":1' in settle_body
    assert '"release_unused":false' in settle_body
    assert '"source_event_id":"generation-key-1"' in settle_body


def test_credit_ledger_releases_only_definitive_failure_and_marks_unknown_pending():
    observed = []

    reserve_count = 0

    def handler(req: httpx.Request) -> httpx.Response:
        nonlocal reserve_count
        observed.append(req.url.path)
        if req.method == "GET":
            return httpx.Response(200, json=[policy_row()])
        if req.url.path.endswith("/credit_ledger_reserve"):
            reserve_count += 1
            reservation_id = RESERVATION if reserve_count == 1 else "00000000-0000-4000-8000-000000000011"
            return httpx.Response(200, json={
                "reservation_id": reservation_id, "account_id": OWNER,
                "task_id": "task-1", "reserved_credits": 5, "state": "reserved",
            })
        if req.url.path.endswith("/credit_ledger_release"):
            return httpx.Response(200, json={"reservation_id": RESERVATION, "state": "released"})
        if req.url.path.endswith("/credit_ledger_mark_pending"):
            return httpx.Response(200, json={"reservation_id": "00000000-0000-4000-8000-000000000011", "state": "pending_reconciliation"})
        return httpx.Response(404)

    async def scenario():
        service = ledger(handler)
        first = await service.reserve(request(), policy())
        await service.release(first, "provider_rejected_before_execution")
        second_request = replace(request(), idempotency_key="generation-key-2")
        second = await service.reserve(second_request, policy())
        await service.mark_pending(second, "provider_outcome_unknown")

    asyncio.run(scenario())
    assert "/rest/v1/rpc/credit_ledger_release" in observed
    assert "/rest/v1/rpc/credit_ledger_mark_pending" in observed


def test_credit_ledger_fails_closed_without_request_unit_or_matching_cost_policy():
    for row in (policy_row(usage_unit="tokens"), policy_row(max_cost=101)):
        calls = []

        def handler(req: httpx.Request, item=row) -> httpx.Response:
            calls.append(req.url.path)
            if req.method == "GET":
                return httpx.Response(200, json=[item])
            return httpx.Response(200, json={"state": "reserved", "reservation_id": RESERVATION})

        with pytest.raises(RuntimeError):
            asyncio.run(ledger(handler).reserve(request(), policy()))
        assert calls == ["/rest/v1/credit_policy_versions"]


def test_credit_ledger_requires_exactly_one_approved_policy():
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[])

    with pytest.raises(RuntimeError, match="exactly one approved credit policy"):
        asyncio.run(ledger(handler).reserve(request(), policy()))

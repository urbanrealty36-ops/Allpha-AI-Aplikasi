from __future__ import annotations

import asyncio

from allpha_api import agent_social_automation_runtime as social_runtime


def _policy_row(*, maximum_cost: int = 2500) -> dict:
    return {
        "policy_version": "social-credit-policy-v4",
        "credit_scheme_version": "credits-v2",
        "approval_reference": "approved-policy-record-4",
        "status": "approved",
        "effective_at": "2026-11-01T00:00:00Z",
        "expires_at": None,
        "configuration": {
            "capabilities": {
                "social-reply-capability": {
                    "action_tool_key": "social.reply",
                    "tariff_version": "reply-tariff-v3",
                    "usage_unit": "token",
                    "credits_per_usage_unit": 2,
                    "cost_unit": "USD_MICRO",
                    "cost_pricing_version": "model-price-v7",
                    "max_cost_microunits": maximum_cost,
                    "max_usage_units_per_request": 100,
                }
            },
            "entitlements": {
                "social-reply-entitlement-v2": {
                    "max_credits_per_request": 300,
                    "max_concurrent_reservations": 2,
                }
            },
            "lifecycle": {
                "allow_success_settlement": True,
                "allow_definitive_failure_release": True,
                "allow_partial_settlement": False,
                "allow_unknown_outcome_release": False,
            },
        },
    }


def test_credit_policy_loader_matches_route_and_returns_bounded_reservation(monkeypatch):
    async def fake_rows(store, table, params):
        assert table == "credit_policy_versions"
        assert params["status"] == "eq.approved"
        return [_policy_row()]

    monkeypatch.setattr(social_runtime, "_rows", fake_rows)
    monkeypatch.setenv("ALLPHA_AGENT_SOCIAL_CREDIT_CAPABILITY_ID", "social-reply-capability")
    monkeypatch.setenv("ALLPHA_AGENT_SOCIAL_CREDIT_ENTITLEMENT_VERSION", "social-reply-entitlement-v2")

    result = asyncio.run(social_runtime._load_credit_terms(
        object(), "social.reply",
        {"pricing_version": "model-price-v7", "cost_unit": "USD_MICRO",
         "max_cost_microunits": 3000},
    ))

    assert result["credits_to_reserve"] == 200
    assert result["estimated_cost_microunits"] == 2500
    assert result["estimated_usage_units"] == 100
    assert result["policy_version"] == "social-credit-policy-v4"


def test_credit_policy_loader_fails_closed_when_route_cost_ceiling_is_lower(monkeypatch):
    async def fake_rows(store, table, params):
        return [_policy_row(maximum_cost=2500)]

    monkeypatch.setattr(social_runtime, "_rows", fake_rows)
    monkeypatch.setenv("ALLPHA_AGENT_SOCIAL_CREDIT_CAPABILITY_ID", "social-reply-capability")
    monkeypatch.setenv("ALLPHA_AGENT_SOCIAL_CREDIT_ENTITLEMENT_VERSION", "social-reply-entitlement-v2")

    try:
        asyncio.run(social_runtime._load_credit_terms(
            object(), "social.reply",
            {"pricing_version": "model-price-v7", "cost_unit": "USD_MICRO",
             "max_cost_microunits": 2000},
        ))
    except social_runtime.AgentSocialEventBlocked as exc:
        assert exc.reason_code == "APPROVED_SOCIAL_CREDIT_POLICY_OR_MATCHING_TARIFF_NOT_FOUND"
    else:
        raise AssertionError("Credit policy must fail closed when route cost ceiling is insufficient")

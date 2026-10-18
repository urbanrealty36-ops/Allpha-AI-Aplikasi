from __future__ import annotations

import pytest
from pydantic import ValidationError

from allpha_api.main import AgentSkillUpdate, AgentSkillPublicationReview
from allpha_api.model_costs_api import ModelCostCreate, ModelCostUpdate


def test_owner_skill_update_cannot_request_publication_or_archive():
    for status in ("published", "archived", "draft"):
        with pytest.raises(ValidationError):
            AgentSkillUpdate.model_validate({"status": status})


def test_skill_publication_requires_pinned_version_digest_and_explicit_reason():
    payload = AgentSkillPublicationReview.model_validate({
        "expected_version": 2,
        "snapshot_digest": "a" * 64,
        "reason": "Review snapshot and evaluation requirements",
    })
    assert payload.expected_version == 2
    with pytest.raises(ValidationError):
        AgentSkillPublicationReview.model_validate({
            "expected_version": 2,
            "snapshot_digest": "a" * 64,
            "reason": "short",
        })
    with pytest.raises(ValidationError):
        AgentSkillPublicationReview.model_validate({
            "expected_version": 2,
            "snapshot_digest": "a" * 64,
            "reason": "Review snapshot and evaluation requirements",
            "status": "published",
        })


def test_model_cost_payloads_cannot_set_policy_approval_or_status():
    create_payload = {
        "provider_id": "nvidia-nim",
        "model_id": "qwen/qwen2.5-coder-32b-instruct",
        "model_version": "test-model-v1",
        "pricing_version": "test-only-nim-v1",
        "cost_unit": "microunits",
        "input_micro_cost_per_token": 1,
        "output_micro_cost_per_token": 2,
        "max_cost_microunits": 5000,
        "policy_approved": True,
        "status": "active",
    }
    with pytest.raises(ValidationError):
        ModelCostCreate.model_validate(create_payload)
    with pytest.raises(ValidationError):
        ModelCostUpdate.model_validate({"policy_approved": True})
    with pytest.raises(ValidationError):
        ModelCostUpdate.model_validate({"status": "active"})


def test_model_cost_activation_is_not_a_policy_approval_contract():
    # Runtime authorization is separately enforced by the approved-policy verifier
    # and explicit deployment gate; the tariff payload has no approval mutation.
    assert "policy_approved" not in ModelCostUpdate.model_fields
    assert "status" not in ModelCostUpdate.model_fields



def test_published_skill_content_update_is_rejected_before_database_write(monkeypatch):
    import asyncio
    from uuid import UUID
    from fastapi import HTTPException
    from allpha_api import main as api_main

    calls = []
    async def owner_check(*args, **kwargs):
        return "owner-session"
    async def db_request(method, table, token, params=None, body=None, prefer=None):
        calls.append((method, table, params, body))
        if method == "GET":
            return [{"id": str(UUID("44444444-4444-4444-8444-444444444444")),
                     "agent_id": str(UUID("22222222-2222-4222-8222-222222222222")),
                     "status": "published", "version": 4}]
        return []
    monkeypatch.setattr(api_main, "_require_agent_owner", owner_check)
    monkeypatch.setattr(api_main, "user_db_request", db_request)

    async def invoke():
        return await api_main.update_agent_skill(
            UUID("22222222-2222-4222-8222-222222222222"),
            UUID("44444444-4444-4444-8444-444444444444"),
            api_main.AgentSkillUpdate(name="Changed name"),
            object(),
            {"id": "11111111-1111-4111-8111-111111111111"},
        )
    with pytest.raises(HTTPException) as error:
        asyncio.run(invoke())
    assert error.value.status_code == 409
    assert error.value.detail["code"] == "SKILL_CONTENT_IMMUTABLE"
    assert len(calls) == 1 and calls[0][0] == "GET"

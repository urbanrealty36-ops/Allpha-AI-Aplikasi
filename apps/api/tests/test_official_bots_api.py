import asyncio
from uuid import uuid4

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from allpha_api import official_bots_api as api


def _request() -> Request:
    return Request({
        "type": "http", "method": "POST", "path": "/v1/admin/official-bots",
        "headers": [], "query_string": b"", "server": ("test", 80),
        "client": ("test", 80), "scheme": "http",
    })


def test_provision_limit_is_bounded_to_500():
    assert api.ProvisionPayload(limit=500).limit == 500
    with pytest.raises(ValueError):
        api.ProvisionPayload(limit=501)


def test_activation_requires_operator_approved_roster_state(monkeypatch):
    bot_id = uuid4()

    async def fake_store(method, table, **kwargs):
        return [{
            "id": str(bot_id), "status": "draft", "agent_id": str(uuid4()),
            "runtime_policy_id": str(uuid4()), "character_asset_key": "theme.asset.character",
            "asset_validation_status": "verified", "skill_key": "research.answer",
        }]

    async def fake_audit(*args, **kwargs):
        raise AssertionError("draft roster cannot be activated")

    monkeypatch.setattr(api, "privileged_rest_request", fake_store)
    monkeypatch.setattr(api, "write_operator_audit", fake_audit)
    with pytest.raises(HTTPException) as caught:
        asyncio.run(api.official_bot_lifecycle_action(
            bot_id, api.BotActionPayload(action="activate", reason="activate test reason"),
            _request(), {"id": str(uuid4()), "scopes": ["platform:capabilities.review.high_risk"]},
        ))
    assert caught.value.status_code == 409
    assert caught.value.detail["code"] == "OFFICIAL_BOT_APPROVAL_REQUIRED"


def test_activation_fails_closed_when_agent_policy_or_verified_asset_is_missing(monkeypatch):
    bot_id = uuid4()
    calls = []

    async def fake_store(method, table, **kwargs):
        calls.append((method, table, kwargs))
        return [{
            "id": str(bot_id), "status": "approved", "agent_id": None,
            "runtime_policy_id": None, "character_asset_key": None,
            "asset_validation_status": "unverified", "skill_key": "research.answer",
        }]

    async def fake_audit(*args, **kwargs):
        raise AssertionError("activation must be rejected before lifecycle write/audit")

    monkeypatch.setattr(api, "privileged_rest_request", fake_store)
    monkeypatch.setattr(api, "write_operator_audit", fake_audit)
    with pytest.raises(HTTPException) as caught:
        asyncio.run(api.official_bot_lifecycle_action(
            bot_id, api.BotActionPayload(action="activate", reason="activate test reason"),
            _request(), {"id": str(uuid4()), "scopes": ["platform:capabilities.review.high_risk"]},
        ))
    assert caught.value.status_code == 409
    assert caught.value.detail["code"] == "OFFICIAL_BOT_ACTIVATION_BLOCKED"
    assert not any(method == "PATCH" for method, _, _ in calls)


def test_stop_action_is_audited_and_marks_roster_stopped(monkeypatch):
    bot_id = uuid4()
    actor_id = str(uuid4())
    stored = {
        "id": str(bot_id), "status": "active", "agent_id": str(uuid4()),
        "runtime_policy_id": str(uuid4()), "character_asset_key": "theme.asset.character",
        "asset_validation_status": "verified", "skill_key": "research.answer",
    }
    writes = []
    audits = []

    async def fake_store(method, table, **kwargs):
        writes.append((method, table, kwargs))
        if method == "GET":
            return [stored]
        return [{**stored, "status": "stopped", **kwargs.get("body", {})}]

    async def fake_audit(*args, **kwargs):
        audits.append(kwargs)

    monkeypatch.setattr(api, "privileged_rest_request", fake_store)
    monkeypatch.setattr(api, "write_operator_audit", fake_audit)
    result = asyncio.run(api.official_bot_lifecycle_action(
        bot_id, api.BotActionPayload(action="stop", reason="stop by operator"),
        _request(), {"id": actor_id, "scopes": ["platform:capabilities.review.high_risk"]},
    ))
    assert result["bot"]["status"] == "stopped"
    assert result["runtime_action_dispatched"] is False
    assert any(method == "PATCH" for method, _, _ in writes)
    assert audits and audits[-1]["action"] == "official_bots.stop"

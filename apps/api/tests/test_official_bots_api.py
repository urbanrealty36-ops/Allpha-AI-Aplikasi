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



def test_platform_agent_identity_provisioning_uses_canonical_rpc_and_is_idempotent(monkeypatch):
    bot_id = uuid4()
    owner_id = uuid4()
    actor_id = str(uuid4())
    calls = []
    audits = []

    async def fake_store(method, table, **kwargs):
        calls.append((method, table, kwargs))
        if method == "GET" and table == "official_agent_bots":
            return [{
                "id": str(bot_id), "skill_key": "research.answer", "status": "draft",
                "agent_id": None, "metadata": {"catalog_version": "allpha-skill-catalog-v1"},
            }]
        if method == "POST" and table == "rpc/provision_official_agent_identity":
            assert kwargs["body"] == {
                "p_bot_id": str(bot_id),
                "p_platform_owner_user_id": str(owner_id),
            }
            return [{
                "id": str(uuid4()), "created_by": str(owner_id), "status": "draft",
                "persona": {"allpha_skill_key": "research.answer"},
            }]
        raise AssertionError(f"unexpected canonical store request: {method} {table}")

    async def fake_audit(*args, **kwargs):
        audits.append(kwargs)

    monkeypatch.setenv("ALLPHA_PLATFORM_OWNER_USER_ID", str(owner_id))
    monkeypatch.setattr(api, "privileged_rest_request", fake_store)
    monkeypatch.setattr(api, "write_operator_audit", fake_audit)

    result = asyncio.run(api.provision_official_bot_identity(
        bot_id, _request(),
        {"id": actor_id, "scopes": ["platform:capabilities.review.high_risk"]},
    ))

    assert result["agent"]["created_by"] == str(owner_id)
    assert result["ownership"]["owner_type"] == "platform"
    assert result["runtime_activation"] == "not_performed"
    assert result["idempotent_replay"] is False
    assert any(method == "POST" and table == "rpc/provision_official_agent_identity" for method, table, _ in calls)
    assert [event["action"] for event in audits] == [
        "official_bots.identity.provision.request",
        "official_bots.identity.provision.complete",
    ]


def test_platform_agent_identity_provisioning_fails_closed_without_configured_owner(monkeypatch):
    bot_id = uuid4()
    monkeypatch.delenv("ALLPHA_PLATFORM_OWNER_USER_ID", raising=False)

    async def forbidden_store(*args, **kwargs):
        raise AssertionError("must not call privileged RPC without a configured platform owner")

    async def forbidden_audit(*args, **kwargs):
        raise AssertionError("must fail configuration before claiming an audited provisioning action")

    monkeypatch.setattr(api, "privileged_rest_request", forbidden_store)
    monkeypatch.setattr(api, "write_operator_audit", forbidden_audit)

    with pytest.raises(HTTPException) as caught:
        asyncio.run(api.provision_official_bot_identity(
            bot_id, _request(),
            {"id": str(uuid4()), "scopes": ["platform:capabilities.review.high_risk"]},
        ))

    assert caught.value.status_code == 503
    assert caught.value.detail["code"] == "PLATFORM_AGENT_OWNER_NOT_CONFIGURED"


def test_platform_identity_migration_is_service_role_only_and_uses_canonical_tables():
    from pathlib import Path

    migration = (
        Path(__file__).parents[1]
        / "supabase"
        / "migrations"
        / "20261016160000_eng_p05_platform_owned_agent_identity.sql"
    ).read_text(encoding="utf-8")

    assert "public.provision_official_agent_identity" in migration
    assert "auth.role()" in migration and "'service_role'" in migration
    assert "insert into public.ai_agents" in migration
    assert "insert into public.agent_ownerships" in migration
    assert "for update" in migration
    assert "grant execute on function public.provision_official_agent_identity(uuid, uuid) to service_role" in migration
    assert "from public, anon, authenticated" in migration

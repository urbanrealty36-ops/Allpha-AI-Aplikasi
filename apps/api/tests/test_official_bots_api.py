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


def test_stop_action_fails_closed_when_runtime_kill_switch_is_unavailable(monkeypatch):
    bot_id = uuid4()
    stored = {
        "id": str(bot_id), "status": "active", "agent_id": str(uuid4()),
        "runtime_policy_id": str(uuid4()), "character_asset_key": "theme.asset.character",
        "asset_validation_status": "verified", "skill_key": "research.answer",
    }
    writes = []

    async def fake_store(method, table, **kwargs):
        writes.append((method, table, kwargs))
        return [stored]

    async def fake_audit(*args, **kwargs):
        raise AssertionError("must not claim a stop without a runtime kill switch")

    monkeypatch.setattr(api, "privileged_rest_request", fake_store)
    monkeypatch.setattr(api, "write_operator_audit", fake_audit)
    with pytest.raises(HTTPException) as caught:
        asyncio.run(api.official_bot_lifecycle_action(
            bot_id, api.BotActionPayload(action="stop", reason="stop by operator"),
            _request(), {"id": str(uuid4()), "scopes": ["platform:capabilities.review.high_risk"]},
        ))
    assert caught.value.status_code == 409
    assert caught.value.detail["code"] == "OFFICIAL_BOT_KILL_SWITCH_UNAVAILABLE"
    assert not any(method == "PATCH" for method, _, _ in writes)


def test_activation_never_marks_roster_active_without_runtime_dispatch(monkeypatch):
    bot_id, agent_id, policy_id = uuid4(), uuid4(), uuid4()
    stored = {
        "id": str(bot_id), "status": "approved", "agent_id": str(agent_id),
        "runtime_policy_id": str(policy_id), "character_asset_key": "theme.asset.character",
        "asset_validation_status": "verified", "skill_key": "upstream.web-research-agent",
    }
    writes = []

    async def fake_store(method, table, **kwargs):
        writes.append((method, table, kwargs))
        if method == "GET" and table == "official_agent_bots":
            return [stored]
        if method == "GET" and table == "agent_runtime_policies":
            return [{"id": str(policy_id), "agent_id": str(agent_id), "status": "approved"}]
        if method == "GET" and table == "ai_agents":
            return [{"id": str(agent_id), "status": "active"}]
        raise AssertionError(f"unexpected persistence operation: {method} {table}")

    async def fake_audit(*args, **kwargs):
        raise AssertionError("runtime dispatch failure must not be recorded as activation success")

    monkeypatch.setattr(api, "privileged_rest_request", fake_store)
    monkeypatch.setattr(api, "write_operator_audit", fake_audit)
    with pytest.raises(HTTPException) as caught:
        asyncio.run(api.official_bot_lifecycle_action(
            bot_id, api.BotActionPayload(action="activate", reason="activate after prerequisites"),
            _request(), {"id": str(uuid4()), "scopes": ["platform:capabilities.review.high_risk"]},
        ))
    assert caught.value.status_code == 409
    assert caught.value.detail["code"] == "OFFICIAL_BOT_RUNTIME_DISPATCH_UNAVAILABLE"
    assert not any(method == "PATCH" for method, _, _ in writes)


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


def test_platform_agent_identity_replay_uses_existing_canonical_agent(monkeypatch):
    bot_id = uuid4()
    owner_id = uuid4()
    agent_id = uuid4()
    calls = []
    audits = []

    async def fake_store(method, table, **kwargs):
        calls.append((method, table, kwargs))
        if method == "GET" and table == "official_agent_bots":
            return [{
                "id": str(bot_id), "skill_key": "research.answer", "status": "draft",
                "agent_id": str(agent_id), "metadata": {"catalog_version": "allpha-skill-catalog-v1"},
            }]
        if method == "POST" and table == "rpc/provision_official_agent_identity":
            return [{
                "id": str(agent_id), "created_by": str(owner_id), "status": "draft",
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
        {"id": str(uuid4()), "scopes": ["platform:capabilities.review.high_risk"]},
    ))

    assert result["agent"]["id"] == str(agent_id)
    assert result["idempotent_replay"] is True
    assert result["runtime_activation"] == "not_performed"
    # The API still delegates ownership/idempotency verification to the canonical RPC.
    assert len([call for call in calls if call[1] == "rpc/provision_official_agent_identity"]) == 1
    assert [event["action"] for event in audits] == [
        "official_bots.identity.provision.request",
        "official_bots.identity.provision.complete",
    ]


def test_platform_agent_identity_provisioning_rejects_malformed_owner_uuid(monkeypatch):
    monkeypatch.setenv("ALLPHA_PLATFORM_OWNER_USER_ID", "not-a-uuid")

    async def forbidden_store(*args, **kwargs):
        raise AssertionError("must not call identity storage with malformed owner configuration")

    monkeypatch.setattr(api, "privileged_rest_request", forbidden_store)

    with pytest.raises(HTTPException) as caught:
        asyncio.run(api.provision_official_bot_identity(
            uuid4(), _request(),
            {"id": str(uuid4()), "scopes": ["platform:capabilities.review.high_risk"]},
        ))

    assert caught.value.status_code == 503
    assert caught.value.detail["code"] == "PLATFORM_AGENT_OWNER_NOT_CONFIGURED"


def test_runtime_link_rejects_catalog_only_skill_before_any_policy_or_asset_binding(monkeypatch):
    bot_id, agent_id, policy_id = uuid4(), uuid4(), uuid4()
    calls = []

    async def fake_store(method, table, **kwargs):
        calls.append((method, table, kwargs))
        if method == "GET" and table == "official_agent_bots":
            return [{
                "id": str(bot_id), "status": "draft", "skill_key": "food.answer",
                "agent_id": str(agent_id), "runtime_policy_id": None,
            }]
        raise AssertionError("catalog-only Skill must be rejected before policy/agent reads")

    async def fake_audit(*args, **kwargs):
        raise AssertionError("rejected catalog blueprint must not be audited as linked")

    monkeypatch.setattr(api, "privileged_rest_request", fake_store)
    monkeypatch.setattr(api, "write_operator_audit", fake_audit)

    with pytest.raises(HTTPException) as caught:
        asyncio.run(api.link_official_bot_runtime(
            bot_id,
            api.BotLinkPayload(agent_id=agent_id, runtime_policy_id=policy_id, character_asset_key="user-supplied-key"),
            _request(),
            {"id": str(uuid4()), "scopes": ["platform:capabilities.review.high_risk"]},
        ))

    assert caught.value.status_code == 409
    assert caught.value.detail["code"] == "OFFICIAL_BOT_SKILL_NOT_EXECUTABLE"
    assert not any(table == "agent_runtime_policies" for _, table, _ in calls)
    assert not any(method == "PATCH" for method, _, _ in calls)


def test_runtime_link_rejects_policy_tools_missing_from_canonical_tool_registry(monkeypatch):
    bot_id, agent_id, policy_id = uuid4(), uuid4(), uuid4()
    actor_id = str(uuid4())
    calls = []
    skill_key = "upstream.web-research-agent"

    monkeypatch.setitem(api.SKILL_CATALOG_BY_KEY, skill_key, {
        "key": skill_key, "executable": True, "execution_status": "implemented",
    })

    async def fake_store(method, table, **kwargs):
        calls.append((method, table, kwargs))
        if method == "GET" and table == "official_agent_bots":
            return [{
                "id": str(bot_id), "status": "draft", "skill_key": skill_key,
                "agent_id": str(agent_id), "runtime_policy_id": None,
            }]
        if method == "GET" and table == "agent_runtime_policies":
            return [{
                "id": str(policy_id), "agent_id": str(agent_id), "status": "approved",
                "approved_tool_keys": ["web.search.not_registered"],
            }]
        raise AssertionError(f"unexpected store call: {method} {table}")

    async def fake_audit(*args, **kwargs):
        raise AssertionError("unknown tool binding must be rejected before audit/write")

    monkeypatch.setattr(api, "privileged_rest_request", fake_store)
    monkeypatch.setattr(api, "write_operator_audit", fake_audit)

    with pytest.raises(HTTPException) as caught:
        asyncio.run(api.link_official_bot_runtime(
            bot_id,
            api.BotLinkPayload(agent_id=agent_id, runtime_policy_id=policy_id, character_asset_key="user-supplied-key"),
            _request(),
            {"id": actor_id, "scopes": ["platform:capabilities.review.high_risk"]},
        ))

    assert caught.value.status_code == 409
    assert caught.value.detail["code"] == "OFFICIAL_BOT_POLICY_TOOL_NOT_REGISTERED"
    assert caught.value.detail["unknown_tool_keys"] == ["web.search.not_registered"]
    assert not any(method == "PATCH" for method, _, _ in calls)


def test_runtime_link_rejects_agent_identity_not_provisioned_for_roster(monkeypatch):
    bot_id, agent_id, other_agent_id, policy_id = uuid4(), uuid4(), uuid4(), uuid4()
    skill_key = "upstream.web-research-agent"
    monkeypatch.setitem(api.SKILL_CATALOG_BY_KEY, skill_key, {
        "key": skill_key, "executable": True, "execution_status": "implemented",
    })

    async def fake_store(method, table, **kwargs):
        if method == "GET" and table == "official_agent_bots":
            return [{
                "id": str(bot_id), "status": "draft", "skill_key": skill_key,
                "agent_id": str(agent_id), "runtime_policy_id": None,
            }]
        raise AssertionError("must reject mismatched identity before policy query")

    async def fake_audit(*args, **kwargs):
        raise AssertionError("identity mismatch must not write")

    monkeypatch.setattr(api, "privileged_rest_request", fake_store)
    monkeypatch.setattr(api, "write_operator_audit", fake_audit)

    with pytest.raises(HTTPException) as caught:
        asyncio.run(api.link_official_bot_runtime(
            bot_id,
            api.BotLinkPayload(agent_id=other_agent_id, runtime_policy_id=policy_id, character_asset_key="user-supplied-key"),
            _request(),
            {"id": str(uuid4()), "scopes": ["platform:capabilities.review.high_risk"]},
        ))

    assert caught.value.status_code == 409
    assert caught.value.detail["code"] == "OFFICIAL_BOT_CANONICAL_IDENTITY_REQUIRED"

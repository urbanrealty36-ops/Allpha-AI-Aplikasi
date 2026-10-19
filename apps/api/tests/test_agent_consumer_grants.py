from __future__ import annotations

import asyncio
import json
import httpx
import pytest

from allpha_api.agent_consumer_grants import AgentConsumerGrantStore, ConsumerGrantUnavailable


OWNER = "00000000-0000-0000-0000-000000000001"
REQUESTER = "00000000-0000-0000-0000-000000000002"
AGENT = "00000000-0000-0000-0000-000000000003"
SKILL = "00000000-0000-0000-0000-000000000004"


def snapshot(**changes):
    value = {
        "capability_id": "public_agent_message",
        "credit_scheme_version": "scheme-v1",
        "approval_reference": "finance-approval-2026-01",
        "tariff_version": "tariff-v1",
        "entitlement_version": "consumer-entitlement-v1",
        "max_usage_units": 2048,
        "max_cost_microunits": 250000,
        "cost_unit": "USD_microunit",
        "pricing_version": "model-rate-v1",
        "payer_role": "consumer",
        "allow_success_settlement": True,
        "allow_definitive_failure_release": True,
        "allow_partial_settlement": False,
    }
    value.update(changes)
    return value


def grant_row(**changes):
    row = {
        "id": "00000000-0000-0000-0000-000000000005",
        "requester_user_id": REQUESTER,
        "owner_user_id": OWNER,
        "agent_id": AGENT,
        "agent_version": 2,
        "skill_id": SKILL,
        "skill_version": 3,
        "runtime_policy_version": "public-runtime-v4",
        **snapshot(),
        "granted_scopes": ["public_invoke"],
        "status": "active",
        "idempotency_key": "grant-key-1",
        "expires_at": None,
    }
    row.update(changes)
    return row


def make_store(handler):
    return AgentConsumerGrantStore(
        supabase_url="https://example.supabase.co",
        service_key="test-only-server-key",
        transport=httpx.MockTransport(handler),
    )


def test_create_persists_complete_policy_snapshot_and_owner_identity():
    seen = []

    async def handler(request):
        seen.append((request.method, request.url.path, dict(request.url.params)))
        if request.method == "GET":
            return httpx.Response(200, json=[])
        payload = json.loads((await request.aread()).decode())
        assert payload["owner_user_id"] == OWNER
        assert payload["granted_by"] == OWNER
        assert payload["requester_user_id"] == REQUESTER
        assert payload["capability_id"] == "public_agent_message"
        assert payload["max_usage_units"] == 2048
        assert payload["payer_role"] == "consumer"
        assert payload["allow_success_settlement"] is True
        return httpx.Response(201, json=[grant_row()])

    result = asyncio.run(make_store(handler).create(
        requester_id=REQUESTER, owner_id=OWNER, agent_id=AGENT, agent_version=2,
        skill_id=SKILL, skill_version=3, runtime_policy_version="public-runtime-v4",
        idempotency_key="grant-key-1", expires_at=None, policy_snapshot=snapshot(),
    ))
    assert result["status"] == "active"
    assert [call[0] for call in seen] == ["GET", "POST"]


def test_create_replay_is_idempotent_but_changed_policy_conflicts():
    existing = grant_row()

    async def handler(request):
        if request.method == "GET":
            return httpx.Response(200, json=[existing])
        raise AssertionError("same-key replay must not insert a second grant")

    store = make_store(handler)
    result = asyncio.run(store.create(
        requester_id=REQUESTER, owner_id=OWNER, agent_id=AGENT, agent_version=2,
        skill_id=SKILL, skill_version=3, runtime_policy_version="public-runtime-v4",
        idempotency_key="grant-key-1", expires_at=None, policy_snapshot=snapshot(),
    ))
    assert result["id"] == existing["id"]

    with pytest.raises(ConsumerGrantUnavailable, match="reused with different parameters"):
        asyncio.run(store.create(
            requester_id=REQUESTER, owner_id=OWNER, agent_id=AGENT, agent_version=2,
            skill_id=SKILL, skill_version=3, runtime_policy_version="public-runtime-v4",
            idempotency_key="grant-key-1", expires_at=None,
            policy_snapshot=snapshot(max_usage_units=4096),
        ))


def test_revoked_idempotency_key_cannot_reactivate_grant():
    async def handler(request):
        return httpx.Response(200, json=[grant_row(status="revoked")])

    with pytest.raises(ConsumerGrantUnavailable, match="revoked grant idempotency key"):
        asyncio.run(make_store(handler).create(
            requester_id=REQUESTER, owner_id=OWNER, agent_id=AGENT, agent_version=2,
            skill_id=SKILL, skill_version=3, runtime_policy_version="public-runtime-v4",
            idempotency_key="grant-key-1", expires_at=None, policy_snapshot=snapshot(),
        ))


def test_resolve_requires_exact_policy_snapshot_and_scope():
    row = grant_row()
    seen = {}

    async def handler(request):
        seen["params"] = dict(request.url.params)
        return httpx.Response(200, json=[row])

    result = asyncio.run(make_store(handler).resolve(
        requester_id=REQUESTER, owner_id=OWNER, agent_id=AGENT, agent_version=2,
        skill_id=SKILL, skill_version=3, runtime_policy_version="public-runtime-v4",
        policy_snapshot=snapshot(),
    ))
    assert result == row
    assert seen["params"]["capability_id"] == "eq.public_agent_message"
    assert seen["params"]["entitlement_version"] == "eq.consumer-entitlement-v1"
    assert seen["params"]["allow_success_settlement"] == "eq.true"

    async def stale_handler(request):
        return httpx.Response(200, json=[grant_row(tariff_version="old-tariff")])

    stale = asyncio.run(make_store(stale_handler).resolve(
        requester_id=REQUESTER, owner_id=OWNER, agent_id=AGENT, agent_version=2,
        skill_id=SKILL, skill_version=3, runtime_policy_version="public-runtime-v4",
        policy_snapshot=snapshot(),
    ))
    assert stale is None


def test_revoke_is_idempotent_and_scoped_to_owner_and_agent():
    calls = []

    async def handler(request):
        calls.append((request.method, request.url.path, dict(request.url.params)))
        if request.method == "GET":
            return httpx.Response(200, json=[grant_row(status="revoked")])
        raise AssertionError("already-revoked grant must not be updated again")

    result = asyncio.run(make_store(handler).revoke(
        grant_id=grant_row()["id"], owner_id=OWNER, agent_id=AGENT, reason="owner_revoked",
    ))
    assert result["status"] == "revoked"
    assert len(calls) == 1
    assert calls[0][2]["owner_user_id"] == f"eq.{OWNER}"
    assert calls[0][2]["agent_id"] == f"eq.{AGENT}"

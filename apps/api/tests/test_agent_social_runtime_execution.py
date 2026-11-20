from __future__ import annotations

import asyncio
import uuid

import pytest

from allpha_api import agent_runtime_api as runtime
from allpha_api.agent_runtime_api import AgentRuntimeBlocked, AgentRuntimePersistenceError
from allpha_api.side_effect_adapter_contract import SideEffectOutcome

OWNER = "00000000-0000-0000-0000-000000000001"
AGENT = "00000000-0000-0000-0000-000000000002"
TASK = "00000000-0000-0000-0000-000000000003"
APPROVAL = "00000000-0000-0000-0000-000000000004"
TARGET = "00000000-0000-0000-0000-000000000005"


class FakeAdapter:
    def __init__(self, reconciled=None, executed=None):
        self.reconciled = reconciled
        self.executed = executed or SideEffectOutcome(
            provider_key="allpha.social", status="completed",
            result_payload={"social_item_id": TARGET},
            external_reference=TARGET, evidence_reference="receipt:evidence",
        )
        self.reconcile_calls = []
        self.execute_calls = []

    async def reconcile(self, command, receipt):
        self.reconcile_calls.append((command, receipt))
        return self.reconciled

    async def execute(self, command):
        self.execute_calls.append(command)
        return self.executed


def command_inputs():
    return {
        "owner_id": OWNER,
        "row": {"id": TASK, "task_version": 3, "agent_id": AGENT, "trace_id": "trace-1"},
        "step": {"step_id": "social-step-1", "tool_key": "social.comment"},
        "inputs": {"approval_id": APPROVAL, "reason": "approved by owner"},
        "lease_token": "lease-token-1",
        "policy": {"id": "policy-1", "policy_version": "7", "policy_digest": "a" * 64},
    }


def test_social_dispatch_reconciles_persisted_receipt_before_any_execution(monkeypatch):
    calls = []

    async def fake_db(method, table, *, params=None, body=None, prefer=None):
        calls.append((method, table, params))
        return [{
            "id": APPROVAL, "owner_user_id": OWNER, "agent_id": AGENT,
            "action_type": "draft_comment", "content_id": TARGET,
            "status": "approved",
        }]

    receipt = SideEffectOutcome(
        provider_key="allpha.social", status="completed",
        result_payload={"social_item_id": TARGET},
        external_reference=TARGET, evidence_reference="receipt:existing",
    )
    adapter = FakeAdapter(reconciled=receipt)
    monkeypatch.setattr(runtime, "_server_db", fake_db)
    monkeypatch.setattr(runtime, "get_side_effect_adapter", lambda key: adapter)

    result = asyncio.run(runtime._execute_social_approval_step(**command_inputs()))

    assert result["social_item_id"] == TARGET
    assert len(calls) == 1
    assert calls[0][0:2] == ("GET", "agent_social_action_approvals")
    assert calls[0][2]["owner_user_id"] == f"eq.{OWNER}"
    assert calls[0][2]["agent_id"] == f"eq.{AGENT}"
    assert adapter.reconcile_calls and adapter.execute_calls == []


def test_social_dispatch_executes_only_after_receipt_reconciliation_misses(monkeypatch):
    async def fake_db(method, table, *, params=None, body=None, prefer=None):
        return [{
            "id": APPROVAL, "owner_user_id": OWNER, "agent_id": AGENT,
            "action_type": "draft_comment", "content_id": TARGET,
            "status": "approved",
        }]

    adapter = FakeAdapter(reconciled=None)
    monkeypatch.setattr(runtime, "_server_db", fake_db)
    monkeypatch.setattr(runtime, "get_side_effect_adapter", lambda key: adapter)

    result = asyncio.run(runtime._execute_social_approval_step(**command_inputs()))

    assert result["social_item_id"] == TARGET
    assert len(adapter.reconcile_calls) == 1
    assert len(adapter.execute_calls) == 1
    command = adapter.execute_calls[0]
    assert command.owner_user_id == OWNER
    assert command.actor_user_id == OWNER
    assert command.agent_id == AGENT
    assert command.approval_id == APPROVAL
    assert command.idempotency_key == APPROVAL
    assert command.target_reference == f"content:{TARGET}"
    assert command.lease_token == "lease-token-1"


def test_social_dispatch_rejects_approval_for_a_different_action_before_adapter(monkeypatch):
    async def fake_db(method, table, *, params=None, body=None, prefer=None):
        return [{
            "id": APPROVAL, "owner_user_id": OWNER, "agent_id": AGENT,
            "action_type": "draft_reply", "content_id": TARGET,
        }]

    adapter = FakeAdapter()
    monkeypatch.setattr(runtime, "_server_db", fake_db)
    monkeypatch.setattr(runtime, "get_side_effect_adapter", lambda key: adapter)

    with pytest.raises(AgentRuntimeBlocked):
        asyncio.run(runtime._execute_social_approval_step(**command_inputs()))
    assert adapter.reconcile_calls == []
    assert adapter.execute_calls == []


def test_social_dispatch_never_advances_on_unknown_provider_outcome(monkeypatch):
    async def fake_db(method, table, *, params=None, body=None, prefer=None):
        return [{
            "id": APPROVAL, "owner_user_id": OWNER, "agent_id": AGENT,
            "action_type": "draft_comment", "content_id": TARGET,
        }]

    adapter = FakeAdapter(executed=SideEffectOutcome(
        provider_key="allpha.social", status="unknown",
        result_payload={"receipt_status": "started"},
    ))
    monkeypatch.setattr(runtime, "_server_db", fake_db)
    monkeypatch.setattr(runtime, "get_side_effect_adapter", lambda key: adapter)

    with pytest.raises(AgentRuntimePersistenceError):
        asyncio.run(runtime._execute_social_approval_step(**command_inputs()))
    assert len(adapter.reconcile_calls) == 1
    assert len(adapter.execute_calls) == 1

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest

from allpha_api import agent_social_side_effect_adapter as adapter_module
from allpha_api.side_effect_adapter_contract import (
    SideEffectAdapterContractError,
    SideEffectCommand,
    validate_side_effect_outcome,
)


def _command():
    approval_id = str(uuid4())
    return SideEffectCommand(
        task_id=str(uuid4()), task_version=2, step_key="social.comment",
        owner_user_id=str(uuid4()), actor_user_id="", agent_id=str(uuid4()),
        action_key="social.comment", target_reference="content:" + str(uuid4()),
        approval_id=approval_id, correlation_id="trace-social-001",
        idempotency_key=approval_id, input_fingerprint="a" * 64,
        lease_token=str(uuid4()), policy_id=str(uuid4()),
        policy_version="policy-v1", policy_digest="b" * 64,
        payload={"reason": "owner approved"},
    )


def test_social_adapter_is_a_real_registered_destination_adapter():
    adapter = adapter_module.get_side_effect_adapter("allpha.social")
    assert adapter is adapter_module.ALLPHA_SOCIAL_APPROVAL_ADAPTER
    assert adapter.supported_actions == {"social.comment", "social.reply", "social.story_reply"}


def test_social_adapter_requires_owner_as_actor_and_approval_id_as_idempotency_key():
    command = _command()
    command = SideEffectCommand(**{**command.__dict__, "actor_user_id": str(uuid4())})
    with pytest.raises(SideEffectAdapterContractError):
        adapter_module.ALLPHA_SOCIAL_APPROVAL_ADAPTER._rpc_payload(command)

    command = _command()
    command = SideEffectCommand(**{**command.__dict__, "actor_user_id": command.owner_user_id,
                                   "idempotency_key": "different-key"})
    with pytest.raises(SideEffectAdapterContractError):
        adapter_module.ALLPHA_SOCIAL_APPROVAL_ADAPTER._rpc_payload(command)


def test_social_adapter_executes_only_through_atomic_canonical_rpc(monkeypatch):
    command = _command()
    command = SideEffectCommand(**{**command.__dict__, "actor_user_id": command.owner_user_id})
    captured = {}

    async def rpc(method, path, *, params=None, body=None, prefer=None):
        captured.update({"method": method, "path": path, "body": body})
        return {
            "outcome": "completed",
            "receipt": {
                "id": str(uuid4()), "status": "completed",
                "result_payload": {"kind": "comment", "comment_id": str(uuid4())},
                "external_reference": str(uuid4()),
                "evidence_reference": "agent_social_action_approvals:" + command.approval_id,
                "completed_at": datetime.now(timezone.utc).isoformat(),
            },
        }

    monkeypatch.setattr(adapter_module, "_server_db", rpc)
    outcome = asyncio.run(adapter_module.ALLPHA_SOCIAL_APPROVAL_ADAPTER.execute(command))
    assert captured["method"] == "POST"
    assert captured["path"] == "rpc/execute_agent_social_approval_effect"
    assert captured["body"]["p_lease_token"] == command.lease_token
    assert captured["body"]["p_approval_id"] == command.approval_id
    assert outcome.status == "completed"
    validate_side_effect_outcome(outcome, expected_provider_key="allpha.social")


def test_social_adapter_reconciliation_rejects_receipt_identity_mismatch(monkeypatch):
    command = _command()
    command = SideEffectCommand(**{**command.__dict__, "actor_user_id": command.owner_user_id})
    async def read(*args, **kwargs):
        return [{
            "task_version": command.task_version,
            "input_fingerprint": command.input_fingerprint,
            "actor_user_id": command.actor_user_id,
            "owner_user_id": command.owner_user_id,
            "agent_id": command.agent_id,
            "target_reference": command.target_reference,
            "action_key": command.action_key,
            "approval_id": command.approval_id,
            "correlation_id": "different-trace",
            "provider_key": "allpha.social",
            "policy_id": command.policy_id,
            "policy_version": command.policy_version,
            "policy_digest": command.policy_digest,
            "status": "unknown",
        }]
    monkeypatch.setattr(adapter_module, "_server_db", read)
    with pytest.raises(SideEffectAdapterContractError):
        asyncio.run(adapter_module.ALLPHA_SOCIAL_APPROVAL_ADAPTER.reconcile(command, {}))


def test_wp07_social_effect_migration_fences_lease_and_persists_full_evidence():
    migration = (
        Path(__file__).parents[1] / "supabase" / "source-only-migrations"
        / "20261120200000_wp07_wp06_atomic_social_effect_receipts.sql"
    ).read_text().lower()
    for field in (
        "actor_user_id", "owner_user_id", "agent_id", "target_reference",
        "action_key", "approval_id", "correlation_id", "provider_key",
        "external_reference", "evidence_reference", "policy_id",
        "policy_version", "policy_digest",
    ):
        assert "add column if not exists " + field in migration
    assert "v_task.execution_lease_token is distinct from p_lease_token" in migration
    assert "v_task.lease_expires_at <= now()" in migration
    assert "public.decide_agent_social_approval(" in migration
    assert "agent_runtime_effect_idempotency_conflict" in migration
    assert "agent_runtime_effect_outcome_unknown_no_replay" in migration
    assert "grant execute on function public.execute_agent_social_approval_effect" in migration


def test_social_adapter_reconciles_completed_receipt_from_prior_lease_generation(monkeypatch):
    command = _command()
    command = SideEffectCommand(**{**command.__dict__, "actor_user_id": command.owner_user_id})
    row = {
        "task_version": command.task_version - 1,
        "input_fingerprint": command.input_fingerprint,
        "actor_user_id": command.actor_user_id,
        "owner_user_id": command.owner_user_id,
        "agent_id": command.agent_id,
        "target_reference": command.target_reference,
        "action_key": command.action_key,
        "approval_id": command.approval_id,
        "correlation_id": command.correlation_id,
        "provider_key": "allpha.social",
        "policy_id": command.policy_id,
        "policy_version": command.policy_version,
        "policy_digest": command.policy_digest,
        "status": "completed",
        "result_payload": {"kind": "comment", "comment_id": str(uuid4())},
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "external_reference": str(uuid4()),
        "evidence_reference": "agent_social_action_approvals:" + command.approval_id,
    }

    async def read(*args, **kwargs):
        return [row]

    monkeypatch.setattr(adapter_module, "_server_db", read)
    outcome = asyncio.run(adapter_module.ALLPHA_SOCIAL_APPROVAL_ADAPTER.reconcile(command, {}))
    assert outcome is not None
    assert outcome.status == "completed"


def test_social_adapter_rejects_receipt_from_future_lease_generation(monkeypatch):
    command = _command()
    command = SideEffectCommand(**{**command.__dict__, "actor_user_id": command.owner_user_id})
    row = {
        "task_version": command.task_version + 1,
        "input_fingerprint": command.input_fingerprint,
        "actor_user_id": command.actor_user_id,
        "owner_user_id": command.owner_user_id,
        "agent_id": command.agent_id,
        "target_reference": command.target_reference,
        "action_key": command.action_key,
        "approval_id": command.approval_id,
        "correlation_id": command.correlation_id,
        "provider_key": "allpha.social",
        "policy_id": command.policy_id,
        "policy_version": command.policy_version,
        "policy_digest": command.policy_digest,
        "status": "completed",
        "result_payload": {"kind": "comment", "comment_id": str(uuid4())},
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "external_reference": str(uuid4()),
        "evidence_reference": "agent_social_action_approvals:" + command.approval_id,
    }

    async def read(*args, **kwargs):
        return [row]

    monkeypatch.setattr(adapter_module, "_server_db", read)
    with pytest.raises(SideEffectAdapterContractError):
        asyncio.run(adapter_module.ALLPHA_SOCIAL_APPROVAL_ADAPTER.reconcile(command, {}))

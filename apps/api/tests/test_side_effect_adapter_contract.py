from datetime import datetime, timezone

import pytest

from allpha_api.side_effect_adapter_contract import (
    SideEffectAdapterContractError,
    SideEffectCommand,
    SideEffectOutcome,
    validate_side_effect_command,
    validate_side_effect_outcome,
)


def _command():
    return SideEffectCommand(
        task_id="task-1", task_version=3, step_key="social.publish",
        owner_user_id="owner-1", actor_user_id="owner-1", agent_id="agent-1",
        action_key="social.publish", target_reference="content:123",
        approval_id="approval-1", correlation_id="trace-1",
        idempotency_key="effect-task-1-step-1", input_fingerprint="a" * 64,
        lease_token="lease-1", policy_id="policy-1", policy_version="v1",
        policy_digest="b" * 64, payload={"content_id": "123"},
    )


def test_side_effect_command_requires_actor_target_approval_policy_and_lease():
    command = _command()
    validate_side_effect_command(command)
    with pytest.raises(SideEffectAdapterContractError):
        validate_side_effect_command(SideEffectCommand(
            **{**command.__dict__, "approval_id": ""},
        ))


def test_completed_effect_requires_provider_evidence_and_timestamp():
    validate_side_effect_outcome(
        SideEffectOutcome(
            provider_key="approved.destination", status="completed",
            result_payload={"accepted": True}, external_reference="remote-123",
            completed_at=datetime.now(timezone.utc),
        ),
        expected_provider_key="approved.destination",
    )
    with pytest.raises(SideEffectAdapterContractError):
        validate_side_effect_outcome(
            SideEffectOutcome(
                provider_key="approved.destination", status="completed",
                result_payload={"accepted": True},
            ),
            expected_provider_key="approved.destination",
        )


def test_ambiguous_effect_cannot_claim_completion_timestamp():
    with pytest.raises(SideEffectAdapterContractError):
        validate_side_effect_outcome(
            SideEffectOutcome(
                provider_key="approved.destination", status="unknown",
                result_payload={}, completed_at=datetime.now(timezone.utc),
            ),
            expected_provider_key="approved.destination",
        )


def test_adapter_identity_must_match_configured_destination():
    with pytest.raises(SideEffectAdapterContractError):
        validate_side_effect_outcome(
            SideEffectOutcome(
                provider_key="unapproved.destination", status="rejected",
                result_payload={},
            ),
            expected_provider_key="approved.destination",
        )

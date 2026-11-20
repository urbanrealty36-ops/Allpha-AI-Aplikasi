"""Formal contract for real Agent Runtime side-effect adapters.

This module intentionally provides interfaces and validation only. It does not
register a provider or make an external call. Until a provider with approved
credentials, destination authorization, and reconciliation support is wired
into the canonical Tool Registry, side-effecting runtime tools remain blocked.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal, Protocol, runtime_checkable


@dataclass(frozen=True)
class SideEffectCommand:
    task_id: str
    task_version: int
    step_key: str
    owner_user_id: str
    actor_user_id: str
    agent_id: str
    action_key: str
    target_reference: str
    approval_id: str
    correlation_id: str
    idempotency_key: str
    input_fingerprint: str
    lease_token: str
    policy_id: str
    policy_version: str
    policy_digest: str
    payload: dict[str, Any]


@dataclass(frozen=True)
class SideEffectOutcome:
    provider_key: str
    status: Literal["completed", "unknown", "rejected"]
    result_payload: dict[str, Any]
    external_reference: str | None = None
    evidence_reference: str | None = None
    completed_at: datetime | None = None


@runtime_checkable
class SideEffectAdapter(Protocol):
    """A real destination adapter must execute and reconcile using stable keys."""

    provider_key: str
    supported_actions: frozenset[str]

    async def execute(self, command: SideEffectCommand) -> SideEffectOutcome:
        """Execute once at the destination, propagating command.idempotency_key."""

    async def reconcile(
        self, command: SideEffectCommand, receipt: dict[str, Any]
    ) -> SideEffectOutcome | None:
        """Resolve an ambiguous prior attempt without blindly replaying it."""


class SideEffectAdapterContractError(ValueError):
    """Adapter response does not prove the claimed destination outcome."""


def validate_side_effect_command(command: SideEffectCommand) -> None:
    required = (
        command.task_id, command.step_key, command.owner_user_id,
        command.actor_user_id, command.agent_id, command.action_key,
        command.target_reference, command.approval_id, command.correlation_id,
        command.idempotency_key, command.input_fingerprint, command.lease_token,
        command.policy_id, command.policy_version, command.policy_digest,
    )
    if not all(isinstance(value, str) and value.strip() for value in required):
        raise SideEffectAdapterContractError("side-effect command is missing required identity or authorization metadata")
    if len(command.input_fingerprint) != 64 or any(c not in "0123456789abcdef" for c in command.input_fingerprint):
        raise SideEffectAdapterContractError("side-effect command fingerprint must be a lowercase SHA-256 digest")
    if command.task_version < 1 or not isinstance(command.payload, dict):
        raise SideEffectAdapterContractError("side-effect command version or payload is invalid")


def validate_side_effect_outcome(
    outcome: SideEffectOutcome, *, expected_provider_key: str
) -> None:
    if outcome.provider_key != expected_provider_key or not outcome.provider_key.strip():
        raise SideEffectAdapterContractError("adapter provider identity does not match the configured destination")
    if not isinstance(outcome.result_payload, dict):
        raise SideEffectAdapterContractError("adapter result payload must be an object")
    if outcome.status == "completed":
        if not (outcome.external_reference or outcome.evidence_reference) or outcome.completed_at is None:
            raise SideEffectAdapterContractError(
                "completed side effects require a destination reference or evidence reference and completion timestamp"
            )
    elif outcome.status == "unknown":
        if outcome.completed_at is not None:
            raise SideEffectAdapterContractError("unknown outcomes cannot claim a completion timestamp")
    elif outcome.status == "rejected":
        if outcome.external_reference or outcome.completed_at is not None:
            raise SideEffectAdapterContractError("rejected outcomes cannot claim a completed destination effect")

"""Policy-gated AI Credit lifecycle orchestration for ENG-P09.

This service defines the transaction boundary expected from a durable repository.
It does not provide persistence itself, invent financial policy, or execute a model.
A concrete repository must implement each operation atomically in the canonical DB.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from allpha_api.credit_ledger_contract import (
    CreditLedgerError,
    CreditReservationCommand,
)


class CreditLifecycleBlocked(CreditLedgerError):
    """The operation cannot proceed safely under the available policy/evidence."""


class OperationOutcome(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED_DEFINITIVE = "failed_definitive"
    UNKNOWN = "unknown"
    PARTIAL = "partial"


class ReservationState(StrEnum):
    RESERVED = "reserved"
    SETTLED = "settled"
    RELEASED = "released"
    PENDING_RECONCILIATION = "pending_reconciliation"


@dataclass(frozen=True)
class ApprovedLifecyclePolicy:
    """Explicitly approved runtime policy; no implicit defaults are provided."""

    policy_version: str
    approval_reference: str
    allow_success_settlement: bool
    allow_definitive_failure_release: bool
    allow_partial_settlement: bool
    allow_unknown_outcome_release: bool = False

    def __post_init__(self) -> None:
        if not self.policy_version.strip() or not self.approval_reference.strip():
            raise CreditLifecycleBlocked("an explicit approved lifecycle policy is required")
        if self.allow_unknown_outcome_release:
            raise CreditLifecycleBlocked(
                "unknown provider outcomes cannot be auto-released; reconcile the outcome first"
            )


@dataclass(frozen=True)
class ReservationReceipt:
    reservation_id: str
    idempotency_key: str
    account_id: str
    task_id: str
    reserved_credits: int
    state: ReservationState
    policy_version: str | None = None
    estimated_usage_units: int | None = None
    usage_unit: str | None = None


@dataclass(frozen=True)
class SettlementCommand:
    reservation_id: str
    idempotency_key: str
    source_event_id: str
    policy_version: str
    actual_credits: int
    actual_usage_units: int
    usage_unit: str
    release_unused: bool


class CreditLedgerTransactionPort(Protocol):
    """Atomic durable-store contract; methods must be DB-transactional and idempotent."""

    async def reserve(self, command: CreditReservationCommand) -> ReservationReceipt:
        """Atomically check spendable balance and reserve; reject concurrent overspend."""

    async def settle(self, command: SettlementCommand) -> ReservationReceipt:
        """Atomically append settlement, release remainder, and update projection/outbox."""

    async def release(self, *, reservation_id: str, idempotency_key: str,
                      policy_version: str, reason_code: str) -> ReservationReceipt:
        """Atomically release an eligible reservation exactly once."""

    async def mark_pending_reconciliation(self, *, reservation_id: str,
                                          reason_code: str) -> ReservationReceipt:
        """Persist an unknown outcome for recovery without guessing charge or release."""


class CreditLedgerLifecycleService:
    """Policy-gated lifecycle coordinator; storage owns atomicity and balances."""

    def __init__(self, store: CreditLedgerTransactionPort) -> None:
        self._store = store

    async def reserve(
        self, command: CreditReservationCommand, *, policy: ApprovedLifecyclePolicy | None
    ) -> ReservationReceipt:
        self._require_policy(policy)
        if command.policy_approval_reference != policy.approval_reference:
            raise CreditLifecycleBlocked("reservation policy approval reference mismatch")
        if command.policy_version != policy.policy_version:
            raise CreditLifecycleBlocked("reservation policy version mismatch")
        return await self._store.reserve(command)

    async def complete(
        self,
        *,
        reservation: ReservationReceipt,
        outcome: OperationOutcome,
        policy: ApprovedLifecyclePolicy | None,
        idempotency_key: str,
        source_event_id: str,
        actual_credits: int | None = None,
        actual_usage_units: int | None = None,
        usage_unit: str | None = None,
        partial_policy_approved: bool = False,
    ) -> ReservationReceipt:
        policy = self._require_policy(policy)
        if not idempotency_key.strip() or not source_event_id.strip():
            raise CreditLifecycleBlocked("completion requires idempotency and source event identifiers")
        if reservation.policy_version and reservation.policy_version != policy.policy_version:
            raise CreditLifecycleBlocked("completion policy version does not match the reservation")
        if reservation.state in {ReservationState.SETTLED, ReservationState.RELEASED}:
            if reservation.idempotency_key == idempotency_key:
                return reservation
            raise CreditLifecycleBlocked("terminal reservation cannot be reused with a different idempotency key")
        if reservation.state not in {ReservationState.RESERVED, ReservationState.PENDING_RECONCILIATION}:
            raise CreditLifecycleBlocked("reservation is not in a chargeable or recoverable state")

        if outcome == OperationOutcome.UNKNOWN:
            return await self._store.mark_pending_reconciliation(
                reservation_id=reservation.reservation_id,
                reason_code="provider_outcome_unknown",
            )

        if outcome == OperationOutcome.FAILED_DEFINITIVE:
            if not policy.allow_definitive_failure_release:
                raise CreditLifecycleBlocked("failure-release behavior is not approved")
            return await self._store.release(
                reservation_id=reservation.reservation_id,
                idempotency_key=idempotency_key,
                policy_version=policy.policy_version,
                reason_code="definitive_failure",
            )

        if outcome == OperationOutcome.PARTIAL:
            if not policy.allow_partial_settlement or not partial_policy_approved:
                raise CreditLifecycleBlocked("partial settlement requires explicit capability policy")
        elif outcome == OperationOutcome.SUCCEEDED:
            if not policy.allow_success_settlement:
                raise CreditLifecycleBlocked("success settlement is not approved")
        else:
            raise CreditLifecycleBlocked("unsupported operation outcome")

        if actual_credits is None or actual_credits <= 0:
            raise CreditLifecycleBlocked("verified positive actual credit charge is required")
        if actual_usage_units is None or actual_usage_units <= 0 or not (usage_unit or "").strip():
            raise CreditLifecycleBlocked("verified actual usage units and unit are required")
        if reservation.estimated_usage_units is not None:
            if actual_usage_units > reservation.estimated_usage_units:
                raise CreditLifecycleBlocked("actual usage exceeds the reserved estimate")
            if reservation.usage_unit and usage_unit != reservation.usage_unit:
                raise CreditLifecycleBlocked("actual usage unit does not match the reservation")
            # estimated_usage_units is a reservation ceiling, not a promise that
            # the provider will consume every reserved unit. A successful operation
            # may settle below the estimate and release unused credits atomically.
            if outcome == OperationOutcome.PARTIAL and actual_usage_units >= reservation.estimated_usage_units:
                raise CreditLifecycleBlocked("partial outcome must have fewer verified units than reserved")
        if actual_credits > reservation.reserved_credits:
            raise CreditLifecycleBlocked("actual charge exceeds reservation; require explicit recovery policy")
        if actual_credits == 0:
            raise CreditLifecycleBlocked("zero-charge semantics must be explicitly defined by Finance/Economy")

        return await self._store.settle(
            SettlementCommand(
                reservation_id=reservation.reservation_id,
                idempotency_key=idempotency_key,
                source_event_id=source_event_id,
                policy_version=policy.policy_version,
                actual_credits=actual_credits,
                actual_usage_units=actual_usage_units,
                usage_unit=usage_unit,
                release_unused=actual_credits < reservation.reserved_credits,
            )
        )

    @staticmethod
    def _require_policy(policy: ApprovedLifecyclePolicy | None) -> ApprovedLifecyclePolicy:
        if policy is None:
            raise CreditLifecycleBlocked("no approved lifecycle policy; charging remains fail-closed")
        return policy

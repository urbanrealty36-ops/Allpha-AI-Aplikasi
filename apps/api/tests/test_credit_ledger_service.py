import asyncio

import pytest

from allpha_api.credit_ledger_contract import CreditReservationCommand
from allpha_api.credit_ledger_service import (
    ApprovedLifecyclePolicy,
    CreditLedgerLifecycleService,
    CreditLifecycleBlocked,
    OperationOutcome,
    ReservationReceipt,
    ReservationState,
    SettlementCommand,
)


class FakeTransactionalStore:
    """Test-only store; proves orchestration contract, not database durability."""

    def __init__(self):
        self.calls = []

    async def reserve(self, command):
        self.calls.append(("reserve", command))
        return ReservationReceipt("reservation-1", command.idempotency_key,
                                  command.account_id, command.task_id,
                                  command.credits_to_reserve, ReservationState.RESERVED)

    async def settle(self, command: SettlementCommand):
        self.calls.append(("settle", command))
        return ReservationReceipt("reservation-1", command.idempotency_key,
                                  "account-1", "task-1", command.actual_credits,
                                  ReservationState.SETTLED)

    async def release(self, *, reservation_id, idempotency_key, policy_version, reason_code):
        self.calls.append(("release", reservation_id, idempotency_key, policy_version, reason_code))
        return ReservationReceipt(reservation_id, idempotency_key, "account-1", "task-1",
                                  0, ReservationState.RELEASED)

    async def mark_pending_reconciliation(self, *, reservation_id, reason_code):
        self.calls.append(("pending", reservation_id, reason_code))
        return ReservationReceipt(reservation_id, "reserve-key", "account-1", "task-1",
                                  10, ReservationState.PENDING_RECONCILIATION)


def command():
    return CreditReservationCommand(
        idempotency_key="reserve-key", account_id="account-1", task_id="task-1",
        capability_id="capability-x", credits_to_reserve=10,
        credit_scheme_version="scheme-v1", tariff_version="tariff-v1",
        entitlement_version="entitlement-v1", policy_approval_reference="approval-1", policy_version="lifecycle-v1",
        estimated_usage_units=10, usage_unit="request",
    )


def policy(**changes):
    values = dict(policy_version="lifecycle-v1", approval_reference="approval-1",
                  allow_success_settlement=True, allow_definitive_failure_release=True,
                  allow_partial_settlement=False)
    values.update(changes)
    return ApprovedLifecyclePolicy(**values)


def test_reservation_fails_closed_without_policy():
    store = FakeTransactionalStore()
    service = CreditLedgerLifecycleService(store)
    with pytest.raises(CreditLifecycleBlocked, match="no approved lifecycle policy"):
        asyncio.run(service.reserve(command(), policy=None))
    assert store.calls == []


def test_reservation_requires_matching_approval_reference():
    store = FakeTransactionalStore()
    service = CreditLedgerLifecycleService(store)
    with pytest.raises(CreditLifecycleBlocked, match="approval reference mismatch"):
        asyncio.run(service.reserve(command(), policy=policy(approval_reference="other")))
    assert store.calls == []


def test_success_settles_actual_amount_and_releases_unused_reservation():
    store = FakeTransactionalStore()
    service = CreditLedgerLifecycleService(store)
    reserved = asyncio.run(service.reserve(command(), policy=policy()))
    result = asyncio.run(service.complete(
        reservation=reserved, outcome=OperationOutcome.SUCCEEDED, policy=policy(),
        idempotency_key="settle-key", source_event_id="usage-event-1", actual_credits=7,
        actual_usage_units=7, usage_unit="request",
    ))
    assert result.state == ReservationState.SETTLED
    settlement = store.calls[-1][1]
    assert settlement == SettlementCommand(
        reservation_id="reservation-1", idempotency_key="settle-key",
        source_event_id="usage-event-1", policy_version="lifecycle-v1",
        actual_credits=7, release_unused=True,
    )


def test_unknown_provider_outcome_is_pending_not_charged_or_released():
    store = FakeTransactionalStore()
    service = CreditLedgerLifecycleService(store)
    reserved = asyncio.run(service.reserve(command(), policy=policy()))
    result = asyncio.run(service.complete(
        reservation=reserved, outcome=OperationOutcome.UNKNOWN, policy=policy(),
        idempotency_key="finish-key", source_event_id="usage-event-2",
    ))
    assert result.state == ReservationState.PENDING_RECONCILIATION
    assert store.calls[-1][0] == "pending"


def test_partial_settlement_requires_explicit_capability_approval():
    store = FakeTransactionalStore()
    service = CreditLedgerLifecycleService(store)
    reserved = asyncio.run(service.reserve(command(), policy=policy()))
    with pytest.raises(CreditLifecycleBlocked, match="partial settlement requires"):
        asyncio.run(service.complete(
            reservation=reserved, outcome=OperationOutcome.PARTIAL, policy=policy(),
            idempotency_key="partial-key", source_event_id="usage-event-3",
            actual_credits=4, actual_usage_units=4, usage_unit="request", partial_policy_approved=False,
        ))
    assert all(call[0] != "settle" for call in store.calls)


def test_actual_charge_cannot_exceed_reservation_or_be_zero_by_default():
    store = FakeTransactionalStore()
    service = CreditLedgerLifecycleService(store)
    reserved = asyncio.run(service.reserve(command(), policy=policy()))
    for actual in (0, 11):
        with pytest.raises(CreditLifecycleBlocked):
            asyncio.run(service.complete(
                reservation=reserved, outcome=OperationOutcome.SUCCEEDED, policy=policy(),
                idempotency_key=f"settle-{actual}", source_event_id="usage-event-4",
                actual_credits=actual, actual_usage_units=actual, usage_unit="request",
            ))
    assert all(call[0] != "settle" for call in store.calls)


def test_reservation_requires_matching_policy_version():
    store = FakeTransactionalStore()
    service = CreditLedgerLifecycleService(store)
    with pytest.raises(CreditLifecycleBlocked, match="policy version mismatch"):
        asyncio.run(service.reserve(command(), policy=policy(policy_version="other")))
    assert store.calls == []

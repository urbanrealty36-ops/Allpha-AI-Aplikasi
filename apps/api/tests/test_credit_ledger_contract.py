import pytest

from allpha_api.credit_ledger_contract import (
    CapabilityTariff, CreditEntryType, CreditLedgerEntry, CreditLedgerError,
    CreditPolicyUnavailable, CreditReservationCommand, calculate_credit_charge,
)


def tariff(**changes):
    values = dict(
        capability_id="embedding", tariff_version="tariff-v1",
        usage_unit="embedding_input_unit", credits_per_usage_unit=3,
        credit_scheme_version="credits-v1", policy_approval_reference="approval-ref-1",
    )
    values.update(changes)
    return CapabilityTariff(**values)


def entry(**changes):
    values = dict(
        entry_id="entry-1", idempotency_key="ledger-key-1", account_id="account-1",
        entry_type=CreditEntryType.RESERVATION, credits=12,
        credit_scheme_version="credits-v1", policy_version="tariff-v1",
        source_event_id="task-1", capability_id="embedding",
        created_at="2026-10-15T00:00:00Z",
    )
    values.update(changes)
    return CreditLedgerEntry(**values)


def reservation(**changes):
    values = dict(
        idempotency_key="reserve-1", account_id="account-1", task_id="task-1",
        capability_id="embedding", credits_to_reserve=6,
        credit_scheme_version="credits-v1", tariff_version="tariff-v1",
        entitlement_version="entitlement-v1", policy_approval_reference="approval-ref-1",
        policy_version="policy-v1", estimated_usage_units=2,
        usage_unit="embedding_input_unit",
    )
    values.update(changes)
    return CreditReservationCommand(**values)


def test_capability_tariff_calculates_exact_integer_units_without_cost_conversion():
    assert calculate_credit_charge(
        usage_units=4, usage_unit="embedding_input_unit", tariff=tariff()
    ) == 12


@pytest.mark.parametrize("usage_units,usage_unit", [(-1, "embedding_input_unit"), (1, "model_call")])
def test_charge_rejects_negative_usage_and_unit_mismatch(usage_units, usage_unit):
    with pytest.raises(CreditLedgerError):
        calculate_credit_charge(usage_units=usage_units, usage_unit=usage_unit, tariff=tariff())


def test_tariff_requires_explicit_approval_and_no_inactive_policy():
    with pytest.raises(CreditPolicyUnavailable):
        tariff(policy_approval_reference=" ")
    with pytest.raises(CreditPolicyUnavailable):
        tariff(active=False)


def test_entry_fingerprint_is_deterministic_and_payload_sensitive():
    assert entry().payload_fingerprint() == entry().payload_fingerprint()
    assert entry().payload_fingerprint() != entry(credits=13).payload_fingerprint()


def test_settlement_requires_related_reservation_and_reversal_reason():
    with pytest.raises(CreditLedgerError, match="related entry"):
        entry(entry_type=CreditEntryType.SETTLEMENT)
    with pytest.raises(CreditLedgerError, match="auditable reason"):
        entry(entry_type=CreditEntryType.REVERSAL, related_entry_id="entry-original")


def test_reversal_is_a_compensating_entry_not_a_mutation():
    original = entry(entry_id="original", entry_type=CreditEntryType.SETTLEMENT,
                     related_entry_id="reservation")
    reversal = entry(entry_id="reversal", idempotency_key="reversal-key",
                     entry_type=CreditEntryType.REVERSAL, related_entry_id=original.entry_id,
                     reversal_reason="approved duplicate charge")
    assert original.entry_id != reversal.entry_id
    assert reversal.related_entry_id == original.entry_id
    assert original.payload_fingerprint() != reversal.payload_fingerprint()


def test_reservation_requires_explicit_policy_versions_and_usage():
    command = reservation()
    assert command.credits_to_reserve == 6
    with pytest.raises(CreditLedgerError):
        reservation(credits_to_reserve=0)
    with pytest.raises(CreditLedgerError):
        reservation(policy_version=" ")
    with pytest.raises(CreditLedgerError):
        reservation(estimated_usage_units=0)

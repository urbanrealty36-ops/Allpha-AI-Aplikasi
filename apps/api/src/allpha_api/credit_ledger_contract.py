"""Policy-neutral AI Credit ledger domain contracts for ENG-P09.

This module is a deterministic domain boundary, not a persistence adapter.
Tariffs must be explicitly supplied by an approved, versioned policy. Usage/cost
metering remains a separate record and is never converted implicitly to credits.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Protocol


class CreditLedgerError(ValueError):
    """A credit ledger command or entry violates a domain invariant."""


class CreditPolicyUnavailable(CreditLedgerError):
    """An approved, active tariff policy is unavailable."""


class LedgerIdempotencyConflict(CreditLedgerError):
    """A key was reused with a different canonical ledger payload."""


class CreditEntryType(StrEnum):
    GRANT = "grant"
    PROMOTIONAL_GRANT = "promotional_grant"
    RESERVATION = "reservation"
    SETTLEMENT = "settlement"
    RELEASE = "release"
    EXPIRY = "expiry"
    REFUND = "refund"
    REWARD = "reward"
    REVERSAL = "reversal"
    ADJUSTMENT = "adjustment"


@dataclass(frozen=True)
class CapabilityTariff:
    """An approved capability tariff; no default or inferred tariff exists."""

    capability_id: str
    tariff_version: str
    usage_unit: str
    credits_per_usage_unit: int
    credit_scheme_version: str
    policy_approval_reference: str
    active: bool = True

    def __post_init__(self) -> None:
        if any(not value.strip() for value in (
            self.capability_id, self.tariff_version, self.usage_unit,
            self.credit_scheme_version, self.policy_approval_reference,
        )):
            raise CreditPolicyUnavailable("tariff identity and approval reference are required")
        if self.credits_per_usage_unit <= 0:
            raise CreditPolicyUnavailable("tariff must define a positive integer credit rate")
        if not self.active:
            raise CreditPolicyUnavailable("tariff policy is not active")


def calculate_credit_charge(*, usage_units: int, usage_unit: str, tariff: CapabilityTariff) -> int:
    """Calculate only exact integer-unit charges; fractional rounding is not implicit."""
    if usage_units < 0:
        raise CreditLedgerError("usage_units must be non-negative")
    if not usage_unit.strip() or usage_unit != tariff.usage_unit:
        raise CreditLedgerError("usage unit does not match the approved capability tariff")
    if not tariff.active:
        raise CreditPolicyUnavailable("tariff policy is not active")
    return usage_units * tariff.credits_per_usage_unit


@dataclass(frozen=True)
class CreditLedgerEntry:
    """Immutable append-only credit movement or reservation record."""

    entry_id: str
    idempotency_key: str
    account_id: str
    entry_type: CreditEntryType
    credits: int
    credit_scheme_version: str
    policy_version: str
    source_event_id: str
    capability_id: str
    created_at: str
    related_entry_id: str | None = None
    reversal_reason: str | None = None
    expires_at: str | None = None

    def __post_init__(self) -> None:
        required = (
            self.entry_id, self.idempotency_key, self.account_id,
            self.credit_scheme_version, self.policy_version,
            self.source_event_id, self.capability_id, self.created_at,
        )
        if any(not value.strip() for value in required):
            raise CreditLedgerError("entry identity, account, policy and source fields are required")
        if self.credits <= 0:
            raise CreditLedgerError("credits must be a positive integer; direction is represented by entry_type")
        if self.entry_type in {CreditEntryType.SETTLEMENT, CreditEntryType.RELEASE, CreditEntryType.REVERSAL,
                               CreditEntryType.REFUND, CreditEntryType.ADJUSTMENT} and not self.related_entry_id:
            raise CreditLedgerError("settlement/release/refund/reversal/adjustment must reference a related entry")
        if self.entry_type == CreditEntryType.REVERSAL and not (self.reversal_reason or "").strip():
            raise CreditLedgerError("reversal must include an auditable reason")

    def payload_fingerprint(self) -> str:
        payload = asdict(self)
        payload["entry_type"] = self.entry_type.value
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class IdempotentCreditLedgerSink(Protocol):
    """Implementations must atomically append entries and enforce unique idempotency keys.

    Same key + same fingerprint is a no-op; same key + different fingerprint is a
    LedgerIdempotencyConflict. Durable database transactions, grants/RLS and
    concurrency are intentionally not claimed by this protocol.
    """

    async def append_idempotent(self, entry: CreditLedgerEntry) -> None:
        """Durably append once, or raise without reporting success."""


@dataclass(frozen=True)
class CreditReservationCommand:
    """Validated request to reserve a precomputed, policy-approved credit amount."""

    idempotency_key: str
    account_id: str
    task_id: str
    capability_id: str
    credits_to_reserve: int
    credit_scheme_version: str
    tariff_version: str
    entitlement_version: str
    policy_approval_reference: str
    policy_version: str
    estimated_usage_units: int
    usage_unit: str
    estimated_cost_microunits: int
    cost_unit: str

    def __post_init__(self) -> None:
        if any(not value.strip() for value in (
            self.idempotency_key, self.account_id, self.task_id, self.capability_id,
            self.credit_scheme_version, self.tariff_version, self.entitlement_version,
            self.policy_approval_reference, self.policy_version, self.usage_unit, self.cost_unit,
        )):
            raise CreditLedgerError("reservation requires trusted identity and explicit policy versions")
        if self.credits_to_reserve <= 0:
            raise CreditLedgerError("reservation amount must be positive")
        if self.estimated_usage_units <= 0:
            raise CreditLedgerError("estimated usage units must be positive")
        if self.estimated_cost_microunits < 0:
            raise CreditLedgerError("estimated cost must be a non-negative integer")

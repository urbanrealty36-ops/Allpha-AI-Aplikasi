"""Durable, idempotent usage-metering contract for ENG-P09.

This module deliberately provides a contract and canonical record only. It does not
pretend an in-memory callback is durable storage and does not select a billing unit,
currency, price list, provider, or database schema.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol

from allpha_api.embedding_contract import EmbeddingRequest, EmbeddingResponse


class MeteringContractError(RuntimeError):
    """Metering record is invalid or conflicts with an existing idempotency key."""


@dataclass(frozen=True)
class MeteringRecord:
    # Stable key across retries of the same logical request; sinks must enforce it
    # with a database uniqueness constraint/transaction, not process-local memory.
    idempotency_key: str
    task_id: str
    trace_id: str
    owner_id: str
    agent_id: str
    source_id: str
    source_version: int
    sensitivity: str
    provider_id: str
    model_id: str
    model_version: str
    usage_units: int
    cost_microunits: int
    completed_at: str

    def __post_init__(self) -> None:
        required = (
            self.idempotency_key, self.task_id, self.trace_id, self.owner_id,
            self.agent_id, self.source_id, self.provider_id, self.model_id,
            self.model_version, self.completed_at,
        )
        if any(not value.strip() for value in required):
            raise ValueError("metering record identity and attribution fields are required")
        if self.source_version < 1 or self.usage_units < 0 or self.cost_microunits < 0:
            raise ValueError("metering version, usage and cost must be valid non-negative values")
        if self.sensitivity not in {"public", "internal", "confidential", "restricted"}:
            raise ValueError("metering sensitivity is invalid")

    def payload_fingerprint(self) -> str:
        """Canonical digest used to distinguish safe duplicate delivery from conflict."""
        payload = {
            "task_id": self.task_id,
            "trace_id": self.trace_id,
            "owner_id": self.owner_id,
            "agent_id": self.agent_id,
            "source_id": self.source_id,
            "source_version": self.source_version,
            "sensitivity": self.sensitivity,
            "provider_id": self.provider_id,
            "model_id": self.model_id,
            "model_version": self.model_version,
            "usage_units": self.usage_units,
            "cost_microunits": self.cost_microunits,
            "completed_at": self.completed_at,
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


class IdempotentMeteringSink(Protocol):
    async def write_idempotent(self, record: MeteringRecord) -> None:
        """Durably commit once per idempotency_key.

        Contract for implementations:
        - commit the record transactionally before returning;
        - same key + same payload fingerprint is a successful no-op;
        - same key + different fingerprint raises MeteringContractError;
        - never log raw input chunks or credentials;
        - propagate storage failure so callers cannot report metering success.
        """


def build_metering_record(request: EmbeddingRequest, response: EmbeddingResponse) -> MeteringRecord:
    if response.task_id != request.task_id or response.trace_id != request.trace_id:
        raise MeteringContractError("metering response task/trace identity mismatch")
    if response.usage_units is None or response.cost_microunits is None:
        raise MeteringContractError("actual usage and cost attribution are required for metering")
    try:
        return MeteringRecord(
            idempotency_key=request.idempotency_key,
            task_id=request.task_id,
            trace_id=request.trace_id,
            owner_id=request.owner_id,
            agent_id=request.agent_id,
            source_id=request.source_id,
            source_version=request.source_version,
            sensitivity=request.sensitivity,
            provider_id=response.provider_id,
            model_id=response.model_id,
            model_version=response.model_version,
            usage_units=response.usage_units,
            cost_microunits=response.cost_microunits,
            completed_at=response.completed_at.astimezone(timezone.utc).isoformat(),
        )
    except (AttributeError, TypeError, ValueError) as exc:
        raise MeteringContractError("actual metering attribution is malformed") from exc

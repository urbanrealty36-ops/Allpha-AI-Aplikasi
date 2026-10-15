"""Durable Supabase RPC adapter for the ENG-P09 AI Credit ledger.

Only the trusted FastAPI backend may instantiate this adapter with a service-role
credential. Never expose the credential to Web, Native, or Super Admin clients.
The database RPCs enforce policy approval, idempotency, balance locking and writes.
"""
from __future__ import annotations

import os
from typing import Any

import httpx

from allpha_api.credit_ledger_contract import CreditLedgerError, CreditReservationCommand
from allpha_api.credit_ledger_service import (
    CreditLedgerTransactionPort,
    ReservationReceipt,
    ReservationState,
    SettlementCommand,
)


class CreditLedgerPersistenceError(CreditLedgerError):
    """Durable credit ledger operation did not commit or could not be confirmed."""


class SupabaseCreditLedgerStore(CreditLedgerTransactionPort):
    _TIMEOUT = httpx.Timeout(10.0, connect=3.0)

    def __init__(
        self,
        *,
        supabase_url: str,
        service_key: str,
        transport: httpx.AsyncBaseTransport | None = None,
        timeout_seconds: float = 10.0,
    ) -> None:
        if not supabase_url.strip() or not service_key.strip():
            raise ValueError("Supabase URL and service-role key are required")
        self._base_url = supabase_url.rstrip("/")
        self._service_key = service_key
        self._transport = transport
        bounded_timeout = max(1.0, min(timeout_seconds, 30.0))
        self._timeout = httpx.Timeout(bounded_timeout, connect=min(3.0, bounded_timeout))

    @classmethod
    def from_environment(cls, *, transport: httpx.AsyncBaseTransport | None = None) -> "SupabaseCreditLedgerStore":
        url = os.getenv("SUPABASE_URL", "")
        key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
        if not url or not key:
            raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required for server-side ledger persistence")
        return cls(supabase_url=url, service_key=key, transport=transport)

    async def _rpc(self, name: str, command: dict[str, Any]) -> dict[str, Any]:
        headers = {
            "apikey": self._service_key,
            "Authorization": f"Bearer {self._service_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        try:
            async with httpx.AsyncClient(timeout=self._timeout, transport=self._transport) as client:
                response = await client.post(
                    f"{self._base_url}/rest/v1/rpc/{name}",
                    headers=headers,
                    json={"p_command": command},
                )
        except httpx.HTTPError as exc:
            raise CreditLedgerPersistenceError("Supabase credit ledger is unavailable; commit status is unknown") from exc

        if response.status_code >= 400:
            try:
                body = response.json()
            except ValueError:
                body = {}
            code = body.get("code", "unknown") if isinstance(body, dict) else "unknown"
            message = body.get("message", "") if isinstance(body, dict) else ""
            if code == "23505" or "IDEMPOTENCY_CONFLICT" in str(message):
                raise CreditLedgerError("credit ledger idempotency key conflicts with a different payload")
            if "INSUFFICIENT_AI_CREDITS" in str(message):
                raise CreditLedgerError("insufficient AI Credits")
            if "POLICY" in str(message) or code == "42501":
                raise CreditLedgerError("approved credit policy is unavailable for this operation")
            raise CreditLedgerPersistenceError(
                f"Supabase credit ledger rejected the operation (HTTP {response.status_code}, code={code})"
            )
        try:
            result = response.json()
        except ValueError as exc:
            raise CreditLedgerPersistenceError("Supabase credit ledger returned non-JSON response") from exc
        if not isinstance(result, dict) or not result.get("reservation_id") and not result.get("entry_id"):
            raise CreditLedgerPersistenceError("Supabase credit ledger did not confirm a durable result")
        return result

    @staticmethod
    def _receipt(payload: dict[str, Any]) -> ReservationReceipt:
        try:
            return ReservationReceipt(
                reservation_id=str(payload["reservation_id"]),
                idempotency_key=str(payload["idempotency_key"]),
                account_id=str(payload["account_id"]),
                task_id=str(payload["task_id"]),
                reserved_credits=int(payload["reserved_credits"]),
                state=ReservationState(payload["state"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise CreditLedgerPersistenceError("Supabase credit ledger returned an invalid reservation receipt") from exc

    async def reserve(self, command: CreditReservationCommand) -> ReservationReceipt:
        result = await self._rpc("credit_ledger_reserve", {
            "owner_user_id": command.account_id,
            "idempotency_key": command.idempotency_key,
            "task_id": command.task_id,
            "capability_id": command.capability_id,
            "credits_to_reserve": command.credits_to_reserve,
            "estimated_usage_units": command.estimated_usage_units,
            "usage_unit": command.usage_unit,
            "credit_scheme_version": command.credit_scheme_version,
            "tariff_version": command.tariff_version,
            "entitlement_version": command.entitlement_version,
            "policy_version": command.policy_version,
            "policy_approval_reference": command.policy_approval_reference,
        })
        return self._receipt(result)

    async def settle(self, command: SettlementCommand) -> ReservationReceipt:
        result = await self._rpc("credit_ledger_settle", {
            "reservation_id": command.reservation_id,
            "idempotency_key": command.idempotency_key,
            "source_event_id": command.source_event_id,
            "policy_version": command.policy_version,
            "actual_credits": command.actual_credits,
            "actual_usage_units": command.actual_usage_units,
            "usage_unit": command.usage_unit,
            "release_unused": command.release_unused,
        })
        return self._receipt(result)

    async def release(
        self, *, reservation_id: str, idempotency_key: str,
        policy_version: str, reason_code: str,
    ) -> ReservationReceipt:
        result = await self._rpc("credit_ledger_release", {
            "reservation_id": reservation_id,
            "idempotency_key": idempotency_key,
            "policy_version": policy_version,
            "reason_code": reason_code,
        })
        return self._receipt(result)

    async def mark_pending_reconciliation(
        self, *, reservation_id: str, reason_code: str,
    ) -> ReservationReceipt:
        result = await self._rpc("credit_ledger_mark_pending", {
            "reservation_id": reservation_id,
            "reason_code": reason_code,
        })
        return self._receipt(result)


    async def reverse(
        self, *, owner_user_id: str, original_entry_id: str, idempotency_key: str,
        credits: int, policy_version: str, policy_approval_reference: str,
        source_event_id: str, reason_code: str, entry_type: str = "reversal",
        actor_type: str = "operator", actor_id: str | None = None,
    ) -> str:
        """Append a policy-approved compensating entry; never mutate the original."""
        if entry_type not in {"refund", "reversal"}:
            raise ValueError("entry_type must be refund or reversal")
        if actor_type not in {"system", "operator"}:
            raise ValueError("actor_type must be system or operator")
        result = await self._rpc("credit_ledger_reverse", {
            "owner_user_id": owner_user_id,
            "original_entry_id": original_entry_id,
            "idempotency_key": idempotency_key,
            "credits": credits,
            "policy_version": policy_version,
            "policy_approval_reference": policy_approval_reference,
            "source_event_id": source_event_id,
            "reason_code": reason_code,
            "entry_type": entry_type,
            "actor_type": actor_type,
            "actor_id": actor_id,
        })
        return str(result["entry_id"])

    async def grant(
        self, *, owner_user_id: str, idempotency_key: str, entry_type: str,
        credits: int, policy_version: str, policy_approval_reference: str,
        source_event_id: str, capability_id: str = "account_grant",
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Post a policy-approved grant/reward; policy config must explicitly permit it."""
        result = await self._rpc("credit_ledger_grant", {
            "owner_user_id": owner_user_id,
            "idempotency_key": idempotency_key,
            "entry_type": entry_type,
            "credits": credits,
            "policy_version": policy_version,
            "policy_approval_reference": policy_approval_reference,
            "source_event_id": source_event_id,
            "capability_id": capability_id,
            "metadata": metadata or {},
        })
        return str(result["entry_id"])

"""ENG-P18 durable owner-approved public Agent Consumer grants and credit reservation.

All mutations are server-side. This module deliberately fails closed when the
approved credit policy does not explicitly define the consumer-messaging tariff.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Any

import httpx

from allpha_api.credit_ledger_contract import CreditReservationCommand
from allpha_api.credit_ledger_service import (
    ApprovedLifecyclePolicy,
    CreditLedgerLifecycleService,
    OperationOutcome,
    ReservationReceipt,
)
from allpha_api.supabase_credit_ledger_store import SupabaseCreditLedgerStore


class ConsumerGrantUnavailable(RuntimeError):
    """A durable Consumer grant or approved runtime budget is unavailable."""


class AgentConsumerGrantStore:
    _timeout = httpx.Timeout(10.0, connect=3.0)

    def __init__(self, *, supabase_url: str, service_key: str) -> None:
        if not supabase_url.strip() or not service_key.strip():
            raise ValueError("Supabase server credentials are required")
        self._base = supabase_url.rstrip("/")
        self._key = service_key

    @classmethod
    def from_environment(cls) -> "AgentConsumerGrantStore":
        return cls(
            supabase_url=os.getenv("SUPABASE_URL", ""),
            service_key=os.getenv("SUPABASE_SERVICE_ROLE_KEY", "") or os.getenv("SUPABASE_SECRET_KEY", ""),
        )

    async def _request(self, method: str, table: str, *, params: dict[str, str] | None = None,
                       body: Any = None, prefer: str | None = None) -> Any:
        headers = {
            "apikey": self._key,
            "Authorization": f"Bearer {self._key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if prefer:
            headers["Prefer"] = prefer
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.request(
                    method, f"{self._base}/rest/v1/{table}", params=params, json=body, headers=headers
                )
        except httpx.HTTPError as exc:
            raise ConsumerGrantUnavailable("Consumer grant persistence is unavailable") from exc
        if response.status_code >= 400:
            # Do not leak database internals or service-role error details.
            if response.status_code == 409:
                raise ConsumerGrantUnavailable("Consumer grant conflicts with an existing grant")
            raise ConsumerGrantUnavailable("Consumer grant operation was not confirmed")
        if not response.content:
            return None
        try:
            return response.json()
        except ValueError as exc:
            raise ConsumerGrantUnavailable("Consumer grant store returned invalid data") from exc

    async def create(self, *, requester_id: str, owner_id: str, agent_id: str,
                     agent_version: int, skill_id: str, skill_version: int,
                     runtime_policy_version: str, idempotency_key: str,
                     expires_at: str | None) -> dict[str, Any]:
        if requester_id == owner_id:
            raise ValueError("owner cannot create a Consumer grant for themselves")
        if not idempotency_key.strip():
            raise ValueError("grant idempotency key is required")
        existing = await self._request(
            "GET", "agent_consumer_grants",
            params={"select":"*", "owner_user_id":f"eq.{owner_id}",
                    "idempotency_key":f"eq.{idempotency_key}", "limit":"1"},
        )
        payload = {
            "requester_user_id": requester_id,
            "owner_user_id": owner_id,
            "agent_id": agent_id,
            "agent_version": agent_version,
            "skill_id": skill_id,
            "skill_version": skill_version,
            "runtime_policy_version": runtime_policy_version,
            "granted_scopes": ["public_invoke"],
            "status": "active",
            "idempotency_key": idempotency_key,
            "expires_at": expires_at,
            "granted_by": owner_id,
        }
        if existing:
            row = existing[0]
            keys = ("requester_user_id","owner_user_id","agent_id","agent_version","skill_id",
                    "skill_version","runtime_policy_version","expires_at")
            if any(row.get(key) != payload.get(key) for key in keys):
                raise ConsumerGrantUnavailable("grant idempotency key was reused with different parameters")
            if row.get("status") == "active":
                return row
        rows = await self._request("POST", "agent_consumer_grants", body=payload, prefer="return=representation")
        if not rows:
            raise ConsumerGrantUnavailable("Consumer grant creation was not confirmed")
        return rows[0]

    async def revoke(self, *, grant_id: str, owner_id: str, agent_id: str,
                     reason: str) -> dict[str, Any]:
        rows = await self._request(
            "GET", "agent_consumer_grants",
            params={"select":"id,status,owner_user_id,agent_id", "id":f"eq.{grant_id}",
                    "owner_user_id":f"eq.{owner_id}", "agent_id":f"eq.{agent_id}", "limit":"1"},
        )
        if not rows:
            raise LookupError("Consumer grant not found")
        if rows[0]["status"] == "revoked":
            return rows[0]
        changed = await self._request(
            "PATCH", "agent_consumer_grants",
            params={"id":f"eq.{grant_id}", "owner_user_id":f"eq.{owner_id}",
                    "agent_id":f"eq.{agent_id}", "status":"eq.active"},
            body={"status":"revoked", "revoked_by":owner_id, "revoked_at":_now(),
                  "revoke_reason":reason.strip() or "owner_revoked", "updated_at":_now()},
            prefer="return=representation",
        )
        if not changed:
            raise ConsumerGrantUnavailable("Consumer grant revocation was not confirmed")
        return changed[0]

    async def resolve(self, *, requester_id: str, owner_id: str, agent_id: str,
                      agent_version: int, skill_id: str, skill_version: int,
                      runtime_policy_version: str) -> dict[str, Any] | None:
        rows = await self._request(
            "GET", "agent_consumer_grants",
            params={"select":"*", "requester_user_id":f"eq.{requester_id}",
                    "owner_user_id":f"eq.{owner_id}", "agent_id":f"eq.{agent_id}",
                    "agent_version":f"eq.{agent_version}", "skill_id":f"eq.{skill_id}",
                    "skill_version":f"eq.{skill_version}", "runtime_policy_version":f"eq.{runtime_policy_version}",
                    "status":"eq.active", "granted_scopes":"cs.{public_invoke}",
                    "or":f"(expires_at.is.null,expires_at.gt.{_now()})",
                    "order":"granted_at.desc", "limit":"1"},
        )
        return rows[0] if rows else None


class ConsumerBudgetReservation:
    """Reserves credits only from an explicitly approved, versioned ledger policy."""

    def __init__(self, *, store: SupabaseCreditLedgerStore, lifecycle: CreditLedgerLifecycleService,
                 policy_version: str, approval_reference: str, credit_scheme_version: str,
                 capability_id: str, tariff_version: str, entitlement_version: str,
                 usage_unit: str, credits_per_usage_unit: int, max_usage_units: int,
                 max_cost_microunits: int, cost_unit: str, pricing_version: str,
                 allow_success_settlement: bool, allow_definitive_failure_release: bool,
                 allow_partial_settlement: bool) -> None:
        if min(credits_per_usage_unit, max_usage_units) <= 0 or max_cost_microunits < 0:
            raise ConsumerGrantUnavailable("approved consumer credit limits are invalid")
        if not all((policy_version, approval_reference, credit_scheme_version, capability_id,
                    tariff_version, entitlement_version, usage_unit, cost_unit, pricing_version)):
            raise ConsumerGrantUnavailable("approved consumer credit policy is incomplete")
        self.store = store
        self.lifecycle = lifecycle
        self.policy_version = policy_version
        self.approval_reference = approval_reference
        self.credit_scheme_version = credit_scheme_version
        self.capability_id = capability_id
        self.tariff_version = tariff_version
        self.entitlement_version = entitlement_version
        self.usage_unit = usage_unit
        self.credits_per_usage_unit = credits_per_usage_unit
        self.max_usage_units = max_usage_units
        self.max_cost_microunits = max_cost_microunits
        self.cost_unit = cost_unit
        self.pricing_version = pricing_version
        self.policy = ApprovedLifecyclePolicy(
            policy_version=policy_version,
            approval_reference=approval_reference,
            allow_success_settlement=allow_success_settlement,
            allow_definitive_failure_release=allow_definitive_failure_release,
            allow_partial_settlement=allow_partial_settlement,
        )

    @classmethod
    async def from_environment(cls, *, expected_cost_unit: str, expected_pricing_version: str,
                               expected_max_cost_microunits: int) -> "ConsumerBudgetReservation":
        base = os.getenv("SUPABASE_URL", "").rstrip("/")
        key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "") or os.getenv("SUPABASE_SECRET_KEY", "")
        if not base or not key:
            raise ConsumerGrantUnavailable("canonical credit ledger is not configured")
        headers = {"apikey":key,"Authorization":f"Bearer {key}","Accept":"application/json"}
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(10.0, connect=3.0)) as client:
                response = await client.get(
                    f"{base}/rest/v1/credit_policy_versions",
                    params={"select":"policy_version,credit_scheme_version,approval_reference,configuration",
                            "status":"eq.approved", "or":f"(effective_at.is.null,effective_at.lte.{_now()})",
                            "order":"approved_at.desc.nullslast", "limit":"10"},
                    headers=headers,
                )
                response.raise_for_status()
                rows = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ConsumerGrantUnavailable("approved credit policy could not be resolved") from exc
        selected = None
        for row in rows if isinstance(rows, list) else []:
            config = row.get("configuration") or {}
            consumer = config.get("consumer_agent_messaging") or {}
            capability_id = str(consumer.get("capability_id") or "")
            cap = (config.get("capabilities") or {}).get(capability_id) if capability_id else None
            entitlements = config.get("entitlements") or {}
            entitlement_version = str(consumer.get("entitlement_version") or "")
            entitlement = entitlements.get(entitlement_version) if entitlement_version else None
            if (consumer.get("enabled") is True and isinstance(cap, dict) and isinstance(entitlement, dict)
                    and cap.get("usage_unit") and cap.get("tariff_version")
                    and cap.get("cost_unit") == expected_cost_unit
                    and cap.get("cost_pricing_version") == expected_pricing_version
                    and cap.get("max_cost_microunits") == expected_max_cost_microunits
                    and consumer.get("max_usage_units_per_request")
                    and cap.get("credits_per_usage_unit")):
                selected = (row, config, consumer, cap, entitlement, entitlement_version, capability_id)
                break
        if selected is None:
            raise ConsumerGrantUnavailable("no approved Consumer messaging tariff and entitlement match the active Model Router route")
        row, config, consumer, cap, entitlement, entitlement_version, capability_id = selected
        store = SupabaseCreditLedgerStore(supabase_url=base, service_key=key)
        return cls(
            store=store, lifecycle=CreditLedgerLifecycleService(store),
            policy_version=str(row["policy_version"]), approval_reference=str(row["approval_reference"]),
            credit_scheme_version=str(row["credit_scheme_version"]), capability_id=capability_id,
            tariff_version=str(cap["tariff_version"]), entitlement_version=entitlement_version,
            usage_unit=str(cap["usage_unit"]), credits_per_usage_unit=int(cap["credits_per_usage_unit"]),
            max_usage_units=int(consumer["max_usage_units_per_request"]),
            max_cost_microunits=int(cap["max_cost_microunits"]), cost_unit=str(cap["cost_unit"]),
            pricing_version=str(cap["cost_pricing_version"]),
            allow_success_settlement=consumer.get("allow_success_settlement") is True,
            allow_definitive_failure_release=consumer.get("allow_definitive_failure_release") is True,
            allow_partial_settlement=consumer.get("allow_partial_settlement") is True,
        )

    async def reserve(self, *, owner_id: str, message_id: str) -> ReservationReceipt:
        units = self.max_usage_units
        credits = units * self.credits_per_usage_unit
        if credits <= 0:
            raise ConsumerGrantUnavailable("approved consumer reservation must be positive")
        command = CreditReservationCommand(
            idempotency_key=f"consumer-message-reserve:{message_id}",
            account_id=owner_id, task_id=f"consumer-message:{message_id}",
            capability_id=self.capability_id, credits_to_reserve=credits,
            credit_scheme_version=self.credit_scheme_version, tariff_version=self.tariff_version,
            entitlement_version=self.entitlement_version, policy_approval_reference=self.approval_reference,
            policy_version=self.policy_version, estimated_usage_units=units, usage_unit=self.usage_unit,
            estimated_cost_microunits=self.max_cost_microunits, cost_unit=self.cost_unit,
        )
        return await self.lifecycle.reserve(command, policy=self.policy)

    async def settle(self, *, reservation: ReservationReceipt, message_id: str,
                     usage_units: int, cost_microunits: int, cost_unit: str,
                     pricing_version: str) -> None:
        if usage_units <= 0 or usage_units > self.max_usage_units:
            await self.lifecycle.complete(
                reservation=reservation, outcome=OperationOutcome.UNKNOWN, policy=self.policy,
                idempotency_key=f"consumer-message-settle:{message_id}",
                source_event_id=message_id,
            )
            raise ConsumerGrantUnavailable("actual usage does not fit the approved reservation; reconciliation required")
        if cost_unit != self.cost_unit or pricing_version != self.pricing_version or cost_microunits > self.max_cost_microunits:
            await self.lifecycle.complete(
                reservation=reservation, outcome=OperationOutcome.UNKNOWN, policy=self.policy,
                idempotency_key=f"consumer-message-settle:{message_id}",
                source_event_id=message_id,
            )
            raise ConsumerGrantUnavailable("actual model cost differs from the approved reservation; reconciliation required")
        actual_credits = usage_units * self.credits_per_usage_unit
        await self.lifecycle.complete(
            reservation=reservation, outcome=OperationOutcome.SUCCEEDED, policy=self.policy,
            idempotency_key=f"consumer-message-settle:{message_id}",
            source_event_id=message_id, actual_credits=actual_credits,
            actual_usage_units=usage_units, usage_unit=self.usage_unit,
        )

    async def mark_unknown(self, *, reservation: ReservationReceipt, reason_code: str) -> None:
        await self.lifecycle.complete(
            reservation=reservation, outcome=OperationOutcome.UNKNOWN, policy=self.policy,
            idempotency_key=f"consumer-message-unknown:{reservation.task_id}",
            source_event_id=reservation.task_id,
        )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

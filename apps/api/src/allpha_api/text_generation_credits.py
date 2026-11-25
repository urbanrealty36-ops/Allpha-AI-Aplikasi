from __future__ import annotations

import hashlib
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import httpx

from allpha_api.model_router import TextGenerationEvidence, TextGenerationPolicy, TextGenerationRequest


@dataclass(frozen=True)
class TextGenerationCreditReservation:
    reservation_id: str
    idempotency_key: str
    owner_user_id: str
    policy_version: str
    reserved_credits: int
    credits_per_usage_unit: int
    usage_unit: str
    capability_id: str


class SupabaseTextGenerationCreditLedger:
    """Atomic request-credit reserve/settle/release over the canonical credit ledger.

    The credit policy must explicitly define one request as its billable unit. This
    avoids estimating provider tokens without a pinned tokenizer. Provider token
    counts and actual currency cost remain recorded in model usage metering.
    """

    def __init__(
        self,
        *,
        supabase_url: str,
        service_role_key: str,
        policy_version: str,
        credit_scheme_version: str,
        approval_reference: str,
        capability_id: str,
        tariff_version: str,
        entitlement_version: str,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        required = (
            supabase_url, service_role_key, policy_version, credit_scheme_version,
            approval_reference, capability_id, tariff_version, entitlement_version,
        )
        if not all(isinstance(value, str) and value.strip() for value in required):
            raise ValueError("text-generation credit ledger configuration is incomplete")
        self._base = supabase_url.rstrip("/")
        self._key = service_role_key
        self._policy_version = policy_version
        self._credit_scheme_version = credit_scheme_version
        self._approval_reference = approval_reference
        self._capability_id = capability_id
        self._tariff_version = tariff_version
        self._entitlement_version = entitlement_version
        self._transport = transport

    @classmethod
    def from_environment(cls) -> "SupabaseTextGenerationCreditLedger":
        service_role_key = (
            os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
            or os.getenv("SUPABASE_SECRET_KEY", "").strip()
        )
        return cls(
            supabase_url=os.getenv("SUPABASE_URL", ""),
            service_role_key=service_role_key,
            policy_version=os.getenv("ALLPHA_TEXTGEN_CREDIT_POLICY_VERSION", ""),
            credit_scheme_version=os.getenv("ALLPHA_TEXTGEN_CREDIT_SCHEME_VERSION", ""),
            approval_reference=os.getenv("ALLPHA_TEXTGEN_CREDIT_POLICY_APPROVAL_REFERENCE", ""),
            capability_id=os.getenv("ALLPHA_TEXTGEN_CREDIT_CAPABILITY_ID", ""),
            tariff_version=os.getenv("ALLPHA_TEXTGEN_CREDIT_TARIFF_VERSION", ""),
            entitlement_version=os.getenv("ALLPHA_TEXTGEN_CREDIT_ENTITLEMENT_VERSION", ""),
        )

    def _headers(self) -> dict[str, str]:
        return {
            "apikey": self._key,
            "Authorization": "Bearer " + self._key,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    async def _request(self, method: str, path: str, *, params: dict[str, str] | None = None,
                       body: dict[str, Any] | None = None) -> Any:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(10.0, connect=3.0), transport=self._transport,
            follow_redirects=False, trust_env=False,
        ) as client:
            response = await client.request(
                method, self._base + path, params=params, json=body,
                headers=self._headers(),
            )
            response.raise_for_status()
            return response.json() if response.content else None

    async def _policy(self, policy: TextGenerationPolicy) -> tuple[int, dict[str, Any]]:
        rows = await self._request(
            "GET", "/rest/v1/credit_policy_versions",
            params={
                "select": "policy_version,credit_scheme_version,approval_reference,status,configuration,effective_at,expires_at",
                "policy_version": "eq." + self._policy_version,
                "credit_scheme_version": "eq." + self._credit_scheme_version,
                "approval_reference": "eq." + self._approval_reference,
                "status": "eq.approved",
                "limit": "2",
            },
        )
        if not isinstance(rows, list) or len(rows) != 1:
            raise RuntimeError("exactly one approved credit policy version is required")
        row = rows[0]
        if (not isinstance(row, dict) or row.get("policy_version") != self._policy_version
                or row.get("credit_scheme_version") != self._credit_scheme_version
                or row.get("approval_reference") != self._approval_reference
                or row.get("status") != "approved"):
            raise RuntimeError("approved credit policy identity is invalid")
        now = datetime.now(timezone.utc)
        effective = row.get("effective_at")
        expires = row.get("expires_at")
        if effective:
            parsed = datetime.fromisoformat(str(effective).replace("Z", "+00:00"))
            if parsed.tzinfo is None or parsed > now:
                raise RuntimeError("credit policy is not yet effective")
        if expires:
            parsed = datetime.fromisoformat(str(expires).replace("Z", "+00:00"))
            if parsed.tzinfo is None or parsed <= now:
                raise RuntimeError("credit policy has expired")
        configuration = row.get("configuration")
        if not isinstance(configuration, dict):
            raise RuntimeError("credit policy configuration is invalid")
        capabilities = configuration.get("capabilities")
        entitlements = configuration.get("entitlements")
        capability = capabilities.get(self._capability_id) if isinstance(capabilities, dict) else None
        entitlement = entitlements.get(self._entitlement_version) if isinstance(entitlements, dict) else None
        if not isinstance(capability, dict) or not isinstance(entitlement, dict):
            raise RuntimeError("credit capability or entitlement is not configured")
        if (capability.get("tariff_version") != self._tariff_version
                or capability.get("usage_unit") != "request"
                or capability.get("cost_unit") != policy.cost_unit
                or capability.get("cost_pricing_version") != policy.pricing_version
                or capability.get("max_cost_microunits") != policy.max_cost_microunits):
            raise RuntimeError("credit tariff does not match the approved text-generation model cost policy")
        credits_per_unit = capability.get("credits_per_usage_unit")
        max_credits = entitlement.get("max_credits_per_request")
        concurrent = entitlement.get("max_concurrent_reservations")
        if (not isinstance(credits_per_unit, int) or isinstance(credits_per_unit, bool) or credits_per_unit <= 0
                or not isinstance(max_credits, int) or isinstance(max_credits, bool) or max_credits < credits_per_unit
                or not isinstance(concurrent, int) or isinstance(concurrent, bool) or concurrent <= 0):
            raise RuntimeError("credit entitlement limits are invalid")
        if configuration.get("allow_success_settlement") is not True:
            raise RuntimeError("credit policy does not approve successful settlement")
        if configuration.get("allow_definitive_failure_release") is not True:
            raise RuntimeError("credit policy does not approve definitive failure release")
        return credits_per_unit, capability

    async def reserve(self, request: TextGenerationRequest, policy: TextGenerationPolicy) -> TextGenerationCreditReservation:
        account = request.billing_account_id or request.owner_id
        if not isinstance(account, str) or not account.strip():
            raise RuntimeError("credit reservation requires a trusted billing account")
        owner_user_id = str(uuid.UUID(account))
        credits_per_unit, capability = await self._policy(policy)
        reservation_key = "textgen:" + hashlib.sha256(request.idempotency_key.encode("utf-8")).hexdigest()
        command = {
            "owner_user_id": owner_user_id,
            "idempotency_key": reservation_key,
            "policy_version": self._policy_version,
            "policy_approval_reference": self._approval_reference,
            "credit_scheme_version": self._credit_scheme_version,
            "capability_id": self._capability_id,
            "tariff_version": self._tariff_version,
            "entitlement_version": self._entitlement_version,
            "estimated_usage_units": 1,
            "usage_unit": "request",
            "estimated_cost_microunits": policy.max_cost_microunits,
            "cost_unit": policy.cost_unit,
            "credits_to_reserve": credits_per_unit,
            "task_id": request.task_id,
        }
        result = await self._request("POST", "/rest/v1/rpc/credit_ledger_reserve", body={"p_command": command})
        if (not isinstance(result, dict) or result.get("state") != "reserved"
                or not isinstance(result.get("reservation_id"), str)):
            raise RuntimeError("credit ledger did not confirm a fresh reserved state")
        reservation_id = str(uuid.UUID(result["reservation_id"]))
        if result.get("account_id") != owner_user_id or result.get("task_id") != request.task_id:
            raise RuntimeError("credit reservation identity does not match the generation request")
        return TextGenerationCreditReservation(
            reservation_id=reservation_id,
            idempotency_key=reservation_key,
            owner_user_id=owner_user_id,
            policy_version=self._policy_version,
            reserved_credits=credits_per_unit,
            credits_per_usage_unit=credits_per_unit,
            usage_unit="request",
            capability_id=self._capability_id,
        )

    async def settle(self, reservation: TextGenerationCreditReservation, evidence: TextGenerationEvidence) -> None:
        if evidence.usage_unit != reservation.usage_unit or evidence.usage_units != 1:
            raise RuntimeError("actual text-generation usage does not match the reserved request unit")
        command = {
            "reservation_id": reservation.reservation_id,
            "idempotency_key": reservation.idempotency_key + ":settle",
            "policy_version": reservation.policy_version,
            "source_event_id": evidence.idempotency_key,
            "actual_credits": reservation.credits_per_usage_unit,
            "actual_usage_units": evidence.usage_units,
            "usage_unit": evidence.usage_unit,
            "release_unused": False,
        }
        result = await self._request("POST", "/rest/v1/rpc/credit_ledger_settle", body={"p_command": command})
        if not isinstance(result, dict) or result.get("state") != "settled":
            raise RuntimeError("credit ledger did not confirm settlement")

    async def release(self, reservation: TextGenerationCreditReservation, reason_code: str) -> None:
        reason = "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in reason_code.lower())[:64] or "definitive_failure"
        command = {
            "reservation_id": reservation.reservation_id,
            "idempotency_key": reservation.idempotency_key + ":release",
            "policy_version": reservation.policy_version,
            "reason_code": reason,
        }
        result = await self._request("POST", "/rest/v1/rpc/credit_ledger_release", body={"p_command": command})
        if not isinstance(result, dict) or result.get("state") != "released":
            raise RuntimeError("credit ledger did not confirm definitive failure release")

    async def mark_pending(self, reservation: TextGenerationCreditReservation, reason_code: str) -> None:
        reason = "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in reason_code.lower())[:64] or "provider_outcome_unknown"
        result = await self._request(
            "POST", "/rest/v1/rpc/credit_ledger_mark_pending",
            body={"p_command": {"reservation_id": reservation.reservation_id, "reason_code": reason}},
        )
        if not isinstance(result, dict) or result.get("state") != "pending_reconciliation":
            raise RuntimeError("credit ledger did not confirm pending reconciliation")

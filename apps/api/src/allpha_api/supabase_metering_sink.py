"""Service-role PostgREST adapter for the ENG-P09 metering RPC.

This adapter is source-only until its migration is validated in isolated
non-production. It never performs credit conversion or ledger settlement.
"""
from __future__ import annotations

from dataclasses import asdict
from typing import Any

import httpx

from allpha_api.metering_contract import IdempotentMeteringSink, MeteringContractError, MeteringRecord


class SupabaseMeteringSink(IdempotentMeteringSink):
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
        self._timeout_seconds = max(1.0, min(timeout_seconds, 30.0))

    async def write_idempotent(self, record: MeteringRecord) -> None:
        payload: dict[str, Any] = asdict(record)
        payload["payload_fingerprint"] = record.payload_fingerprint()
        headers = {
            "apikey": self._service_key,
            "Authorization": f"Bearer {self._service_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(self._timeout_seconds, connect=min(3.0, self._timeout_seconds)),
            transport=self._transport,
        ) as client:
            response = await client.post(
                f"{self._base_url}/rest/v1/rpc/record_agent_model_usage_metering",
                headers=headers,
                json={"p_record": payload},
            )
        if response.status_code >= 400:
            try:
                error = response.json()
            except ValueError:
                error = {}
            code = error.get("code") if isinstance(error, dict) else None
            message = error.get("message", "") if isinstance(error, dict) else ""
            if code == "23505" or "METERING_IDEMPOTENCY_CONFLICT" in str(message):
                raise MeteringContractError("idempotency key already exists with a different metering payload")
            raise RuntimeError(f"Supabase metering persistence failed (HTTP {response.status_code}, code={code or 'unknown'})")
        try:
            result = response.json()
        except ValueError as exc:
            raise RuntimeError("Supabase metering RPC returned a non-JSON response") from exc
        if result is not True:
            raise RuntimeError("Supabase metering RPC did not confirm durable persistence")

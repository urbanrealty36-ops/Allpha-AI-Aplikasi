"""Supabase/PostgreSQL durable sink for canonical embedding usage evidence."""
from __future__ import annotations

import os
from dataclasses import asdict

import httpx

from allpha_api.metering_contract import MeteringRecord


class SupabaseEmbeddingMeteringSink:
    """Use the same conflict-detecting Postgres RPC as text-generation metering."""

    def __init__(
        self, *, supabase_url: str, service_role_key: str,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if not supabase_url.strip() or not service_role_key.strip():
            raise ValueError("server-side Supabase URL and service-role key are required")
        self._url = supabase_url.rstrip("/") + "/rest/v1/rpc/record_agent_model_usage_metering"
        self._key = service_role_key
        self._transport = transport

    @classmethod
    def from_environment(cls) -> "SupabaseEmbeddingMeteringSink":
        return cls(
            supabase_url=os.getenv("SUPABASE_URL", ""),
            service_role_key=os.getenv("SUPABASE_SERVICE_ROLE_KEY", ""),
        )

    async def write_idempotent(self, record: MeteringRecord) -> None:
        if not record.billing_account_id:
            raise RuntimeError("durable embedding metering requires an explicit billing account")
        payload = asdict(record)
        payload["payload_fingerprint"] = record.payload_fingerprint()
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(10.0, connect=3.0), transport=self._transport,
            ) as client:
                response = await client.post(
                    self._url,
                    headers={
                        "apikey": self._key,
                        "Authorization": "Bearer " + self._key,
                        "Content-Type": "application/json",
                        "Accept": "application/json",
                    },
                    json={"p_record": payload},
                )
                response.raise_for_status()
                result = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise RuntimeError(
                "embedding usage metering could not be durably confirmed; provider replay is blocked"
            ) from exc
        if result is not True:
            raise RuntimeError("embedding metering RPC did not confirm idempotent persistence")

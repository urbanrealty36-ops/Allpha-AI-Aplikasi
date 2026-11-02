"""Durable social graph outbox consumer; effects are committed idempotently in Postgres."""
from __future__ import annotations

import asyncio
import logging
import os
import signal
import uuid
from typing import Any

import httpx

log = logging.getLogger("allpha.social_graph_outbox")


class OutboxWorker:
    def __init__(self) -> None:
        self.base = os.environ["SUPABASE_URL"].rstrip("/")
        self.key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ["SUPABASE_SECRET_KEY"]
        self.worker_id = f"social-outbox-{uuid.uuid4()}"
        self.batch_size = max(1, min(int(os.getenv("SOCIAL_OUTBOX_BATCH_SIZE", "25")), 100))
        self.lease_seconds = max(10, min(int(os.getenv("SOCIAL_OUTBOX_LEASE_SECONDS", "45")), 300))
        self.poll_seconds = max(0.5, float(os.getenv("SOCIAL_OUTBOX_POLL_SECONDS", "2")))
        self.max_attempts = max(1, min(int(os.getenv("SOCIAL_OUTBOX_MAX_ATTEMPTS", "8")), 20))
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(15.0, connect=4.0),
            headers={"apikey": self.key, "Authorization": f"Bearer {self.key}",
                     "Content-Type": "application/json", "Accept": "application/json"},
        )
        self.stopping = False

    async def rpc(self, name: str, payload: dict[str, Any]) -> Any:
        response = await self.client.post(f"{self.base}/rest/v1/rpc/{name}", json=payload)
        response.raise_for_status()
        return response.json() if response.content else None

    async def process_batch(self) -> int:
        events = await self.rpc("claim_social_graph_events", {
            "p_worker_id": self.worker_id, "p_limit": self.batch_size,
            "p_lease_seconds": self.lease_seconds,
        }) or []
        for event in events:
            event_id, token = str(event["id"]), str(event["lease_token"])
            try:
                # The database function verifies the live lease and atomically applies
                # the unique event effect plus processed state in the same transaction.
                result = await self.rpc("apply_social_graph_event_effect", {
                    "p_event_id": event_id, "p_lease_token": token,
                })
                if result is not True:
                    log.warning("outbox lease lost before effect commit event_id=%s", event_id)
            except Exception as exc:
                code = type(exc).__name__.upper()[:80]
                try:
                    state = await self.rpc("fail_social_graph_event", {
                        "p_event_id": event_id, "p_lease_token": token,
                        "p_error_code": code, "p_max_attempts": self.max_attempts,
                    })
                    log.exception("outbox effect failed event_id=%s state=%s", event_id, state)
                except Exception:
                    # Lease expiry makes the event reclaimable if failure recording is unavailable.
                    log.exception("outbox failure could not be recorded event_id=%s", event_id)
        return len(events)

    async def run(self) -> None:
        try:
            while not self.stopping:
                try:
                    count = await self.process_batch()
                except Exception:
                    log.exception("social graph outbox poll failed")
                    count = 0
                if count == 0:
                    await asyncio.sleep(self.poll_seconds)
        finally:
            await self.client.aclose()


def main() -> None:
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
    worker = OutboxWorker()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: setattr(worker, "stopping", True))
    try:
        loop.run_until_complete(worker.run())
    finally:
        loop.close()


if __name__ == "__main__":
    main()

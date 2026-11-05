"""Durable AI generation worker.

A claimed job is executed at most once. Any provider, metering, settlement, or
worker-lease uncertainty moves the job and its credit reservation to
pending_reconciliation; no automatic provider replay is allowed.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import uuid
from typing import Any

import httpx

from allpha_api.credit_ledger_service import (
    ApprovedLifecyclePolicy,
    CreditLedgerLifecycleService,
    OperationOutcome,
    ReservationReceipt,
    ReservationState,
)
from allpha_api.model_router import TextGenerationRequest
from allpha_api.supabase_credit_ledger_store import SupabaseCreditLedgerStore
from allpha_api.text_generation_adapters import build_text_generation_router_from_environment

logger = logging.getLogger("allpha.generation.worker")
_TIMEOUT = httpx.Timeout(15.0, connect=3.0)


def _database() -> tuple[str, str]:
    url = os.getenv("SUPABASE_URL", "").rstrip("/")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not key:
        raise RuntimeError("generation worker requires SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY")
    return url, key


async def _rpc(name: str, args: dict[str, Any]) -> Any:
    url, key = _database()
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            response = await client.post(
                f"{url}/rest/v1/rpc/{name}",
                headers={"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json", "Accept": "application/json"},
                json=args,
            )
            response.raise_for_status()
            return response.json() if response.content else None
    except httpx.HTTPError as exc:
        raise RuntimeError(f"generation worker RPC unavailable: {name}") from exc


async def _mark_pending(job: dict[str, Any], worker_id: str, reason: str) -> None:
    try:
        await _rpc("generation_mark_pending_reconciliation", {
            "p_job_id": job["id"], "p_lease_token": worker_id,
            "p_reason_code": reason[:100],
        })
    except Exception:
        # The lease will expire and the claim RPC will persist the unknown outcome.
        logger.warning("generation_job_pending_transition_unconfirmed job_id=%s", job.get("id"))


async def _process_job(job: dict[str, Any], worker_id: str, router: Any,
                       lifecycle: CreditLedgerLifecycleService) -> str:
    try:
        request = TextGenerationRequest(
            task_id=str(job["task_id"]),
            trace_id=str(job["trace_id"]),
            idempotency_key=str(job["idempotency_key"]),
            sensitivity=str(job["sensitivity"]),
            prompt=str(job["prompt"]),
            max_output_tokens=int(job["max_output_tokens"]),
            timeout_ms=int(job["timeout_ms"]),
            owner_id=str(job["owner_user_id"]),
            agent_id=str(job["agent_id"]),
            source_id=str(job["skill_id"]),
            source_version=int(job["source_version"]),
            billing_account_id=str(job["owner_user_id"]),
        )
    except Exception:
        await _mark_pending(job, worker_id, "generation_request_contract_invalid")
        return "pending_reconciliation"

    try:
        response, evidence = await router.generate(request)
    except Exception as exc:
        # Once a job is claimed, exceptions may happen before or after provider
        # acceptance. Keep the reservation pending; never guess or retry.
        await _mark_pending(job, worker_id, "provider_outcome_unknown:" + type(exc).__name__)
        return "pending_reconciliation"

    result = {
        "output_text": response.output_text,
        "output_sha256": hashlib.sha256(response.output_text.encode("utf-8")).hexdigest(),
        "input_tokens": response.input_tokens,
        "output_tokens": response.output_tokens,
        "cost_microunits": response.cost_microunits,
    }
    try:
        # Persist the metered result privately before settlement. The owner API
        # does not expose output until the job reaches succeeded.
        await _rpc("generation_store_provider_result", {
            "p_job_id": job["id"], "p_lease_token": worker_id, "p_result": result,
        })
        actual_units = response.input_tokens + response.output_tokens
        credits_per_unit = int(job["credits_per_usage_unit"])
        actual_credits = actual_units * credits_per_unit
        reservation = ReservationReceipt(
            reservation_id=str(job["reservation_id"]),
            idempotency_key="generation-reserve:" + str(job["task_id"]),
            account_id=str(job["owner_user_id"]),
            task_id=str(job["task_id"]),
            reserved_credits=int(job["credits_to_reserve"]),
            state=ReservationState.RESERVED,
            policy_version=str(job["policy_version"]),
            estimated_usage_units=int(job["estimated_usage_units"]),
            usage_unit=str(job["usage_unit"]),
        )
        policy = ApprovedLifecyclePolicy(
            policy_version=str(job["policy_version"]),
            approval_reference=str(job["policy_approval_reference"]),
            allow_success_settlement=bool(job["allow_success_settlement"]),
            allow_definitive_failure_release=bool(job["allow_definitive_failure_release"]),
            allow_partial_settlement=bool(job["allow_partial_settlement"]),
        )
        await lifecycle.complete(
            reservation=reservation,
            outcome=OperationOutcome.SUCCEEDED,
            policy=policy,
            idempotency_key="generation-settlement:" + str(job["task_id"]),
            source_event_id=evidence.idempotency_key,
            actual_credits=actual_credits,
            actual_usage_units=actual_units,
            usage_unit="tokens_total",
        )
        await _rpc("generation_complete_job", {
            "p_job_id": job["id"], "p_lease_token": worker_id, "p_result": result,
        })
        return "succeeded"
    except Exception as exc:
        await _mark_pending(job, worker_id, "settlement_or_completion_unknown:" + type(exc).__name__)
        return "pending_reconciliation"


async def run_once(*, batch_size: int = 5) -> int:
    router = build_text_generation_router_from_environment()
    if router is None:
        logger.info("generation_worker_idle reason=model_route_not_configured")
        return 0
    try:
        await router.preflight("private")
    except Exception:
        logger.warning("generation_worker_idle reason=model_route_preflight_failed")
        return 0

    worker_id = str(uuid.uuid4())
    jobs = await _rpc("claim_generation_jobs", {
        "p_worker_id": worker_id,
        "p_limit": max(1, min(batch_size, 20)),
        "p_lease_seconds": 300,
    })
    if not isinstance(jobs, list) or not jobs:
        return 0
    lifecycle = CreditLedgerLifecycleService(SupabaseCreditLedgerStore.from_environment())
    for job in jobs:
        if not isinstance(job, dict):
            continue
        status = await _process_job(job, worker_id, router, lifecycle)
        logger.info("generation_job_finished job_id=%s status=%s", job.get("id"), status)
    return len(jobs)


async def run_forever() -> None:
    poll_seconds = max(1, min(int(os.getenv("ALLPHA_GENERATION_WORKER_POLL_SECONDS", "5")), 60))
    batch_size = max(1, min(int(os.getenv("ALLPHA_GENERATION_WORKER_BATCH_SIZE", "5")), 20))
    while True:
        try:
            await run_once(batch_size=batch_size)
        except Exception as exc:
            logger.error("generation_worker_batch_failed error_type=%s", type(exc).__name__)
        await asyncio.sleep(poll_seconds)


def main() -> None:
    if os.getenv("ALLPHA_GENERATION_WORKER_ENABLED", "false").strip().lower() != "true":
        logger.info("generation_worker_disabled")
        return
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO").upper())
    asyncio.run(run_forever())


if __name__ == "__main__":
    main()

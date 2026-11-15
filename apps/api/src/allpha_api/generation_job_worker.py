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

from allpha_api.model_router import TextGenerationRequest
from allpha_api.generation_prompt import build_generation_prompts, snapshot_sha256
from allpha_api.text_generation_adapters import build_text_generation_router_from_environment
from allpha_api.generation_output_moderation import load_generation_output_moderator

logger = logging.getLogger("allpha.generation.worker")
_TIMEOUT = httpx.Timeout(15.0, connect=3.0)


async def _upload_private_artifact(job: dict[str, Any], output_text: str) -> tuple[str, str]:
    url, key = _database()
    path = f"{job['owner_user_id']}/{job['id']}/output.txt"
    body = output_text.encode("utf-8")
    if not body or len(body) > 10 * 1024 * 1024:
        raise RuntimeError("generation artifact size is outside the approved bound")
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(20.0, connect=3.0)) as client:
            response = await client.post(
                f"{url}/storage/v1/object/generation-artifacts/{path}",
                headers={"apikey": key, "Authorization": f"Bearer {key}",
                         "Content-Type": "text/plain; charset=utf-8", "Cache-Control": "no-store",
                         "x-upsert": "false"},
                content=body,
            )
            if response.status_code >= 400:
                raise RuntimeError("private generation artifact upload was not confirmed")
    except httpx.HTTPError as exc:
        raise RuntimeError("private generation artifact storage is unavailable") from exc
    return "generation-artifacts", path


async def _approved_moderation_policy() -> dict[str, Any] | None:
    url, key = _database()
    now = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            response = await client.get(
                f"{url}/rest/v1/generation_output_moderation_policies",
                params={"select":"policy_version,approval_reference,configuration,effective_at,expires_at",
                        "status":"eq.approved","effective_at":"lte."+now,
                        "order":"effective_at.desc","limit":"10"},
                headers={"apikey":key,"Authorization":f"Bearer {key}","Accept":"application/json"},
            )
            response.raise_for_status()
            rows=response.json()
    except (httpx.HTTPError,ValueError) as exc:
        raise RuntimeError("approved generation moderation policy is unavailable") from exc
    for row in rows if isinstance(rows,list) else []:
        expiry=row.get("expires_at")
        if expiry:
            parsed=__import__("datetime").datetime.fromisoformat(expiry.replace("Z","+00:00"))
            if parsed <= __import__("datetime").datetime.now(__import__("datetime").timezone.utc):
                continue
        if row.get("policy_version") and row.get("approval_reference") and isinstance(row.get("configuration"),dict):
            return row
    return None


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


def _build_execution_prompts(job: dict[str, Any]) -> tuple[str, str]:
    """Build prompts from the immutable Agent/Skill and ACL-filtered Knowledge snapshots."""
    agent_snapshot = job.get("agent_snapshot")
    skill_snapshot = job.get("skill_snapshot")
    if not isinstance(agent_snapshot, dict) or not isinstance(skill_snapshot, dict):
        raise ValueError("generation Agent or Skill execution snapshot is missing")
    instructions = skill_snapshot.get("instructions")
    if snapshot_sha256(agent_snapshot) != job.get("agent_snapshot_sha256"):
        raise ValueError("generation Agent identity snapshot integrity check failed")
    if snapshot_sha256(skill_snapshot) != job.get("skill_snapshot_sha256"):
        raise ValueError("generation Skill version snapshot integrity check failed")
    expected_digest = job.get("skill_instructions_sha256")
    if not isinstance(instructions, str) or not isinstance(expected_digest, str) or len(expected_digest) != 64:
        raise ValueError("generation Skill instruction snapshot is invalid")
    if hashlib.sha256(instructions.encode("utf-8")).hexdigest() != expected_digest:
        raise ValueError("generation Skill instruction snapshot integrity check failed")
    return build_generation_prompts(
        prompt=str(job["prompt"]),
        agent_snapshot=agent_snapshot,
        skill_snapshot=skill_snapshot,
        knowledge_snapshot=job.get("knowledge_snapshot") if isinstance(job.get("knowledge_snapshot"), dict) else {},
    )


async def _consumer_grant_is_current(job: dict[str, Any]) -> bool:
    """Revalidate external Agent permission immediately before any provider side effect."""
    grant_id = job.get("consumer_grant_id")
    if not grant_id:
        return True
    url, key = _database()
    now = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()
    params = {
        "select": "id,requester_user_id,owner_user_id,agent_id,agent_version,skill_id,skill_version,capability_id,granted_scopes,status,expires_at,credit_scheme_version,approval_reference,tariff_version,entitlement_version,max_usage_units,max_cost_microunits,cost_unit,pricing_version,payer_role,allow_success_settlement,allow_definitive_failure_release,allow_partial_settlement",
        "id": f"eq.{grant_id}",
        "requester_user_id": f"eq.{job.get('owner_user_id')}",
        "owner_user_id": f"eq.{job.get('agent_owner_user_id')}",
        "agent_id": f"eq.{job.get('agent_id')}",
        "skill_id": f"eq.{job.get('skill_id')}",
        "status": "eq.active",
        "granted_scopes": "cs.{generation_invoke}",
        "or": f"(expires_at.is.null,expires_at.gt.{now})",
        "limit": "1",
    }
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            response = await client.get(
                f"{url}/rest/v1/agent_consumer_grants",
                params=params,
                headers={"apikey": key, "Authorization": f"Bearer {key}", "Accept": "application/json"},
            )
            response.raise_for_status()
            rows = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise RuntimeError("external Agent grant could not be revalidated") from exc
    if not isinstance(rows, list) or len(rows) != 1:
        return False
    grant = rows[0]
    expected_payer_role = (
        "consumer" if str(job.get("payer_user_id")) == str(job.get("owner_user_id"))
        else "agent_owner" if str(job.get("payer_user_id")) == str(job.get("agent_owner_user_id"))
        else ""
    )
    checks = {
        "agent_version": job.get("agent_version"),
        "skill_version": job.get("source_version"),
        "runtime_policy_version": job.get("runtime_policy_version"),
        "capability_id": job.get("capability_id"),
        "credit_scheme_version": job.get("credit_scheme_version"),
        "approval_reference": job.get("policy_approval_reference"),
        "tariff_version": job.get("tariff_version"),
        "entitlement_version": job.get("entitlement_version"),
        "cost_unit": job.get("cost_unit"),
        "pricing_version": job.get("pricing_version"),
        "payer_role": expected_payer_role,
        "allow_success_settlement": job.get("allow_success_settlement"),
        "allow_definitive_failure_release": job.get("allow_definitive_failure_release"),
        "allow_partial_settlement": job.get("allow_partial_settlement"),
    }
    for field, expected in checks.items():
        if expected is None or grant.get(field) != expected:
            return False
    if int(grant.get("max_usage_units") or 0) < int(job.get("estimated_usage_units") or 0):
        return False
    if int(grant.get("max_cost_microunits") or 0) < int(job.get("max_cost_microunits") or 0):
        return False
    scopes = grant.get("granted_scopes") if isinstance(grant.get("granted_scopes"), list) else []
    if job.get("knowledge_context_sha256") and "knowledge_public_read" not in scopes:
        return False
    return True


async def _fail_before_provider(job: dict[str, Any], worker_id: str, reason: str) -> str:
    try:
        result = await _rpc("generation_mark_failed", {
            "p_job_id": job["id"], "p_lease_token": worker_id, "p_reason_code": reason,
        })
        if isinstance(result, dict):
            return str(result.get("status") or "pending_reconciliation")
    except Exception:
        await _mark_pending(job, worker_id, reason)
    return "pending_reconciliation"


async def _process_job(job: dict[str, Any], worker_id: str, router: Any,
                       moderator: Any, moderation_policy: dict[str, Any]) -> str:
    try:
        system_prompt, user_prompt = _build_execution_prompts(job)
        request = TextGenerationRequest(
            task_id=str(job["task_id"]),
            trace_id=str(job["trace_id"]),
            idempotency_key=str(job["idempotency_key"]),
            sensitivity=str(job["sensitivity"]),
            prompt=user_prompt,
            max_output_tokens=int(job["max_output_tokens"]),
            timeout_ms=int(job["timeout_ms"]),
            owner_id=str(job.get("payer_user_id") or job["owner_user_id"]),
            agent_id=str(job["agent_id"]),
            source_id=str(job["skill_id"]),
            source_version=int(job["source_version"]),
            billing_account_id=str(job.get("payer_user_id") or job["owner_user_id"]),
            system_prompt=system_prompt,
        )
    except Exception:
        await _mark_pending(job, worker_id, "generation_request_contract_invalid")
        return "pending_reconciliation"

    if job.get("consumer_grant_id"):
        try:
            if not await _consumer_grant_is_current(job):
                return await _fail_before_provider(job, worker_id, "consumer_grant_revoked_or_policy_changed")
        except Exception as exc:
            await _mark_pending(job, worker_id, "consumer_grant_revalidation_unknown:" + type(exc).__name__)
            return "pending_reconciliation"

    try:
        response, evidence = await router.generate(request)
    except Exception as exc:
        # Once a job is claimed, exceptions may happen before or after provider
        # acceptance. Keep the reservation pending; never guess or retry.
        await _mark_pending(job, worker_id, "provider_outcome_unknown:" + type(exc).__name__)
        return "pending_reconciliation"

    try:
        bucket, artifact_path = await _upload_private_artifact(job, response.output_text)
        result = {
            "artifact_bucket": bucket,
            "artifact_path": artifact_path,
            "output_sha256": hashlib.sha256(response.output_text.encode("utf-8")).hexdigest(),
            "input_tokens": response.input_tokens,
            "output_tokens": response.output_tokens,
            "cost_microunits": response.cost_microunits,
        }
        await _rpc("generation_store_provider_result", {
            "p_job_id": job["id"], "p_lease_token": worker_id, "p_result": result,
        })
        verdict = await moderator.moderate(
            text=response.output_text,
            policy=moderation_policy.get("configuration") or {},
            metadata={"job_id": str(job["id"]), "agent_id": str(job["agent_id"]),
                      "skill_id": str(job["skill_id"]), "trace_id": str(job["trace_id"])},
        )
        decision = str(verdict.get("decision") or "")
        if decision not in {"approved", "rejected", "review_required"}:
            await _mark_pending(job, worker_id, "generation_moderation_verdict_invalid")
            return "pending_reconciliation"
        await _rpc("generation_record_output_moderation", {
            "p_job_id": job["id"], "p_lease_token": worker_id,
            "p_decision": decision,
            "p_policy_version": moderation_policy["policy_version"],
            "p_approval_reference": moderation_policy["approval_reference"],
        })
        if decision != "approved":
            await _mark_pending(job, worker_id, "generation_output_moderation_" + decision)
            return "pending_reconciliation"
    except Exception as exc:
        await _mark_pending(job, worker_id, "artifact_or_moderation_unknown:" + type(exc).__name__)
        return "pending_reconciliation"

    try:
        completion_result = {**result, "source_event_id": evidence.idempotency_key}
        # Payer debit, policy-approved Agent-owner credit, DM receipt and terminal
        # job transition are committed by one PostgreSQL function transaction.
        await _rpc("generation_complete_job", {
            "p_job_id": job["id"], "p_lease_token": worker_id, "p_result": completion_result,
        })
        return "succeeded"
    except Exception as exc:
        # Recover a lost response after a committed completion without replaying a provider call.
        try:
            rows = await _admin_get_job_status(str(job["id"]))
            if rows and rows[0].get("status") == "succeeded":
                return "succeeded"
        except Exception:
            pass
        await _mark_pending(job, worker_id, "settlement_or_completion_unknown:" + type(exc).__name__)
        return "pending_reconciliation"


async def _admin_get_job_status(job_id: str) -> list[dict[str, Any]]:
    url, key = _database()
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            response = await client.get(
                f"{url}/rest/v1/generation_jobs",
                params={"select":"status", "id":f"eq.{job_id}", "limit":"1"},
                headers={"apikey":key,"Authorization":f"Bearer {key}","Accept":"application/json"},
            )
            response.raise_for_status()
            rows = response.json()
            return rows if isinstance(rows, list) else []
    except (httpx.HTTPError, ValueError) as exc:
        raise RuntimeError("generation completion status could not be recovered") from exc


async def run_once(*, batch_size: int = 5) -> int:
    router = build_text_generation_router_from_environment()
    if router is None:
        logger.info("generation_worker_idle reason=model_route_not_configured")
        return 0
    moderator = load_generation_output_moderator()
    moderation_policy = await _approved_moderation_policy()
    if moderator is None or moderation_policy is None:
        logger.info("generation_worker_idle reason=output_moderation_not_approved_or_configured")
        return 0
    worker_id = str(uuid.uuid4())
    jobs = await _rpc("claim_generation_jobs", {
        "p_worker_id": worker_id,
        "p_limit": max(1, min(batch_size, 20)),
        "p_lease_seconds": 300,
    })
    if not isinstance(jobs, list) or not jobs:
        return 0
    for job in jobs:
        if not isinstance(job, dict):
            continue
        status = await _process_job(job, worker_id, router, moderator, moderation_policy)
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

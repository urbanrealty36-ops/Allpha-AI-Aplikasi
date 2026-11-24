"""Durable polling worker for canonical Agent Runtime tool-plan tasks.

Only registered pure tools are executed here. Task claims, checkpoints, leases,
policy checks and finalization remain in AgentRuntimeStore and the shared runtime.
"""
from __future__ import annotations

import asyncio
import logging
import os
import signal
from fastapi import HTTPException

from allpha_api.agent_runtime_api import _execute_native_orchestration_task, _execute_planned_task, _is_native_orchestration_task
from allpha_api.agent_social_automation_runtime import (
    execute_agent_social_reply_task, is_agent_social_reply_task,
    reconcile_social_reply_approvals, run_social_events_once,
)
from allpha_api.text_generation_adapters import build_text_generation_router_from_environment
from allpha_api.agent_runtime_store import AgentRuntimePersistenceError, AgentRuntimeStore

logger = logging.getLogger("allpha.agent_runtime_worker")


def _enabled() -> bool:
    return os.getenv("ALLPHA_AGENT_RUNTIME_WORKER_ENABLED", "false").lower() == "true"


def _poll_seconds() -> float:
    try:
        value = float(os.getenv("ALLPHA_AGENT_RUNTIME_WORKER_POLL_SECONDS", "2"))
    except ValueError:
        value = 2.0
    return max(0.5, min(value, 30.0))


def _batch_size() -> int:
    try:
        value = int(os.getenv("ALLPHA_AGENT_RUNTIME_WORKER_BATCH_SIZE", "5"))
    except ValueError:
        value = 5
    return max(1, min(value, 25))


async def _social_schema_ready(store: AgentRuntimeStore) -> bool:
    """Fail closed for WP-06 until its own tables, RPCs, RLS and grants are ready."""
    enabled = (
        os.getenv("ALLPHA_AGENT_SOCIAL_AUTOMATION_SCHEMA_ENABLED", "false").lower() == "true"
        and os.getenv("ALLPHA_AGENT_SOCIAL_AUTOMATION_WORKER_ENABLED", "false").lower() == "true"
    )
    if not enabled:
        return False
    try:
        result = await store.request("POST", "rpc/agent_social_automation_schema_readiness", body={})
    except AgentRuntimePersistenceError:
        logger.warning("WP-06 Social consumer remains idle; schema readiness RPC is unavailable")
        return False
    if isinstance(result, list):
        result = result[0] if result and isinstance(result[0], dict) else {}
    if not isinstance(result, dict) or result.get("ready") is not True:
        logger.warning(
            "WP-06 Social consumer remains idle; missing_tables=%s missing_columns=%s missing_functions=%s missing_privileges=%s",
            (result or {}).get("missing_tables", []) if isinstance(result, dict) else [],
            (result or {}).get("missing_columns", []) if isinstance(result, dict) else [],
            (result or {}).get("missing_functions", []) if isinstance(result, dict) else [],
            (result or {}).get("missing_privileges", []) if isinstance(result, dict) else [],
        )
        return False
    return True


def _consumer_enabled(name: str, gate) -> bool:
    """An invalid optional consumer gate must not disable unrelated worker domains."""
    try:
        return bool(gate())
    except SystemExit as exc:
        logger.error("%s consumer disabled by invalid configuration: %s", name, exc)
        return False
    except Exception:
        logger.exception("%s consumer gate failed; consumer remains disabled", name)
        return False


async def _serve_consumer_isolated(name: str, consumer) -> None:
    """Keep one optional consumer's startup/config failure from cancelling siblings."""
    try:
        await consumer
    except asyncio.CancelledError:
        raise
    except BaseException as exc:
        # SystemExit may be raised by a consumer's strict environment validation.
        logger.error(
            "%s consumer stopped during startup/runtime; sibling consumers remain active: %s",
            name, type(exc).__name__,
            exc_info=(type(exc), exc, exc.__traceback__),
        )


def _concurrency() -> int:
    """Bound parallel task execution; each task still obtains its own DB lease."""
    try:
        value = int(os.getenv("ALLPHA_AGENT_RUNTIME_WORKER_CONCURRENCY", "3"))
    except ValueError:
        value = 3
    return max(1, min(value, 10))


async def _process_runnable_task(
    store: AgentRuntimeStore, row: dict[str, Any],
) -> tuple[int, bool]:
    """Execute one independently lease-fenced task; return (processed, stop_batch)."""
    owner_id, task_id = row.get("owner_user_id"), row.get("id")
    if not isinstance(owner_id, str) or not isinstance(task_id, str):
        logger.error("Skipping malformed runtime task envelope")
        return 0, False

    if row.get("effect_outcome") in {"started", "unknown"} and _is_native_orchestration_task(row):
        try:
            await store.mark_unknown_effect(owner_id, task_id)
            return 1, False
        except AgentRuntimePersistenceError:
            logger.exception(
                "Could not terminalize native task with unknown non-reconcilable effect; task_id=%s",
                task_id,
            )
            return 0, True

    # Each executor claims through the canonical Postgres lease RPC before doing work.
    # Planned Social effects are reconciled by their lease-owning executor before retry.
    try:
        if is_agent_social_reply_task(row):
            await execute_agent_social_reply_task(
                store, owner_id, task_id, row,
                build_text_generation_router_from_environment(),
            )
        elif _is_native_orchestration_task(row):
            await _execute_native_orchestration_task(store, owner_id, task_id, row)
        else:
            await _execute_planned_task(store, owner_id, task_id, row)
        return 1, False
    except HTTPException as exc:
        detail = exc.detail if isinstance(exc.detail, dict) else {}
        code = str(detail.get("code") or "RUNTIME_TASK_REJECTED")
        if row.get("cancel_requested") is True:
            logger.info("Runtime task cancellation remains pending; task_id=%s code=%s", task_id, code)
            return 1, False
        if is_agent_social_reply_task(row) and code == "SOCIAL_PROVIDER_OUTCOME_UNKNOWN":
            logger.warning(
                "WP-06 provider outcome is unknown; reservation is held for reconciliation; task_id=%s",
                task_id,
            )
            return 1, False
        try:
            latest_getter = getattr(store, "get_task", None)
            latest = await latest_getter(owner_id, task_id) if callable(latest_getter) else None
            if latest and latest.get("state") in {
                "succeeded", "partially_succeeded", "failed", "cancelled", "timed_out", "budget_exhausted",
            }:
                return 1, False
            if row.get("state") in {"created", "queued", "retrying", "executing"}:
                await store.fail_unclaimed_task(
                    owner_id, task_id, int(row.get("task_version") or 1), code,
                    lease_token=row.get("execution_lease_token"),
                )
        except AgentRuntimePersistenceError:
            logger.exception("Could not reconcile rejected runtime task; task_id=%s", task_id)
            return 0, True
        logger.info(
            "Runtime task not completed; task_id=%s status=%s code=%s",
            task_id, exc.status_code, code,
        )
        return 1, False
    except AgentRuntimePersistenceError:
        # Outcome may be uncertain. Stop admitting more work in this batch; the
        # canonical lease/recovery contract decides what already-running tasks do.
        logger.exception("Runtime persistence uncertain; stopping batch at task_id=%s", task_id)
        return 0, True
    except Exception:
        logger.exception("Unexpected runtime worker failure; task_id=%s", task_id)
        return 0, True


async def run_once(store: AgentRuntimeStore) -> int:
    """Process a bounded, schema-gated batch with bounded concurrent lease-fenced tasks."""
    readiness = await store.runtime_schema_readiness()
    if readiness.get("ready") is not True:
        logger.error(
            "Agent Runtime worker remains idle; missing_tables=%s missing_columns=%s missing_functions=%s missing_privileges=%s",
            readiness.get("missing_tables") or [],
            readiness.get("missing_columns") or [],
            readiness.get("missing_functions") or [],
            readiness.get("missing_privileges") or [],
        )
        return 0
    await store.reap_retry_exhaustion()
    social_ready = await _social_schema_ready(store)
    if social_ready:
        try:
            await run_social_events_once(store, limit=_batch_size())
            await reconcile_social_reply_approvals(store, limit=_batch_size())
        except AgentRuntimePersistenceError:
            logger.exception("WP-06 Social intake or approval reconciliation unavailable")

    rows = await store.list_runnable_planned_tasks(limit=_batch_size())
    if not social_ready:
        rows = [row for row in rows if not is_agent_social_reply_task(row)]
    processed = 0
    concurrency = _concurrency()
    # Process bounded groups. If one group encounters uncertain persistence,
    # wait for its in-flight tasks to settle before admitting another group.
    for offset in range(0, len(rows), concurrency):
        group = rows[offset:offset + concurrency]
        outcomes = await asyncio.gather(*(
            _process_runnable_task(store, row) for row in group
        ))
        processed += sum(count for count, _ in outcomes)
        if any(stop_batch for _, stop_batch in outcomes):
            break

    if social_ready:
        try:
            await reconcile_social_reply_approvals(store, limit=_batch_size())
        except AgentRuntimePersistenceError:
            logger.exception("WP-06 post-batch approval reconciliation unavailable")
    return processed


async def _wait_for_stop(stop_event: asyncio.Event, interval: float) -> None:
    try:
        await asyncio.wait_for(stop_event.wait(), timeout=interval)
    except asyncio.TimeoutError:
        pass


async def _serve_runtime_enabled(stop_event: asyncio.Event) -> None:
    store = AgentRuntimeStore.from_environment()
    interval = _poll_seconds()
    logger.info("Agent Runtime worker started; poll_seconds=%s batch_size=%s", interval, _batch_size())
    while not stop_event.is_set():
        try:
            await run_once(store)
        except AgentRuntimePersistenceError:
            logger.exception("Agent Runtime worker persistence unavailable")
        except Exception:
            logger.exception("Agent Runtime worker loop failed")
        if not stop_event.is_set():
            await _wait_for_stop(stop_event, interval)


async def serve() -> None:
    """Host independently gated runtime, workflow and Knowledge consumers in one process."""
    from allpha_api import workflow_worker_host, knowledge_ingestion_worker, knowledge_worker

    runtime_enabled = _consumer_enabled("Agent Runtime", _enabled)
    workflow_enabled = _consumer_enabled("Workflow", workflow_worker_host.enabled)
    knowledge_documents_enabled = _consumer_enabled("Knowledge document", knowledge_ingestion_worker.enabled)
    knowledge_embeddings_enabled = _consumer_enabled("Knowledge embedding", knowledge_worker.enabled)
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop_event.set)
        except (NotImplementedError, RuntimeError):
            logger.debug("Worker signal handler unavailable for %s", sig.name)

    consumers: list[asyncio.Task[Any]] = []
    if runtime_enabled:
        consumers.append(asyncio.create_task(
            _serve_consumer_isolated("Agent Runtime", _serve_runtime_enabled(stop_event)),
            name="agent-runtime-worker",
        ))
    if workflow_enabled:
        consumers.append(asyncio.create_task(
            _serve_consumer_isolated("Workflow", workflow_worker_host.serve_enabled(stop_event=stop_event)),
            name="workflow-worker",
        ))
    if knowledge_documents_enabled:
        consumers.append(asyncio.create_task(
            _serve_consumer_isolated(
                "Knowledge document", knowledge_ingestion_worker.serve_enabled(stop_event=stop_event),
            ),
            name="knowledge-document-ingestion-worker",
        ))
    if knowledge_embeddings_enabled:
        consumers.append(asyncio.create_task(
            _serve_consumer_isolated(
                "Knowledge embedding", knowledge_worker.serve_enabled(stop_event=stop_event),
            ),
            name="knowledge-embedding-worker",
        ))

    if not consumers:
        logger.warning(
            "Allpha worker container is healthy but idle; Agent Runtime, Workflow and Knowledge consumers are disabled"
        )
        await stop_event.wait()
        return

    logger.info(
        "Allpha shared worker host started; agent_runtime=%s workflow=%s knowledge_documents=%s knowledge_embeddings=%s",
        runtime_enabled, workflow_enabled, knowledge_documents_enabled, knowledge_embeddings_enabled,
    )
    await asyncio.gather(*consumers)


def main() -> None:
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO").upper())
    asyncio.run(serve())


if __name__ == "__main__":
    main()

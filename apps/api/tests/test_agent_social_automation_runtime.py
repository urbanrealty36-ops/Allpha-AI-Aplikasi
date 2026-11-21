import asyncio
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src/allpha_api"


def test_wp06_event_consumer_dispatches_only_to_canonical_runtime_and_model_router():
    source = (SRC / "agent_social_automation_runtime.py").read_text()
    store = (SRC / "agent_runtime_store.py").read_text()
    worker = (SRC / "agent_runtime_worker.py").read_text()
    assert "claim_agent_social_automation_events" in source
    assert "heartbeat_agent_social_automation_event" in source
    assert "complete_agent_social_automation_event" in source
    assert "find_task_by_idempotency" in source
    assert "AgentRuntime().execute_skill_generation" in source
    assert "build_text_generation_router_from_environment" in source
    assert "_agent_social_reply_version" in source
    assert "agent.social_auto_reply" in source
    assert "_agent_social_reply_version.eq.1" in store
    assert "execute_agent_social_reply_task" in worker
    assert "run_social_events_once" in worker
    assert "reconcile_social_reply_approvals" in worker


def test_wp06_runtime_pins_acl_memory_policy_model_and_skill_context():
    source = (SRC / "agent_social_automation_runtime.py").read_text()
    assert "social_policy_version" in source
    assert "automation_grant_id" in source
    assert "action_capability_snapshot" in source
    assert "route_snapshot" in source
    assert "context_snapshot_sha256" in source
    assert "memory_context_refs" in source
    assert "MemoryCoordinator().retrieve_context" in source
    assert "SOCIAL_BLOCK_EDGE_ACTIVE" in source
    assert "SOCIAL_CONTENT_PRIVACY_OR_LIFECYCLE_DENIED" in source
    assert "SOCIAL_QUIET_HOURS_ACTIVE" in source
    assert "SOCIAL_RATE_LIMIT_EXCEEDED" in source
    assert "SOCIAL_ESCALATION_REQUIRED" in source


def test_wp06_reservation_settlement_and_daily_budget_use_canonical_credit_ledger():
    source = (SRC / "agent_social_automation_runtime.py").read_text()
    store = (SRC / "supabase_credit_ledger_store.py").read_text()
    migrations = ROOT / "supabase/source-only-migrations"
    migration = next(migrations.glob("*wp06*social*credit*budget*.sql"))
    sql = migration.read_text()
    assert "CreditLedgerLifecycleService" in source
    assert "credit_ledger_reserve_agent_social_auto_reply" in store
    assert "credit_ledger_reserve_agent_social_auto_reply" in sql
    assert "public.credit_ledger_reserve(" in sql
    assert "SOCIAL_DAILY_CREDIT_BUDGET_EXCEEDED" in sql
    assert "for update" in sql.lower()
    assert "OperationOutcome.UNKNOWN" in source
    assert "mark_pending" in (SRC / "credit_ledger_service.py").read_text()


def test_wp06_social_outputs_are_moderated_and_require_canonical_owner_approval():
    source = (SRC / "agent_social_automation_runtime.py").read_text()
    assert "load_generation_output_moderator" in source
    assert '"manual_review_only": True' in source
    assert "rpc/request_agent_social_draft" in source
    assert '"status": "awaiting_approval"' in source


def test_wp06_dm_uses_canonical_message_approval_and_receipt_adapter():
    source = (SRC / "agent_social_automation_runtime.py").read_text()
    runtime_api = (SRC / "agent_runtime_api.py").read_text()
    adapter = (SRC / "agent_social_side_effect_adapter.py").read_text()
    assert '"dm": ("social.reply", "draft_reply")' in source
    assert "request_agent_social_message_draft" in source
    assert "target_conversation_id" in source and "target_message_id" in source
    assert 'target_reference = "conversation:"' in runtime_api
    assert "execute_agent_social_message_approval_effect" in adapter
    assert "SOCIAL_DM_PARTICIPANT_ACL_FAILED" in source
    assert "SOCIAL_DM_SOURCE_MESSAGE_STALE" in source


def test_wp06_live_chat_fails_closed_until_eng_p25_agent_session_permission_exists():
    source = (SRC / "agent_social_automation_runtime.py").read_text()
    assert "ENG_P25_LIVE_AGENT_PARTICIPANT_AUTHORITY_NOT_AVAILABLE" in source
    assert "live_chat" in source


def test_wp06_owner_api_exposes_events_runs_and_ledger_budget():
    source = (SRC / "agent_social_api.py").read_text()
    assert '"/automation/{agent_id}/events"' in source
    assert '"/automation/{agent_id}/runs"' in source
    assert '"/automation/{agent_id}/budget"' in source
    assert "SupabaseCreditLedgerStore.from_environment().get_balance" in source


def test_wp06_event_intake_serializes_rate_limit_count_and_insert():
    migration = ROOT / "supabase/source-only-migrations/20261122100000_wp06_social_event_intake_rate_serialization.sql"
    sql = migration.read_text().lower()
    lock = sql.index("pg_advisory_xact_lock")
    count = sql.index("select greatest(0,count(*)::integer-v_policy.max_replies_per_minute+1)")
    insert = sql.index("insert into public.agent_social_automation_events")
    assert lock < count < insert
    assert "p_channel='comments' and p_source_table<>'content_comments'" in sql
    assert "p_channel='mentions' and p_source_table<>'content_mentions'" in sql
    assert "p_channel in ('dm','live_chat') and p_source_table<>'messages'" in sql
    assert "on conflict(owner_user_id,agent_id,channel,source_table,source_record_id) do nothing" in sql



def test_wp06_event_heartbeat_fails_closed_when_lease_renewal_is_uncertain():
    from allpha_api.agent_social_automation_runtime import _event_heartbeat

    class FailingHeartbeatStore:
        async def request(self, method, path, *, body):
            raise RuntimeError("heartbeat transport unavailable")

    stop = asyncio.Event()
    lease_lost = asyncio.Event()
    asyncio.run(_event_heartbeat(
        FailingHeartbeatStore(), "event-1", "claim-1", stop, lease_lost,
        interval_seconds=0,
    ))
    assert lease_lost.is_set()



def test_wp06_task_heartbeat_fails_closed_when_lease_renewal_is_uncertain():
    from allpha_api.agent_social_automation_runtime import _task_heartbeat
    from allpha_api.agent_runtime_store import AgentRuntimePersistenceError

    class FailingTaskHeartbeatStore:
        async def heartbeat_task(self, *args, **kwargs):
            raise AgentRuntimePersistenceError("heartbeat transport unavailable")

    stop = asyncio.Event()
    lease_lost = asyncio.Event()
    cancellation_requested = asyncio.Event()
    asyncio.run(_task_heartbeat(
        FailingTaskHeartbeatStore(), "owner-1", "task-1", "lease-1", 1,
        stop, lease_lost, cancellation_requested, interval_seconds=0,
    ))
    assert lease_lost.is_set()
    assert not cancellation_requested.is_set()


def test_wp06_task_heartbeat_surfaces_canonical_cancellation_request():
    from allpha_api.agent_social_automation_runtime import _task_heartbeat

    class CancelledTaskHeartbeatStore:
        async def heartbeat_task(self, *args, **kwargs):
            return {"id": "task-1", "cancel_requested": True}

    stop = asyncio.Event()
    lease_lost = asyncio.Event()
    cancellation_requested = asyncio.Event()
    asyncio.run(_task_heartbeat(
        CancelledTaskHeartbeatStore(), "owner-1", "task-1", "lease-1", 1,
        stop, lease_lost, cancellation_requested, interval_seconds=0,
    ))
    assert cancellation_requested.is_set()
    assert not lease_lost.is_set()

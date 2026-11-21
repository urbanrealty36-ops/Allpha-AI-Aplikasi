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


def test_wp06_message_channels_fail_closed_until_wp07_messaging_receipt_adapter_exists():
    source = (SRC / "agent_social_automation_runtime.py").read_text()
    assert "WP07_MESSAGE_APPROVAL_ADAPTER_NOT_IMPLEMENTED" in source
    assert "live_chat" in source and "dm" in source


def test_wp06_owner_api_exposes_events_runs_and_ledger_budget():
    source = (SRC / "agent_social_api.py").read_text()
    assert '"/automation/{agent_id}/events"' in source
    assert '"/automation/{agent_id}/runs"' in source
    assert '"/automation/{agent_id}/budget"' in source
    assert "SupabaseCreditLedgerStore.from_environment().get_balance" in source

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_wp06_social_event_intake_migration_is_durable_and_fail_closed():
    migration = ROOT / "supabase" / "source-only-migrations" / "20261121130000_wp06_social_event_intake_claims.sql"
    source = migration.read_text()
    for token in (
        "agent_social_automation_events",
        "content_comments_agent_automation_event",
        "content_mentions_agent_automation_event",
        "messages_agent_automation_event",
        "claim_agent_social_automation_events",
        "heartbeat_agent_social_automation_event",
        "complete_agent_social_automation_event",
        "fail_agent_social_automation_event",
        "cancel_agent_social_automation_events",
        "for update skip locked",
        "auto_reply_skill_id",
        "takeover_active",
        "agent_social_automation_grants",
        "live_sessions",
        "live_participants",
    ):
        assert token in source.lower()


def test_wp06_event_store_reuses_canonical_agent_runtime_persistence():
    source = (ROOT / "src" / "allpha_api" / "agent_social_event_store.py").read_text()
    assert "AgentRuntimeStore" in source
    assert "agent_runtime_tasks" not in source
    assert "claim_agent_social_automation_events" in source
    assert "mark_dispatched" in source
    assert "heartbeat" in source
    assert "fail_agent_social_automation_event" in source

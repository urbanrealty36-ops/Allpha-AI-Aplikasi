from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_wp03_outbox_worker_uses_database_leases_and_idempotent_effect_rpc():
    source = (ROOT / "src/allpha_api/social_graph_outbox_worker.py").read_text(encoding="utf-8")
    assert '"claim_social_graph_events"' in source
    assert '"apply_social_graph_event_effect"' in source
    assert '"fail_social_graph_event"' in source
    assert '"p_lease_token": token' in source
    assert '"p_max_attempts": self.max_attempts' in source
    assert "self.batch_size = max(1, min(int(os.getenv(\"SOCIAL_OUTBOX_BATCH_SIZE\", \"25\")), 100))" in source
    assert "self.lease_seconds = max(10, min(int(os.getenv(\"SOCIAL_OUTBOX_LEASE_SECONDS\", \"45\")), 300))" in source


def test_wp03_effect_invalidates_snapshots_for_both_graph_participants_once():
    migration = ROOT / "supabase/migrations/20261102015102_wp03_invalidate_both_graph_participants.sql"
    sql = migration.read_text(encoding="utf-8").lower()
    assert "where id=p_event_id" in sql
    assert "lease_token=p_lease_token" in sql
    assert "lease_expires_at>now()" in sql
    assert "insert into public.social_graph_event_effects" in sql
    assert "on conflict(event_id) do nothing" in sql
    assert "viewer_user_id in (v_event.actor_user_id,v_event.target_user_id)" in sql
    assert "invalidated_at=coalesce(invalidated_at,now())" in sql
    assert "delivery_state='processed'" in sql

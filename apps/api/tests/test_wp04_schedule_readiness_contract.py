from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_wp04_schedule_functions_enforce_identical_media_readiness_and_policy():
    migration = ROOT / "supabase/migrations/20261105120000_wp04_schedule_media_readiness_guard.sql"
    sql = migration.read_text(encoding="utf-8").lower()
    # Each function rejects media that fails any one of the same readiness predicates.
    assert sql.count("m.status<>'ready'") == 2
    assert sql.count("m.scan_status<>'clean'") == 2
    assert sql.count("m.processed_at is null") == 2
    assert sql.count("jsonb_array_length") == 2
    assert sql.count("jsonb_typeof(m.derivatives) is distinct from 'array'") == 2
    assert "v_content.moderation_status<>'approved'" in sql
    assert "p_rights_confirmed" in sql and "p_disclosure_confirmed" in sql
    assert "p_expected_version" in sql
    assert "lease_token" in sql and "lease_expires_at" in sql
    assert "revoke all on function public.create_content_schedule" in sql
    assert "revoke all on function public.publish_scheduled_content" in sql
    assert "to service_role" in sql


def test_wp04_cron_connects_all_existing_lifecycle_workers_with_bounded_batches():
    source = (ROOT / "src/allpha_api/wp04_vercel_cron.py").read_text(encoding="utf-8")
    for worker in ("ContentScheduler", "MediaWorker", "TranscodeWorker", "CallbackWorker", "CleanupWorker", "RetentionWorker"):
        assert worker in source
    assert 'getattr(worker, "batch", None) or getattr(worker, "process_batch", None)' in source
    assert '"max_jobs_per_worker": 1' in source
    assert "CLAMAV_HOST" in source
    for gate in ("CONTENT_RETENTION_PURGE_ENABLED", "CONTENT_RETENTION_BACKUP_VERIFIED",
                 "CONTENT_RETENTION_RESTORE_DRILL_VERIFIED", "CONTENT_RETENTION_LEGAL_HOLD_VERIFIED",
                 "CONTENT_RETENTION_APPROVAL_VERIFIED"):
        assert gate in source

from pathlib import Path

MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "supabase"
    / "migrations"
    / "20261016100000_eng_p11_worker_lifecycle_hardening.sql"
).read_text(encoding="utf-8")


def test_worker_rpc_functions_are_service_only():
    for function in ("timeout_workflow_run", "claim_workflow_step", "finalize_workflow_step"):
        assert f"function public.{function}(" in MIGRATION
        assert f"grant execute on function public.{function}" in MIGRATION
        assert f"from public, anon, authenticated;" in MIGRATION


def test_expired_lease_retry_exhaustion_is_terminal_and_observable():
    assert "s.lease_expires_at < now()" in MIGRATION
    assert "attempts >= max_attempts" in MIGRATION
    assert "LEASE_EXPIRED_RETRY_EXHAUSTED" in MIGRATION
    assert "'step_failed'" in MIGRATION
    assert "'run_failed'" in MIGRATION


def test_terminal_run_cannot_be_finalized_and_cancellation_fences_lease():
    assert "run_row.status not in ('queued','running') or run_row.cancel_requested" in MIGRATION
    assert "step_row.lease_token is distinct from p_lease_token" in MIGRATION
    assert "step_row.lease_expires_at <= now()" in MIGRATION


def test_run_timeout_cancels_unfinished_steps_atomically():
    assert "status = 'timed_out'" in MIGRATION
    assert "error_code = 'RUN_TIMED_OUT'" in MIGRATION
    assert "'run_timed_out'" in MIGRATION


def test_migration_is_source_only():
    assert "Source-only migration" in MIGRATION
    assert "not authorization to mutate canonical production" in MIGRATION

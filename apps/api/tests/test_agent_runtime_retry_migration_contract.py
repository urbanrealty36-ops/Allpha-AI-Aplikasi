from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase" / "source-only-migrations" / "20261118195000_wp07_durable_retry_attempts.sql"


def test_retry_migration_is_one_complete_transaction_with_fenced_rpcs():
    sql = MIGRATION.read_text(encoding="utf-8")
    assert sql.count("begin;") == 1
    assert sql.count("commit;") == 1
    assert sql.rstrip().endswith("commit;")
    assert "p_error_code !~ '^[A-Z0-9_]{1,80}$' then" in sql
    assert "fail_unclaimed_agent_runtime_task(uuid,uuid,integer,text,uuid)" in sql
    assert "grant execute on function public.fail_unclaimed_agent_runtime_task(uuid,uuid,integer,text,uuid) to service_role;" in sql
    assert "v_task.cancel_requested then" in sql
    assert "coalesce(v_task.effect_outcome,'none') in ('started','unknown')" in sql
    assert "next_attempt_at=now()+make_interval(secs=>p_retry_after_seconds)" in sql



def test_worker_readiness_migration_checks_schema_and_service_role_access():
    readiness = ROOT / "supabase" / "source-only-migrations" / "20261118195500_wp07_runtime_worker_schema_readiness.sql"
    sql = readiness.read_text(encoding="utf-8")
    assert sql.count("begin;") == 1
    assert sql.count("commit;") == 1
    assert "agent_runtime_tool_plans" in sql
    assert "agent_runtime_checkpoints" in sql
    assert "has_table_privilege('service_role'" in sql
    assert "has_function_privilege('service_role'" in sql
    assert "agent_runtime_worker_schema_readiness()" in sql

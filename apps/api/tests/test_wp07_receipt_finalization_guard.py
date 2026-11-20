from pathlib import Path


MIGRATION = (
    Path(__file__).parents[1] / "supabase" / "source-only-migrations"
    / "20261121100000_wp07_success_receipt_finalization_guard.sql"
)


def test_task_success_requires_resolved_effect_receipts_and_approved_social_step_evidence():
    sql = " ".join(MIGRATION.read_text().lower().split())
    assert "create or replace function public.guard_agent_runtime_task_success_receipts()" in sql
    assert "old.effect_outcome, 'none') in ('started','unknown')" in sql
    assert "r.status <> 'completed'" in sql
    assert "jsonb_array_elements(v_steps)" in sql
    assert "r.actor_user_id = new.owner_user_id" in sql
    assert "r.approval_id is not null" in sql
    assert "r.provider_key = 'allpha.social'" in sql
    assert "agent_runtime_task_success_receipt_guard" in sql
    assert "grant execute on function public.agent_runtime_effect_receipt_guard_readiness()" in sql


def test_receipt_guard_migration_is_transactional_and_non_destructive():
    sql = MIGRATION.read_text().lower()
    assert sql.strip().startswith("-- wp-07")
    assert "begin;" in sql and sql.strip().endswith("commit;")
    assert "drop table" not in sql
    assert "truncate " not in sql


def test_worker_receipt_rpc_requires_prior_owner_approval_and_never_approves_itself():
    migration = (
        Path(__file__).parents[1] / "supabase" / "source-only-migrations"
        / "20261121110000_wp07_require_owner_approved_social_result.sql"
    )
    sql = migration.read_text().lower()
    function = sql.split(
        "create or replace function public.execute_agent_social_approval_effect(", 1
    )[1]
    assert "v_approval.status <> 'approved'" in function
    assert "v_execution := v_approval.execution_result" in function
    assert "public.decide_agent_social_approval(" not in function
    assert "agent_social_approved_execution_result_invalid" in function

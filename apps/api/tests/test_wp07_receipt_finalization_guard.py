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

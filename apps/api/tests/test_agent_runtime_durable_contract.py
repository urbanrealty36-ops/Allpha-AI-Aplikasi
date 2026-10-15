from pathlib import Path


MIGRATION = Path(__file__).parents[1] / "supabase" / "migrations" / "20261015170000_eng_p10_durable_checkpoints_policy_registry.sql"


def test_durable_runtime_contract_has_leased_checkpoints_effect_receipts_and_policy_registry():
    sql = " ".join(MIGRATION.read_text().lower().split())
    assert "create table if not exists public.agent_runtime_policies" in sql
    assert "create table if not exists public.agent_runtime_checkpoints" in sql
    assert "create table if not exists public.agent_runtime_effect_receipts" in sql
    assert "unique (task_id, step_key, idempotency_key)" in sql
    assert "input_fingerprint text not null" in sql
    assert "create or replace function public.claim_agent_runtime_task" in sql
    assert "create or replace function public.append_agent_runtime_checkpoint" in sql
    assert "create or replace function public.begin_agent_runtime_effect" in sql
    assert "create or replace function public.complete_agent_runtime_effect" in sql
    assert "create or replace function public.finalize_agent_runtime_task" in sql
    assert "create or replace function public.mark_agent_runtime_effect_unknown" in sql
    assert "execution_lease_token is distinct from p_lease_token" in sql
    assert "task_row.task_version <> p_task_version" in sql
    assert "revoke all on public.agent_runtime_policies, public.agent_runtime_checkpoints" in sql
    assert "grant execute on function public.claim_agent_runtime_task" in sql
    assert "create trigger agent_runtime_policy_immutable" in sql


def test_durable_runtime_migration_is_source_only_and_non_destructive():
    sql = MIGRATION.read_text().lower()
    assert "drop table" not in sql
    assert "insert into public.agent_runtime_tasks" not in sql
    assert "update public.agent_runtime_tasks" not in sql

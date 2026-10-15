from pathlib import Path


MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "supabase"
    / "migrations"
    / "20261015130000_eng_p09_durable_credit_ledger.sql"
)


def test_credit_ledger_migration_is_versioned_and_has_no_financial_defaults():
    sql = MIGRATION.read_text(encoding="utf-8").lower()
    assert "create table public.credit_policy_versions" in sql
    assert "create table public.credit_ledger_entries" in sql
    assert "create table public.credit_reservations" in sql
    assert "create table public.credit_balance_projection" in sql
    assert "create table public.credit_reconciliation_events" in sql
    assert "insert into public.credit_policy_versions" not in sql
    assert "financial phase" in sql


def test_credit_ledger_mutations_are_server_only_and_append_only():
    sql = MIGRATION.read_text(encoding="utf-8").lower()
    for table in (
        "credit_policy_versions", "credit_ledger_accounts", "credit_ledger_entries",
        "credit_reservations", "credit_balance_projection", "credit_reconciliation_events",
    ):
        assert f"alter table public.{table} enable row level security" in sql
    assert "from public, anon, authenticated, service_role" in sql
    assert "to service_role" in sql
    assert "credit_ledger_entries_append_only" in sql
    assert "credit_policy_versions_immutable" in sql
    assert "for update" in sql
    assert "credit_cost_guardrail_not_configured_or_exceeded" in sql
    assert "credit_actual_cost_guardrail_exceeded_or_mismatch" in sql
    assert "credit_settlement_metering_not_found" in sql
    assert "max_concurrent_reservations" in sql
    assert "max_reversal_credits" in sql
    assert "credit_ledger_reserve" in sql
    assert "credit_ledger_settle" in sql
    assert "credit_ledger_release" in sql
    assert "credit_ledger_reverse" in sql
    assert "credit_ledger_mark_pending" in sql
    assert "credit_ledger_get_balance" in sql
    assert "credit_reservations_recovery_idx" in sql


def test_migration_has_no_destructive_drop_or_provider_execution():
    sql = MIGRATION.read_text(encoding="utf-8").lower()
    assert "drop table" not in sql
    assert "http://" not in sql
    assert "https://" not in sql
    assert "execute immediate" not in sql

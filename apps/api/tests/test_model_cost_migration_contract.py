from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CANONICAL = ROOT / "supabase" / "migrations" / "20261016200000_eng_p12_model_cost_admin.sql"
MISPLACED = ROOT / "migrations" / "20261016200000_eng_p12_model_cost_admin.sql"


def test_model_cost_migration_uses_the_canonical_supabase_migration_directory():
    assert CANONICAL.is_file()
    assert not MISPLACED.exists()


def test_model_cost_migration_is_fail_closed_and_operator_only():
    sql = CANONICAL.read_text(encoding="utf-8").lower()
    assert "create table if not exists public.ai_model_cost_configs" in sql
    assert "policy_approved boolean not null default false" in sql
    assert "status text not null default 'draft'" in sql
    assert "enable row level security" in sql
    assert "revoke all on public.ai_model_cost_configs from anon, authenticated" in sql
    assert "grant select, insert, update, delete on public.ai_model_cost_configs to service_role" in sql
    assert "create unique index if not exists ai_model_cost_one_active_version" in sql

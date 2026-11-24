from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CANONICAL = ROOT / "supabase" / "migrations" / "20261017125436_20261016200000_eng_p12_model_cost_admin.sql"
MISPLACED = ROOT / "migrations" / "20261017125436_eng_p12_model_cost_admin.sql"


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


APPROVAL = ROOT / "supabase" / "migrations" / "20261124064458_eng_p09_model_policy_approval_metadata.sql"


def test_model_policy_approval_is_auditable_and_separate_from_tariff_activation():
    sql = APPROVAL.read_text(encoding="utf-8").lower()
    assert "policy_version text not null default '1'" in sql
    assert "policy_approval_reference text" in sql
    assert "policy_approved_by uuid references auth.users(id) on delete restrict" in sql
    assert "policy_approved_at timestamptz" in sql
    assert "ai_model_cost_policy_approval_consistency" in sql
    assert "ai_model_cost_policy_requires_active" in sql
    assert "policy_approved = false or status = 'active'" in sql


def test_model_usage_summary_is_service_only_and_does_not_mix_cost_units():
    sql = " ".join(APPROVAL.read_text(encoding="utf-8").lower().split())
    assert "create or replace function public.get_agent_model_usage_summary" in sql
    assert "revoke all on function public.get_agent_model_usage_summary(timestamptz,timestamptz)" in sql
    assert "grant execute on function public.get_agent_model_usage_summary(timestamptz,timestamptz) to service_role" in sql
    assert "group by provider_id,model_id,usage_unit,cost_unit,pricing_version" in sql
    assert "generation_output_moderation_one_approved" in sql

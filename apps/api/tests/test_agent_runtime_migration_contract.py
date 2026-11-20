from pathlib import Path


MIGRATION = Path(__file__).parents[1] / "supabase" / "migrations" / "20261015160000_eng_p10_agent_runtime_sessions_tasks.sql"


def test_runtime_migration_defines_durable_owner_scoped_sessions_and_tasks():
    sql = MIGRATION.read_text()
    normalized = " ".join(sql.lower().split())
    assert "create table if not exists public.agent_runtime_sessions" in normalized
    assert "create table if not exists public.agent_runtime_tasks" in normalized
    assert "owner_user_id uuid not null references auth.users(id)" in normalized
    assert "unique (owner_user_id, idempotency_key)" in normalized
    assert "request_fingerprint text not null" in normalized
    assert "foreign key (session_id, owner_user_id)" in normalized
    assert "foreign key (skill_id, agent_id)" in normalized
    assert "enable row level security" in normalized
    assert "revoke all on public.agent_runtime_sessions, public.agent_runtime_tasks from public, anon, authenticated" in normalized
    assert "grant select, insert, update, delete on public.agent_runtime_sessions, public.agent_runtime_tasks to service_role" in normalized
    assert "add column if not exists policy_version text" in normalized
    assert "revoke update on public.agent_capabilities from authenticated" in normalized
    assert "grant update (description, required_permission_scopes, risk_level, status, updated_at)" in normalized
    assert "add column if not exists version integer not null default 1" in normalized


def test_runtime_migration_is_source_only_and_does_not_seed_or_apply_runtime_data():
    sql = MIGRATION.read_text().lower()
    assert "insert into public.agent_runtime_sessions" not in sql
    assert "insert into public.agent_runtime_tasks" not in sql
    assert "update public.agent_runtime_tasks" not in sql
    assert "drop table" not in sql


def test_worker_readiness_includes_social_effect_receipt_contract():
    migration = (
        Path(__file__).parents[1] / "supabase" / "source-only-migrations"
        / "20261118195500_wp07_runtime_worker_schema_readiness.sql"
    ).read_text()
    for column in (
        "actor_user_id", "owner_user_id", "agent_id", "target_reference",
        "action_key", "approval_id", "correlation_id", "provider_key",
        "external_reference", "evidence_reference", "policy_id",
        "policy_version", "policy_digest",
    ):
        assert f"array['agent_runtime_effect_receipts','{column}']" in migration
    assert "execute_agent_social_approval_effect(uuid,uuid,uuid,integer,text,text,text,uuid,uuid,text,text,uuid,text,uuid,text,text,text)" in migration

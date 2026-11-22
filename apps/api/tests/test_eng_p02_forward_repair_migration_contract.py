from pathlib import Path
import re


MIGRATION = Path(__file__).parents[1] / "supabase" / "migrations" / "20261123191500_eng_p02_forward_repair_tenant_and_session_schema.sql"


def test_eng_p02_forward_repair_is_versioned_after_live_ledger_and_preserves_legacy_source():
    assert MIGRATION.exists()
    assert MIGRATION.name.startswith("20261123191500_")
    legacy = MIGRATION.with_name(
        "20261122140000_eng_p02_restore_missing_tenant_authorization_schema.sql"
    )
    assert legacy.exists(), "the historical source candidate must remain immutable"


def test_eng_p02_forward_repair_restores_only_additive_tenant_and_session_objects():
    sql = MIGRATION.read_text(encoding="utf-8").lower()
    required = (
        "create table if not exists public.organizations",
        "create table if not exists public.organization_memberships",
        "create table if not exists public.audit_events",
        "create or replace function public.list_my_auth_sessions",
        "create or replace function public.revoke_my_auth_session",
        "create or replace function public.revoke_my_other_auth_sessions",
        "create or replace function public.create_organization_for_user",
        "alter table public.organizations enable row level security",
        "alter table public.organization_memberships enable row level security",
        "alter table public.audit_events enable row level security",
        "revoke all on function public.list_my_auth_sessions(uuid) from public,anon",
        "grant execute on function public.list_my_auth_sessions(uuid) to authenticated",
    )
    for fragment in required:
        assert fragment in sql, f"missing forward-repair contract: {fragment}"

    # Policy/trigger replacement is intentionally idempotent. Table/data
    # destruction and schema contraction are forbidden in this repair.
    forbidden = (
        r"\bdrop\s+table\b",
        r"\btruncate\b",
        r"\balter\s+table\b[^;]*\bdrop\s+column\b",
        r"\bdrop\s+schema\b",
    )
    for pattern in forbidden:
        assert re.search(pattern, sql) is None, f"destructive migration statement found: {pattern}"


def test_session_inventory_never_exposes_refresh_tokens_or_cross_user_sessions():
    sql = MIGRATION.read_text(encoding="utf-8").lower()
    start = sql.index("create or replace function public.list_my_auth_sessions")
    end = sql.index("$allpha_session_list$", start)
    body = sql[start:end]
    assert "where s.user_id = (select auth.uid())" in body
    assert "s.id = p_current_session_id" in body
    assert "refresh_token" not in body

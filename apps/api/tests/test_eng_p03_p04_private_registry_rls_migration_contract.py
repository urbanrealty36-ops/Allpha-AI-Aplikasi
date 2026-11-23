from pathlib import Path

MIGRATION = (
    Path(__file__).parents[1]
    / "supabase"
    / "migrations"
    / "20261123210000_eng_p03_p04_private_registry_rls.sql"
)


def test_private_registries_enable_rls_and_revoke_client_table_access():
    source = " ".join(MIGRATION.read_text(encoding="utf-8").lower().split())
    assert "alter table private.account_export_sources enable row level security" in source
    assert "alter table private.user_interest_discovery_index enable row level security" in source
    assert "revoke all on table private.account_export_sources from public, anon, authenticated" in source
    assert "revoke all on table private.user_interest_discovery_index from public, anon, authenticated" in source
    assert "to_regclass('private.account_export_sources')" in source
    assert "to_regclass('private.user_interest_discovery_index')" in source


def test_private_registry_migration_does_not_create_client_policies_or_bypass_rls():
    source = MIGRATION.read_text(encoding="utf-8").lower()
    assert "create policy" not in source
    assert "force row level security" not in source
    assert "grant select" not in source

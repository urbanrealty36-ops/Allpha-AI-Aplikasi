from pathlib import Path


MIGRATION = (
    Path(__file__).parents[1]
    / "supabase"
    / "migrations"
    / "20261123124933_eng_p03_export_interest_graph_sources.sql"
)


def test_account_export_includes_owner_scoped_passion_and_habit_sources():
    source = " ".join(MIGRATION.read_text(encoding="utf-8").lower().split())

    for source_key, table_name, order in (
        ("interest_graph_signals", "user_interest_graph_signals", 44),
        ("interest_graph_signal_events", "user_interest_graph_signal_events", 45),
    ):
        assert f"('{source_key}','{table_name}','owner_columns',array['user_id']::text[],{order},true)" in source

    assert "on conflict (source_key) do nothing" in source
    assert "account_export_interest_graph_source_registry_conflict" in source


def test_account_export_interest_sources_fail_closed_if_owner_schema_is_missing():
    source = " ".join(MIGRATION.read_text(encoding="utf-8").lower().split())

    assert "account_export_interest_graph_source_table_missing" in source
    assert "account_export_interest_graph_owner_column_missing" in source
    assert "table_name='user_interest_graph_signals'" in source
    assert "table_name='user_interest_graph_signal_events'" in source
    assert "column_name='user_id'" in source


def test_derived_private_interest_discovery_projection_is_not_exported():
    source = MIGRATION.read_text(encoding="utf-8").lower()

    assert "private.user_interest_discovery_index" not in source
    assert "rebuildable from source preferences" in source

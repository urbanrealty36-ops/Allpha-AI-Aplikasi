from pathlib import Path

MIGRATION = (
    Path(__file__).parents[1] / "supabase" / "migrations"
    / "20261123200000_eng_p04_passion_habit_recommendation_engine.sql"
)


def test_passion_and_habit_signals_are_owner_readable_but_server_written():
    source = MIGRATION.read_text(encoding="utf-8").lower()
    assert "create table if not exists public.user_interest_graph_signals" in source
    assert "signal_type in ('passion','habit')" in source
    assert "passion_never_inferred" in source
    assert "revoke all privileges on public.user_interest_graph_signals from public,anon,authenticated" in source
    assert "grant select on public.user_interest_graph_signals to authenticated" in source


def test_observed_habit_signals_require_personalization_enabled():
    source = MIGRATION.read_text(encoding="utf-8").lower()
    assert "signal_source='observed_interaction'" in source
    assert "personalization_enabled" in source
    assert "personalization_consent_required" in source


def test_recommendation_policy_is_canonical_and_service_managed():
    source = MIGRATION.read_text(encoding="utf-8").lower()
    assert "create table if not exists public.recommendation_scoring_policies" in source
    assert "allpha-recommendation-v2" in source
    assert "revoke all privileges on public.recommendation_scoring_policies from public,anon,authenticated" in source

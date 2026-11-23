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



def test_agent_signals_are_owner_bound_and_sensitive_observation_is_blocked():
    source = MIGRATION.read_text(encoding="utf-8").lower()
    assert "agent_id uuid references public.ai_agents(id)" in source
    assert "interest_agent_ownership_required" in source
    assert "interest_sensitive_inference_prohibited" in source
    assert "c.sensitivity into v_key,v_sensitivity" in source


def test_personalization_opt_out_purges_observed_signals_and_export_includes_history():
    source = MIGRATION.read_text(encoding="utf-8").lower()
    assert "feed_preferences_purge_observed_interest_signals" in source
    assert "new.personalization_enabled is false" in source
    assert "s.signal_source='observed_interaction'" in source
    assert "interest_graph_signals','user_interest_graph_signals'" in source
    assert "interest_graph_signal_events','user_interest_graph_signal_events'" in source


def test_agent_signals_are_owner_bound_and_sensitive_observation_is_blocked():
    source = MIGRATION.read_text(encoding="utf-8").lower()
    assert "agent_id uuid references public.ai_agents(id)" in source
    assert "interest_agent_ownership_required" in source
    assert "interest_sensitive_inference_prohibited" in source
    assert "c.sensitivity into v_key,v_sensitivity" in source


def test_personalization_opt_out_purges_observed_signals_and_export_includes_history():
    source = MIGRATION.read_text(encoding="utf-8").lower()
    assert "feed_preferences_purge_observed_interest_signals" in source
    assert "new.personalization_enabled is false" in source
    assert "s.signal_source='observed_interaction'" in source
    assert "interest_graph_signals','user_interest_graph_signals'" in source
    assert "interest_graph_signal_events','user_interest_graph_signal_events'" in source


def test_signal_source_is_required_and_server_version_is_fixed():
    source = MIGRATION.read_text(encoding="utf-8").lower()
    assert "p_signal_source is null" in source
    assert "p_consent_version is distinct from 'interest-graph-v1'" in source


def test_observed_habit_requires_both_feed_personalization_and_discovery_consent():
    source = MIGRATION.read_text(encoding="utf-8").lower()
    assert "v_interest_matching_enabled boolean" in source
    assert "us.privacy_settings @> '{\"allow_interest_matching\":true}'::jsonb" in source
    assert "v_personalization_enabled is not true or v_interest_matching_enabled is not true" in source
    assert "interest_observation_consent_required" in source


def test_discovery_consent_revocation_purges_observed_signals_for_human_and_agent():
    source = MIGRATION.read_text(encoding="utf-8").lower()
    assert "user_settings_purge_observed_interest_signals" in source
    assert "purge_observed_interest_signals_on_matching_opt_out" in source
    assert "old.privacy_settings is distinct from new.privacy_settings" in source
    assert "s.user_id=new.user_id and s.signal_source='observed_interaction'" in source
    assert "perform private.refresh_user_interest_discovery_index(new.user_id)" in source

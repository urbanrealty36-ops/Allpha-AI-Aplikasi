from pathlib import Path


MIGRATION = (
    Path(__file__).parents[1]
    / "supabase"
    / "migrations"
    / "20261123191900_eng_p04_interest_ontology_and_discovery_index.sql"
)


def test_interest_ontology_is_seeded_and_client_read_only():
    source = MIGRATION.read_text(encoding="utf-8").lower()
    assert "create table if not exists public.interest_catalog" in source
    for key in (
        "health", "technology", "spatial_3d", "content_creator",
        "business_finance", "design_ui_ux", "education_research", "gaming_metaverse",
    ):
        assert f"('{key}'" in source
    assert "create policy interest_catalog_read_active" in source
    assert "grant select on public.interest_catalog to anon,authenticated" in source


def test_interest_discovery_index_requires_explicit_opt_in_and_public_discovery():
    source = MIGRATION.read_text(encoding="utf-8").lower()
    assert "create table if not exists private.user_interest_discovery_index" in source
    assert '"discoverable_by_username":true,"allow_interest_matching":true' in source
    assert "ui.preference='interested'" in source
    assert "p.visibility='public' and p.account_status='active'" in source
    assert "join public.interest_catalog c on c.interest_key=i.interest_key and c.active=true" in source
    assert "create trigger user_interests_refresh_discovery_index" in source
    assert "create trigger user_settings_refresh_discovery_index" in source
    assert "revoke all privileges on private.user_interest_discovery_index from public,anon,authenticated" in source


def test_interest_mutations_are_server_only_and_client_dml_is_revoked():
    source = MIGRATION.read_text(encoding="utf-8").lower()
    for function_name in (
        "set_my_interest_preference_for_actor",
        "delete_my_interest_for_actor",
        "find_interest_discovery_candidates",
    ):
        assert f"public.{function_name}" in source
        assert "coalesce(auth.role(),'') <> 'service_role'" in source
        assert f"grant execute on function public.{function_name}" in source
    assert "revoke insert,update,delete on public.user_interests from anon,authenticated" in source



def test_passion_and_habit_graph_share_owner_scoped_signal_store_and_events():
    source = MIGRATION.read_text(encoding="utf-8").lower()
    assert "create table if not exists public.user_interest_graph_signals" in source
    assert "create table if not exists public.user_interest_graph_signal_events" in source
    assert "agent_id uuid references public.ai_agents(id)" in source
    assert "signal_type in ('passion','habit')" in source
    assert "interest_observation_consent_required" in source
    assert "'allow_interest_matching':true" in source
    assert "delete from public.user_interest_graph_signals s" in source
    assert "action,signal_source,consent_version" in source
    assert "create table if not exists public.recommendation_scoring_policies" in source
    assert "'allpha-recommendation-v2'" in source


def test_interest_signal_data_is_exported_and_observed_signals_are_removed_on_opt_out():
    source = MIGRATION.read_text(encoding="utf-8").lower()
    assert "interest_graph_signals','user_interest_graph_signals'" in source
    assert "interest_graph_signal_events','user_interest_graph_signal_events'" in source
    assert "s.signal_source='observed_interaction'" in source
    assert "create policy user_interest_graph_signals_select_self" in source
    assert "create policy user_interest_graph_signal_events_select_self" in source

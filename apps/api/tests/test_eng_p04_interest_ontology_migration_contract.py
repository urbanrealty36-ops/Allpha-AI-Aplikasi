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
        "ai_agents", "social_network", "ai_cinema", "live_streaming",
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



def test_interest_ontology_exposes_semantic_relationships_and_sensitive_inference_guard():
    source = MIGRATION.read_text(encoding="utf-8").lower()
    assert "create table if not exists public.interest_taxonomy_edges" in source
    assert "('technology','spatial_3d','parent_of',1)" in source
    assert "('technology','gaming_metaverse','parent_of',1)" in source
    assert "sensitivity in ('standard','sensitive')" in source
    assert "where interest_key='health' and sensitivity<>'sensitive'" in source


def test_interest_upsert_uses_named_primary_key_to_avoid_output_column_ambiguity():
    source = MIGRATION.read_text(encoding="utf-8").lower()
    assert "on conflict on constraint user_interests_pkey do update" in source


def test_allpha_cinema_live_and_agent_ontology_relationships_are_seeded():
    source = MIGRATION.read_text(encoding="utf-8").lower()
    assert "('technology','ai_agents','parent_of',1)" in source
    assert "('social_network','content_creator','related_to',0.8)" in source
    assert "('content_creator','ai_cinema','related_to',0.8)" in source
    assert "('ai_cinema','live_streaming','related_to',0.9)" in source

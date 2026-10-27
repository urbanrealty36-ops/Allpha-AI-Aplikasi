from pathlib import Path


MIGRATIONS = Path(__file__).parents[1] / "supabase" / "migrations"
USER_SETTINGS_GRANTS = MIGRATIONS / "20261027180000_eng_p03_user_settings_least_privilege_grants.sql"
PROFILE_VISIBILITY = MIGRATIONS / "20261013053502_eng_p03_single_source_profile_visibility.sql"
SOCIAL_GRAPH = MIGRATIONS / "20261013234034_eng_p04_social_graph.sql"
SOCIAL_GRAPH_ANON_REVOKE = MIGRATIONS / "20261014130000_eng_p04_revoke_anon_social_graph_privileges.sql"


def test_user_settings_grants_are_column_scoped_and_keep_api_owned_fields_read_only():
    sql = " ".join(USER_SETTINGS_GRANTS.read_text().lower().split())

    assert "revoke all privileges on table public.user_settings from public, anon, authenticated" in sql
    assert "revoke all privileges (user_id, theme, notification_preferences, privacy_settings, updated_at) on table public.user_settings from public, anon, authenticated" in sql
    assert "grant select on table public.user_settings to authenticated" in sql
    assert "grant insert (user_id, theme, notification_preferences, privacy_settings)" in sql
    assert "grant update (theme, notification_preferences, privacy_settings)" in sql
    assert "updated_at" not in sql.split("grant update", 1)[1]
    assert "grant truncate" not in sql
    assert "grant all" not in sql


def test_profile_visibility_has_one_canonical_privacy_setting():
    sql = " ".join(PROFILE_VISIBILITY.read_text().lower().split())

    assert "privacy_settings set default" in sql
    assert "discoverable_by_username" in sql
    assert "privacy_settings = privacy_settings - 'profile_visibility'" in sql


def test_social_graph_rls_scopes_relationships_to_participants_and_self():
    sql = " ".join(SOCIAL_GRAPH.read_text().lower().split())

    assert "alter table public.social_edges enable row level security" in sql
    assert "alter table public.user_interests enable row level security" in sql
    assert "actor_user_id = (select auth.uid())" in sql
    assert "target_user_id = (select auth.uid())" in sql
    assert "user_id = (select auth.uid())" in sql
    assert "grant update (status) on public.social_edges to authenticated" in sql
    assert "revoke update on public.social_edges from authenticated" in sql


def test_social_graph_anonymous_access_is_revoked_without_broad_default_privilege_changes():
    sql = " ".join(SOCIAL_GRAPH_ANON_REVOKE.read_text().lower().split())

    assert "revoke all privileges on table public.social_edges from anon" in sql
    assert "revoke all privileges on table public.user_interests from anon" in sql
    assert "alter default privileges" not in sql
    assert "drop table" not in sql

def test_social_graph_grant_repair_draft_is_least_privilege_and_non_destructive():
    draft_path = Path(__file__).parents[3] / "docs" / "PHASES" / "ENG-P04_SOCIAL_GRAPH_GRANT_REPAIR_DRAFT.sql"
    sql = " ".join(draft_path.read_text().lower().split())

    assert "design draft only — not a supabase migration" in sql
    for table in ("social_edges", "user_interests"):
        assert f"revoke all privileges on table public.{table} from public, anon, authenticated" in sql
        assert f"from public, anon, authenticated" in sql
    assert "grant select, delete on table public.social_edges to authenticated" in sql
    assert "grant insert (actor_user_id, target_user_id, edge_type, status)" in sql
    assert "grant update (status) on table public.social_edges to authenticated" in sql
    assert "grant select, delete on table public.user_interests to authenticated" in sql
    assert "grant insert (user_id, interest_key, preference)" in sql
    assert "grant update (user_id, interest_key, preference)" in sql
    assert "grant truncate" not in sql
    assert "alter default privileges" not in sql
    assert "drop policy" not in sql
    assert "drop table" not in sql

def test_cli_generated_social_graph_grant_repair_migration_is_least_privilege():
    matches = list(MIGRATIONS.glob("*_eng_p04_social_graph_least_privilege_grants.sql"))
    assert len(matches) == 1, f"Expected one CLI-generated Social Graph grant migration, got {len(matches)}"
    sql = " ".join(matches[0].read_text().lower().split())

    assert "revoke all privileges on table public.social_edges from public, anon, authenticated" in sql
    assert "revoke all privileges (id, actor_user_id, target_user_id, edge_type, status, created_at) on table public.social_edges from public, anon, authenticated" in sql
    assert "revoke all privileges on table public.user_interests from public, anon, authenticated" in sql
    assert "revoke all privileges (user_id, interest_key, preference, created_at, updated_at) on table public.user_interests from public, anon, authenticated" in sql
    assert "grant select, delete on table public.social_edges to authenticated" in sql
    assert "grant insert (actor_user_id, target_user_id, edge_type, status)" in sql
    assert "grant update (status) on table public.social_edges to authenticated" in sql
    assert "grant select, delete on table public.user_interests to authenticated" in sql
    assert "grant insert (user_id, interest_key, preference)" in sql
    assert "grant update (user_id, interest_key, preference)" in sql
    assert "grant truncate" not in sql
    assert "grant all" not in sql
    assert "alter default privileges" not in sql
    assert "drop policy" not in sql
    assert "drop table" not in sql


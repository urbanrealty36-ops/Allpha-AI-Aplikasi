from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase" / "migrations" / "20261018171421_eng_p14_social_feed_interactions.sql"


def test_social_feed_migration_is_in_the_canonical_migration_directory():
    assert MIGRATION.is_file()


def test_social_feed_tables_are_backend_only_and_rls_protected():
    sql = MIGRATION.read_text(encoding="utf-8").lower()
    for table in ("content_reactions", "content_saves", "content_comments", "content_reports", "feed_preferences"):
        assert f"create table if not exists public.{table}" in sql
        assert f"alter table public.{table} enable row level security" in sql
    assert "revoke all on public.content_reactions, public.content_saves, public.content_comments" in sql
    assert "public.content_reports, public.feed_preferences from public, anon, authenticated" in sql
    assert "grant all on public.content_reactions, public.content_saves, public.content_comments" in sql
    assert "public.content_reports, public.feed_preferences to service_role" in sql


def test_social_feed_migration_pins_interaction_uniqueness_and_review_invariants():
    sql = MIGRATION.read_text(encoding="utf-8").lower()
    assert "content_reactions_unique_actor unique (content_id, actor_user_id)" in sql
    assert "content_saves_unique_actor unique (content_id, actor_user_id)" in sql
    assert "content_reports_one_pending_per_reporter_idx" in sql
    assert "content_reports_review_fields check" in sql
    assert "ranking_mode text not null default 'for_you' check (ranking_mode in ('for_you','recent'))" in sql

from pathlib import Path


MIGRATIONS = Path(__file__).parents[1] / "supabase" / "migrations"
TRANSFER = MIGRATIONS / "20261124120000_eng_p03_account_deletion_ownership_transfers.sql"
ANONYMIZATION = MIGRATIONS / "20261124140000_eng_p03_account_deletion_attribution_anonymization.sql"
SOURCE_DISPOSITIONS = MIGRATIONS / "20261124160000_eng_p03_cinema_conversation_spatial_anonymization.sql"


def test_transfer_migration_is_owner_scoped_and_revalidates_successor_at_execution():
    source = " ".join(TRANSFER.read_text(encoding="utf-8").lower().split())
    assert "create table if not exists public.account_deletion_ownership_transfers" in source
    assert "public.set_my_account_deletion_ownership_transfer(uuid,text,uuid,uuid)" in source
    assert "auth.uid()" in source
    assert "p.account_status='active'" in source
    assert "m.organization_id=o.id and m.user_id=p_successor_user_id" in source
    assert "v_step.action='transfer_owner'" in source
    assert "account_deletion_agent_transfer_incomplete" in source
    assert "account_deletion_organization_transfer_incomplete" in source
    assert "resolution_action='transfer_owner'" in source
    assert "deletion_action='preserve'" in source


def test_attribution_migration_uses_nullable_set_null_and_revokes_invites_and_operator_grants():
    source = " ".join(ANONYMIZATION.read_text(encoding="utf-8").lower().split())
    assert "alter table public.ai_agents alter column created_by drop not null" in source
    assert "foreign key (created_by) references auth.users(id) on delete set null" in source
    assert "resolution_action='set_null'" in source
    assert "delete_rule='set null'" in source
    assert "update public.community_invites" in source
    assert "set revoked_at=coalesce(revoked_at,clock_timestamp())" in source
    assert "update public.platform_operator_grants" in source
    assert "status='revoked'" in source
    assert "revocation_reason=coalesce(revocation_reason,'account_deletion')" in source
    assert "account_deletion_anonymization_executor_patch_anchor_missing" in source



def test_remaining_source_dispositions_preserve_shared_conversations_and_spatial_catalog():
    source = " ".join(SOURCE_DISPOSITIONS.read_text(encoding="utf-8").lower().split())
    assert "conversations_created_by_fkey" in source
    assert "foreign key (created_by) references auth.users(id) on delete set null" in source
    assert "private.anonymize_account_deletion_source" in source
    assert "spatial_theme_versions" in source
    assert "spatial_themes_created" in source
    assert "v_step.action='anonymize'" in source
    assert "p.deletion_action in ('preserve','anonymize')" in source
    assert "cinema_episodes','cinema_titles" in source

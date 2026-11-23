from pathlib import Path


MIGRATIONS = Path(__file__).parents[1] / "supabase" / "migrations"
TRANSFER = MIGRATIONS / "20261123173919_eng_p03_account_deletion_ownership_transfers.sql"
ANONYMIZATION = MIGRATIONS / "20261123174325_eng_p03_account_deletion_attribution_anonymization.sql"
SOURCE_DISPOSITIONS = MIGRATIONS / "20261123174529_eng_p03_cinema_conversation_spatial_anonymization.sql"


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



IDENTITY_TOMBSTONES = MIGRATIONS / "20261124193000_eng_p03_identity_tombstones_and_provider_cancellation.sql"


def test_financial_fk_references_use_private_pseudonymous_identity_subjects():
    source = " ".join(IDENTITY_TOMBSTONES.read_text(encoding="utf-8").lower().split())
    assert "create table if not exists private.account_identity_subjects" in source
    assert "subject_ref text not null unique check (subject_ref ~ '^[a-f0-9]{64}$')" in source
    assert "references private.account_identity_subjects(subject_id) on delete restrict" in source
    assert "billing_orders_owner_user_id_fkey" in source
    assert "billing_receipts_owner_user_id_fkey" in source
    assert "credit_ledger_accounts_owner_user_id_fkey" in source
    assert "content_retention_holds_created_by_fkey" in source
    assert "resolution_action='preserve_tombstone'" in source
    assert "account_deletion_identity_tombstone_conflict" in source
    assert "account_deletion_active_subscription_unresolved" in source


def test_subscription_cancellation_is_leased_idempotent_and_provider_confirmed():
    source = " ".join(IDENTITY_TOMBSTONES.read_text(encoding="utf-8").lower().split())
    assert "private.account_deletion_subscription_cancellation_jobs" in source
    assert "public.prepare_account_deletion_subscription_cancellations()" in source
    assert "public.claim_account_deletion_subscription_cancellation_jobs" in source
    assert "public.complete_account_deletion_subscription_cancellation_job" in source
    assert "public.fail_account_deletion_subscription_cancellation_job" in source
    assert "idempotency_key text not null unique" in source
    assert "lease_expires_at" in source
    assert "status='completed'" in source
    assert "generation_artifact_deletions" in source
    assert "account_deletion_artifact_queue_lease_active" in source
    assert "account_deletion_subscription_cancellation_pending" in source

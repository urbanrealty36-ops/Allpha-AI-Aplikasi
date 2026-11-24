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



IDENTITY_TOMBSTONES = MIGRATIONS / "20261123180112_eng_p03_identity_tombstones_and_provider_cancellation.sql"
EXECUTOR_HARDENING = MIGRATIONS / "20261123180725_eng_p03_executor_referential_integrity_hardening.sql"
STRIPE_ENVIRONMENT = MIGRATIONS / "20261123181359_eng_p03_billing_stripe_environment_binding.sql"
LEGACY_BILLING_GUARD = MIGRATIONS / "20261123181531_eng_p03_legacy_billing_order_rpc_guard.sql"
GOVERNANCE_RETRY = MIGRATIONS / "20261123182248_eng_p03_governance_policy_gate_and_retry.sql"
AGENT_OWNERSHIP_TOMBSTONE = MIGRATIONS / "20261124005951_eng_p03_agent_ownership_tombstone_attribution.sql"
API_SOURCE = Path(__file__).parents[1] / "src" / "allpha_api" / "stripe_billing_api.py"
WORKER_SOURCE = Path(__file__).parents[1] / "src" / "allpha_api" / "account_lifecycle_worker.py"


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



def test_storage_cleanup_source_and_ownership_transfer_history_are_tombstone_safe():
    source = " ".join(EXECUTOR_HARDENING.read_text(encoding="utf-8").lower().split())
    assert "generation_artifact_deletions" in source
    assert "account_deletion_storage_jobs_source_key_check" in source
    assert "references private.account_identity_subjects(subject_id)" in source
    assert "account_deletion_transfer_identity_subject_unavailable" in source
    assert "user_id=null" in source
    assert "account_deletion_execution_job_subject_redaction_anchor_missing" in source



def test_subscription_cancellation_uses_the_persisted_stripe_environment_not_checkout_mode():
    migration = " ".join(STRIPE_ENVIRONMENT.read_text(encoding="utf-8").lower().split())
    api = " ".join(API_SOURCE.read_text(encoding="utf-8").lower().split())
    worker = " ".join(WORKER_SOURCE.read_text(encoding="utf-8").lower().split())
    assert "add column if not exists stripe_environment text" in migration
    assert "p_stripe_environment text" in migration
    assert "billing_orders_stripe_environment_check" in migration
    assert "p_subscription_id,v_order.stripe_environment,p_customer_id" in migration
    assert "rename column stripe_mode to stripe_environment" in migration
    assert "bs.stripe_environment" in migration
    assert "billing_stripe_environment_required" in migration
    assert '"p_stripe_environment": stripe_environment' in api
    assert 'job.get("stripe_environment")' in worker
    assert "stripe_environment != mode" in worker



def test_legacy_checkout_rpc_is_explicitly_fail_closed_for_old_clients():
    source = " ".join(LEGACY_BILLING_GUARD.read_text(encoding="utf-8").lower().split())
    assert "grant execute on function public.billing_create_order(uuid,text,text) to service_role" in source



def test_deletion_governance_rechecks_owner_directives_holds_sources_fks_and_transfers():
    source = " ".join(GOVERNANCE_RETRY.read_text(encoding="utf-8").lower().split())
    assert "public.evaluate_account_deletion_governance" in source
    assert "decision_source='product_owner_directive'" in source
    assert "decision_reference" in source
    assert "public.account_legal_holds" in source
    assert "private.account_deletion_source_handler_available" in source
    assert "missing_fk_rules" in source
    assert "missing_ownership_transfers" in source
    assert "public.prepare_account_deletion_execution_batch" in source
    assert "status in ('awaiting_policy','scheduled','blocked_dependency')" in source
    assert "coalesce(scheduled_for,clock_timestamp())<=clock_timestamp()" in source



def test_new_auth_users_get_private_subjects_and_agent_ownership_transfer_is_bulk_safe():
    source = " ".join(AGENT_OWNERSHIP_TOMBSTONE.read_text(encoding="utf-8").lower().split())
    assert "private.ensure_account_identity_subject_from_auth_user()" in source
    assert "after insert on auth.users" in source
    assert "extensions.digest(new.id::text,'sha256')" in source
    assert "public.set_my_account_deletion_agent_ownership_transfers(uuid,uuid)" in source
    assert "ownership_role='owner' and ao.status='active'" in source
    assert "account_deletion_agent_successor_conflict" in source
    assert "agent_transfer_executor_fence_anchor_missing" in source



def test_account_deletion_and_export_failure_use_qualified_pgcrypto_with_empty_search_path():
    migration = MIGRATIONS / "20261124010254_eng_p03_subject_digest_path_repairs.sql"
    source = " ".join(migration.read_text(encoding="utf-8").lower().split())
    assert "private.ensure_account_identity_subject()" in source
    assert "public.create_account_deletion_request_for_actor(uuid)" in source
    assert "public.fail_account_export_job(uuid,uuid,text,integer)" in source
    assert "replace(v_definition,'digest(','extensions.digest(')" in source



def test_deletion_request_metadata_uses_live_owner_directive_configuration_and_null_safe_service_guard():
    migration = MIGRATIONS / "20261124010416_eng_p03_retention_request_metadata_accuracy.sql"
    source = " ".join(migration.read_text(encoding="utf-8").lower().split())
    assert "if coalesce(auth.role()" in source and "service_role" in source
    assert "count(distinct p.data_class)=6" in source
    assert "decision_source='product_owner_directive'" in source
    assert "retention_policy_configured',false" in source



def test_fk_rule_catalog_matches_real_constraints_and_governance_requires_active_agent_owners():
    migration = MIGRATIONS / "20261124010741_eng_p03_fk_action_integrity_gate.sql"
    source = " ".join(migration.read_text(encoding="utf-8").lower().split())
    assert "private.account_deletion_fk_action_mismatch_count()" in source
    assert "set delete_rule='restrict'" in source
    assert "or private.account_deletion_fk_action_mismatch_count()>0 then" in source
    assert "ao.ownership_role='owner' and ao.status='active'" in source



def test_all_original_eng_p03_executor_migrations_have_replayable_versioned_sources():
    expected = [
        "20261123142156_eng_p03_account_deletion_executor.sql",
        "20261123142329_eng_p03_deletion_dependency_requeue.sql",
        "20261123142451_eng_p03_retention_canonical_data_classes.sql",
        "20261123142930_eng_p03_legal_hold_release_requeue.sql",
        "20261123143130_eng_p03_storage_disposition_gate.sql",
        "20261123143201_eng_p03_source_registry_metadata.sql",
    ]
    sources = {name: (MIGRATIONS / name).read_text(encoding="utf-8").lower() for name in expected}
    assert "create table if not exists public.account_deletion_execution_jobs" in sources[expected[0]]
    assert "create or replace function public.execute_account_deletion_execution_job" in sources[expected[0]]
    assert "requeue_blocked_account_deletion_requests" in sources[expected[1]]
    assert "create table if not exists public.account_data_retention_policies" in sources[expected[2]]
    assert "requeue_account_deletion_after_hold_release" in sources[expected[3]]
    assert "source_key text not null default 'account_export_jobs'" in sources[expected[4]]
    assert "status in ('pending','running','completed','preserved','failed')" in sources[expected[4]]
    assert "sync_account_deletion_source_policy_metadata" in sources[expected[5]]

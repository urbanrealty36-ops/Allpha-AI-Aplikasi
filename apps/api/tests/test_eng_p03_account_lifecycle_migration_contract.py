from pathlib import Path


MIGRATION = (
    Path(__file__).parents[1]
    / "supabase"
    / "migrations"
    / "20261123191600_eng_p03_account_export_and_deletion_request_lifecycle.sql"
)


def test_account_lifecycle_migration_has_real_sql_statement_delimiters():
    source = MIGRATION.read_text(encoding="utf-8")

    # Literal backslash-n sequences inside SQL are not statement separators.
    assert "\\n" not in source
    assert "\ndo $\n" not in source
    assert "\n$;\n" not in source
    assert source.rstrip().endswith("$;")
    for function_name in (
        "complete_account_export_job",
        "fail_account_export_job",
        "create_account_deletion_request_for_actor",
        "cancel_my_account_deletion",
    ):
        assert source.count("create or replace function public." + function_name) == 1
    assert source.count("alter table public.account_export_jobs enable row level security") == 1
    normalized = " ".join(source.lower().split())

    assert (
        "revoke all on function public.renew_account_export_job_lease(uuid,uuid,integer) "
        "from public, anon, authenticated; grant execute on function "
        "public.renew_account_export_job_lease(uuid,uuid,integer) to service_role;"
    ) in normalized
    assert (
        "revoke all on function public.build_my_account_export_snapshot(uuid,uuid) "
        "from public, anon, authenticated; grant execute on function "
        "public.build_my_account_export_snapshot(uuid,uuid) to service_role;"
    ) in normalized


def test_account_export_and_deletion_lifecycle_remain_owner_scoped_and_private():
    normalized = " ".join(MIGRATION.read_text(encoding="utf-8").lower().split())

    assert "alter table public.account_export_jobs enable row level security" in normalized
    assert "alter table public.account_deletion_requests enable row level security" in normalized
    assert "for select to authenticated using (user_id = (select auth.uid()))" in normalized
    assert "values ('account-exports','account-exports',false)" in normalized
    assert "account_exports_bucket_must_remain_private" in normalized
    assert "private.redact_account_export_jsonb" in normalized
    assert "jsonb_each(p_value)" in normalized
    assert "jsonb_array_elements(p_value)" in normalized
    assert "account_export_filter_kind_unsupported" in normalized
    assert "set_account_retention_policy_active" in normalized
    assert "platform:account_lifecycle.manage" in normalized
    assert "p_storage_path = j.user_id::text || '/' || j.id::text || '.json.gz'" in normalized


def test_permanent_deletion_stays_blocked_until_retention_and_legal_hold_policy_exists():
    normalized = " ".join(MIGRATION.read_text(encoding="utf-8").lower().split())

    assert "status text not null default 'awaiting_policy'" in normalized
    assert "retention periods are intentionally not seeded" in normalized
    assert "account_retention_one_active_policy_per_class" in normalized
    assert "account_legal_holds_subject_active_idx" in normalized


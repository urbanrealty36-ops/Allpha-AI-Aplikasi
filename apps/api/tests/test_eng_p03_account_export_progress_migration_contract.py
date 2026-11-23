from pathlib import Path


MIGRATION = (
    Path(__file__).parents[1]
    / "supabase"
    / "migrations"
    / "20261123125248_eng_p03_account_export_progress.sql"
)


def test_account_export_progress_is_persisted_and_bounded():
    sql = " ".join(MIGRATION.read_text(encoding="utf-8").lower().split())

    assert "add column if not exists progress_percent smallint not null default 0" in sql
    assert "add column if not exists progress_stage text not null default 'queued'" in sql
    assert "check (progress_percent between 0 and 100)" in sql
    assert "('queued','claimed','snapshot','compress','upload','publishing','completed','failed')" in sql


def test_progress_is_bound_to_current_export_lease_and_monotonic():
    sql = " ".join(MIGRATION.read_text(encoding="utf-8").lower().split())

    assert "j.status='running'" in sql
    assert "j.lease_token=p_lease_token" in sql
    assert "j.lease_expires_at > pg_catalog.clock_timestamp()" in sql
    assert "j.progress_percent <= p_progress_percent" in sql
    assert "old.lease_token is distinct from new.lease_token" in sql


def test_progress_rpc_is_service_role_only():
    sql = " ".join(MIGRATION.read_text(encoding="utf-8").lower().split())

    assert "coalesce(auth.role(),'') <> 'service_role'" in sql
    assert "revoke all on function public.update_account_export_job_progress(uuid,uuid,smallint,text) from public,anon,authenticated" in sql
    assert "grant execute on function public.update_account_export_job_progress(uuid,uuid,smallint,text) to service_role" in sql

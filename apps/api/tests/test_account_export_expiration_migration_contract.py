from pathlib import Path

MIGRATION = Path(__file__).parents[1] / "supabase" / "migrations" / "20261123192100_eng_p03_export_artifact_expiration.sql"


def test_export_expiration_requires_explicit_active_policy():
    source = MIGRATION.read_text(encoding="utf-8").lower()
    assert "add column if not exists expires_at timestamptz" in source
    assert "data_class = 'account_export_artifact' and p.active" in source
    assert "if found then" in source
    assert "else\n      new.expires_at := null" in source
    assert "create trigger account_export_artifact_expiry" in source


def test_expired_artifact_cleanup_uses_durable_leases_and_service_role_only():
    source = MIGRATION.read_text(encoding="utf-8").lower()
    assert "create table if not exists public.account_export_artifact_cleanup_jobs" in source
    assert "for update skip locked" in source
    assert "claim_account_export_artifact_cleanup_jobs" in source
    assert "complete_account_export_artifact_cleanup_job" in source
    assert "fail_account_export_artifact_cleanup_job" in source
    assert "grant execute on function public.claim_account_export_artifact_cleanup_jobs(text,integer,integer) to service_role" in source
    assert "grant execute on function public.complete_account_export_artifact_cleanup_job(uuid,uuid) to service_role" in source
    assert "revoke all privileges on public.account_export_artifact_cleanup_jobs from public,anon,authenticated" in source

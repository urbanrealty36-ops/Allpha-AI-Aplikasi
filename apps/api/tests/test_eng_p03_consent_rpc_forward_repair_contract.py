from pathlib import Path

MIGRATION = (
    Path(__file__).parents[1] / "supabase" / "migrations"
    / "20261123191800_eng_p03_lease_scoped_export_artifacts.sql"
)


def test_forward_repair_qualifies_idempotency_constraint_without_rewriting_history():
    source = MIGRATION.read_text(encoding="utf-8").lower()
    assert "create or replace function public.record_account_consent_event_for_actor" in source
    assert "on conflict on constraint user_consent_events_user_id_idempotency_key_key do nothing" in source
    assert "on conflict (user_id,idempotency_key) do nothing" not in source
    assert "revoke all on function public.record_account_consent_event_for_actor" in source
    assert "grant execute on function public.record_account_consent_event_for_actor" in source

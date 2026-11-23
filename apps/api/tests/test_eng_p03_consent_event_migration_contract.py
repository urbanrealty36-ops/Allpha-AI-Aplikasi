from pathlib import Path


MIGRATION = (
    Path(__file__).parents[1]
    / "supabase"
    / "migrations"
    / "20261123191700_eng_p03_consent_event_history.sql"
)


def test_consent_event_history_is_append_only_and_owner_read_scoped():
    source = MIGRATION.read_text(encoding="utf-8").lower()
    assert "create table if not exists public.user_consent_events" in source
    assert "unique (user_id,idempotency_key)" in source
    assert "alter table public.user_consent_events enable row level security" in source
    assert "for select to authenticated using (user_id=(select auth.uid()))" in source
    assert "grant select on public.user_consent_events to authenticated" in source
    assert "grant select,insert,update,delete on public.user_consent_events to service_role" in source
    assert "drop policy if exists user_consents_insert_self on public.user_consents" in source
    assert "grant select on public.user_consents to authenticated" in source


def test_consent_event_write_rpc_is_service_role_only_and_idempotent():
    source = MIGRATION.read_text(encoding="utf-8").lower()
    assert "public.record_account_consent_event_for_actor" in source
    assert "coalesce(auth.role(),'') <> 'service_role'" in source
    assert "on conflict (user_id,idempotency_key) do nothing" in source
    assert "consent_idempotency_key_conflict" in source
    assert "revoke all on function public.record_account_consent_event_for_actor" in source
    assert "from public,anon,authenticated" in source
    assert "to service_role" in source


def test_consent_revocation_is_limited_to_optional_product_updates():
    source = MIGRATION.read_text(encoding="utf-8").lower()
    assert "p_decision='revoked' and p_consent_type<>'product_updates'" in source
    assert "required_policy_withdrawal_requires_account_lifecycle" in source
    assert "consent_events','user_consent_events','owner_columns',array['user_id'],31" in source

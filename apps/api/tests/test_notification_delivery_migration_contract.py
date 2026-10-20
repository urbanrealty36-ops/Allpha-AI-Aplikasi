from __future__ import annotations

from pathlib import Path


def test_eng_p20_delivery_migration_is_additive_and_lease_bounded():
    migration = Path(__file__).parents[1] / "supabase" / "migrations" / "20261020082804_eng_p20_notification_delivery.sql"
    sql = migration.read_text(encoding="utf-8").lower()
    assert "create table if not exists public.notification_devices" in sql
    assert "create table if not exists public.notification_push_deliveries" in sql
    assert "create trigger messages_enqueue_notification" in sql
    assert "create trigger community_invites_enqueue_accepted_notification" in sql
    assert "community_invite_accepted:" in sql
    assert "on conflict (user_id, event_key) do nothing" in sql
    assert "for update skip locked" in sql
    assert "enable row level security" in sql
    assert "grant execute on function public.claim_notification_push_deliveries" in sql
    assert "drop table" not in sql
    assert "delete from public.notifications" not in sql

from pathlib import Path


SUPABASE = Path(__file__).parents[1] / "supabase"


def test_wp06_social_event_intake_forward_repair_uses_verified_extension_signature():
    repaired = SUPABASE / "source-only-migrations" / "20261122110000_wp06_social_event_intake_rate_serialization_forward_repair.sql"
    historical = SUPABASE / "source-only-migrations" / "20261122100000_wp06_social_event_intake_rate_serialization.sql"
    assert repaired.is_file()
    assert historical.is_file()

    sql = repaired.read_text(encoding="utf-8")
    historical_sql = historical.read_text(encoding="utf-8")

    assert "extensions.digest(convert_to(" in sql
    assert "to_regprocedure('extensions.digest(bytea,text)')" in sql
    assert "v_fingerprint := encode(public.digest(" not in sql
    assert "public.enqueue_agent_social_automation_event(" in sql
    assert "grant execute on function public.enqueue_agent_social_automation_event(" in sql

    # Preserve the original source bytes for migration provenance; the broken
    # historical candidate is superseded, not edited or silently re-timestamped.
    assert "public.digest(" in historical_sql
    assert not (SUPABASE / "migrations" / historical.name).exists()
    assert not (SUPABASE / "migrations" / repaired.name).exists()

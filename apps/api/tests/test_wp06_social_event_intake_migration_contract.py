from pathlib import Path


SUPABASE = Path(__file__).parents[1] / "supabase"


def test_wp06_social_event_intake_forward_repair_uses_verified_extension_signature():
    repaired = SUPABASE / "source-only-migrations" / "20261122110000_wp06_social_event_intake_rate_serialization_forward_repair.sql"
    historical = SUPABASE / "source-only-migrations" / "20261122100000_wp06_social_event_intake_rate_serialization.sql"
    assert repaired.is_file()
    assert historical.is_file()

    sql = repaired.read_text(encoding="utf-8")
    historical_sql = historical.read_text(encoding="utf-8")

    dollar_quote = chr(36) * 2
    assert "do " + dollar_quote in sql
    assert "end " + dollar_quote + ";" in sql
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



def test_wp06_worker_schema_readiness_gate_is_service_role_only_and_fail_closed():
    migration = (
        SUPABASE / "source-only-migrations"
        / "20261122130000_wp06_social_automation_schema_readiness.sql"
    )
    assert migration.is_file()
    sql = migration.read_text(encoding="utf-8")
    assert "create or replace function public.agent_social_automation_schema_readiness()" in sql
    assert "'agent_social_automation_events'" in sql
    assert "'agent_social_automation_runs'" in sql
    assert "'agent_social_control_events'" in sql
    assert "'agent_social_automation_events','event_fingerprint'" in sql
    assert "'agent_social_automation_events','claim_token'" in sql
    assert "'missing_columns', to_jsonb(v_missing_columns)" in sql
    assert "public.claim_agent_social_automation_events(uuid,integer,integer)" in sql
    assert "public.heartbeat_agent_social_automation_event(uuid,uuid,integer)" in sql
    assert "public.complete_agent_social_automation_event(uuid,uuid,uuid)" in sql
    assert "public.fail_agent_social_automation_event(uuid,uuid,text,integer)" in sql
    assert "public.cancel_agent_social_automation_events(uuid,uuid,text)" in sql
    assert "has_table_privilege('service_role'" in sql
    assert "has_function_privilege('service_role'" in sql
    assert "revoke all on function public.agent_social_automation_schema_readiness() from public, anon, authenticated" in sql
    assert "grant execute on function public.agent_social_automation_schema_readiness() to service_role" in sql

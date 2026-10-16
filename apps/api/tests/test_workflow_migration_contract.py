from pathlib import Path


MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "supabase"
    / "migrations"
    / "20261016090000_eng_p11_canonical_workflow_engine.sql"
).read_text(encoding="utf-8")


def test_workflow_tables_are_rls_enabled_and_not_client_writable():
    for table in ("workflow_definitions", "workflow_runs", "workflow_steps", "workflow_run_events"):
        assert f"alter table public.{table} enable row level security;" in MIGRATION
    assert "from public, anon, authenticated;" in MIGRATION
    assert "grant select, insert on public.workflow_definitions to service_role;" in MIGRATION
    assert "grant select, insert, update on public.workflow_runs to service_role;" in MIGRATION


def test_run_and_step_state_transitions_are_atomic_rpc_contracts():
    for function in (
        "create_workflow_run",
        "cancel_workflow_run",
        "claim_workflow_step",
        "finalize_workflow_step",
    ):
        assert f"function public.{function}(" in MIGRATION
        assert f"grant execute on function public.{function}" in MIGRATION
        assert f"from public, anon, authenticated;" in MIGRATION


def test_run_creation_pins_owner_and_definition_version_and_creates_steps_in_one_rpc():
    assert "where d.id = p_definition_id and d.owner_user_id = p_owner_user_id and d.status = 'active'" in MIGRATION
    assert "definition_id, definition_version, input_payload" in MIGRATION
    assert "insert into public.workflow_steps" in MIGRATION
    assert "insert into public.workflow_run_events" in MIGRATION


def test_step_claim_uses_lease_fencing_and_dependency_success():
    assert "for update of s skip locked" in MIGRATION
    assert "s.lease_expires_at < now()" in MIGRATION
    assert "where parent.status <> 'succeeded'" in MIGRATION
    assert "step_row.lease_token is distinct from p_lease_token" in MIGRATION
    assert "step_row.lease_expires_at <= now()" in MIGRATION


def test_source_only_migration_explicitly_forbids_production_apply():
    assert "Source-only migration" in MIGRATION
    assert "not authorization to mutate canonical production" in MIGRATION

from pathlib import Path

MIGRATION = Path(__file__).parents[1] / "supabase" / "migrations" / "20261123192200_eng_p03_deletion_legal_hold_governance_worker.sql"


def test_deletion_governance_evaluator_blocks_and_unblocks_legal_holds():
    source = MIGRATION.read_text(encoding="utf-8").lower()
    assert "evaluate_account_deletion_governance" in source
    assert "h.subject_ref=v_request.subject_ref and h.active=true" in source
    assert "status='blocked_legal_hold'" in source
    assert "status='awaiting_policy'" in source
    assert "'deletion_blocked'" in source
    assert "'deletion_unblocked'" in source


def test_deletion_governance_never_executes_without_policy_and_dependency_mapping():
    source = MIGRATION.read_text(encoding="utf-8").lower()
    assert "awaiting_approved_retention_policy_and_dependency_mapping" in source
    assert "'deletion_policy_pending'" in source
    assert "processing" not in source
    assert "delete from public.account_deletion_requests" not in source
    assert "delete from auth.users" not in source
    assert "revoke all on function public.evaluate_account_deletion_governance(integer) from public,anon,authenticated" in source
    assert "grant execute on function public.evaluate_account_deletion_governance(integer) to service_role" in source

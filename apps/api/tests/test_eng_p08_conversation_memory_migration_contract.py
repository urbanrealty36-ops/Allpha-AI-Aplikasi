from pathlib import Path

from allpha_api.memory_coordinator import MEMORY_TYPES


def test_conversation_is_a_policy_type_but_not_a_persistent_memory_item_type():
    assert "conversation" in MEMORY_TYPES
    source = Path(__file__).resolve().parents[1] / "supabase" / "migrations"
    policy_migration = source / "20261125030000_eng_p08_conversation_memory_consent.sql"
    transition_migration = source / "20261125040000_eng_p08_conversation_policy_transition.sql"
    assert policy_migration.exists()
    sql = transition_migration.read_text(encoding="utf-8")
    assert "v_memory_type not in ('conversation','working','episodic','semantic','procedural','long_term')" in sql
    assert "MEMORY_CONVERSATION_STORED_IN_MESSAGING" in sql

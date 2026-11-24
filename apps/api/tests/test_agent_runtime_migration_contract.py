from pathlib import Path


MIGRATION = Path(__file__).parents[1] / "supabase" / "migrations" / "20261015160000_eng_p10_agent_runtime_sessions_tasks.sql"


def test_runtime_migration_defines_durable_owner_scoped_sessions_and_tasks():
    sql = MIGRATION.read_text()
    normalized = " ".join(sql.lower().split())
    assert "create table if not exists public.agent_runtime_sessions" in normalized
    assert "create table if not exists public.agent_runtime_tasks" in normalized
    assert "owner_user_id uuid not null references auth.users(id)" in normalized
    assert "unique (owner_user_id, idempotency_key)" in normalized
    assert "request_fingerprint text not null" in normalized
    assert "foreign key (session_id, owner_user_id)" in normalized
    assert "foreign key (skill_id, agent_id)" in normalized
    assert "enable row level security" in normalized
    assert "revoke all on public.agent_runtime_sessions, public.agent_runtime_tasks from public, anon, authenticated" in normalized
    assert "grant select, insert, update, delete on public.agent_runtime_sessions, public.agent_runtime_tasks to service_role" in normalized
    assert "add column if not exists policy_version text" in normalized
    assert "revoke update on public.agent_capabilities from authenticated" in normalized
    assert "grant update (description, required_permission_scopes, risk_level, status, updated_at)" in normalized
    assert "add column if not exists version integer not null default 1" in normalized


def test_runtime_migration_is_source_only_and_does_not_seed_or_apply_runtime_data():
    sql = MIGRATION.read_text().lower()
    assert "insert into public.agent_runtime_sessions" not in sql
    assert "insert into public.agent_runtime_tasks" not in sql
    assert "update public.agent_runtime_tasks" not in sql
    assert "drop table" not in sql


def test_worker_readiness_includes_social_effect_receipt_contract():
    migration = (
        Path(__file__).parents[1] / "supabase" / "source-only-migrations"
        / "20261118195500_wp07_runtime_worker_schema_readiness.sql"
    ).read_text()
    for column in (
        "actor_user_id", "owner_user_id", "agent_id", "target_reference",
        "action_key", "approval_id", "correlation_id", "provider_key",
        "external_reference", "evidence_reference", "policy_id",
        "policy_version", "policy_digest",
    ):
        assert f"array['agent_runtime_effect_receipts','{column}']" in migration
    assert "execute_agent_social_approval_effect(uuid,uuid,uuid,integer,text,text,text,uuid,uuid,text,text,uuid,text,uuid,text,text,text)" in migration


def _source_only(name: str) -> str:
    return (Path(__file__).parents[1] / "supabase" / "source-only-migrations" / name).read_text(encoding="utf-8").lower()


def test_runtime_execution_trace_is_append_only_owner_scoped_and_lease_fenced():
    sql = " ".join(_source_only("20261116120000_eng_p10_agent_runtime_execution_trace.sql").split())
    assert "create table if not exists public.agent_runtime_execution_events" in sql
    assert "foreign key(task_id,owner_user_id)" in sql
    assert "unique(task_id,sequence)" in sql
    assert "before update or delete on public.agent_runtime_execution_events" in sql
    assert "agent_runtime_execution_events_are_append_only" in sql
    assert "v_task.state<>'executing'" in sql
    assert "v_task.execution_lease_token is distinct from p_lease_token" in sql
    assert "v_task.lease_expires_at<=now()" in sql
    assert "runtime_execution_event_detail_key_denied" in sql
    assert "grant select,insert on public.agent_runtime_execution_events to service_role" in sql
    assert "from public,anon,authenticated" in sql


def test_durable_tool_plan_reservations_are_owner_idempotent_and_do_not_store_raw_intent():
    sql = " ".join(_source_only("20261116200000_wp07_durable_model_tool_plans.sql").split())
    assert "create table if not exists public.agent_runtime_tool_plans" in sql
    assert "unique (owner_user_id, idempotency_key)" in sql
    assert "request_fingerprint text not null" in sql
    assert "intent_sha256 text not null" in sql
    assert "memory_context_refs jsonb not null" in sql
    assert "knowledge_context_refs jsonb not null" in sql
    assert "knowledge_context_sha256 text not null" in sql
    assert "knowledge_context_state text not null" in sql
    assert "foreign key (session_id, owner_user_id)" in sql
    assert "foreign key (skill_id, agent_id)" in sql
    assert "enable row level security" in sql
    assert "grant all on public.agent_runtime_tool_plans to service_role" in sql
    assert "raw user intent, private memory and knowledge text are not stored" in sql


def test_runtime_heartbeat_and_retry_migrations_preserve_uncertain_effects():
    heartbeat = " ".join(_source_only("20261118194500_wp07_runtime_lease_heartbeat.sql").split())
    retry = " ".join(_source_only("20261118195000_wp07_durable_retry_attempts.sql").split())
    assert "t.lease_expires_at > now()" in heartbeat
    assert "when t.cancel_requested then t.lease_expires_at" in heartbeat
    assert "p_lease_seconds < 5 or p_lease_seconds > 300" in heartbeat
    assert "max_execution_attempts between 1 and 5" in retry
    assert "p_retry_after_seconds not between 1 and 60" in retry
    assert "coalesce(v_task.effect_outcome,'none') in ('started','unknown')" in retry
    assert "create or replace function public.schedule_agent_runtime_retry" in retry
    assert "create or replace function public.reap_agent_runtime_retry_exhaustion" in retry
    assert "create or replace function public.fail_unclaimed_agent_runtime_task" in retry
    assert "grant execute on function public.schedule_agent_runtime_retry" in retry
    assert "grant execute on function public.reap_agent_runtime_retry_exhaustion()" in retry
    assert "grant execute on function public.fail_unclaimed_agent_runtime_task" in retry


def test_runtime_worker_readiness_and_success_receipt_guard_are_fail_closed():
    readiness = " ".join(_source_only("20261118195500_wp07_runtime_worker_schema_readiness.sql").split())
    receipt = " ".join(_source_only("20261121100000_wp07_success_receipt_finalization_guard.sql").split())
    for table in ("agent_runtime_tool_plans","agent_runtime_execution_events","agent_runtime_effect_receipts","agent_memory_policies","agent_memory_items","agent_memory_events"):
        assert f"'{table}'" in readiness
    for function in ("heartbeat_agent_runtime_task","append_agent_runtime_execution_event","schedule_agent_runtime_retry","reap_agent_runtime_retry_exhaustion","fail_unclaimed_agent_runtime_task"):
        assert f"public.{function}" in readiness
    assert "has_table_privilege('service_role'" in readiness
    assert "c.relrowsecurity" in readiness
    assert "cardinality(v_missing_functions)=0" in readiness
    assert "array['agent_runtime_tool_plans','knowledge_context_refs']" in readiness
    assert "array['agent_runtime_tool_plans','knowledge_context_sha256']" in readiness
    assert "array['agent_runtime_tool_plans','knowledge_context_state']" in readiness
    assert "agent_runtime_task_success_receipt_guard" in receipt
    assert "agent_runtime_success_requires_confirmed_effect_outcome" in receipt
    assert "agent_runtime_success_requires_approved_social_effect_receipt" in receipt
    assert "agent_runtime_effect_receipt_guard_readiness" in receipt
    assert "grant execute on function public.agent_runtime_effect_receipt_guard_readiness()" in receipt

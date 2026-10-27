from pathlib import Path
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from allpha_api.agent_task_schedule_api import TaskScheduleCreate, _next_occurrence
from allpha_api.workflow_engine import WorkflowDefinition


def schedule_payload(**overrides):
    value = {
        "agent_id": "00000000-0000-4000-8000-000000000001",
        "session_id": "00000000-0000-4000-8000-000000000002",
        "skill_id": "00000000-0000-4000-8000-000000000003",
        "tool_key": "content.generate",
        "title": "Laporan harian",
        "instructions": "Buat ringkasan dari sumber yang diizinkan.",
        "task_type": "ANALYTICS_REPORT",
        "schedule_kind": "daily",
        "timezone_name": "Asia/Jakarta",
        "local_time": "18:00",
    }
    value.update(overrides)
    return value


def test_daily_schedule_uses_owner_timezone():
    parsed = TaskScheduleCreate.model_validate(schedule_payload())
    now = datetime(2026, 10, 26, 10, 0, tzinfo=timezone.utc)
    assert _next_occurrence(parsed, now) == datetime(2026, 10, 26, 11, 0, tzinfo=timezone.utc)


def test_weekly_schedule_respects_weekday_and_timezone():
    parsed = TaskScheduleCreate.model_validate(schedule_payload(schedule_kind="weekly", weekdays=[0]))
    now = datetime(2026, 10, 26, 10, 0, tzinfo=timezone.utc)
    next_run = _next_occurrence(parsed, now)
    assert next_run.astimezone(timezone.utc) > now
    assert next_run.astimezone(ZoneInfo("Asia/Jakarta")).weekday() == 0


def test_once_schedule_requires_offset_and_future_timestamp():
    future_run = (datetime.now(timezone.utc) + timedelta(days=2)).astimezone(ZoneInfo("Asia/Jakarta"))
    parsed = TaskScheduleCreate.model_validate(schedule_payload(
        schedule_kind="once", run_at=future_run.isoformat()))
    assert _next_occurrence(parsed, datetime.now(timezone.utc)) == parsed.run_at.astimezone(timezone.utc)
    with pytest.raises(ValidationError):
        TaskScheduleCreate.model_validate(schedule_payload(
            schedule_kind="once", run_at="2026-10-27T18:00:00"))


@pytest.mark.parametrize("overrides", [
    {"schedule_kind": "weekly", "weekdays": []},
    {"schedule_kind": "daily", "weekdays": [1]},
    {"schedule_kind": "once", "run_at": "2026-10-27T18:00:00"},
    {"timezone_name": "Not/AZone"},
    {"local_time": "25:00"},
    {"weekdays": [0, 0]},
])
def test_invalid_schedule_shapes_fail_closed(overrides):
    with pytest.raises(ValidationError):
        TaskScheduleCreate.model_validate(schedule_payload(**overrides))


def test_agent_task_node_is_explicitly_bound_to_a_schedule():
    valid = WorkflowDefinition.model_validate({
        "workflow_key": "agent-task-contract", "version": 1,
        "nodes": [{"key": "execute-agent-task", "kind": "agent_task",
                   "config": {"schedule_id": "00000000-0000-4000-8000-000000000001"}}],
    })
    assert valid.nodes[0].kind == "agent_task"
    with pytest.raises(ValidationError):
        WorkflowDefinition.model_validate({
            "workflow_key": "agent-task-contract", "version": 1,
            "nodes": [{"key": "execute-agent-task", "kind": "agent_task", "config": {}}],
        })


def test_schedule_migration_has_atomic_claims_and_idempotent_occurrences():
    migration = (Path(__file__).resolve().parents[1] / "supabase" / "migrations" /
                 "20261026100000_eng_p11_agent_task_schedules.sql").read_text(encoding="utf-8")
    assert "for update skip locked" in migration.lower()
    assert "unique (schedule_id, scheduled_for)" in migration
    assert "claim_due_agent_task_schedules" in migration
    assert "enable row level security" in migration
    assert "from public, anon, authenticated" in migration
    assert "workflow_runs_agent_schedule_trace_uidx" in migration

def test_schedule_approval_route_is_unique():
    source = (Path(__file__).resolve().parents[1] / "src" / "allpha_api" / "agent_task_schedule_api.py").read_text(encoding="utf-8")
    assert source.count('@router.post("/{schedule_id}/runs/{run_id}/approve")') == 1
    start = source.index('@router.post("/{schedule_id}/runs/{run_id}/approve")')
    end = source.index('@router.patch("/{schedule_id}/status")', start)
    handler = source[start:end]
    assert '"require_approval": False' not in handler
    assert '"approved_by": owner_id' in handler


def test_schedule_requires_tool_permission_scopes_to_be_explicitly_granted():
    source = (Path(__file__).resolve().parents[1] / "src" / "allpha_api" / "agent_task_schedule_api.py").read_text(encoding="utf-8")
    assert "required_scopes = set(tool.required_permission_scopes)" in source
    assert "required_scopes.issubset(set(payload.granted_permission_scopes))" in source
    assert "TASK_TOOL_PERMISSION_NOT_GRANTED" in source


def test_schedule_worker_bounds_poll_batch_and_lease():
    source = (Path(__file__).resolve().parents[1] / "src" / "allpha_api" / "agent_task_schedule_worker.py").read_text(encoding="utf-8")
    assert 'if not 1 <= limit <= 100' in source
    assert 'if not 5 <= lease_seconds <= 300' in source
    assert 'bounded_env("ALLPHA_AGENT_TASK_SCHEDULER_BATCH_LIMIT", 25, 1, 100)' in source
    assert 'bounded_env("ALLPHA_AGENT_TASK_SCHEDULER_LEASE_SECONDS", 60, 5, 300)' in source

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from allpha_api.agent_task_schedule_api import TaskScheduleCreate, _next_occurrence


def base_payload(**overrides):
    payload = {
        "agent_id": "00000000-0000-4000-8000-000000000001",
        "session_id": "00000000-0000-4000-8000-000000000002",
        "skill_id": "00000000-0000-4000-8000-000000000003",
        "tool_key": "content.generate",
        "title": "Jadwalkan ringkasan",
        "instructions": "Buat ringkasan berdasarkan sumber yang diizinkan.",
        "task_type": "ANALYTICS_REPORT",
        "schedule_kind": "daily",
        "timezone_name": "Asia/Jakarta",
        "local_time": "18:00",
    }
    payload.update(overrides)
    return payload


def test_daily_schedule_computes_next_occurrence_in_iana_timezone():
    payload = TaskScheduleCreate.model_validate(base_payload())
    now = datetime(2026, 10, 26, 10, 0, tzinfo=timezone.utc)
    next_run = _next_occurrence(payload, now)
    assert next_run is not None
    assert datetime.fromisoformat(next_run).astimezone(timezone.utc).hour == 11


def test_weekly_schedule_respects_local_weekday_and_timezone():
    payload = TaskScheduleCreate.model_validate(base_payload(
        schedule_kind="weekly", weekdays=[0], local_time="18:00",
    ))
    now = datetime(2026, 10, 26, 10, 0, tzinfo=timezone.utc)
    next_run = datetime.fromisoformat(_next_occurrence(payload, now))
    assert next_run.astimezone(timezone.utc) > now


def test_one_time_schedule_requires_offset_and_future_run_is_selected():
    payload = TaskScheduleCreate.model_validate(base_payload(
        schedule_kind="once", run_at="2026-10-27T18:00:00+07:00",
    ))
    next_run = _next_occurrence(payload, datetime(2026, 10, 26, tzinfo=timezone.utc))
    assert next_run == datetime(2026, 10, 27, 11, 0, tzinfo=timezone.utc).isoformat()


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
        TaskScheduleCreate.model_validate(base_payload(**overrides))

import pytest

from allpha_api.task_planner import TaskPlanningError, build_bounded_task_plan


def test_planner_builds_one_registered_schema_validated_step():
    plan = build_bounded_task_plan("text.normalize", {"text": "  hello  "})
    assert plan.max_tool_calls == 1
    assert len(plan.steps) == 1
    assert plan.steps[0].step_key == "tool:text.normalize"
    assert plan.steps[0].tool_key == "text.normalize"
    assert plan.steps[0].input_payload == {"text": "  hello  "}
    assert plan.public_contract()["steps"] == [{
        "step_key": "tool:text.normalize",
        "tool_key": "text.normalize",
        "tool_version": plan.steps[0].tool_version,
    }]


def test_planner_fails_closed_for_unknown_tool_and_invalid_input():
    with pytest.raises(TaskPlanningError):
        build_bounded_task_plan("not.registered", {})
    with pytest.raises(TaskPlanningError):
        build_bounded_task_plan("text.normalize", {"text": 42})
    with pytest.raises(TaskPlanningError):
        build_bounded_task_plan("text.normalize", {"text": "ok", "unplanned": True})


def test_planner_does_not_turn_instructions_into_executable_steps():
    with pytest.raises(TaskPlanningError):
        build_bounded_task_plan("", {"instructions": "run arbitrary command"})

"""Deterministic, fail-closed planner for the currently supported Agent Tool slice.

The planner never interprets free-form instructions as executable code. A plan is
limited to one explicitly selected, registered Tool with schema-validated input.
Multi-step plans remain unsupported until each step has a canonical dependency and
policy contract.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from allpha_api.tool_registry import ToolInputError, UnknownToolError, get_tool, validate_tool_input


class TaskPlanningError(ValueError):
    """A request cannot be represented as a safe bounded execution plan."""


@dataclass(frozen=True)
class PlannedToolStep:
    step_key: str
    tool_key: str
    tool_version: str
    input_payload: dict[str, Any]


@dataclass(frozen=True)
class BoundedTaskPlan:
    version: int
    steps: tuple[PlannedToolStep, ...]
    max_tool_calls: int = 1

    def public_contract(self) -> dict[str, Any]:
        return {
            "planner": "bounded-tool-planner",
            "version": self.version,
            "max_tool_calls": self.max_tool_calls,
            "steps": [
                {
                    "step_key": step.step_key,
                    "tool_key": step.tool_key,
                    "tool_version": step.tool_version,
                }
                for step in self.steps
            ],
        }


def build_bounded_task_plan(tool_key: str, input_payload: dict[str, Any]) -> BoundedTaskPlan:
    """Build one deterministic Tool step; reject unknown Tools and invalid inputs."""
    if not isinstance(tool_key, str) or not tool_key.strip():
        raise TaskPlanningError("an explicit registered tool_key is required")
    if not isinstance(input_payload, dict):
        raise TaskPlanningError("tool input must be an object")
    try:
        tool = get_tool(tool_key)
        validated = validate_tool_input(tool_key, input_payload)
    except (ToolInputError, UnknownToolError) as exc:
        raise TaskPlanningError("tool is not registered or input does not match its contract") from exc
    return BoundedTaskPlan(
        version=1,
        steps=(PlannedToolStep(
            step_key=f"tool:{tool.key}",
            tool_key=tool.key,
            tool_version=tool.version,
            input_payload=validated,
        ),),
        max_tool_calls=1,
    )
